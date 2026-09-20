#!/usr/bin/env python3
"""Combine legacy floor validators with the reviewed V3 geometry audit."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from villa_validation_core import FLOOR_Z, resolve_audit_candidates


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def legacy_counts(data: dict) -> tuple[int, int]:
    summary = data.get("summary", data)
    return int(summary.get("passed", 0)), int(summary.get("failed", 0))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_source_manifest(root: Path) -> dict:
    failures = []
    entries = 0
    for line in (root / "villa_v2_source_sha256.txt").read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        path = root.parent / relative
        entries += 1
        if not path.is_file():
            failures.append({"path": str(path), "reason": "missing"})
        elif sha256(path) != expected:
            failures.append({"path": str(path), "reason": "hash mismatch"})
    return {"status": "PASS" if not failures else "FAIL", "entries": entries, "failures": failures}


def validate(root: Path) -> dict:
    decisions = load_json(root / "geometry_audit_decisions.json").get("floors", {})
    floors = {}
    all_pass = True
    for floor in FLOOR_Z:
        audit = load_json(root / "audit" / f"{floor}_audit_after.json")
        resolved, unresolved = resolve_audit_candidates(audit, decisions.get(floor, {}))
        validation = load_json(root / "01_shell" / floor / f"{floor}_shell_validation.json")
        passed, failed = legacy_counts(validation)
        receipt_path = root / "audit" / f"{floor}_repair_receipt.json"
        receipt = load_json(receipt_path) if receipt_path.exists() else {"applied": [], "status": "PASS"}
        repairs = receipt.get("applied", [])
        preserved = [item for item in resolved
                     if item.get("decision") in {"PRESERVED_REFERENCE_INTENT", "FALSE_POSITIVE"}]
        warnings = [f"Unresolved candidate: {item['id']}" for item in unresolved]
        if failed:
            warnings.append(f"Legacy validator has {failed} failed check(s).")
        if receipt.get("status") != "PASS":
            warnings.append("Repair receipt does not report PASS.")
        status = "PASS" if not warnings else "FAIL"
        all_pass &= status == "PASS"
        counts = audit.get("metrics", {}).get("candidate_counts", {})
        floors[floor] = {
            "floor": floor,
            "elevation_m": FLOOR_Z[floor],
            "status": status,
            "legacy_validator": {"passed": passed, "failed": failed},
            "raw_candidate_counts": counts,
            "confirmed_defects_found": len(repairs),
            "wall_wall_cracks_found": sum(1 for r in repairs if r.get("classification") == "WALL_WALL_CRACK"),
            "wall_glass_cracks_found": sum(1 for r in repairs if r.get("classification") == "WALL_GLASS_CRACK"),
            "exterior_gaps_found": sum(1 for r in repairs if r.get("classification") == "ACCIDENTAL_EXTERIOR_GAP"),
            "interior_accidental_gaps_found": sum(1 for r in repairs if r.get("classification") in {"ACCIDENTAL_INTERIOR_GAP", "WALL_WALL_CRACK"}),
            "unwalkable_slivers_found": sum(1 for r in repairs if r.get("classification") == "UNWALKABLE_SLIVER"),
            "accidental_columns_found": sum(1 for r in repairs if r.get("classification") == "ACCIDENTAL_COLUMN"),
            "floating_objects_found": sum(1 for r in repairs if r.get("classification") == "FLOATING_GEOMETRY"),
            "overlapping_objects_found": sum(1 for r in repairs if r.get("classification") == "OVERLAPPING_GEOMETRY"),
            "intentional_openings_preserved": audit.get("intentional_openings", []) + preserved,
            "fixes_applied": repairs,
            "remaining_warnings": warnings,
        }
    source_integrity = verify_source_manifest(root)
    assembly_path = root / "02_assembly" / "assembly_validation.json"
    gazebo_path = root / "gazebo" / "gazebo_validation.json"
    headless_path = root / "gazebo" / "headless_validation.json"
    assembly = load_json(assembly_path) if assembly_path.exists() else {"status": "NOT_RUN"}
    gazebo = load_json(gazebo_path) if gazebo_path.exists() else {"status": "NOT_RUN"}
    headless = load_json(headless_path) if headless_path.exists() else {"status": "NOT_RUN"}
    required_outputs = {
        "full_blender_assembly": root / "02_assembly" / "villa_v3_full.blend",
        "inspection_render": root / "02_assembly" / "villa_v3_full.png",
        "gazebo_world": root / "gazebo" / "worlds" / "villa_v3.sdf",
    }
    deliverables = {name: {"path": str(path), "exists": path.is_file(),
                            "bytes": path.stat().st_size if path.exists() else 0}
                    for name, path in required_outputs.items()}
    supporting_statuses = [source_integrity["status"], assembly["status"],
                           gazebo["status"], headless["status"]]
    all_pass &= all(value == "PASS" for value in supporting_statuses)
    all_pass &= all(item["exists"] and item["bytes"] > 0 for item in deliverables.values())
    return {"schema_version": 1, "stage": "complete", "status": "PASS" if all_pass else "FAIL",
            "source_villa_v2_integrity": source_integrity, "floors": floors,
            "assembly_validation": assembly, "gazebo_validation": gazebo,
            "gazebo_headless_validation": headless, "deliverables": deliverables,
            "remaining_warnings": [] if all_pass else ["One or more required validation stages failed."]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = validate(args.root.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"VILLA_V3_GEOMETRY_VALIDATION {report['status']}")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
