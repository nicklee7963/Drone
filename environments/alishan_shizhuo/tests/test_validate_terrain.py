"""Tests for GIS terrain validation reports."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import rasterio
from affine import Affine


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from site_geometry import load_site_config, project_site, site_bounds  # noqa: E402
from validate_terrain import validate_terrain  # noqa: E402


class TerrainValidationTests(unittest.TestCase):
    """Validation behavior independent of the external DTM archive."""

    def test_validation_reports_georeferencing_elevation_and_nodata(self) -> None:
        """Dropping CRS, physical extent, or elevation checks must break this report contract."""
        site = load_site_config(PROJECT_ROOT / "configs" / "site.yaml")
        requested_bounds = site_bounds(site, project_site(site))
        data = np.arange(625, dtype=np.float32).reshape(25, 25)
        data[0, 0] = -9999.0

        with tempfile.TemporaryDirectory() as temporary_directory:
            terrain_path = Path(temporary_directory) / "terrain.tif"
            profile = {
                "driver": "GTiff",
                "width": 25,
                "height": 25,
                "count": 1,
                "dtype": "float32",
                "crs": "EPSG:3826",
                "transform": Affine(20.0, 0.0, requested_bounds.west_m, 0.0, -20.0, requested_bounds.north_m),
                "nodata": -9999.0,
            }
            with rasterio.open(terrain_path, "w", **profile) as dataset:
                dataset.write(data, 1)

            report = validate_terrain(terrain_path, site)

        self.assertEqual((report.width, report.height), (25, 25))
        self.assertEqual((report.pixel_width_m, report.pixel_height_m), (20.0, 20.0))
        self.assertEqual((report.physical_width_m, report.physical_height_m), (500.0, 500.0))
        self.assertTrue(report.center_inside_raster)
        self.assertEqual((report.minimum_elevation_m, report.maximum_elevation_m), (1.0, 624.0))
        self.assertEqual(report.elevation_range_m, 623.0)
        self.assertAlmostEqual(report.nodata_percent, 100.0 / 625.0)
        self.assertIsNotNone(report.center_elevation_m)


if __name__ == "__main__":
    unittest.main()
