import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "01_shell" / "B1" / "B1_shell_pre_v3_cleanup.blend"
SCRIPT = ROOT / "tools" / "apply_geometry_repairs.py"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_repair(blend: Path, manifest: Path, receipt: Path):
    return subprocess.run(
        [
            "blender", "-b", str(blend), "--python", str(SCRIPT), "--",
            "--floor", "B1", "--manifest", str(manifest),
            "--receipt", str(receipt), "--no-backup",
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=120,
    )


class RepairEngineContractTests(unittest.TestCase):
    def test_unknown_object_aborts_without_saving(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            blend = root / "B1_shell.blend"
            manifest = root / "repairs.json"
            receipt = root / "receipt.json"
            shutil.copy2(SOURCE, blend)
            before = digest(blend)
            manifest.write_text(json.dumps({
                "version": 1,
                "floors": {"B1": [{
                    "id": "missing",
                    "operation": "remove_object",
                    "object": "DOES_NOT_EXIST",
                    "reason": "precondition test",
                    "classification": "FLOATING_GEOMETRY",
                    "reference_files": [],
                }]},
            }), encoding="utf-8")
            completed = run_repair(blend, manifest, receipt)
            self.assertNotEqual(completed.returncode, 0, completed.stdout)
            self.assertEqual(digest(blend), before)
            self.assertFalse(receipt.exists())

    def test_terminal_plane_edit_is_bounded_and_receipted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            blend = root / "B1_shell.blend"
            manifest = root / "repairs.json"
            receipt = root / "receipt.json"
            shutil.copy2(SOURCE, blend)
            before = digest(blend)
            manifest.write_text(json.dumps({
                "version": 1,
                "floors": {"B1": [{
                    "id": "b1_linen_wall_endpoint",
                    "operation": "move_terminal_plane",
                    "object": "B1_Wall_Interior_013_Linen_CorridorSouth",
                    "axis": "Y",
                    "side": "min",
                    "expected_m": 7.474815,
                    "target_m": 7.461296,
                    "max_displacement_m": 0.02,
                    "reason": "close plan-proven endpoint crack",
                    "classification": "WALL_WALL_CRACK",
                    "reference_files": ["01_shell/B1/B1.png"],
                }]},
            }), encoding="utf-8")
            completed = run_repair(blend, manifest, receipt)
            self.assertEqual(completed.returncode, 0, completed.stdout)
            self.assertNotEqual(digest(blend), before)
            result = json.loads(receipt.read_text(encoding="utf-8"))
        self.assertEqual(result["applied"][0]["id"], "b1_linen_wall_endpoint")
        self.assertAlmostEqual(result["applied"][0]["displacement_m"], 0.013519, places=6)

    def test_translation_preserves_object_dimensions(self):
        source = ROOT / "01_shell" / "1F" / "1F_shell_pre_v3_cleanup.blend"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            blend = root / "1F_shell.blend"
            manifest = root / "repairs.json"
            receipt = root / "receipt.json"
            shutil.copy2(source, blend)
            manifest.write_text(json.dumps({
                "version": 1,
                "floors": {"1F": [{
                    "id": "translate_glass",
                    "operation": "translate_object",
                    "object": "1F_Glass_014_Pantry_East",
                    "axis": "X",
                    "expected_min_m": 18.480356,
                    "delta_m": 0.027191,
                    "max_displacement_m": 0.03,
                    "reason": "test wall/glass alignment",
                    "classification": "WALL_GLASS_CRACK",
                    "reference_files": ["01_shell/1F/1F.png"],
                }]},
            }), encoding="utf-8")
            completed = subprocess.run(
                [
                    "blender", "-b", str(blend), "--python", str(SCRIPT), "--",
                    "--floor", "1F", "--manifest", str(manifest),
                    "--receipt", str(receipt), "--no-backup",
                ],
                cwd=ROOT, text=True, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, timeout=120,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout)
            applied = json.loads(receipt.read_text(encoding="utf-8"))["applied"][0]
        before = applied["bounds_before_m"]
        after = applied["bounds_after_m"]
        self.assertAlmostEqual(after[0] - before[0], 0.027191, places=6)
        self.assertAlmostEqual(after[3] - after[0], before[3] - before[0], places=6)


if __name__ == "__main__":
    unittest.main()
