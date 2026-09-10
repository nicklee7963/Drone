"""Crop a verified native Taiwan DTM tile into a georeferenced GeoTIFF."""

from __future__ import annotations

import argparse
import io
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZipFile

import numpy as np
import rasterio
from affine import Affine

from inspect_dtm import CoverageError, GridTile, SourceFormatError, inspect_archive
from site_geometry import ProjectedBounds, SiteConfigError, load_site_config, project_site, site_bounds


OUTPUT_NODATA = -9999.0


class CropError(RuntimeError):
    """Raised when a verified source cannot produce a complete terrain crop."""


@dataclass(frozen=True)
class CropResult:
    """Details of a written GIS terrain crop."""

    output_path: Path
    bounds: ProjectedBounds
    width: int
    height: int
    nodata_percent: float


def _read_native_xyz(archive_path: Path, tile: GridTile) -> np.ndarray:
    """Read one verified ASCII XYZ native grid directly from its ZIP member."""
    with ZipFile(archive_path) as archive:
        raw_grid = archive.read(tile.grid_member)
    try:
        xyz = np.loadtxt(io.BytesIO(raw_grid), dtype=np.float64)
    except ValueError as error:
        raise CropError(f"Grid {tile.grid_member} is not a readable three-column numeric XYZ file") from error
    if xyz.ndim != 2 or xyz.shape[1] != 3:
        raise CropError(f"Grid {tile.grid_member} must contain exactly three numeric columns: E N H")
    if xyz.shape[0] != tile.header.point_count:
        raise CropError(
            f"Grid {tile.grid_member} has {xyz.shape[0]} points; "
            f"header declares {tile.header.point_count}"
        )
    return xyz


def _selected_grid_coordinates(values: np.ndarray, lower: float, upper: float, spacing: float) -> np.ndarray:
    """Select ordered source grid coordinates within a requested site extent."""
    selected = np.unique(values[(values >= lower) & (values < upper)])
    if selected.size == 0:
        raise CoverageError("Requested bounds contain no native DTM sample coordinates")
    if selected.size > 1 and not np.allclose(np.diff(selected), spacing, atol=1e-6):
        raise CropError("Selected DTM coordinates are not a regular native grid")
    return selected


def crop_tile(
    archive_path: Path,
    tile: GridTile,
    requested_bounds: ProjectedBounds,
    output_path: Path,
    *,
    source_nodata: float | None = None,
    max_nodata_percent: float = 5.0,
    overwrite: bool = False,
) -> CropResult:
    """Write native samples intersecting requested bounds to a north-up EPSG:3826 GeoTIFF."""
    if output_path.exists() and not overwrite:
        raise CropError(f"Refusing to overwrite existing terrain output: {output_path}")
    if not 0.0 <= max_nodata_percent <= 100.0:
        raise CropError("max_nodata_percent must be between 0 and 100")

    xyz = _read_native_xyz(archive_path, tile)
    header = tile.header
    eastings = _selected_grid_coordinates(
        xyz[:, 0], requested_bounds.west_m, requested_bounds.east_m, header.easting_spacing_m
    )
    northings = _selected_grid_coordinates(
        xyz[:, 1], requested_bounds.south_m, requested_bounds.north_m, header.northing_spacing_m
    )
    terrain = np.full((northings.size, eastings.size), OUTPUT_NODATA, dtype=np.float32)
    easting_indices = {float(value): index for index, value in enumerate(eastings)}
    northing_indices = {float(value): index for index, value in enumerate(northings)}

    for easting, northing, elevation in xyz:
        column = easting_indices.get(float(easting))
        ascending_row = northing_indices.get(float(northing))
        if column is None or ascending_row is None:
            continue
        if not np.isfinite(elevation) or (source_nodata is not None and elevation == source_nodata):
            continue
        row = northings.size - 1 - ascending_row
        if terrain[row, column] != OUTPUT_NODATA:
            raise CropError(f"Grid {tile.grid_member} contains duplicate sample coordinates")
        terrain[row, column] = elevation

    nodata_percent = 100.0 * float(np.count_nonzero(terrain == OUTPUT_NODATA)) / terrain.size
    if nodata_percent > max_nodata_percent:
        raise CropError(
            f"Crop NoData is {nodata_percent:.2f}%, exceeding the allowed {max_nodata_percent:.2f}%"
        )

    output_bounds = ProjectedBounds(
        west_m=float(eastings[0] - header.easting_spacing_m / 2.0),
        south_m=float(northings[0] - header.northing_spacing_m / 2.0),
        east_m=float(eastings[-1] + header.easting_spacing_m / 2.0),
        north_m=float(northings[-1] + header.northing_spacing_m / 2.0),
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    profile = {
        "driver": "GTiff",
        "width": terrain.shape[1],
        "height": terrain.shape[0],
        "count": 1,
        "dtype": "float32",
        "crs": "EPSG:3826",
        "transform": Affine(
            header.easting_spacing_m,
            0.0,
            output_bounds.west_m,
            0.0,
            -header.northing_spacing_m,
            output_bounds.north_m,
        ),
        "nodata": OUTPUT_NODATA,
        "compress": "deflate",
    }
    with rasterio.open(output_path, "w", **profile) as destination:
        destination.write(terrain, 1)
        destination.update_tags(
            SOURCE_ARCHIVE=archive_path.name,
            SOURCE_GRID=tile.grid_member,
            HORIZONTAL_CRS="EPSG:3826",
            VERTICAL_DATUM=header.vertical_datum,
            ELEVATION_UNITS="m",
            PROCESSING="native samples only; no smoothing or interpolation",
        )

    return CropResult(
        output_path=output_path,
        bounds=output_bounds,
        width=terrain.shape[1],
        height=terrain.shape[0],
        nodata_percent=nodata_percent,
    )


def write_preview(terrain_path: Path, preview_path: Path, *, overwrite: bool = False) -> None:
    """Write a non-interactive PNG that visualizes, but never changes, GeoTIFF elevations."""
    if preview_path.exists() and not overwrite:
        raise CropError(f"Refusing to overwrite existing terrain preview: {preview_path}")
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as pyplot

    with rasterio.open(terrain_path) as dataset:
        terrain = dataset.read(1, masked=True)
        if terrain.count() == 0:
            raise CropError("Cannot preview a terrain raster containing only NoData")
        figure, axes = pyplot.subplots(figsize=(7, 6), constrained_layout=True)
        image = axes.imshow(
            terrain,
            extent=(dataset.bounds.left, dataset.bounds.right, dataset.bounds.bottom, dataset.bounds.top),
            origin="upper",
            cmap="terrain",
            interpolation="nearest",
        )
        axes.set_aspect("equal")
        axes.set_xlabel("Easting (m, EPSG:3826)")
        axes.set_ylabel("Northing (m, EPSG:3826)")
        axes.set_title("Terrain elevation preview")
        figure.colorbar(image, ax=axes, label="Elevation (m, TWVD2001)")
        preview_path.parent.mkdir(parents=True, exist_ok=True)
        figure.savefig(preview_path, dpi=160)
        pyplot.close(figure)


def main() -> None:
    """Create a GeoTIFF terrain crop from a native DTM ZIP and site configuration."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Official native DTM ZIP archive")
    parser.add_argument(
        "--site-config", type=Path, default=Path("configs/site.yaml"), help="Canonical site YAML path"
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output GeoTIFF path (default derives from the site name)",
    )
    parser.add_argument(
        "--preview",
        type=Path,
        help="Output preview PNG path (default derives from the site name)",
    )
    parser.add_argument(
        "--no-preview", action="store_true", help="Skip non-interactive PNG preview creation"
    )
    parser.add_argument(
        "--source-nodata", type=float, help="Optional source elevation value that denotes NoData"
    )
    parser.add_argument(
        "--max-nodata-percent", type=float, default=5.0, help="Maximum allowed output NoData percentage"
    )
    parser.add_argument("--overwrite", action="store_true", help="Permit replacing existing processed outputs")
    arguments = parser.parse_args()

    site = load_site_config(arguments.site_config)
    output_path = arguments.output or Path("data/processed") / f"{site.name}_terrain_20m.tif"
    preview_path = arguments.preview or Path("data/processed") / f"{site.name}_terrain_preview.png"
    bounds = site_bounds(site, project_site(site))
    source = inspect_archive(arguments.input)
    tile = source.tile_covering(bounds)
    result = crop_tile(
        source.path,
        tile,
        bounds,
        output_path,
        source_nodata=arguments.source_nodata,
        max_nodata_percent=arguments.max_nodata_percent,
        overwrite=arguments.overwrite,
    )
    print(f"output: {result.output_path}")
    print(f"dimensions: {result.width} x {result.height} pixels")
    print(f"bounds_epsg3826: {result.bounds.west_m:.3f}, {result.bounds.south_m:.3f}, " f"{result.bounds.east_m:.3f}, {result.bounds.north_m:.3f}")
    print(f"nodata_percent: {result.nodata_percent:.2f}")
    if not arguments.no_preview:
        write_preview(result.output_path, preview_path, overwrite=arguments.overwrite)
        print(f"preview: {preview_path}")


if __name__ == "__main__":
    try:
        main()
    except (CropError, SourceFormatError, SiteConfigError) as error:
        raise SystemExit(f"error: {error}")
