import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class UnifiedValidatorContractTests(unittest.TestCase):
    def test_geometry_stage_emits_per_floor_machine_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "geometry.json"
            completed = subprocess.run(
                ["python3", str(ROOT / "tools" / "validate_villa_v3.py"),
                 "--root", str(ROOT), "--output", str(output)],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout)
            report = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(set(report["floors"]), {"B1", "1F", "2F", "3F", "Roof"})
        self.assertEqual(report["status"], "PASS")
        self.assertTrue(all(not item["remaining_warnings"] for item in report["floors"].values()))


if __name__ == "__main__":
    unittest.main()
