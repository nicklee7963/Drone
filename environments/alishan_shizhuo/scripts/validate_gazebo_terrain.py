#!/usr/bin/env python3
"""Validate the direct-GeoTIFF Gazebo terrain model contract."""

from __future__ import annotations

import argparse
import hashlib
import math
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path


HEIGHTMAP_SIZE_M = (500.0, 500.0, 229.830)
HEIGHTMAP_POSITION_M = (0.0, 0.0, -1330.340)
SOURCE_MIN_ELEVATION_M = 1330.340
SOURCE_MAXIMUM_ELEVATION_M = 1560.170
SOURCE_CENTER_ELEVATION_M = 1441.440
HEIGHTMAP_SAMPLING = 1
# Digest recorded immediately before creating the Gazebo asset link.  It makes
# the preservation check meaningful instead of merely comparing a symlink to
# its own current target.
EXPECTED_SOURCE_TIFF_SHA256 = "b082d7f874808eb531a27daa293dd5766faf3339763219cdeab0bd578fd2c8dc"


class TerrainValidationError(ValueError):
    """Raised when the Gazebo terrain model violates the V0 contract."""


@dataclass(frozen=True)
class TerrainModelReport:
    """Validated geometry, local elevation, and source-asset details."""

    heightmap_size_m: tuple[float, float, float]
    heightmap_position_m: tuple[float, float, float]
    collision_pose_m: tuple[float, float, float]
    local_minimum_elevation_m: float
    local_maximum_elevation_m: float
    local_center_elevation_m: float
    terrain_asset: Path
    source_tiff_sha256: str
    source_tiff_unchanged: bool


def local_z(elevation_m: float) -> float:
    """Convert TWVD2001 terrain elevation to the documented local Gazebo Z."""
    return round(elevation_m - SOURCE_MIN_ELEVATION_M, 3)


def sha256(path: Path) -> str:
    """Return a SHA-256 digest while reading the source file without mutation."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_vector(text: str | None, field: str) -> tuple[float, float, float]:
    """Parse an SDF three-value vector with a clear validation error."""
    if text is None:
        raise TerrainValidationError(f"Heightmap is missing <{field}>")
    try:
        values = tuple(float(value) for value in text.split())
    except ValueError as error:
        raise TerrainValidationError(f"Heightmap <{field}> must contain numeric values") from error
    if len(values) != 3:
        raise TerrainValidationError(f"Heightmap <{field}> must contain exactly three values")
    return values  # type: ignore[return-value]


def parse_collision_pose(text: str | None) -> tuple[float, float, float]:
    """Parse the collision pose that aligns DART's attached heightfield."""
    if text is None:
        raise TerrainValidationError("Terrain collision is missing <pose>")
    try:
        values = tuple(float(value) for value in text.split())
    except ValueError as error:
        raise TerrainValidationError("Terrain collision <pose> must contain numeric values") from error
    if len(values) != 6:
        raise TerrainValidationError("Terrain collision <pose> must contain exactly six values")
    translation = values[:3]
    rotation = values[3:]
    require_expected_vector(translation, HEIGHTMAP_POSITION_M, "collision pose translation")
    require_expected_vector(rotation, (0.0, 0.0, 0.0), "collision pose rotation")
    return translation  # type: ignore[return-value]


def resolve_terrain_uri(uri: str, model_sdf: Path) -> Path:
    """Resolve the model-local terrain URI without relying on Gazebo environment state."""
    model_directory = model_sdf.parent
    if uri.startswith("model://"):
        model_name, separator, relative_path = uri.removeprefix("model://").partition("/")
        if not separator or not relative_path:
            raise TerrainValidationError(f"Heightmap URI must name a model-local asset: {uri}")
        if model_name != model_directory.name:
            raise TerrainValidationError(
                f"Heightmap model URI names [{model_name}] but model directory is [{model_directory.name}]"
            )
        return model_directory / relative_path
    if uri.startswith("file://"):
        return Path(uri.removeprefix("file://"))
    if "://" in uri:
        raise TerrainValidationError(f"Unsupported heightmap URI scheme: {uri}")
    return model_directory / uri


def require_expected_vector(actual: tuple[float, float, float], expected: tuple[float, float, float], field: str) -> None:
    """Require exact design values to floating-point text precision."""
    if not all(math.isclose(value, required, rel_tol=0.0, abs_tol=1e-6) for value, required in zip(actual, expected)):
        raise TerrainValidationError(f"Heightmap <{field}> is {actual}; expected {expected}")


def validate_terrain_model(model_sdf: Path, expected_tiff: Path) -> TerrainModelReport:
    """Validate paired collision/visual direct-DEM heightmaps and their source asset."""
    model_sdf = model_sdf.resolve()
    expected_tiff = expected_tiff.resolve()
    if not model_sdf.is_file():
        raise TerrainValidationError(f"Model SDF does not exist: {model_sdf}")
    if not expected_tiff.is_file():
        raise TerrainValidationError(f"Expected source GeoTIFF does not exist: {expected_tiff}")

    try:
        root = ET.parse(model_sdf).getroot()
    except ET.ParseError as error:
        raise TerrainValidationError(f"Model SDF is not valid XML: {model_sdf}") from error

    heightmaps = root.findall(".//heightmap")
    if len(heightmaps) != 2:
        raise TerrainValidationError(f"Expected exactly two heightmaps (collision and visual), found {len(heightmaps)}")
    collisions = root.findall(".//collision")
    if len(collisions) != 1:
        raise TerrainValidationError(f"Expected exactly one terrain collision, found {len(collisions)}")
    collision_pose_m = parse_collision_pose(collisions[0].findtext("pose"))

    contracts: list[tuple[str, tuple[float, float, float], tuple[float, float, float], int, Path]] = []
    for heightmap in heightmaps:
        uri = (heightmap.findtext("uri") or "").strip()
        if not uri:
            raise TerrainValidationError("Heightmap is missing <uri>")
        size = parse_vector(heightmap.findtext("size"), "size")
        position = parse_vector(heightmap.findtext("pos"), "pos")
        sampling_text = heightmap.findtext("sampling")
        try:
            sampling = int(sampling_text) if sampling_text is not None else 0
        except ValueError as error:
            raise TerrainValidationError("Heightmap <sampling> must be an integer") from error
        contracts.append((uri, size, position, sampling, resolve_terrain_uri(uri, model_sdf)))

    first_uri, first_size, first_position, first_sampling, first_asset = contracts[0]
    for uri, size, position, sampling, asset in contracts[1:]:
        if (uri, size, position, sampling, asset) != (first_uri, first_size, first_position, first_sampling, first_asset):
            raise TerrainValidationError("Collision and visual heightmaps must use identical terrain parameters")

    require_expected_vector(first_size, HEIGHTMAP_SIZE_M, "size")
    require_expected_vector(first_position, HEIGHTMAP_POSITION_M, "pos")
    if first_sampling != HEIGHTMAP_SAMPLING:
        raise TerrainValidationError(f"Heightmap <sampling> is {first_sampling}; expected {HEIGHTMAP_SAMPLING}")
    if not first_asset.is_file():
        raise TerrainValidationError(f"Heightmap terrain asset does not exist: {first_asset}")
    if first_asset.resolve() != expected_tiff:
        raise TerrainValidationError(f"Heightmap terrain asset resolves to {first_asset.resolve()}, not {expected_tiff}")

    source_hash = sha256(expected_tiff)
    if source_hash != EXPECTED_SOURCE_TIFF_SHA256:
        raise TerrainValidationError(
            "Processed source GeoTIFF SHA-256 differs from the validated terrain input: "
            f"{source_hash}"
        )
    asset_hash = sha256(first_asset)
    if asset_hash != source_hash:
        raise TerrainValidationError("Heightmap terrain asset bytes differ from the processed source GeoTIFF")

    return TerrainModelReport(
        heightmap_size_m=first_size,
        heightmap_position_m=first_position,
        collision_pose_m=collision_pose_m,
        local_minimum_elevation_m=local_z(SOURCE_MIN_ELEVATION_M),
        local_maximum_elevation_m=local_z(SOURCE_MAXIMUM_ELEVATION_M),
        local_center_elevation_m=local_z(SOURCE_CENTER_ELEVATION_M),
        terrain_asset=first_asset,
        source_tiff_sha256=source_hash,
        source_tiff_unchanged=True,
    )


def format_report(report: TerrainModelReport) -> str:
    """Render the concise report used by the reproducible command-line check."""
    return "\n".join(
        (
            f"heightmap_size_m: {report.heightmap_size_m[0]:.3f} x {report.heightmap_size_m[1]:.3f} x {report.heightmap_size_m[2]:.3f}",
            f"heightmap_position_m: {report.heightmap_position_m[0]:.3f} {report.heightmap_position_m[1]:.3f} {report.heightmap_position_m[2]:.3f}",
            f"collision_pose_m: {report.collision_pose_m[0]:.3f} {report.collision_pose_m[1]:.3f} {report.collision_pose_m[2]:.3f}",
            f"local_elevation_m: min={report.local_minimum_elevation_m:.3f}, max={report.local_maximum_elevation_m:.3f}, center={report.local_center_elevation_m:.3f}",
            f"terrain_asset: {report.terrain_asset}",
            f"source_tiff_sha256: {report.source_tiff_sha256}",
            f"source_tiff_unchanged: {report.source_tiff_unchanged}",
        )
    )


def main() -> int:
    """Run the Gazebo terrain model validation from the command line."""
    project_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model-sdf",
        type=Path,
        default=project_root / "gazebo/models/alishan_shizhuo_terrain/model.sdf",
    )
    parser.add_argument(
        "--source-tiff",
        type=Path,
        default=project_root / "data/processed/alishan_shizhuo_terrain_20m.tif",
    )
    arguments = parser.parse_args()
    try:
        print(format_report(validate_terrain_model(arguments.model_sdf, arguments.source_tiff)))
    except TerrainValidationError as error:
        print(f"terrain validation error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
