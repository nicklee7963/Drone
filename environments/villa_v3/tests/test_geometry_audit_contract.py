import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLASSIFICATIONS = {
    "INTENTIONAL_DOOR",
    "INTENTIONAL_CIRCULATION",
    "INTENTIONAL_STAIR_OPENING",
    "INTENTIONAL_GLASS_TRANSITION",
    "INTENTIONAL_TERRACE_OPENING",
    "ACCIDENTAL_EXTERIOR_GAP",
    "ACCIDENTAL_INTERIOR_GAP",
    "WALL_GLASS_CRACK",
    "WALL_WALL_CRACK",
    "UNWALKABLE_SLIVER",
    "ACCIDENTAL_COLUMN",
    "FLOATING_GEOMETRY",
    "OVERLAPPING_GEOMETRY",
    "UNKNOWN",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class GeometryAuditContractTests(unittest.TestCase):
    def run_floor_audit(self, floor, blend_name=None):
        blend = ROOT / "01_shell" / floor / (blend_name or f"{floor}_shell.blend")
        temporary = tempfile.TemporaryDirectory()
        output = Path(temporary.name) / "audit.json"
        completed = subprocess.run(
            [
                "blender", "-b", str(blend),
                "--python", str(ROOT / "tools" / "villa_geometry_audit.py"),
                "--", "--floor", floor, "--output", str(output),
            ],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=120,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout)
        data = json.loads(output.read_text(encoding="utf-8"))
        temporary.cleanup()
        return data

    def test_audit_is_read_only_and_emits_stable_contract(self):
        source = ROOT / "01_shell" / "Roof" / "Roof_shell.blend"
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            blend = tmp_path / "Roof_shell.blend"
            output = tmp_path / "audit.json"
            shutil.copy2(source, blend)
            before = digest(blend)
            completed = subprocess.run(
                [
                    "blender", "-b", str(blend),
                    "--python", str(ROOT / "tools" / "villa_geometry_audit.py"),
                    "--", "--floor", "Roof", "--output", str(output),
                ],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=120,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout)
            self.assertEqual(digest(blend), before)
            data = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(
            set(data),
            {"floor", "blend", "objects", "candidates", "intentional_openings",
             "metrics", "warnings", "status"},
        )
        self.assertEqual(data["floor"], "Roof")
        self.assertTrue(data["objects"])
        for candidate in data["candidates"]:
            self.assertIn(candidate["classification"], CLASSIFICATIONS)
            self.assertIn("evidence", candidate)
            self.assertIn("decision", candidate)

    def test_subtracted_footprints_are_not_false_overlap_candidates(self):
        blend = ROOT / "01_shell" / "B1" / "B1_shell_pre_v3_cleanup.blend"
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "audit.json"
            completed = subprocess.run(
                [
                    "blender", "-b", str(blend),
                    "--python", str(ROOT / "tools" / "villa_geometry_audit.py"),
                    "--", "--floor", "B1", "--output", str(output),
                ],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=120,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout)
            candidates = json.loads(output.read_text(encoding="utf-8"))["candidates"]
        ids = {item["id"] for item in candidates}
        self.assertIn(
            "endpoint:B1_Wall_Interior_013_Linen_CorridorSouth:"
            "B1_Wall_Interior_015_TopRoomsSouth_Main",
            ids,
        )
        false_positive_pairs = {
            frozenset(("B1_Glass_007_Lounge_SouthWest", "B1_Wall_Exterior_013_StairVestibule_EastReturn")),
            frozenset(("B1_Glass_007_Lounge_SouthWest", "B1_Wall_Exterior_015_Lounge_SouthCenter")),
            frozenset(("B1_Glass_008_Lounge_SouthEast", "B1_Wall_Exterior_015_Lounge_SouthCenter")),
            frozenset(("B1_Glass_008_Lounge_SouthEast", "B1_Wall_Exterior_016_Lounge_SouthEast")),
            frozenset(("B1_Wall_Exterior_018_Services_EastLower", "B1_Wall_Interior_025_WaterBath_EastJamb")),
        }
        reported_overlap_pairs = {
            frozenset(item["objects"])
            for item in candidates
            if item["classification"] == "OVERLAPPING_GEOMETRY"
        }
        self.assertTrue(false_positive_pairs.isdisjoint(reported_overlap_pairs))

    def test_multipart_walls_are_not_called_floating_and_larger_endpoint_cracks_are_audited(self):
        candidates = self.run_floor_audit("1F", "1F_shell_pre_v3_cleanup.blend")["candidates"]
        self.assertFalse(any(item["id"].startswith("components:") for item in candidates))
        wall_glass_pairs = {
            frozenset(item["objects"])
            for item in candidates
            if item["classification"] == "WALL_GLASS_CRACK"
        }
        self.assertIn(
            frozenset(("1F_Wall_Exterior_018_Ensuite2_South", "1F_Glass_022_Ensuite2_South")),
            wall_glass_pairs,
        )

    def test_floor_slabs_are_not_wall_endpoint_or_sliver_candidates(self):
        candidates = self.run_floor_audit("2F")["candidates"]
        self.assertFalse(
            any(
                any("Floor" in name or "Slab" in name for name in item["objects"])
                and item["classification"] in {
                    "WALL_WALL_CRACK", "WALL_GLASS_CRACK", "UNWALKABLE_SLIVER"
                }
                for item in candidates
            )
        )

    def test_roof_parapet_supported_by_slab_top_is_not_floating(self):
        candidates = self.run_floor_audit("Roof")["candidates"]
        self.assertNotIn("support:Roof_Parapet", {item["id"] for item in candidates})


if __name__ == "__main__":
    unittest.main()
