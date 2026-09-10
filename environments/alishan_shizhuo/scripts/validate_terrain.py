"""Validate a processed EPSG:3826 terrain GeoTIFF against a site definition."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
from rasterio.crs import CRS

from site_geometry import PROCESSING_CRS, SiteConfig, SiteConfigError, project_site


class ValidationError(RuntimeError):
    """Raised when a processed terrain file violates the GIS pipeline contract."""


@dataclass(frozen=True)
class TerrainValidation:
    """Concise GIS and elevation quality report for one terrain raster."""

    terrain_path: Path
    width: int
    height: int
    pixel_width_m: float
    pixel_height_m: float
    west_m: float
    south_m: float
    east_m: float
    north_m: float
    physical_width_m: float
    physical_height_m: float
    minimum_elevation_m: float
    maximum_elevation_m: float
    elevation_range_m: float
    nodata_count: int
    nodata_percent: float
    center_inside_raster: bool
    center_elevation_m: float | None


def validate_terrain(
    terrain_path: Path, site: SiteConfig, *, max_nodata_percent: float = 5.0
) -> TerrainValidation:
    """Validate raster georeferencing, extent, center coverage, and elevation statistics."""
    if not 0.0 <= max_nodata_percent <= 100.0:
        raise ValidationError("max_nodata_percent must be between 0 and 100")
    try:
        with rasterio.open(terrain_path) as dataset:
            if dataset.count != 1:
                raise ValidationError(f"Expected one terrain band, found {dataset.count}")
            if dataset.crs != CRS.from_string(PROCESSING_CRS):
                raise ValidationError(f"Expected output CRS {PROCESSING_CRS}, found {dataset.crs}")
            pixel_width_m, pixel_height_m = dataset.res
            if pixel_width_m <= 0 or pixel_height_m <= 0:
                raise ValidationError("Raster has non-positive pixel resolution")
            raster_bounds = dataset.bounds
            physical_width_m = raster_bounds.right - raster_bounds.left
            physical_height_m = raster_bounds.top - raster_bounds.bottom
            tolerance_m = max(pixel_width_m, pixel_height_m)
            if abs(physical_width_m - site.width_m) > tolerance_m or abs(physical_height_m - site.height_m) > tolerance_m:
                raise ValidationError(
                    "Raster physical extent differs from the site dimensions by more than one source pixel: "
                    f"{physical_width_m:.3f} m x {physical_height_m:.3f} m"
                )

            projected_center = project_site(site)
            center_inside_raster = (
                raster_bounds.left <= projected_center.easting_m < raster_bounds.right
                and raster_bounds.bottom < projected_center.northing_m <= raster_bounds.top
            )
            if not center_inside_raster:
                raise ValidationError("The configured site center is outside the cropped terrain raster")

            terrain = np.ma.masked_invalid(dataset.read(1, masked=True))
            valid_elevations = terrain.compressed()
            if valid_elevations.size == 0:
                raise ValidationError("Terrain raster contains only NoData values")
            nodata_count = int(terrain.size - valid_elevations.size)
            nodata_percent = 100.0 * nodata_count / terrain.size
            if nodata_percent > max_nodata_percent:
                raise ValidationError(
                    f"Terrain NoData is {nodata_percent:.2f}%, exceeding allowed {max_nodata_percent:.2f}%"
                )

            center_row, center_column = dataset.index(projected_center.easting_m, projected_center.northing_m)
            center_value = terrain[center_row, center_column]
            center_elevation_m = None if np.ma.is_masked(center_value) else float(center_value)
    except rasterio.errors.RasterioIOError as error:
        raise ValidationError(f"Unable to read terrain raster {terrain_path}: {error}") from error

    return TerrainValidation(
        terrain_path=terrain_path,
        width=dataset.width,
        height=dataset.height,
        pixel_width_m=float(pixel_width_m),
        pixel_height_m=float(pixel_height_m),
        west_m=float(raster_bounds.left),
        south_m=float(raster_bounds.bottom),
        east_m=float(raster_bounds.right),
        north_m=float(raster_bounds.top),
        physical_width_m=float(physical_width_m),
        physical_height_m=float(physical_height_m),
        minimum_elevation_m=float(valid_elevations.min()),
        maximum_elevation_m=float(valid_elevations.max()),
        elevation_range_m=float(valid_elevations.max() - valid_elevations.min()),
        nodata_count=nodata_count,
        nodata_percent=float(nodata_percent),
        center_inside_raster=center_inside_raster,
        center_elevation_m=center_elevation_m,
    )


def main() -> None:
    """Print the validation report for a processed terrain GeoTIFF."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--site-config", type=Path, default=Path("configs/site.yaml"), help="Canonical site YAML path"
    )
    parser.add_argument("--input", type=Path, help="Processed terrain GeoTIFF path")
    parser.add_argument(
        "--max-nodata-percent", type=float, default=5.0, help="Maximum allowed NoData percentage"
    )
    arguments = parser.parse_args()

    from site_geometry import load_site_config

    site = load_site_config(arguments.site_config)
    terrain_path = arguments.input or Path("data/processed") / f"{site.name}_terrain_20m.tif"
    report = validate_terrain(terrain_path, site, max_nodata_percent=arguments.max_nodata_percent)
    print(f"terrain: {report.terrain_path}")
    print(f"crs: {PROCESSING_CRS}")
    print(f"dimensions: {report.width} x {report.height} pixels")
    print(f"pixel_resolution: {report.pixel_width_m:g} m x {report.pixel_height_m:g} m")
    print(
        "bounds_epsg3826: "
        f"west={report.west_m:.3f}, south={report.south_m:.3f}, "
        f"east={report.east_m:.3f}, north={report.north_m:.3f}"
    )
    print(f"physical_extent: {report.physical_width_m:g} m x {report.physical_height_m:g} m")
    print(f"minimum_elevation: {report.minimum_elevation_m:.3f} m")
    print(f"maximum_elevation: {report.maximum_elevation_m:.3f} m")
    print(f"elevation_range: {report.elevation_range_m:.3f} m")
    center_text = "NoData" if report.center_elevation_m is None else f"{report.center_elevation_m:.3f} m"
    print(f"center_elevation: {center_text}")
    print(f"nodata: {report.nodata_count} cells ({report.nodata_percent:.2f}%)")
    print(f"center_inside_raster: {report.center_inside_raster}")


if __name__ == "__main__":
    try:
        main()
    except (ValidationError, SiteConfigError) as error:
        raise SystemExit(f"error: {error}")
