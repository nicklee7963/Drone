#!/usr/bin/env python3
"""Transform raw OSM highway ways into terrain-following Gazebo OBJ ribbons."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from pyproj import Transformer

from site_geometry import PROCESSING_CRS, WGS84_CRS, load_site_config


ROAD_Z_OFFSET_M = 0.10
MAX_SEGMENT_LENGTH_M = 5.0
HIDDEN_HIGHWAY_TYPES = frozenset({"steps"})
ROAD_WIDTHS_M = {
    "motorway": 9.0,
    "trunk": 8.0,
    "primary": 8.0,
    "secondary": 5.0,
    "tertiary": 5.0,
    "unclassified": 3.5,
    "residential": 5.0,
    "living_street": 4.0,
    "service": 2.5,
    "track": 1.8,
    "path": 0.8,
    "footway": 0.7,
    "cycleway": 1.8,
    "bridleway": 1.8,
    "steps": 0.0,
}
DEFAULT_ROAD_WIDTH_M = 3.0
HIGHWAY_MATERIALS = {
    "motorway": "road_secondary",
    "trunk": "road_secondary",
    "primary": "road_secondary",
    "secondary": "road_secondary",
    "tertiary": "road_unclassified",
    "unclassified": "road_unclassified",
    "residential": "road_unclassified",
    "living_street": "road_unclassified",
    "service": "road_service",
    "track": "road_track",
    "path": "road_path",
    "cycleway": "road_path",
    "bridleway": "road_path",
    "footway": "road_footway",
}
ROAD_MATERIALS = {
    "road_secondary": (0.08, 0.08, 0.08),
    "road_unclassified": (0.28, 0.28, 0.28),
    "road_service": (0.58, 0.58, 0.58),
    "road_track": (0.34, 0.18, 0.06),
    "road_path": (0.62, 0.42, 0.20),
    "road_footway": (0.72, 0.54, 0.30),
    "road_other": (0.45, 0.45, 0.45),
}


class RoadMeshError(ValueError):
    """Raised when source roads or terrain cannot form a trustworthy V1 mesh."""


@dataclass(frozen=True)
class MeshReport:
    """Summary of the OBJ artifact and its terrain-registration contract."""

    feature_count: int
    highway_types: dict[str, int]
    material_types: dict[str, int]
    vertex_count: int
    face_count: int
    terrain_minimum_m: float
    terrain_maximum_m: float
    local_minimum_m: float
    local_maximum_m: float
    z_offset_m: float
    source_tiff_sha256: str
    terrain_bounds_epsg3826: tuple[float, float, float, float]


def sha256(path: Path) -> str:
    """Return a digest while reading an asset without changing it."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def clip_segment_to_rectangle(
    start: tuple[float, float],
    end: tuple[float, float],
    rectangle: tuple[float, float, float, float],
) -> tuple[tuple[float, float], tuple[float, float]] | None:
    """Clip one projected segment to west, south, east, north using Liang-Barsky."""
    west, south, east, north = rectangle
    x0, y0 = start
    dx, dy = end[0] - x0, end[1] - y0
    lower, upper = 0.0, 1.0
    for p, q in ((-dx, x0 - west), (dx, east - x0), (-dy, y0 - south), (dy, north - y0)):
        if math.isclose(p, 0.0, abs_tol=1e-12):
            if q < 0.0:
                return None
            continue
        ratio = q / p
        if p < 0.0:
            if ratio > upper:
                return None
            lower = max(lower, ratio)
        else:
            if ratio < lower:
                return None
            upper = min(upper, ratio)
    return (x0 + lower * dx, y0 + lower * dy), (x0 + upper * dx, y0 + upper * dy)


def clip_polyline_to_rectangle(
    points: list[tuple[float, float]], rectangle: tuple[float, float, float, float]
) -> list[list[tuple[float, float]]]:
    """Return every continuous part of a polyline that lies inside the terrain footprint."""
    parts: list[list[tuple[float, float]]] = []
    current: list[tuple[float, float]] = []
    for start, end in zip(points, points[1:]):
        clipped = clip_segment_to_rectangle(start, end, rectangle)
        if clipped is None:
            if len(current) >= 2:
                parts.append(current)
            current = []
            continue
        clipped_start, clipped_end = clipped
        if not current or math.dist(current[-1], clipped_start) > 1e-6:
            if len(current) >= 2:
                parts.append(current)
            current = [clipped_start]
        if math.dist(current[-1], clipped_end) > 1e-6:
            current.append(clipped_end)
    if len(current) >= 2:
        parts.append(current)
    return parts


def densify_polyline(points: list[tuple[float, float]], maximum_length_m: float = MAX_SEGMENT_LENGTH_M) -> list[tuple[float, float]]:
    """Densify projected segments in metres without altering their horizontal path."""
    if maximum_length_m <= 0.0:
        raise RoadMeshError("maximum road segment length must be positive")
    dense = [points[0]]
    for start, end in zip(points, points[1:]):
        length = math.dist(start, end)
        steps = max(1, math.ceil(length / maximum_length_m))
        for index in range(1, steps + 1):
            fraction = index / steps
            dense.append((start[0] + (end[0] - start[0]) * fraction, start[1] + (end[1] - start[1]) * fraction))
    return dense


def bilinear_elevation(
    terrain: np.ma.MaskedArray[Any], transform: Any, easting_m: float, northing_m: float
) -> float:
    """Sample a north-up DTM with bilinear interpolation and explicit NoData rejection."""
    if not math.isclose(transform.b, 0.0, abs_tol=1e-12) or not math.isclose(transform.d, 0.0, abs_tol=1e-12):
        raise RoadMeshError("Road sampling requires an axis-aligned terrain GeoTIFF")
    col = (easting_m - transform.c) / transform.a - 0.5
    row = (northing_m - transform.f) / transform.e - 0.5
    row = min(max(row, 0.0), terrain.shape[0] - 1.0)
    col = min(max(col, 0.0), terrain.shape[1] - 1.0)
    row0, col0 = math.floor(row), math.floor(col)
    row1, col1 = min(row0 + 1, terrain.shape[0] - 1), min(col0 + 1, terrain.shape[1] - 1)
    values = (terrain[row0, col0], terrain[row0, col1], terrain[row1, col0], terrain[row1, col1])
    if any(np.ma.is_masked(value) or not math.isfinite(float(value)) for value in values):
        raise RoadMeshError("Terrain NoData intersects a road vertex; refusing to fabricate elevation")
    row_fraction, col_fraction = row - row0, col - col0
    top = float(values[0]) * (1.0 - col_fraction) + float(values[1]) * col_fraction
    bottom = float(values[2]) * (1.0 - col_fraction) + float(values[3]) * col_fraction
    return top * (1.0 - row_fraction) + bottom * row_fraction


def local_xy(
    easting_m: float, northing_m: float, terrain_bounds: tuple[float, float, float, float]
) -> tuple[float, float]:
    """Map the GeoTIFF's EPSG:3826 footprint to the terrain model's ±250 m local space."""
    west, south, east, north = terrain_bounds
    return easting_m - (west + east) / 2.0, northing_m - (south + north) / 2.0


def road_width_m(highway_type: str) -> float:
    """Return the intentionally approximate V1 visual width for an OSM highway tag."""
    return ROAD_WIDTHS_M.get(highway_type, DEFAULT_ROAD_WIDTH_M)


def road_material_name(highway_type: str) -> str:
    """Return the simple V1 visual material assigned to an OSM highway type."""
    if highway_type in HIDDEN_HIGHWAY_TYPES:
        return ""
    return HIGHWAY_MATERIALS.get(highway_type, "road_other")


def projected_way_points(geometry: Any, transformer: Transformer) -> list[tuple[float, float]]:
    """Validate and project the coordinate list emitted by Overpass ``out geom``."""
    if not isinstance(geometry, list):
        return []
    result: list[tuple[float, float]] = []
    for point in geometry:
        if not isinstance(point, dict) or "lon" not in point or "lat" not in point:
            return []
        try:
            easting_m, northing_m = transformer.transform(float(point["lon"]), float(point["lat"]))
        except (TypeError, ValueError) as error:
            raise RoadMeshError("OSM way geometry contains non-numeric longitude or latitude") from error
        result.append((easting_m, northing_m))
    return result


def osm_elements_from_source(source_path: Path) -> list[dict[str, Any]]:
    """Read an unchanged Overpass JSON or official OSM API XML way dataset."""
    try:
        raw_text = source_path.read_text(encoding="utf-8")
    except OSError as error:
        raise RoadMeshError(f"Unable to read raw OSM source: {source_path}") from error
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError:
        payload = None
    if isinstance(payload, dict):
        elements = payload.get("elements")
        if not isinstance(elements, list):
            raise RoadMeshError("Raw Overpass JSON does not contain an elements list")
        return [element for element in elements if isinstance(element, dict)]

    try:
        root = ET.fromstring(raw_text)
    except ET.ParseError as error:
        raise RoadMeshError("Raw OSM source must be valid Overpass JSON or OSM XML") from error
    if root.tag != "osm":
        raise RoadMeshError("Raw OSM XML root must be <osm>")
    nodes: dict[str, dict[str, float]] = {}
    for node in root.findall("node"):
        try:
            nodes[node.attrib["id"]] = {"lat": float(node.attrib["lat"]), "lon": float(node.attrib["lon"])}
        except (KeyError, ValueError) as error:
            raise RoadMeshError("Raw OSM XML node lacks numeric id, latitude, or longitude") from error
    elements: list[dict[str, Any]] = []
    for way in root.findall("way"):
        geometry = [nodes[reference.attrib["ref"]] for reference in way.findall("nd") if reference.attrib.get("ref") in nodes]
        tags = {tag.attrib["k"]: tag.attrib["v"] for tag in way.findall("tag") if "k" in tag.attrib and "v" in tag.attrib}
        elements.append({"type": "way", "id": way.attrib.get("id"), "tags": tags, "geometry": geometry})
    return elements


def add_ribbon(
    points: list[tuple[float, float]],
    width_m: float,
    terrain: np.ma.MaskedArray[Any],
    transform: Any,
    terrain_bounds: tuple[float, float, float, float],
    terrain_reference_m: float,
    vertices: list[tuple[float, float, float]],
    faces: list[tuple[int, int, int, int]],
    face_materials: list[str],
    material_name: str,
) -> None:
    """Append one terrain-draped ribbon to OBJ vertex and quad arrays."""
    west, south, east, north = terrain_bounds
    half_width = width_m / 2.0
    start_vertex = len(vertices) + 1
    for index, point in enumerate(points):
        previous = points[max(0, index - 1)]
        following = points[min(len(points) - 1, index + 1)]
        tangent_x, tangent_y = following[0] - previous[0], following[1] - previous[1]
        tangent_length = math.hypot(tangent_x, tangent_y)
        if math.isclose(tangent_length, 0.0, abs_tol=1e-12):
            raise RoadMeshError("Road geometry contains a zero-length segment after clipping")
        normal_x, normal_y = -tangent_y / tangent_length, tangent_x / tangent_length
        left = (
            min(max(point[0] + normal_x * half_width, west), east),
            min(max(point[1] + normal_y * half_width, south), north),
        )
        right = (
            min(max(point[0] - normal_x * half_width, west), east),
            min(max(point[1] - normal_y * half_width, south), north),
        )
        for easting_m, northing_m in (left, right):
            x_m, y_m = local_xy(easting_m, northing_m, terrain_bounds)
            z_m = bilinear_elevation(terrain, transform, easting_m, northing_m) - terrain_reference_m + ROAD_Z_OFFSET_M
            vertices.append((x_m, y_m, z_m))
    for index in range(len(points) - 1):
        first = start_vertex + index * 2
        faces.append((first, first + 1, first + 3, first + 2))
        face_materials.append(material_name)


def write_obj(
    path: Path,
    vertices: list[tuple[float, float, float]],
    faces: list[tuple[int, int, int, int]],
    face_materials: list[str],
    mtl_name: str,
) -> None:
    """Write a concise static OBJ with category-specific material groups."""
    if len(faces) != len(face_materials):
        raise RoadMeshError("Road OBJ faces and material assignments must have the same count")
    with path.open("w", encoding="utf-8") as output:
        output.write("# Generated from OpenStreetMap highway ways; see road metadata JSON.\n")
        output.write(f"mtllib {mtl_name}\n")
        output.write("o alishan_shizhuo_roads\n")
        for x_m, y_m, z_m in vertices:
            output.write(f"v {x_m:.6f} {y_m:.6f} {z_m:.6f}\n")
        active_material: str | None = None
        for face, material_name in zip(faces, face_materials):
            if material_name != active_material:
                output.write(f"usemtl {material_name}\n")
                active_material = material_name
            output.write("f " + " ".join(str(index) for index in face) + "\n")


def write_mtl(path: Path) -> None:
    """Write simple diffuse-only V1 material definitions by road category."""
    lines = ["# Simple visual-only V1 road materials by OSM highway category."]
    for material_name, (red, green, blue) in ROAD_MATERIALS.items():
        lines.extend(
            (
                f"newmtl {material_name}",
                f"Kd {red:.2f} {green:.2f} {blue:.2f}",
                f"Ka {red * 0.25:.2f} {green * 0.25:.2f} {blue * 0.25:.2f}",
                "Ks 0.00 0.00 0.00",
                "Ns 1.0",
                "",
            )
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def visual_mesh_path(output_obj: Path, material_name: str) -> Path:
    """Return the deterministic per-material OBJ path used by the Gazebo SDF visuals."""
    category = material_name.removeprefix("road_")
    return output_obj.with_name(f"{output_obj.stem}_{category}{output_obj.suffix}")


def write_visual_meshes(
    output_obj: Path,
    mtl_name: str,
    vertices: list[tuple[float, float, float]],
    faces: list[tuple[int, int, int, int]],
    face_materials: list[str],
) -> dict[str, Path]:
    """Split one immutable-coordinate ribbon set into SDF-material-addressable OBJ meshes."""
    grouped_vertices: dict[str, list[tuple[float, float, float]]] = {}
    grouped_faces: dict[str, list[tuple[int, int, int, int]]] = {}
    vertex_indices: dict[str, dict[int, int]] = {}
    for face, material_name in zip(faces, face_materials):
        material_vertices = grouped_vertices.setdefault(material_name, [])
        material_faces = grouped_faces.setdefault(material_name, [])
        index_map = vertex_indices.setdefault(material_name, {})
        remapped_face: list[int] = []
        for index in face:
            if index not in index_map:
                index_map[index] = len(material_vertices) + 1
                material_vertices.append(vertices[index - 1])
            remapped_face.append(index_map[index])
        material_faces.append(tuple(remapped_face))

    paths: dict[str, Path] = {}
    for material_name in sorted(grouped_faces):
        path = visual_mesh_path(output_obj, material_name)
        with path.open("w", encoding="utf-8") as output:
            output.write("# Generated terrain-following OSM road ribbon; model.sdf explicitly overrides this matte material.\n")
            output.write(f"mtllib {mtl_name}\n")
            output.write(f"o alishan_shizhuo_{material_name}\n")
            output.write(f"usemtl {material_name}\n")
            for x_m, y_m, z_m in grouped_vertices[material_name]:
                output.write(f"v {x_m:.6f} {y_m:.6f} {z_m:.6f}\n")
            for face in grouped_faces[material_name]:
                output.write("f " + " ".join(str(index) for index in face) + "\n")
        paths[material_name] = path
    return paths


def generate_road_mesh(
    source_json: Path,
    terrain_tiff: Path,
    site_config: Path,
    output_obj: Path,
    output_mtl: Path,
    output_metadata: Path,
) -> MeshReport:
    """Create a static terrain-following OBJ while retaining source data unchanged."""
    for required_path, label in ((source_json, "raw OSM JSON"), (terrain_tiff, "processed terrain GeoTIFF"), (site_config, "site configuration")):
        if not required_path.is_file():
            raise RoadMeshError(f"Missing {label}: {required_path}")
    elements = osm_elements_from_source(source_json)

    _ = load_site_config(site_config)
    with rasterio.open(terrain_tiff) as dataset:
        if dataset.crs is None or dataset.crs.to_epsg() != 3826:
            raise RoadMeshError(f"Terrain CRS must be EPSG:3826, found {dataset.crs}")
        if dataset.count != 1:
            raise RoadMeshError(f"Terrain must contain exactly one elevation band, found {dataset.count}")
        terrain = dataset.read(1, masked=True)
        if terrain.mask is np.ma.nomask or np.ma.getmaskarray(terrain).all():
            raise RoadMeshError("Terrain contains no valid elevations")
        terrain_minimum_m = float(terrain.min())
        terrain_maximum_m = float(terrain.max())
        terrain_reference_m = round(terrain_minimum_m, 3)
        terrain_bounds = (dataset.bounds.left, dataset.bounds.bottom, dataset.bounds.right, dataset.bounds.top)
        transform = dataset.transform

    transformer = Transformer.from_crs(WGS84_CRS, PROCESSING_CRS, always_xy=True)
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int, int]] = []
    face_materials: list[str] = []
    highway_types: Counter[str] = Counter()
    material_types: Counter[str] = Counter()
    feature_count = 0
    for element in elements:
        if not isinstance(element, dict) or element.get("type") != "way":
            continue
        tags = element.get("tags")
        highway_type = tags.get("highway") if isinstance(tags, dict) else None
        if not isinstance(highway_type, str):
            continue
        if highway_type in HIDDEN_HIGHWAY_TYPES:
            continue
        points = projected_way_points(element.get("geometry"), transformer)
        if len(points) < 2:
            continue
        rendered_parts = clip_polyline_to_rectangle(points, terrain_bounds)
        rendered = False
        for part in rendered_parts:
            dense_points = densify_polyline(part)
            if len(dense_points) < 2:
                continue
            add_ribbon(
                dense_points,
                road_width_m(highway_type),
                terrain,
                transform,
                terrain_bounds,
                terrain_reference_m,
                vertices,
                faces,
                face_materials,
                road_material_name(highway_type),
            )
            rendered = True
        if rendered:
            feature_count += 1
            highway_types[highway_type] += 1
            material_types[road_material_name(highway_type)] += 1
    if not faces:
        raise RoadMeshError("No OSM highway way intersects the terrain GeoTIFF footprint")

    output_obj.parent.mkdir(parents=True, exist_ok=True)
    output_mtl.parent.mkdir(parents=True, exist_ok=True)
    output_metadata.parent.mkdir(parents=True, exist_ok=True)
    write_obj(output_obj, vertices, faces, face_materials, output_mtl.name)
    write_mtl(output_mtl)
    visual_meshes = write_visual_meshes(output_obj, output_mtl.name, vertices, faces, face_materials)
    report = MeshReport(
        feature_count=feature_count,
        highway_types=dict(sorted(highway_types.items())),
        material_types=dict(sorted(material_types.items())),
        vertex_count=len(vertices),
        face_count=len(faces),
        terrain_minimum_m=terrain_minimum_m,
        terrain_maximum_m=terrain_maximum_m,
        local_minimum_m=0.0,
        local_maximum_m=terrain_maximum_m - terrain_reference_m,
        z_offset_m=ROAD_Z_OFFSET_M,
        source_tiff_sha256=sha256(terrain_tiff),
        terrain_bounds_epsg3826=terrain_bounds,
    )
    metadata = asdict(report)
    metadata.update(
        {
            "source_osm_json": str(source_json),
            "terrain_tiff": str(terrain_tiff),
            "site_config": str(site_config),
            "coordinate_pipeline": "EPSG:4326 -> EPSG:3826 -> GeoTIFF-centred Gazebo local XY",
            "terrain_sampling": "bilinear sample of the source 20 m DTM; no terrain modification",
            "local_z": "TWVD2001 elevation - 1330.340 m + 0.100 m road offset",
            "hidden_highway_types": sorted(HIDDEN_HIGHWAY_TYPES),
            "gazebo_visual_meshes": {material: str(path) for material, path in sorted(visual_meshes.items())},
            "gazebo_material_assignment": "one explicit matte SDF material per per-category OBJ visual",
        }
    )
    output_metadata.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> int:
    """Run mesh generation as a reproducible explicit command."""
    project_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-config", type=Path, default=project_root / "configs/site.yaml")
    parser.add_argument(
        "--source-json",
        type=Path,
        default=project_root / "data/raw/osm/alishan_shizhuo_roads_overpass.json",
    )
    parser.add_argument(
        "--terrain-tiff",
        type=Path,
        default=project_root / "data/processed/alishan_shizhuo_terrain_20m.tif",
    )
    parser.add_argument(
        "--output-obj",
        type=Path,
        default=project_root / "data/processed/roads/alishan_shizhuo_roads.obj",
    )
    parser.add_argument(
        "--output-mtl",
        type=Path,
        default=project_root / "data/processed/roads/alishan_shizhuo_roads.mtl",
    )
    parser.add_argument(
        "--output-metadata",
        type=Path,
        default=project_root / "data/processed/roads/alishan_shizhuo_roads_metadata.json",
    )
    arguments = parser.parse_args()
    try:
        report = generate_road_mesh(
            source_json=arguments.source_json,
            terrain_tiff=arguments.terrain_tiff,
            site_config=arguments.site_config,
            output_obj=arguments.output_obj,
            output_mtl=arguments.output_mtl,
            output_metadata=arguments.output_metadata,
        )
    except RoadMeshError as error:
        print(f"road mesh error: {error}", file=sys.stderr)
        return 1
    print(json.dumps(asdict(report), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
