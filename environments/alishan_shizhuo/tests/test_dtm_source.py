"""Tests for format discovery of official-style DTM archives."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from inspect_dtm import inspect_archive  # noqa: E402


def write_fixture_archive(path: Path, metadata_crs: str = "EPSG:3826") -> None:
    """Create a small archive using the verified 2025 header/grid conventions."""
    header = "\n".join(
        [
            "Synthetic tile",
            "fixture",
            "TWD97[2020]",
            "TWVD2001",
            "5000",
            "20",
            "20",
            "9",
            "3",
            "3",
            "100",
            "200",
            "10",
        ]
    )
    grid = "\n".join(
        f"{easting} {northing} {easting + northing / 1000:.2f}"
        for northing in (200, 220, 240)
        for easting in (100, 120, 140)
    )
    with ZipFile(path, "w") as archive:
        archive.writestr("Metadata.xml", f"<metadata>{metadata_crs}</metadata>")
        archive.writestr("fixture.hdr", header)
        archive.writestr("fixture.grd", grid)


class DtmArchiveInspectionTests(unittest.TestCase):
    """Archive format behavior that must work without external data."""

    def test_inspection_discovers_verified_header_grid_pair(self) -> None:
        """Removing or mispairing a native grid/header pair must break discovery."""
        with tempfile.TemporaryDirectory() as temporary_directory:
            archive_path = Path(temporary_directory) / "fixture.zip"
            write_fixture_archive(archive_path)

            source = inspect_archive(archive_path)

        self.assertEqual(source.metadata_crs, "EPSG:3826")
        self.assertEqual(len(source.tiles), 1)
        tile = source.tiles[0]
        self.assertEqual(tile.grid_member, "fixture.grd")
        self.assertEqual(tile.header.easting_spacing_m, 20.0)
        self.assertEqual(tile.header.northing_spacing_m, 20.0)
        self.assertEqual(tile.header.point_count, 9)


if __name__ == "__main__":
    unittest.main()
