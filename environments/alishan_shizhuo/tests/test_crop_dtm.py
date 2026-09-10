"""Tests for preserving native grid elevations in a GeoTIFF crop."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

import numpy as np
import rasterio


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from crop_dtm import crop_tile, write_preview  # noqa: E402
from inspect_dtm import inspect_archive  # noqa: E402
from site_geometry import ProjectedBounds  # noqa: E402


def write_crop_fixture(path: Path) -> None:
    """Create a 4 by 4 native DTM fixture with hand-derived elevations."""
    header = "\n".join(
        [
            "Synthetic tile",
            "fixture",
            "TWD97[2020]",
            "TWVD2001",
            "5000",
            "20",
            "20",
            "16",
            "4",
            "4",
            "100",
            "200",
            "10",
        ]
    )
    grid = "\n".join(
        f"{easting} {northing} {easting + northing / 1000:.2f}"
        for northing in (200, 220, 240, 260)
        for easting in (100, 120, 140, 160)
    )
    with ZipFile(path, "w") as archive:
        archive.writestr("Metadata.xml", "<metadata>EPSG:3826</metadata>")
        archive.writestr("fixture.hdr", header)
        archive.writestr("fixture.grd", grid)


class DtmCropTests(unittest.TestCase):
    """Crop behavior that must preserve samples rather than smooth them."""

    def test_crop_writes_selected_native_samples_to_north_up_geotiff(self) -> None:
        """Changing source sample positions or values must fail this raster output contract."""
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            archive_path = temporary_path / "fixture.zip"
            output_path = temporary_path / "terrain.tif"
            write_crop_fixture(archive_path)
            source = inspect_archive(archive_path)
            bounds = ProjectedBounds(west_m=105, south_m=205, east_m=145, north_m=245)

            crop_tile(source.path, source.tile_covering(bounds), bounds, output_path)

            with rasterio.open(output_path) as dataset:
                data = dataset.read(1)
                self.assertEqual((dataset.width, dataset.height), (2, 2))
                self.assertEqual(dataset.res, (20.0, 20.0))
                self.assertEqual(tuple(dataset.bounds), (110.0, 210.0, 150.0, 250.0))
                self.assertEqual(dataset.crs.to_epsg(), 3826)
                self.assertEqual(dataset.tags()["VERTICAL_DATUM"], "TWVD2001")

        np.testing.assert_allclose(data, np.array([[120.24, 140.24], [120.22, 140.22]]))

    def test_preview_is_a_noninteractive_png_of_the_written_geotiff(self) -> None:
        """Removing preview rendering or writing another format must break inspection output."""
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            archive_path = temporary_path / "fixture.zip"
            terrain_path = temporary_path / "terrain.tif"
            preview_path = temporary_path / "preview.png"
            write_crop_fixture(archive_path)
            source = inspect_archive(archive_path)
            bounds = ProjectedBounds(west_m=105, south_m=205, east_m=145, north_m=245)
            crop_tile(source.path, source.tile_covering(bounds), bounds, terrain_path)

            write_preview(terrain_path, preview_path)

            self.assertTrue(preview_path.is_file())
            self.assertEqual(preview_path.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")


if __name__ == "__main__":
    unittest.main()
