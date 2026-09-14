"""Requirements and physical-clearance checks for the generated villa."""
import importlib
import json
import math
from pathlib import Path
import sys
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def _builder():
    try:
        return importlib.import_module("villa").build_villa
    except ModuleNotFoundError:
        return None


def _rotation(rotation):
    r, p, y = rotation
    cr, sr, cp, sp, cy, sy = math.cos(r), math.sin(r), math.cos(p), math.sin(p), math.cos(y), math.sin(y)
    return np.array([[cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
                     [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
                     [-sp, cp * sr, cp * cr]])


def _sphere_hits_primitive(point, radius, obj):
    """Independent sphere/OBB test; other curved shapes use safe outer bounds."""
    if not obj.get("collision"):
        return False
    if "center" not in obj:
        # Villa meshes are visual-only; a new colliding mesh needs an exact test.
        raise AssertionError(f"Unsupported colliding geometry: {obj['name']}")
    q = _rotation(obj.get("rotation", (0, 0, 0))).T @ (np.asarray(point) - obj["center"])
    if obj["kind"] == "box":
        half = np.asarray(obj["size"]) * 0.5
        return np.linalg.norm(np.maximum(np.abs(q) - half, 0)) < radius - 1e-7
    if obj["kind"] == "cylinder":
        d = np.array([max(np.linalg.norm(q[:2]) - obj["radius"], 0),
                      max(abs(q[2]) - obj["length"] / 2, 0)])
        return np.linalg.norm(d) < radius - 1e-7
    if obj["kind"] == "sphere":
        return np.linalg.norm(q) < max(obj["radii"]) + radius - 1e-7
    raise AssertionError(f"Unsupported primitive: {obj['kind']}")


class VillaImplementationTest(unittest.TestCase):
    def test_builder_exists(self):
        self.assertIsNotNone(_builder(), "The villa geometry builder has not been implemented")


@unittest.skipUnless(_builder(), "Villa implementation is being authored")
class VillaGeometryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from geometry import Scene
        cls.scene = Scene()
        cls.config = json.loads((ROOT / "configs" / "estate.json").read_text())
        cls.meta = _builder()(cls.scene, cls.config)
        cls.objects = cls.scene.models["summit_villa"].objects

    def test_required_spaces_have_bounded_usable_geometry(self):
        rooms = self.meta["rooms"]
        functions = {r["function"] for r in rooms}
        self.assertTrue({"kitchen", "dining", "living", "bathroom", "gym", "boxing",
                         "cinema", "study", "storage"}.issubset(functions))
        bedrooms = [r for r in rooms if r["function"] == "bedroom"]
        self.assertEqual(len(bedrooms), 4)
        self.assertEqual(len([r for r in rooms if r["function"] == "bathroom"]), 4)
        for room in rooms:
            x0, x1, y0, y1, z0, z1 = room["bounds"]
            self.assertGreater((x1 - x0) * (y1 - y0), 8, room["name"])
            self.assertGreater(z1 - z0, 3, room["name"])
        for bedroom in bedrooms:
            self.assertEqual(bedroom["level"], "upper")
            beds = [o for o in self.objects if o["name"].startswith(bedroom["name"] + "_bed_")]
            self.assertTrue(beds, bedroom["name"] + " has no bed geometry")

    def test_main_entry_and_bedroom_doors_are_physically_open(self):
        portals = self.meta["portals"]
        entry = next(p for p in portals if p["name"] == "main_entry")
        self.assertGreaterEqual(entry["width"], 6)
        self.assertGreaterEqual(entry["height"], 4)
        suite_doors = [p for p in portals if p["name"].startswith("bedroom_") and p["name"].endswith("_door")]
        self.assertEqual(len(suite_doors), 4)
        for p in [entry] + suite_doors:
            self.assertGreaterEqual(p["width"], 2)
            for side in (-1, 0, 1):
                point = np.asarray(p["center"]) + np.asarray(p["normal"]) * side
                hit = [o["name"] for o in self.objects if _sphere_hits_primitive(point, .45, o)]
                self.assertEqual(hit, [], f"Portal {p['name']} is obstructed")

    def test_flight_routes_clear_real_collision_geometry(self):
        routes = self.meta["flight_routes"]
        self.assertGreaterEqual(len(routes), 7)
        route_points = [p for r in routes for p in r["waypoints"]]
        self.assertLess(min(p[2] for p in route_points), 78)
        self.assertGreater(max(p[2] for p in route_points), 87)
        # Removing a slab hole, glazing an open portal, or moving furniture into
        # a corridor must fail this test, even if metadata is unchanged.
        for route in routes:
            self.assertGreaterEqual(route["clearance_radius"], .45)
            for a, b in zip(route["waypoints"], route["waypoints"][1:]):
                a, b = np.asarray(a), np.asarray(b)
                count = max(2, math.ceil(np.linalg.norm(b - a) / .25) + 1)
                for point in np.linspace(a, b, count):
                    for obj in self.objects:
                        if _sphere_hits_primitive(point, .45, obj):
                            self.fail(f"{route['name']} blocked by {obj['name']} at {point.tolist()}")

    def test_basement_has_west_walkout_and_terrain_excavation(self):
        walkout = next(p for p in self.meta["portals"] if p["name"] == "basement_walkout")
        self.assertEqual(walkout["center"][0], 30)
        self.assertGreaterEqual(walkout["width"], 4)
        self.assertEqual(walkout["normal"], [-1, 0, 0])
        self.assertTrue(any(e["bounds"] == [8, 30, 125, 153] and e["z"] <= 74.4
                            for e in self.meta["excavations"]))
        for p in ((18, 140, 76.8), (29, 140, 76.8), (31, 140, 76.8)):
            self.assertFalse(any(_sphere_hits_primitive(p, .45, o) for o in self.objects))

    def test_program_has_equipment_and_collidable_glass(self):
        names = [o["name"] for o in self.objects]
        for equipment in ("treadmill", "exercise_bike", "rowing_machine", "weight_rack",
                          "bench_press", "boxing_ring", "punch_bag", "cinema_screen",
                          "library_desk", "bookshelf", "storage_shelf"):
            self.assertTrue(any(equipment in name for name in names), equipment)
        panes = [o for o in self.objects if o["material"] == "glass" and o["collision"]]
        self.assertGreater(len(panes), 30)
        self.assertGreater(len(self.objects), 500)


if __name__ == "__main__":
    unittest.main()
