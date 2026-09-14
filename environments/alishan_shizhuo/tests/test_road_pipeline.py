"""Behavioral tests for the bounded OSM-road V1 preprocessing pipeline."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
SITE_CONFIG = PROJECT_ROOT / "configs" / "site.yaml"
SOURCE_TIFF = PROJECT_ROOT / "data" / "processed" / "alishan_shizhuo_terrain_20m.tif"
sys.path.insert(0, str(SCRIPTS_DIR))

from download_osm_roads import build_overpass_query, osm_api_map_url_for_site, overpass_bbox_for_site  # noqa: E402
from generate_road_mesh import generate_road_mesh, road_material_name, road_width_m  # noqa: E402


class RoadPipelineTests(unittest.TestCase):
    """The V1 pipeline must preserve site geometry and local terrain alignment."""

    def test_overpass_bbox_is_derived_from_the_exact_metric_site_extent(self) -> None:
        """A degree-offset regression must not query outside the configured 500 m site."""
        south, west, north, east = overpass_bbox_for_site(SITE_CONFIG)

        self.assertAlmostEqual(south, 23.477127735, places=8)
        self.assertAlmostEqual(west, 120.696157403, places=8)
        self.assertAlmostEqual(north, 23.481652227, places=8)
        self.assertAlmostEqual(east, 120.701062514, places=8)
        query = build_overpass_query((south, west, north, east))
        self.assertIn('way["highway"]', query)
        self.assertIn("out tags geom;", query)

    def test_official_osm_api_url_uses_the_same_metric_derived_bbox(self) -> None:
        """A fallback-download regression must not swap latitude and longitude bbox order."""
        url = osm_api_map_url_for_site(SITE_CONFIG)

        self.assertIn("bbox=120.696157403%2C23.477127735%2C120.701062514%2C23.481652227", url)

    def test_generated_ribbon_stays_on_the_local_terrain_and_preserves_the_source(self) -> None:
        """A projected-road or elevation-origin regression must be visible in the OBJ output."""
        source_hash_before = hashlib.sha256(SOURCE_TIFF.read_bytes()).hexdigest()
        source_payload = {
            "version": 0.6,
            "elements": [
                {
                    "type": "way",
                    "id": 123456,
                    "tags": {"highway": "residential", "name": "V1 fixture road"},
                    "geometry": [
                        {"lat": 23.47939, "lon": 120.69750},
                        {"lat": 23.47939, "lon": 120.69972},
                    ],
                }
            ],
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            source_json = temporary_root / "roads.json"
            output_obj = temporary_root / "roads.obj"
            output_mtl = temporary_root / "roads.mtl"
            output_metadata = temporary_root / "roads.json.metadata"
            source_json.write_text(json.dumps(source_payload), encoding="utf-8")

            report = generate_road_mesh(
                source_json=source_json,
                terrain_tiff=SOURCE_TIFF,
                site_config=SITE_CONFIG,
                output_obj=output_obj,
                output_mtl=output_mtl,
                output_metadata=output_metadata,
            )

            vertices = [
                tuple(float(value) for value in line.split()[1:])
                for line in output_obj.read_text(encoding="utf-8").splitlines()
                if line.startswith("v ")
            ]
            first_face = next(
                tuple(int(value) for value in line.split()[1:])
                for line in output_obj.read_text(encoding="utf-8").splitlines()
                if line.startswith("f ")
            )
            obj_text = output_obj.read_text(encoding="utf-8")
            mtl_text = output_mtl.read_text(encoding="utf-8")

        self.assertEqual(report.feature_count, 1)
        self.assertEqual(report.highway_types, {"residential": 1})
        self.assertTrue(vertices)
        self.assertTrue(all(-250.0 <= x <= 250.0 and -250.0 <= y <= 250.0 for x, y, _ in vertices))
        self.assertTrue(all(0.10 <= z <= 229.93 for _, _, z in vertices))
        first, second, third = (vertices[index - 1] for index in first_face[:3])
        first_edge = tuple(second[index] - first[index] for index in range(3))
        second_edge = tuple(third[index] - first[index] for index in range(3))
        normal_z = first_edge[0] * second_edge[1] - first_edge[1] * second_edge[0]
        self.assertGreater(normal_z, 0.0, "Road OBJ faces must point upward for single-sided rendering")
        self.assertIn("usemtl road_unclassified", obj_text)
        self.assertIn("newmtl road_unclassified", mtl_text)
        self.assertEqual(hashlib.sha256(SOURCE_TIFF.read_bytes()).hexdigest(), source_hash_before)

    def test_visual_categories_have_the_requested_width_hierarchy_and_materials(self) -> None:
        """A category-width regression must remain obvious from the overview camera."""
        self.assertEqual(road_width_m("secondary"), 5.0)
        self.assertEqual(road_width_m("unclassified"), 3.5)
        self.assertEqual(road_width_m("service"), 2.5)
        self.assertEqual(road_width_m("track"), 1.8)
        self.assertEqual(road_width_m("path"), 0.8)
        self.assertEqual(road_width_m("footway"), 0.7)
        self.assertEqual(road_width_m("steps"), 0.0)
        self.assertGreater(road_width_m("secondary"), road_width_m("unclassified"))
        self.assertGreater(road_width_m("unclassified"), road_width_m("service"))
        self.assertGreater(road_width_m("service"), road_width_m("track"))
        self.assertEqual(road_material_name("secondary"), "road_secondary")
        self.assertEqual(road_material_name("track"), "road_track")
        self.assertEqual(road_material_name("steps"), "")

    def test_category_meshes_use_explicit_visual_assets_and_hide_steps(self) -> None:
        """A renderer must receive separately addressable category meshes, not one MTL-dependent mesh."""
        source_payload = {
            "version": 0.6,
            "elements": [
                {
                    "type": "way",
                    "id": 1,
                    "tags": {"highway": "secondary"},
                    "geometry": [
                        {"lat": 23.47939, "lon": 120.69750},
                        {"lat": 23.47939, "lon": 120.69972},
                    ],
                },
                {
                    "type": "way",
                    "id": 2,
                    "tags": {"highway": "steps"},
                    "geometry": [
                        {"lat": 23.47920, "lon": 120.69750},
                        {"lat": 23.47920, "lon": 120.69972},
                    ],
                },
            ],
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            source_json = temporary_root / "roads.json"
            output_obj = temporary_root / "roads.obj"
            output_mtl = temporary_root / "roads.mtl"
            output_metadata = temporary_root / "roads.metadata.json"
            source_json.write_text(json.dumps(source_payload), encoding="utf-8")

            report = generate_road_mesh(
                source_json=source_json,
                terrain_tiff=SOURCE_TIFF,
                site_config=SITE_CONFIG,
                output_obj=output_obj,
                output_mtl=output_mtl,
                output_metadata=output_metadata,
            )

            secondary_mesh = temporary_root / "roads_secondary.obj"
            steps_mesh = temporary_root / "roads_steps.obj"
            secondary_text = secondary_mesh.read_text(encoding="utf-8") if secondary_mesh.exists() else ""
            secondary_mesh_exists = secondary_mesh.is_file()
            steps_mesh_exists = steps_mesh.exists()

        self.assertEqual(report.feature_count, 1)
        self.assertEqual(report.highway_types, {"secondary": 1})
        self.assertTrue(secondary_mesh_exists)
        self.assertFalse(steps_mesh_exists)
        self.assertIn("mtllib roads.mtl", secondary_text)
        self.assertIn("usemtl road_secondary", secondary_text)

    def test_generated_ribbon_accepts_the_unchanged_official_osm_xml_response(self) -> None:
        """A fallback-source regression must not require rewriting official OSM XML as JSON."""
        source_xml = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<osm version=\"0.6\">
  <node id=\"1\" lat=\"23.47939\" lon=\"120.69750\"/>
  <node id=\"2\" lat=\"23.47939\" lon=\"120.69972\"/>
  <way id=\"42\">
    <nd ref=\"1\"/><nd ref=\"2\"/>
    <tag k=\"highway\" v=\"service\"/>
  </way>
</osm>
"""
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            raw_xml = temporary_root / "roads.osm"
            output_obj = temporary_root / "roads.obj"
            output_mtl = temporary_root / "roads.mtl"
            output_metadata = temporary_root / "roads.metadata.json"
            raw_xml.write_text(source_xml, encoding="utf-8")

            report = generate_road_mesh(
                source_json=raw_xml,
                terrain_tiff=SOURCE_TIFF,
                site_config=SITE_CONFIG,
                output_obj=output_obj,
                output_mtl=output_mtl,
                output_metadata=output_metadata,
            )

        self.assertEqual(report.feature_count, 1)
        self.assertEqual(report.highway_types, {"service": 1})


if __name__ == "__main__":
    unittest.main()
