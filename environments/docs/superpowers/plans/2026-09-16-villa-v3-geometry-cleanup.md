# Villa V3 Geometry Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a conservatively repaired `villa_v3` with five validated Blender floors, a full-building Blender render, and a collision-enabled Gazebo world.

**Architecture:** Preserve the copied Blender scenes and apply only preconditioned named-object repairs discovered by a Blender audit. Keep geometric classification, repair receipts, assembly checks, and Gazebo resource checks machine-readable and aggregate them into one final report.

**Tech Stack:** Blender 4.5 Python (`bpy`, `bmesh`, `mathutils`), Python 3 standard library, Bash, Wavefront OBJ, SDF 1.9/1.10, Gazebo Harmonic CLI.

**Spec:** `docs/superpowers/specs/2026-09-16-villa-v3-geometry-cleanup-design.md`

## Global Constraints

- `villa_v2` is immutable; its complete SHA-256 manifest must match before and after work.
- Start from a metadata-preserving copy of `villa_v2` named `villa_v3`.
- Do not regenerate entire floor scenes or redesign architecture.
- Use only confirmed, reference-backed object-specific repairs.
- Storey poses are B1 `-3.2`, 1F `0`, 2F `3.2`, 3F `6.4`, Roof `9.6` metres.
- Exterior accidental endpoint gaps may not exceed `0.02 m`.
- Run copied existing validators and the unified validator after each repaired floor.
- Every Gazebo floor model must contain both visual and collision geometry.

---

### Task 1: Immutable baseline and working copy

**Files:**
- Create: `villa_v3/`
- Create: `villa_v3/villa_v2_source_sha256.txt`

**Interfaces:**
- Consumes: existing `villa_v2/`
- Produces: byte-identical initial `villa_v3/` plus a source hash manifest

- [ ] **Step 1: Confirm target absence and inventory source shell names**

Run: `test ! -e villa_v3 && find villa_v2/01_shell -maxdepth 2 -name '*_shell.blend' -print | sort`

Expected: exactly B1, 1F, 2F, 3F, and Roof shell paths; target test exits zero.

- [ ] **Step 2: Create a complete source hash manifest outside the source tree**

Run: `find villa_v2 -type f -print0 | sort -z | xargs -0 sha256sum > /tmp/villa_v2_pre.sha256`

Expected: nonempty manifest containing every source file, including reference images and blends.

- [ ] **Step 3: Copy the project and preserve metadata**

Run: `cp -a villa_v2 villa_v3 && cp /tmp/villa_v2_pre.sha256 villa_v3/villa_v2_source_sha256.txt`

Expected: `diff -qr villa_v2 villa_v3` reports only `villa_v3/villa_v2_source_sha256.txt` until V3 work begins.

- [ ] **Step 4: Verify copied shell hashes match the source**

Run: `for f in B1 1F 2F 3F Roof; do cmp "villa_v2/01_shell/$f/${f}_shell.blend" "villa_v3/01_shell/$f/${f}_shell.blend"; done`

Expected: exit zero and no output.

- [ ] **Step 5: Commit the copy baseline metadata only if repository policy permits**

Run: `git status --short villa_v3 | head`

Expected: V3 appears as new work; do not stage generated binaries during intermediate development.

### Task 2: Pure validation core with tests

**Files:**
- Create: `villa_v3/tools/villa_validation_core.py`
- Create: `villa_v3/tests/test_villa_validation_core.py`

**Interfaces:**
- Produces: `interval_gap(a0, a1, b0, b1) -> float`, `rect_overlap_area(a, b) -> float`, `classify_gap(width_m, context) -> str`, `validate_floor_name(name) -> str`, `floor_z(name) -> float`, `validate_sdf_tree(root) -> list[dict]`

- [ ] **Step 1: Write failing unit tests with literal expected geometry values**

```python
import unittest
from pathlib import Path
from tools.villa_validation_core import (
    classify_gap, floor_z, interval_gap, rect_overlap_area,
    validate_floor_name, validate_sdf_tree,
)

class CoreTests(unittest.TestCase):
    def test_interval_gap_distinguishes_contact_gap_and_overlap(self):
        self.assertEqual(interval_gap(0, 1, 1, 2), 0.0)
        self.assertAlmostEqual(interval_gap(0, 1, 1.015, 2), 0.015)
        self.assertAlmostEqual(interval_gap(0, 1.2, 1, 2), -0.2)

    def test_rect_overlap_area_uses_positive_area_only(self):
        self.assertAlmostEqual(rect_overlap_area((0, 0, 2, 2), (1, 1, 3, 4)), 1.0)
        self.assertEqual(rect_overlap_area((0, 0, 1, 1), (1, 0, 2, 1)), 0.0)

    def test_floor_contract(self):
        self.assertEqual([floor_z(f) for f in ('B1','1F','2F','3F','Roof')], [-3.2,0.0,3.2,6.4,9.6])
        with self.assertRaises(ValueError): validate_floor_name('4F')

    def test_gap_classification_is_conservative(self):
        self.assertEqual(classify_gap(0.015, 'undeclared_exterior'), 'ACCIDENTAL_EXTERIOR_GAP')
        self.assertEqual(classify_gap(1.2, 'declared_door'), 'INTENTIONAL_DOOR')
        self.assertEqual(classify_gap(0.40, 'interior_free_space'), 'UNWALKABLE_SLIVER')

    def test_sdf_requires_visual_collision_and_existing_mesh(self):
        issues = validate_sdf_tree(Path('tests/fixtures/missing_collision'))
        self.assertEqual([i['code'] for i in issues], ['MISSING_COLLISION'])
```

- [ ] **Step 2: Run the tests and verify the import fails**

Run: `cd villa_v3 && python3 -m unittest tests.test_villa_validation_core -v`

Expected: FAIL with `ModuleNotFoundError` for `tools.villa_validation_core`.

- [ ] **Step 3: Implement the minimal pure helpers and XML checks**

Implement the exact interfaces above using `xml.etree.ElementTree`; resolve each `<mesh><uri>` relative to its model directory and emit stable issue dictionaries containing `code`, `path`, and `detail`.

- [ ] **Step 4: Run the focused tests**

Run: `cd villa_v3 && python3 -m unittest tests.test_villa_validation_core -v`

Expected: all focused tests pass.

### Task 3: Blender floor auditor

**Files:**
- Create: `villa_v3/tools/villa_geometry_audit.py`
- Create: `villa_v3/tests/test_geometry_audit_contract.py`
- Create: `villa_v3/audit/`

**Interfaces:**
- Consumes: `--floor FLOOR --blend PATH --output PATH [--diagnostic-dir PATH]`
- Produces: one JSON record containing `floor`, `objects`, `candidates`, `intentional_openings`, `metrics`, `warnings`, and `status`

- [ ] **Step 1: Write a failing contract test**

The test invokes Blender on a copied shell in a temporary directory and asserts that the output has all required keys, every candidate has a required classification, and the loaded blend is byte-identical before/after auditing.

- [ ] **Step 2: Run the test and verify the missing auditor fails**

Run: `cd villa_v3 && python3 -m unittest tests.test_geometry_audit_contract -v`

Expected: FAIL because `tools/villa_geometry_audit.py` does not exist.

- [ ] **Step 3: Implement evaluated-mesh evidence collection**

Use `bpy.context.evaluated_depsgraph_get()`, world-space bounding boxes, `bmesh` connected components/non-manifold inspection, deterministic rounded vertex signatures, BVH overlap candidates, plan-view endpoint distances, support checks at slab-top Z, and declared-opening metadata extraction. Do not save the source blend.

- [ ] **Step 4: Generate baseline audits in floor order**

Run for B1, 1F, 2F, 3F, and Roof with `blender -b <blend> --python tools/villa_geometry_audit.py -- --floor <floor> --output audit/<floor>_audit_before.json --diagnostic-dir audit/<floor>`.

- [ ] **Step 5: Run the contract test and inspect every candidate against references**

Expected: contract passes; each candidate gets a decision record containing `reference_files`, `decision`, and `rationale` before any repair is added.

### Task 4: Preconditioned repair engine and floor-by-floor repair

**Files:**
- Create: `villa_v3/tools/apply_geometry_repairs.py`
- Create: `villa_v3/geometry_repairs.json`
- Create: `villa_v3/tests/test_repair_engine_contract.py`
- Modify only when confirmed: `villa_v3/01_shell/*/*_shell.blend`

**Interfaces:**
- Consumes: `--floor FLOOR --blend PATH --manifest geometry_repairs.json --receipt PATH`
- Produces: repaired blend, one `*_shell_pre_v3_cleanup.blend` backup, and receipt with old/new coordinates

- [ ] **Step 1: Write failing repair-precondition tests**

Tests must prove an unknown object, unexpected old bound, displacement beyond the manifest maximum, or unsupported operation exits nonzero without changing the blend hash.

- [ ] **Step 2: Run tests and verify failure due to missing engine**

Run: `cd villa_v3 && python3 -m unittest tests.test_repair_engine_contract -v`

Expected: FAIL because the repair engine does not exist.

- [ ] **Step 3: Implement only narrow named-object operations**

Implement `move_terminal_plane`, `align_terminal_plane`, `remove_object`, `remove_component`, and `move_slab_boundary`; abort before save when any expected precondition differs by more than `0.0001 m`.

- [ ] **Step 4: Repair and validate B1**

Populate only confirmed B1 repair entries; run the repair engine, copied `validate_B1_shell.py`, and unified post-audit. Repeat this exact red/green sequence for 1F, 2F, 3F, and Roof in the user-specified order.

- [ ] **Step 5: Reject regressions immediately**

If an existing validator or unified audit regresses, restore the V3 backup, remove the unproven repair entry, and return to evidence collection rather than stacking changes.

### Task 5: Cross-floor alignment validator

**Files:**
- Create: `villa_v3/tools/validate_vertical_alignment.py`
- Create: `villa_v3/tests/test_vertical_alignment_contract.py`
- Create: `villa_v3/audit/vertical_alignment.json`

**Interfaces:**
- Consumes: five accepted shell files
- Produces: world-space stair/opening/slab comparisons at the five approved Z poses

- [ ] **Step 1: Write a failing contract test for exact poses and paired openings**

The test asserts the pose map and requires explicit records for B1↔1F, 1F↔2F, 2F↔3F, and 3F↔Roof.

- [ ] **Step 2: Implement collection-independent comparison from scene metadata and evaluated bounds**

Read connection markers and stair custom properties; report XY maximum error, vertical datum error, slab blockers, and clearance. Do not move stairs automatically.

- [ ] **Step 3: Run the validator**

Expected: no blocker or unexplained error greater than `0.02 m`; otherwise investigate the responsible floor before assembly.

### Task 6: Full Blender assembly and inspection render

**Files:**
- Create: `villa_v3/tools/build_full_assembly.py`
- Create: `villa_v3/tools/validate_full_assembly.py`
- Create: `villa_v3/02_assembly/villa_v3_full.blend`
- Create: `villa_v3/02_assembly/villa_v3_full.png`
- Create: `villa_v3/02_assembly/villa_v3_full_validation.json`

**Interfaces:**
- Produces: collections `B1`, `1F`, `2F`, `3F`, `Roof` at exact Z offsets and a 1920×1080 perspective render

- [ ] **Step 1: Write the assembly validator before the builder**

It must fail when the assembly file is absent and later compare object counts, local XY bounds, Z offsets, source identifiers, render resolution, and camera framing.

- [ ] **Step 2: Verify the expected failure**

Run: `cd villa_v3 && blender -b --python tools/validate_full_assembly.py`

Expected: nonzero exit with `assembly file not found`.

- [ ] **Step 3: Build by appending accepted architectural objects without changing local coordinates**

Append into floor collections, set only collection instance/parent Z to the approved pose, create neutral render-only lighting and camera, save, then render.

- [ ] **Step 4: Validate assembly and image**

Expected: all five collections visible, roof included, 1920×1080 image nonempty, exact floor poses, and no missing source mesh.

### Task 7: Adapt and test the per-floor Gazebo exporter

**Files:**
- Modify: `villa_v3/tools/export_floor_to_gazebo.sh`
- Create: `villa_v3/tests/test_exporter.py`

**Interfaces:**
- Consumes: one of `B1 1F 2F 3F Roof`
- Produces: `gazebo/villa_<floor>/meshes/villa_<floor>.obj`, `model.config`, and `model.sdf`

- [ ] **Step 1: Write failing integration tests for root independence, Roof acceptance, invalid-floor rejection, and visual/collision parity**

Invoke the copied exporter from `/tmp`, verify outputs under V3, parse model SDF, and assert one nonempty OBJ URI is used by both visual and collision.

- [ ] **Step 2: Run tests against the copied V2-hardcoded script**

Expected: FAIL because outputs resolve to `villa_v2` and the usage omits Roof.

- [ ] **Step 3: Make the script resolve V3 root from its own location**

Use `SCRIPT_DIR` and `ROOT`, validate the exact floor allowlist, select only exportable architectural meshes, update V3 descriptions, retain OBJ export and SDF validation.

- [ ] **Step 4: Run the exporter tests**

Expected: all tests pass and each generated model passes `gz sdf -k`.

### Task 8: One-command Gazebo build and world validation

**Files:**
- Create: `villa_v3/tools/build_villa_v3_gazebo.sh`
- Create: `villa_v3/tools/validate_gazebo_output.py`
- Create: `villa_v3/gazebo/worlds/villa_v3.sdf`
- Create: `villa_v3/gazebo/villa_{B1,1F,2F,3F,Roof}/...`

**Interfaces:**
- Produces all five models and a complete world in one command

- [ ] **Step 1: Write a failing world validation test**

Assert five unique includes with literal poses, all model URIs resolvable through `gazebo/`, every model has visual and collision mesh geometry, and no duplicate include names.

- [ ] **Step 2: Verify failure before the V3 world exists**

Run: `cd villa_v3 && python3 tools/validate_gazebo_output.py gazebo/worlds/villa_v3.sdf`

Expected: nonzero exit with missing-world evidence.

- [ ] **Step 3: Implement the build wrapper and world generation**

Call the existing exporter five times in order, write the established physics/plugins/light/ground configuration, and include B1, 1F, 2F, 3F, Roof at `-3.2, 0, 3.2, 6.4, 9.6`.

- [ ] **Step 4: Run complete static Gazebo validation**

Run: `cd villa_v3 && ./tools/build_villa_v3_gazebo.sh`

Expected: all five model checks, `gz sdf -k gazebo/worlds/villa_v3.sdf`, and `validate_gazebo_output.py` pass.

- [ ] **Step 5: Perform a bounded headless load**

Run: `cd villa_v3 && env SDF_PATH="$PWD/gazebo" GZ_SIM_RESOURCE_PATH="$PWD/gazebo" GZ_PARTITION=villa_v3_validation timeout 30s gz sim -s -r -v 4 gazebo/worlds/villa_v3.sdf`

Expected: server reaches world startup with no missing-resource, mesh, or SDF errors; timeout exit `124` after successful running is recorded as bounded success.

### Task 9: Aggregate report and immutable-source proof

**Files:**
- Create: `villa_v3/tools/build_validation_report.py`
- Create: `villa_v3/villa_v3_validation.json`

**Interfaces:**
- Consumes: per-floor before/after audits, repair receipts, existing validator JSON, vertical/assembly/Gazebo results
- Produces: final report matching the requested per-floor schema plus project-level evidence

- [ ] **Step 1: Write a failing schema test**

Require exactly five floor records, requested count fields, `intentional_openings_preserved`, `fixes_applied`, `remaining_warnings`, existing/unified validator results, assembly paths, Gazebo paths, and source-hash verification.

- [ ] **Step 2: Implement deterministic aggregation**

Derive counts from evidence records rather than manually entered totals. A floor or project with an `UNKNOWN`, failed validator, missing output, remaining confirmed defect, or changed V2 hash cannot be PASS.

- [ ] **Step 3: Prove V2 remains unchanged**

Run: `sha256sum -c villa_v3/villa_v2_source_sha256.txt`

Expected: every V2 source file reports `OK`.

- [ ] **Step 4: Run the full verification suite fresh**

Run Python unit/contract tests, all five copied floor validators, all five unified audits, vertical validation, assembly validation, the one-command Gazebo build, `gz sdf -k`, and the bounded headless load.

- [ ] **Step 5: Inspect final deliverables and report only evidence-backed status**

Run: `find villa_v3/01_shell villa_v3/02_assembly villa_v3/gazebo villa_v3/tools -maxdepth 3 -type f -print | sort` and parse `villa_v3_validation.json`.

Expected: every requested deliverable exists; any unresolved ambiguity remains explicitly reported rather than being declared PASS.

