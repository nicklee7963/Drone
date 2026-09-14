"""Tests for the production V1 roads asset and Gazebo world contract."""

from __future__ import annotations

import importlib
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

validator = importlib.import_module("validate_v1_environment")


class V1EnvironmentValidatorTests(unittest.TestCase):
    """V1 roads must be a non-destructive, locally bounded visual-only layer."""

    def test_production_roads_reference_a_real_bounded_mesh_and_unchanged_terrain(self) -> None:
        """Broken mesh resources, invalid local coordinates, or terrain mutation must fail V1 validation."""
        report = validator.validate_v1_environment(
            roads_model_sdf=PROJECT_ROOT / "gazebo/models/alishan_shizhuo_roads/model.sdf",
            world_sdf=PROJECT_ROOT / "gazebo/worlds/alishan_shizhuo.sdf",
            terrain_tiff=PROJECT_ROOT / "data/processed/alishan_shizhuo_terrain_20m.tif",
            road_metadata=PROJECT_ROOT / "data/processed/roads/alishan_shizhuo_roads_metadata.json",
        )

        self.assertGreater(report.vertex_count, 0)
        self.assertGreater(report.face_count, 0)
        self.assertGreater(report.feature_count, 0)
        self.assertLessEqual(report.max_abs_x_m, 250.0)
        self.assertLessEqual(report.max_abs_y_m, 250.0)
        self.assertGreaterEqual(report.minimum_z_m, 0.10)
        self.assertLessEqual(report.maximum_z_m, 229.94)
        self.assertTrue(report.terrain_source_unchanged)
        self.assertEqual(
            set(report.road_meshes),
            {"secondary", "unclassified", "service", "track", "path", "footway"},
        )
        for category, mesh in report.road_meshes.items():
            mesh_text = mesh.read_text(encoding="utf-8")
            self.assertIn("mtllib alishan_shizhuo_roads.mtl", mesh_text)
            self.assertIn(f"usemtl road_{category}", mesh_text)

    def test_production_roads_have_explicit_matte_sdf_materials_per_visible_category(self) -> None:
        """An OBJ-import fallback to white must not erase the overview road hierarchy."""
        report = validator.validate_v1_environment(
            roads_model_sdf=PROJECT_ROOT / "gazebo/models/alishan_shizhuo_roads/model.sdf",
            world_sdf=PROJECT_ROOT / "gazebo/worlds/alishan_shizhuo.sdf",
            terrain_tiff=PROJECT_ROOT / "data/processed/alishan_shizhuo_terrain_20m.tif",
            road_metadata=PROJECT_ROOT / "data/processed/roads/alishan_shizhuo_roads_metadata.json",
        )

        self.assertEqual(
            getattr(report, "visual_materials", None),
            {
                "secondary": (0.08, 0.08, 0.08, 1.0),
                "unclassified": (0.28, 0.28, 0.28, 1.0),
                "service": (0.58, 0.58, 0.58, 1.0),
                "track": (0.34, 0.18, 0.06, 1.0),
                "path": (0.62, 0.42, 0.20, 1.0),
                "footway": (0.72, 0.54, 0.30, 1.0),
            },
        )
        self.assertFalse(getattr(report, "steps_rendered", True))
        self.assertTrue(all(path.is_file() for path in getattr(report, "road_meshes", {}).values()))


if __name__ == "__main__":
    unittest.main()
