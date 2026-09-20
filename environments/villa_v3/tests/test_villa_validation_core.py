import tempfile
import unittest
from pathlib import Path

from tools.villa_validation_core import (
    classify_gap,
    floor_z,
    interval_gap,
    rect_overlap_area,
    resolve_audit_candidates,
    validate_floor_name,
    validate_sdf_tree,
)


class CoreTests(unittest.TestCase):
    def test_interval_gap_distinguishes_contact_gap_and_overlap(self):
        self.assertEqual(interval_gap(0, 1, 1, 2), 0.0)
        self.assertAlmostEqual(interval_gap(0, 1, 1.015, 2), 0.015)
        self.assertAlmostEqual(interval_gap(0, 1.2, 1, 2), -0.2)

    def test_rect_overlap_area_uses_positive_area_only(self):
        self.assertAlmostEqual(
            rect_overlap_area((0, 0, 2, 2), (1, 1, 3, 4)), 1.0
        )
        self.assertEqual(
            rect_overlap_area((0, 0, 1, 1), (1, 0, 2, 1)), 0.0
        )

    def test_floor_contract(self):
        self.assertEqual(
            [floor_z(f) for f in ("B1", "1F", "2F", "3F", "Roof")],
            [-3.2, 0.0, 3.2, 6.4, 9.6],
        )
        with self.assertRaises(ValueError):
            validate_floor_name("4F")

    def test_gap_classification_is_conservative(self):
        self.assertEqual(
            classify_gap(0.015, "undeclared_exterior"),
            "ACCIDENTAL_EXTERIOR_GAP",
        )
        self.assertEqual(
            classify_gap(1.2, "declared_door"), "INTENTIONAL_DOOR"
        )
        self.assertEqual(
            classify_gap(0.40, "interior_free_space"), "UNWALKABLE_SLIVER"
        )

    def test_sdf_requires_visual_collision_and_existing_mesh(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "model.sdf").write_text(
                """<?xml version='1.0'?>
<sdf version='1.9'><model name='broken'><link name='link'>
<visual name='visual'><geometry><mesh><uri>meshes/test.obj</uri></mesh></geometry></visual>
</link></model></sdf>""",
                encoding="utf-8",
            )
            (root / "meshes").mkdir()
            (root / "meshes" / "test.obj").write_text("v 0 0 0\n", encoding="utf-8")
            issues = validate_sdf_tree(root)
        self.assertEqual([i["code"] for i in issues], ["MISSING_COLLISION"])

    def test_candidate_resolution_requires_an_explicit_matching_decision(self):
        audit = {"candidates": [{"id": "endpoint:a:b", "classification": "WALL_WALL_CRACK",
                                  "decision": "REVIEW_REQUIRED"}]}
        resolved, unresolved = resolve_audit_candidates(audit, {
            "endpoint:a:b": {"decision": "PRESERVED_REFERENCE_INTENT",
                              "classification": "INTENTIONAL_DOOR",
                              "reference_files": ["plan.png"], "rationale": "Door jamb."}
        })
        self.assertFalse(unresolved)
        self.assertEqual(resolved[0]["classification"], "INTENTIONAL_DOOR")
        self.assertEqual(resolved[0]["decision"], "PRESERVED_REFERENCE_INTENT")

        _, unresolved = resolve_audit_candidates(audit, {})
        self.assertEqual([item["id"] for item in unresolved], ["endpoint:a:b"])


if __name__ == "__main__":
    unittest.main()
