import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class GazeboBuildContractTests(unittest.TestCase):
    def test_exporter_is_root_relative_and_wrapper_builds_all_floors(self):
        exporter = (ROOT / "tools" / "export_floor_to_gazebo.sh").read_text(encoding="utf-8")
        wrapper_path = ROOT / "tools" / "build_villa_v3_gazebo.sh"
        self.assertNotIn("villa_v2", exporter)
        self.assertIn('SCRIPT_DIR=', exporter)
        self.assertTrue(wrapper_path.is_file())
        wrapper = wrapper_path.read_text(encoding="utf-8")
        for floor in ("B1", "1F", "2F", "3F", "Roof"):
            self.assertIn(floor, wrapper)
        self.assertIn("villa_v3.sdf", wrapper)


if __name__ == "__main__":
    unittest.main()
