"""Amenity behavior tests: real geometry, spatial clearance, and water physics."""
import importlib
import json
from pathlib import Path
import sys
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def bounds(obj):
    if "vertices" in obj:
        vertices = np.asarray(obj["vertices"])
        return vertices.min(axis=0), vertices.max(axis=0)
    center = np.asarray(obj["center"])
    size = np.asarray(obj.get("size", [0, 0, 0]))
    if obj["kind"] == "cylinder":
        size = np.array([2 * obj["radius"], 2 * obj["radius"], obj["length"]])
    if obj["kind"] == "sphere":
        size = 2 * np.asarray(obj["radii"])
    # Rotation-aware AABB for beams represented as rotated boxes.
    roll, pitch, yaw = obj.get("rotation", [0, 0, 0])
    cr, sr, cp, sp, cy, sy = np.cos(roll), np.sin(roll), np.cos(pitch), np.sin(pitch), np.cos(yaw), np.sin(yaw)
    rot = np.array([[cy*cp, cy*sp*sr-sy*cr, cy*sp*cr+sy*sr],
                    [sy*cp, sy*sp*sr+cy*cr, sy*sp*cr-cy*sr],
                    [-sp, cp*sr, cp*cr]])
    half = np.abs(rot) @ size / 2
    return center - half, center + half


class AmenitiesTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue((ROOT / "scripts" / "amenities.py").exists(), "The amenity builder has not been implemented")
        from geometry import Scene
        builder = importlib.import_module("amenities")
        self.config = json.loads((ROOT / "configs" / "estate.json").read_text())
        self.scene = Scene()
        self.metadata = builder.build_amenities(self.scene, self.config)
        self.objects = [o for m in self.scene.models.values() for o in m.objects]
        self.features = {f["name"]: f for f in self.metadata["features"]}

    def test_pool_water_is_open_above_a_collidable_recessed_basin(self):
        water = [o for o in self.objects if o["material"] == "pool_water"]
        self.assertTrue(water, "A visible pool water surface is required")
        self.assertTrue(all(not o["collision"] for o in water))
        pool = self.features["swimming_pool"]
        self.assertEqual(pool["water_z"], 79.9)
        self.assertEqual(pool["floor_z"], 77.7)
        floor = next(o for o in self.objects if o["name"] == "pool_floor")
        low, high = bounds(floor)
        self.assertTrue(floor["collision"])
        self.assertAlmostEqual(high[2], 77.7)
        self.assertLessEqual(low[0], 149)
        self.assertGreaterEqual(high[0], 185)
        holes = self.metadata["excavations"]
        self.assertTrue(any(h["bounds"][0] <= 149 and h["bounds"][1] >= 185 and
                            h["bounds"][2] <= 139 and h["bounds"][3] >= 159 and h["z"] <= low[2]
                            for h in holes), "Terrain must be excavated beneath the whole pool")
        for obj in self.objects:
            if not obj["collision"]:
                continue
            lo, hi = bounds(obj)
            self.assertFalse(lo[0] < 167 < hi[0] and lo[1] < 149 < hi[1] and
                             lo[2] < 79.9 < hi[2], f"Pool surface blocked by {obj['name']}")

    def test_open_gate_keeps_twelve_metre_approach_passage_clear(self):
        gate = self.features["entrance_gate"]
        self.assertGreaterEqual(gate["clear_width"], 12)
        self.assertTrue(gate["leaves_open"])
        for obj in self.scene.models["estate_entrance"].objects:
            if obj["collision"]:
                lo, hi = bounds(obj)
                intersects = (lo[0] < -179 and hi[0] > -191 and lo[1] < -380 and
                              hi[1] > -405 and hi[2] > 27.2 and lo[2] < 31)
                self.assertFalse(intersects, f"Open gate passage blocked by {obj['name']}")

    def test_reserved_basement_access_and_main_entry_are_clear(self):
        for obj in self.objects:
            if not obj["collision"]:
                continue
            lo, hi = bounds(obj)
            west = lo[0] < 30 and hi[0] > 8 and lo[1] < 153 and hi[1] > 125 and hi[2] > 75
            main = lo[0] < 81 and hi[0] > 75 and lo[1] < 115 and hi[1] > 95 and hi[2] > 81
            self.assertFalse(west, f"Basement access obstructed by {obj['name']}")
            self.assertFalse(main, f"Main entry approach obstructed by {obj['name']}")
        approach = self.features["villa_approach"]
        self.assertGreaterEqual(approach["clear_width"], 6)
        self.assertEqual(approach["endpoint"], [78, 115, 80.2])

    def test_court_has_regulation_lines_two_hoops_and_a_collision_floor(self):
        court = self.features["basketball_court"]
        self.assertEqual(court["playing_size"], [28, 15])
        self.assertEqual(court["runoff_size"], [32, 19])
        self.assertEqual(court["three_point_radius"], 6.75)
        self.assertEqual(court["line_width"], 0.05)
        self.assertEqual(len(court["hoops"]), 2)
        for hoop in court["hoops"]:
            self.assertAlmostEqual(hoop[2] - court["surface_z"], 3.05)
        floor = next(o for o in self.objects if o["name"] == "court_surface")
        self.assertTrue(floor["collision"])
        lines = [o for o in self.scene.models["estate_basketball"].objects if o["material"] == "white"]
        self.assertTrue(lines)
        self.assertTrue(any(o["kind"] == "mesh" and len(o["faces"]) > 100 for o in lines))

    def test_fountain_has_annular_drive_and_noncollidable_water(self):
        self.assertEqual(self.features["arrival_drive"]["radii"], [26, 37])
        fountain = self.features["arrival_fountain"]
        self.assertGreaterEqual(fountain["jet_count"], 12)
        self.assertGreaterEqual(fountain["basin_count"], 3)
        water = [o for o in self.objects if o["material"] == "water"]
        self.assertTrue(water)
        self.assertTrue(all(not o["collision"] for o in water))

    def test_required_amenities_are_separate_from_villa_and_lake_dock_is_usable(self):
        for name in ["entrance_gate", "arrival_drive", "arrival_fountain", "swimming_pool", "pool_deck",
                     "basketball_court", "fire_pit_lounge", "lake_pavilion", "villa_approach"]:
            self.assertIn(name, self.features)
        dock = self.features["lake_pavilion"]
        self.assertLess(dock["center"][0], -50)
        self.assertGreater(dock["floor_z"], 49)
        self.assertGreaterEqual(dock["clear_headroom"], 3)
        self.assertTrue(any(o["name"] == "dock_platform" and o["collision"] for o in self.objects))

    def test_batched_meshes_have_finite_valid_nondegenerate_triangles(self):
        for obj in self.objects:
            if obj["kind"] != "mesh":
                continue
            verts, faces = np.asarray(obj["vertices"]), np.asarray(obj["faces"])
            self.assertTrue(np.isfinite(verts).all(), obj["name"])
            self.assertTrue(((faces >= 0) & (faces < len(verts))).all(), obj["name"])
            cross = np.cross(verts[faces[:, 1]] - verts[faces[:, 0]], verts[faces[:, 2]] - verts[faces[:, 0]])
            self.assertTrue((np.linalg.norm(cross, axis=1) > 1e-10).all(), obj["name"])

    def test_court_painted_surfaces_face_upward_for_render_visibility(self):
        tested = 0
        for obj in self.scene.models["estate_basketball"].objects:
            if obj["kind"] != "mesh" or obj["material"] not in ["white", "court_key"]:
                continue
            paint_z = 80.126 if obj["material"] == "white" else 80.122
            verts, faces = np.asarray(obj["vertices"]), np.asarray(obj["faces"])
            triangles = verts[faces]
            planar = np.isclose(triangles[:, :, 2], paint_z, atol=1e-6).all(axis=1)
            triangles = triangles[planar]
            tested += len(triangles)
            normals = np.cross(triangles[:, 1]-triangles[:, 0], triangles[:, 2]-triangles[:, 0])
            self.assertTrue((normals[:, 2] > 0).all(), "Court arcs must face upward, or backface culling hides them")
        self.assertGreater(tested, 100)


if __name__ == "__main__":
    unittest.main()
