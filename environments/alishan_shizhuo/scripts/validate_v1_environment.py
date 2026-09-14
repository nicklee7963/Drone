#!/usr/bin/env python3
"""Validate the V1 road mesh, Gazebo references, and preserved V0 terrain."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

import rasterio


EXPECTED_TERRAIN_SHA256 = "b082d7f874808eb531a27daa293dd5766faf3339763219cdeab0bd578fd2c8dc"
ROAD_Z_OFFSET_M = 0.10
LOCAL_HALF_EXTENT_M = 250.0


class V1ValidationError(ValueError):
    """Raised when the V1 road layer violates its bounded terrain contract."""


@dataclass(frozen=True)
class V1ValidationReport:
    """Concise V1 geometry and asset-integrity results."""

    feature_count: int
    highway_types: dict[str, int]
    vertex_count: int
    face_count: int
    minimum_z_m: float
    maximum_z_m: float
    max_abs_x_m: float
    max_abs_y_m: float
    terrain_local_maximum_m: float
    terrain_source_unchanged: bool
    road_meshes: dict[str, Path]
    visual_materials: dict[str, tuple[float, float, float, float]]
    steps_rendered: bool


def sha256(path: Path) -> str:
    """Return a read-only SHA-256 digest."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def resolve_model_uri(uri: str, model_sdf: Path) -> Path:
    """Resolve the road model's own mesh URI without Gazebo environment state."""
    model_directory = model_sdf.parent
    prefix = "model://"
    if not uri.startswith(prefix):
        raise V1ValidationError(f"Road mesh URI must be model://, found {uri}")
    model_name, separator, relative_path = uri.removeprefix(prefix).partition("/")
    if not separator or model_name != model_directory.name or not relative_path:
        raise V1ValidationError(f"Road mesh URI must point inside {model_directory.name}: {uri}")
    return model_directory / relative_path


def parse_obj_vertices(mesh: Path) -> tuple[list[tuple[float, float, float]], int]:
    """Read visual OBJ vertices and quad faces without relying on its MTL import."""
    vertices: list[tuple[float, float, float]] = []
    face_count = 0
    for line in mesh.read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if not fields:
            continue
        if fields[0] == "v" and len(fields) == 4:
            try:
                vertices.append(tuple(float(value) for value in fields[1:]))
            except ValueError as error:
                raise V1ValidationError(f"Road OBJ has non-numeric vertex: {line}") from error
        elif fields[0] == "f" and len(fields) == 5:
            face_count += 1
    if not vertices or not face_count:
        raise V1ValidationError("Road OBJ must contain vertices and quad faces")
    return vertices, face_count


def parse_rgba(element: ET.Element | None, label: str) -> tuple[float, float, float, float]:
    """Parse one explicit SDF color and reject incomplete or non-finite values."""
    if element is None or element.text is None:
        raise V1ValidationError(f"Road visual lacks {label} material color")
    try:
        rgba = tuple(float(value) for value in element.text.split())
    except ValueError as error:
        raise V1ValidationError(f"Road visual has invalid {label} material color") from error
    if len(rgba) != 4 or not all(math.isfinite(value) and 0.0 <= value <= 1.0 for value in rgba):
        raise V1ValidationError(f"Road visual has invalid {label} RGBA values")
    return rgba  # type: ignore[return-value]


def validate_v1_environment(
    roads_model_sdf: Path, world_sdf: Path, terrain_tiff: Path, road_metadata: Path
) -> V1ValidationReport:
    """Verify V1 assets without launching Gazebo or altering any source data."""
    for required_path, label in (
        (roads_model_sdf, "roads model SDF"),
        (world_sdf, "world SDF"),
        (terrain_tiff, "terrain GeoTIFF"),
        (road_metadata, "road metadata"),
    ):
        if not required_path.is_file():
            raise V1ValidationError(f"Missing {label}: {required_path}")
    if sha256(terrain_tiff) != EXPECTED_TERRAIN_SHA256:
        raise V1ValidationError("Processed V0 terrain GeoTIFF SHA-256 differs from the validated source")
    with rasterio.open(terrain_tiff) as dataset:
        if dataset.crs is None or dataset.crs.to_epsg() != 3826:
            raise V1ValidationError(f"Terrain CRS must be EPSG:3826, found {dataset.crs}")
        terrain = dataset.read(1, masked=True)
        terrain_reference_m = round(float(terrain.min()), 3)
        terrain_local_maximum_m = float(terrain.max()) - terrain_reference_m

    try:
        model_root = ET.parse(roads_model_sdf).getroot()
        world_root = ET.parse(world_sdf).getroot()
    except ET.ParseError as error:
        raise V1ValidationError("Road model or world is not valid SDF XML") from error
    model = model_root.find("model")
    if model is None or model.attrib.get("name") != "alishan_shizhuo_roads":
        raise V1ValidationError("Road model must be named alishan_shizhuo_roads")
    if model.findtext("static") != "true":
        raise V1ValidationError("Road model must be static in V1")
    if model.findall(".//collision"):
        raise V1ValidationError("V1 roads must remain visual-only; terrain supplies collision")
    expected_categories = {"secondary", "unclassified", "service", "track", "path", "footway"}
    road_meshes: dict[str, Path] = {}
    visual_materials: dict[str, tuple[float, float, float, float]] = {}
    vertices: list[tuple[float, float, float]] = []
    face_count = 0
    for visual in model.findall(".//visual"):
        category = visual.attrib.get("name", "")
        mesh_uri = visual.findtext("geometry/mesh/uri")
        if not mesh_uri:
            raise V1ValidationError(f"Road visual {category!r} must reference an OBJ mesh")
        mesh = resolve_model_uri(mesh_uri.strip(), roads_model_sdf)
        if not mesh.is_file():
            raise V1ValidationError(f"Road mesh does not exist: {mesh}")
        material = visual.find("material")
        diffuse = parse_rgba(material.find("diffuse") if material is not None else None, "diffuse")
        specular = parse_rgba(material.find("specular") if material is not None else None, "specular")
        if specular[:3] != (0.0, 0.0, 0.0):
            raise V1ValidationError(f"Road visual {category!r} must use a matte zero-specular material")
        if diffuse[:3] == (1.0, 1.0, 1.0):
            raise V1ValidationError(f"Road visual {category!r} must not use a default white material")
        if category in road_meshes:
            raise V1ValidationError(f"Road visual category is duplicated: {category}")
        category_vertices, category_faces = parse_obj_vertices(mesh)
        road_meshes[category] = mesh
        visual_materials[category] = diffuse
        vertices.extend(category_vertices)
        face_count += category_faces
    steps_rendered = "steps" in road_meshes
    if set(road_meshes) != expected_categories:
        raise V1ValidationError(
            f"Road visual categories must be {sorted(expected_categories)}, found {sorted(road_meshes)}"
        )
    if steps_rendered:
        raise V1ValidationError("Steps must be hidden in the focused V1 road rendering")
    if not any((include.findtext("uri") or "").strip() == "model://alishan_shizhuo_roads" for include in world_root.findall(".//include")):
        raise V1ValidationError("World does not include model://alishan_shizhuo_roads")
    try:
        metadata = json.loads(road_metadata.read_text(encoding="utf-8"))
        feature_count = int(metadata["feature_count"])
        highway_types = {str(key): int(value) for key, value in metadata["highway_types"].items()}
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        raise V1ValidationError("Road metadata is missing a valid feature count or highway types") from error
    if feature_count <= 0:
        raise V1ValidationError("Road metadata reports no rendered OSM features")
    maximum_x = max(abs(vertex[0]) for vertex in vertices)
    maximum_y = max(abs(vertex[1]) for vertex in vertices)
    minimum_z = min(vertex[2] for vertex in vertices)
    maximum_z = max(vertex[2] for vertex in vertices)
    tolerance = 1e-6
    if maximum_x > LOCAL_HALF_EXTENT_M + tolerance or maximum_y > LOCAL_HALF_EXTENT_M + tolerance:
        raise V1ValidationError("Road mesh extends outside the 500 m terrain footprint")
    if minimum_z < ROAD_Z_OFFSET_M - tolerance or maximum_z > terrain_local_maximum_m + ROAD_Z_OFFSET_M + tolerance:
        raise V1ValidationError("Road mesh Z values do not follow the local V0 terrain range")
    if not all(math.isfinite(value) for vertex in vertices for value in vertex):
        raise V1ValidationError("Road mesh contains non-finite coordinates")
    return V1ValidationReport(
        feature_count=feature_count,
        highway_types=highway_types,
        vertex_count=len(vertices),
        face_count=face_count,
        minimum_z_m=minimum_z,
        maximum_z_m=maximum_z,
        max_abs_x_m=maximum_x,
        max_abs_y_m=maximum_y,
        terrain_local_maximum_m=terrain_local_maximum_m,
        terrain_source_unchanged=True,
        road_meshes=road_meshes,
        visual_materials=visual_materials,
        steps_rendered=steps_rendered,
    )


def main() -> int:
    """Run the V1 validation report from the command line."""
    project_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--roads-model-sdf", type=Path, default=project_root / "gazebo/models/alishan_shizhuo_roads/model.sdf"
    )
    parser.add_argument("--world-sdf", type=Path, default=project_root / "gazebo/worlds/alishan_shizhuo.sdf")
    parser.add_argument(
        "--terrain-tiff", type=Path, default=project_root / "data/processed/alishan_shizhuo_terrain_20m.tif"
    )
    parser.add_argument(
        "--road-metadata", type=Path, default=project_root / "data/processed/roads/alishan_shizhuo_roads_metadata.json"
    )
    arguments = parser.parse_args()
    try:
        report = validate_v1_environment(
            roads_model_sdf=arguments.roads_model_sdf,
            world_sdf=arguments.world_sdf,
            terrain_tiff=arguments.terrain_tiff,
            road_metadata=arguments.road_metadata,
        )
    except V1ValidationError as error:
        print(f"V1 validation error: {error}", file=sys.stderr)
        return 1
    print(f"feature_count: {report.feature_count}")
    print(f"highway_types: {json.dumps(report.highway_types, sort_keys=True)}")
    print("meshes:")
    for category, mesh in sorted(report.road_meshes.items()):
        print(f"  {category}: {mesh}")
    print(f"visual_materials: {json.dumps(report.visual_materials, sort_keys=True)}")
    print(f"steps_rendered: {report.steps_rendered}")
    print(f"vertices: {report.vertex_count}")
    print(f"faces: {report.face_count}")
    print(f"local_xy_abs_max_m: x={report.max_abs_x_m:.3f}, y={report.max_abs_y_m:.3f}")
    print(f"road_local_z_m: min={report.minimum_z_m:.3f}, max={report.maximum_z_m:.3f}")
    print(f"terrain_local_z_max_m: {report.terrain_local_maximum_m:.3f}")
    print(f"terrain_source_unchanged: {report.terrain_source_unchanged}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
