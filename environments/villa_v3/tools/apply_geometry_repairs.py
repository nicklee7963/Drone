"""Apply narrowly scoped, preconditioned repairs to a copied Villa V3 blend."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys

import bpy


VALID_FLOORS = ("B1", "1F", "2F", "3F", "Roof")
AXIS_INDEX = {"X": 0, "Y": 1, "Z": 2}
TOLERANCE = 0.0001


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--floor", required=True, choices=VALID_FLOORS)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--no-backup", action="store_true")
    return parser.parse_args(argv)


def fail(message):
    print(f"VILLA_REPAIR_ERROR: {message}", file=sys.stderr)
    raise SystemExit(2)


def world_bounds(obj):
    coords = [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]
    return [
        min(co.x for co in coords), min(co.y for co in coords), min(co.z for co in coords),
        max(co.x for co in coords), max(co.y for co in coords), max(co.z for co in coords),
    ]


def plane_coordinate(bounds, axis, side):
    index = AXIS_INDEX[axis]
    return bounds[index if side == "min" else index + 3]


def validate_entry(entry):
    operation = entry.get("operation")
    if operation not in {"move_terminal_plane", "align_terminal_plane", "translate_object", "remove_object"}:
        fail(f"repair {entry.get('id')} uses unsupported operation {operation!r}")
    obj = bpy.data.objects.get(entry.get("object", ""))
    if obj is None or obj.type != "MESH":
        fail(f"repair {entry.get('id')} object {entry.get('object')!r} is missing or not a mesh")
    if operation == "remove_object":
        if not entry.get("confirmed_duplicate_of") and not entry.get("confirmed_fragment"):
            fail(f"repair {entry.get('id')} removal lacks duplicate/fragment precondition")
        return
    if operation == "translate_object":
        axis = entry.get("axis")
        if axis not in AXIS_INDEX:
            fail(f"repair {entry.get('id')} has invalid translation axis")
        bounds = world_bounds(obj)
        expected = float(entry["expected_min_m"])
        actual = bounds[AXIS_INDEX[axis]]
        if abs(actual - expected) > TOLERANCE:
            fail(f"repair {entry.get('id')} expected minimum {expected:.6f} m but found {actual:.6f} m")
        displacement = abs(float(entry["delta_m"]))
        if displacement > float(entry["max_displacement_m"]) + 1e-12:
            fail(f"repair {entry.get('id')} displacement {displacement:.6f} exceeds limit")
        return
    axis = entry.get("axis")
    side = entry.get("side")
    if axis not in AXIS_INDEX or side not in {"min", "max"}:
        fail(f"repair {entry.get('id')} has invalid axis/side")
    expected = float(entry["expected_m"])
    actual = plane_coordinate(world_bounds(obj), axis, side)
    if abs(actual - expected) > TOLERANCE:
        fail(f"repair {entry.get('id')} expected {expected:.6f} m but found {actual:.6f} m")
    if operation == "align_terminal_plane":
        target = bpy.data.objects.get(entry.get("target_object", ""))
        if target is None or target.type != "MESH":
            fail(f"repair {entry.get('id')} target object is missing or not a mesh")
        target_axis = entry.get("target_axis", axis)
        target_side = entry.get("target_side")
        if target_axis not in AXIS_INDEX or target_side not in {"min", "max"}:
            fail(f"repair {entry.get('id')} has invalid target axis/side")
        target_m = plane_coordinate(world_bounds(target), target_axis, target_side)
        entry["target_m"] = target_m
    target_m = float(entry["target_m"])
    displacement = abs(target_m - expected)
    if displacement > float(entry["max_displacement_m"]) + 1e-12:
        fail(f"repair {entry.get('id')} displacement {displacement:.6f} exceeds limit")


def update_rect_metadata(obj, axis, side, expected, target):
    raw = obj.get("footprint_rectangles_world")
    if not isinstance(raw, str):
        return
    try:
        rectangles = json.loads(raw)
    except json.JSONDecodeError:
        return
    coordinate_index = AXIS_INDEX[axis] + (2 if side == "max" else 0)
    changed = 0
    for rect in rectangles:
        if abs(float(rect[coordinate_index]) - expected) <= TOLERANCE:
            rect[coordinate_index] = target
            changed += 1
    if changed:
        obj["footprint_rectangles_world"] = json.dumps(rectangles)


def translate_rect_metadata(obj, axis, delta):
    raw = obj.get("footprint_rectangles_world")
    if not isinstance(raw, str):
        return
    try:
        rectangles = json.loads(raw)
    except json.JSONDecodeError:
        return
    index = AXIS_INDEX[axis]
    for rect in rectangles:
        rect[index] += delta
        rect[index + 2] += delta
    obj["footprint_rectangles_world"] = json.dumps(rectangles)


def move_terminal_plane(entry):
    obj = bpy.data.objects[entry["object"]]
    if obj.data.users > 1:
        obj.data = obj.data.copy()
    axis = entry["axis"]
    axis_index = AXIS_INDEX[axis]
    expected = float(entry["expected_m"])
    target = float(entry["target_m"])
    inverse = obj.matrix_world.inverted()
    changed = 0
    for vertex in obj.data.vertices:
        world = obj.matrix_world @ vertex.co
        if abs(world[axis_index] - expected) <= TOLERANCE:
            world[axis_index] = target
            vertex.co = inverse @ world
            changed += 1
    if changed == 0:
        fail(f"repair {entry.get('id')} found no vertices on terminal plane")
    obj.data.update()
    update_rect_metadata(obj, axis, entry["side"], expected, target)
    repairs = json.loads(obj.get("v3_repairs_json", "[]"))
    repairs.append(entry["id"])
    obj["v3_repairs_json"] = json.dumps(repairs)
    return changed


def translate_object(entry):
    obj = bpy.data.objects[entry["object"]]
    if obj.data.users > 1:
        obj.data = obj.data.copy()
    axis = entry["axis"]
    index = AXIS_INDEX[axis]
    delta = float(entry["delta_m"])
    inverse = obj.matrix_world.inverted()
    for vertex in obj.data.vertices:
        world = obj.matrix_world @ vertex.co
        world[index] += delta
        vertex.co = inverse @ world
    obj.data.update()
    translate_rect_metadata(obj, axis, delta)
    repairs = json.loads(obj.get("v3_repairs_json", "[]"))
    repairs.append(entry["id"])
    obj["v3_repairs_json"] = json.dumps(repairs)
    return len(obj.data.vertices)


def apply_entry(entry):
    obj = bpy.data.objects[entry["object"]]
    before = world_bounds(obj)
    if entry["operation"] in {"move_terminal_plane", "align_terminal_plane", "translate_object"}:
        vertices = (translate_object(entry) if entry["operation"] == "translate_object"
                    else move_terminal_plane(entry))
        after = world_bounds(obj)
        return {
            "id": entry["id"],
            "operation": entry["operation"],
            "object": entry["object"],
            "classification": entry["classification"],
            "reason": entry["reason"],
            "reference_files": entry.get("reference_files", []),
            "bounds_before_m": [round(value, 6) for value in before],
            "bounds_after_m": [round(value, 6) for value in after],
            "vertices_changed": vertices,
            "displacement_m": round(
                abs(float(entry["delta_m"])) if entry["operation"] == "translate_object"
                else abs(float(entry["target_m"]) - float(entry["expected_m"])), 6
            ),
        }
    name = obj.name
    bpy.data.objects.remove(obj, do_unlink=True)
    return {
        "id": entry["id"], "operation": "remove_object", "object": name,
        "classification": entry["classification"], "reason": entry["reason"],
        "reference_files": entry.get("reference_files", []),
        "bounds_before_m": [round(value, 6) for value in before],
        "bounds_after_m": None, "vertices_changed": 0, "displacement_m": 0.0,
    }


def main():
    args = parse_args()
    manifest_path = Path(args.manifest)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("version") != 1:
        fail("manifest version must be 1")
    entries = manifest.get("floors", {}).get(args.floor)
    if entries is None:
        fail(f"manifest has no entry list for {args.floor}")
    if not isinstance(entries, list):
        fail(f"manifest floor {args.floor} is not a list")
    for entry in entries:
        for key in ("id", "operation", "object", "reason", "classification"):
            if key not in entry:
                fail(f"repair entry lacks {key}")
        validate_entry(entry)

    blend = Path(bpy.data.filepath).resolve()
    if not args.no_backup and entries:
        backup = blend.with_name(f"{blend.stem}_pre_v3_cleanup{blend.suffix}")
        if not backup.exists():
            bpy.ops.wm.save_as_mainfile(filepath=str(backup), copy=True)

    applied = [apply_entry(entry) for entry in entries]
    scene_receipts = json.loads(bpy.context.scene.get("villa_v3_repair_receipts_json", "[]"))
    scene_receipts.extend(item["id"] for item in applied)
    bpy.context.scene["villa_v3_repair_receipts_json"] = json.dumps(scene_receipts)
    if entries:
        bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    receipt = {
        "floor": args.floor,
        "blend": str(blend),
        "manifest": str(manifest_path.resolve()),
        "applied": applied,
        "status": "PASS",
    }
    receipt_path = Path(args.receipt)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(f"VILLA_REPAIR floor={args.floor} applied={len(applied)}")


if __name__ == "__main__":
    main()
