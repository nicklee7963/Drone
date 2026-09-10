"""Tests for the direct-GeoTIFF Gazebo terrain SDF contract."""

from __future__ import annotations

import importlib
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_TIFF = PROJECT_ROOT / "data" / "processed" / "alishan_shizhuo_terrain_20m.tif"
PRODUCTION_MODEL_SDF = PROJECT_ROOT / "gazebo" / "models" / "alishan_shizhuo_terrain" / "model.sdf"
PRODUCTION_WORLD_SDF = PROJECT_ROOT / "gazebo" / "worlds" / "alishan_shizhuo.sdf"
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

try:
    validator = importlib.import_module("validate_gazebo_terrain")
except ModuleNotFoundError:
    validator = None


def write_model_sdf(path: Path, terrain_uri: str) -> None:
    """Write the smallest model that exercises both heightmap consumers."""
    heightmap = f"""
      <heightmap>
        <uri>{terrain_uri}</uri>
        <size>500 500 229.830</size>
        <pos>0 0 -1330.340</pos>
        <sampling>1</sampling>
      </heightmap>"""
    path.write_text(
        f"""<?xml version=\"1.0\"?>
<sdf version=\"1.10\">
  <model name=\"fixture_terrain\">
    <static>true</static>
    <link name=\"terrain_link\">
      <collision name=\"terrain_collision\"><pose>0 0 -1330.340 0 0 0</pose><geometry>{heightmap}</geometry></collision>
      <visual name=\"terrain_visual\"><geometry>{heightmap}</geometry></visual>
    </link>
  </model>
</sdf>
""",
        encoding="utf-8",
    )


class GazeboTerrainValidatorTests(unittest.TestCase):
    """The validator must protect the exact direct-DEM terrain contract."""

    def make_fixture(
        self,
        terrain_uri: str = "model://fixture_terrain/terrain/terrain.tif",
        source_tiff: Path = SOURCE_TIFF,
    ) -> tuple[Path, Path]:
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        fixture_root = Path(temporary_directory.name) / "fixture_terrain"
        terrain_directory = fixture_root / "terrain"
        terrain_directory.mkdir(parents=True)
        (terrain_directory / "terrain.tif").symlink_to(source_tiff)
        model_sdf = fixture_root / "model.sdf"
        write_model_sdf(model_sdf, terrain_uri)
        return model_sdf, source_tiff

    def test_validator_reports_direct_geotiff_geometry_and_local_elevations(self) -> None:
        """Changing SDF scale, local origin, or source asset must fail this contract."""
        self.assertIsNotNone(validator, "validate_gazebo_terrain module must exist")
        model_sdf, source_tiff = self.make_fixture()

        report = validator.validate_terrain_model(model_sdf, source_tiff)

        self.assertEqual(report.heightmap_size_m, (500.0, 500.0, 229.83))
        self.assertEqual(report.heightmap_position_m, (0.0, 0.0, -1330.34))
        self.assertEqual(report.collision_pose_m, (0.0, 0.0, -1330.34))
        self.assertEqual(report.local_minimum_elevation_m, 0.0)
        self.assertEqual(report.local_maximum_elevation_m, 229.83)
        self.assertEqual(report.local_center_elevation_m, 111.1)
        self.assertTrue(report.source_tiff_unchanged)

    def test_validator_rejects_unresolvable_heightmap_asset(self) -> None:
        """A broken direct-DEM URI must report a clear, actionable failure."""
        self.assertIsNotNone(validator, "validate_gazebo_terrain module must exist")
        model_sdf, source_tiff = self.make_fixture("model://fixture_terrain/terrain/missing.tif")

        with self.assertRaisesRegex(validator.TerrainValidationError, "does not exist"):
            validator.validate_terrain_model(model_sdf, source_tiff)

    def test_production_model_meets_direct_geotiff_contract(self) -> None:
        """The committed model must retain the validated V0 terrain parameters."""
        self.assertIsNotNone(validator, "validate_gazebo_terrain module must exist")

        report = validator.validate_terrain_model(PRODUCTION_MODEL_SDF, SOURCE_TIFF)

        self.assertEqual(report.heightmap_size_m, (500.0, 500.0, 229.83))
        self.assertEqual(report.heightmap_position_m, (0.0, 0.0, -1330.34))
        self.assertEqual(report.collision_pose_m, (0.0, 0.0, -1330.34))

    def test_validator_rejects_changed_processed_geotiff(self) -> None:
        """The canonical validated GeoTIFF must retain its recorded SHA-256."""
        self.assertIsNotNone(validator, "validate_gazebo_terrain module must exist")
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        changed_tiff = Path(temporary_directory.name) / "changed.tif"
        changed_tiff.write_bytes(b"not the validated Alishan GeoTIFF")
        model_sdf, source_tiff = self.make_fixture(source_tiff=changed_tiff)

        with self.assertRaisesRegex(validator.TerrainValidationError, "SHA-256"):
            validator.validate_terrain_model(model_sdf, source_tiff)

    def test_production_world_populates_minimal_scene(self) -> None:
        """A terrain-only GUI must load Scene Manager to display server visuals."""
        plugin_names = {
            plugin.attrib.get("filename")
            for plugin in ET.parse(PRODUCTION_WORLD_SDF).findall(".//gui/plugin")
        }

        self.assertIn("GzSceneManager", plugin_names)

    def test_overview_camera_clip_covers_the_full_terrain(self) -> None:
        """The overview camera far clip must include the far 500 m terrain corner."""
        minimal_scene = ET.parse(PRODUCTION_WORLD_SDF).find(".//gui/plugin[@filename='MinimalScene']")

        self.assertIsNotNone(minimal_scene)
        self.assertEqual(minimal_scene.findtext("camera_clip/near"), "0.25")
        self.assertEqual(minimal_scene.findtext("camera_clip/far"), "25000")

    def test_production_visual_heightmap_has_a_neutral_diffuse_layer(self) -> None:
        """Ogre2 Terra needs one terrain texture layer to compile the visual shader."""
        model_root = ET.parse(PRODUCTION_MODEL_SDF).getroot()
        visual_heightmap = model_root.find(".//visual/geometry/heightmap")

        self.assertIsNotNone(visual_heightmap)
        diffuse = visual_heightmap.findtext("texture/diffuse")
        self.assertEqual(diffuse, "terrain/alishan_neutral.ppm")
        if diffuse is None:
            return
        normal = visual_heightmap.findtext("texture/normal")
        self.assertEqual(normal, "terrain/alishan_flat_normal.ppm")
        if normal is None:
            return
        self.assertTrue(
            (PRODUCTION_MODEL_SDF.parent / diffuse).is_file(),
            "The visual diffuse layer must resolve relative to model.sdf",
        )
        self.assertTrue(
            (PRODUCTION_MODEL_SDF.parent / normal).is_file(),
            "The visual normal layer must resolve relative to model.sdf",
        )


if __name__ == "__main__":
    unittest.main()
