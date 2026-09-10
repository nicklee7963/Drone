# Alishan Shizhuo Terrain Preprocessing Design

## Goal

Create a reproducible GIS preprocessing pipeline that crops the official 2025 Chiayi County 20 m DTM to the 500 m by 500 m Alishan Shizhuo site and emits a validated GeoTIFF and preview PNG. The pipeline does not create simulation assets.

## Inputs and coordinate systems

`configs/site.yaml` remains the sole human-readable site input in WGS84 latitude/longitude. The processing CRS is EPSG:3826 (`TWD97 / TM2 zone 121`), whose metre-based easting and northing coordinates match the official DTM metadata. Elevations are retained in metres relative to TWVD2001 and recorded in GeoTIFF tags.

The raw input is the original official 2025 Chiayi County archive, saved unchanged at `data/raw/chiayi_20m_dtm_2025.zip`. Its SHA-256 is recorded by the command output. The archive is inspected before parsing: unsupported structures, CRS declarations, grid spacing, and target coverage are failures, never assumptions.

## Data flow

`site.yaml` → `site_geometry.py` → projected 500 m bounds → `inspect_dtm.py` → archive/tile discovery → `crop_dtm.py` → GeoTIFF and PNG → `validate_terrain.py` → concise report.

The crop is exactly 500 m by 500 m in EPSG:3826. It preserves source elevation samples, uses no smoothing, and rejects missing coverage or an excessive NoData ratio instead of fabricating values.

## Modules and command-line interfaces

- `scripts/site_geometry.py`: site loading, EPSG:3826 transformation, and bounding-box calculation.
- `scripts/inspect_dtm.py`: archive discovery, metadata inspection, format checks, and coverage inspection.
- `scripts/crop_dtm.py`: extraction, native-grid conversion, exact crop creation, GeoTIFF writing, and optional PNG output.
- `scripts/validate_terrain.py`: output metadata and data-quality validation.

Every CLI accepts `--site-config`, defaulting to `configs/site.yaml` relative to the project root, and never embeds Shizhuo coordinates.

## Dependencies

`PyYAML` reads configuration, `pyproj` transforms CRS coordinates, `rasterio` writes and reads GeoTIFF, `numpy` handles raster arrays, and `matplotlib` writes the non-interactive preview. Direct GDAL Python bindings are not required because Rasterio is the raster interface.

## Tests

Standard-library `unittest` tests use the actual site configuration and check WGS84-to-EPSG:3826 conversion, the exact 500 m bounding-box dimensions, and configuration loading. They do not require the external DTM archive.
