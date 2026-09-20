import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AssemblyContractTests(unittest.TestCase):
    def test_builder_stacks_all_five_floors_at_contract_elevations(self):
        with tempfile.TemporaryDirectory() as tmp:
            blend = Path(tmp) / "villa_v3_full.blend"
            report = Path(tmp) / "assembly.json"
            build = subprocess.run(
                ["blender", "-b", "--python", str(ROOT / "tools" / "build_full_assembly.py"),
                 "--", "--root", str(ROOT), "--output", str(blend), "--skip-render"],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180,
            )
            self.assertEqual(build.returncode, 0, build.stdout)
            validate = subprocess.run(
                ["blender", "-b", str(blend), "--python", str(ROOT / "tools" / "validate_full_assembly.py"),
                 "--", "--output", str(report)],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120,
            )
            self.assertEqual(validate.returncode, 0, validate.stdout)
            data = json.loads(report.read_text(encoding="utf-8"))
        self.assertEqual(data["status"], "PASS")
        self.assertEqual(data["floor_elevations_m"],
                         {"B1": -3.2, "1F": 0.0, "2F": 3.2, "3F": 6.4, "Roof": 9.6})


if __name__ == "__main__":
    unittest.main()
