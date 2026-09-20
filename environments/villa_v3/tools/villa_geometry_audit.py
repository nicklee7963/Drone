"""Read-only, evidence-producing geometry audit for one Villa V3 floor.

Run with Blender:
  blender -b floor.blend --python tools/villa_geometry_audit.py -- \
      --floor 1F --output audit/1F_audit.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import bmesh
import bpy
from mathutils import Vector


VALID_FLOORS = ("B1", "1F", "2F", "3F", "Roof")
ARCH_WORDS = (
    "wall", "glass", "column", "slab", "floor", "terrace", "porch",
    "stair", "parapet", "guard", "rail", "landing", "tread",
)
STRUCTURAL_ROLES = {"wall", "glass", "column", "slab", "floor", "parapet"}
ENDPOINT_ROLES = {"wall", "glass", "column", "parapet"}


def parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--floor", required=True, choices=VALID_FLOORS)
    parser.add_argument("--blend", default="")
    parser.add_argument("--output", required=True)
    parser.add_argument("--diagnostic-dir", default="")
    return parser.parse_args(argv)


def json_value(value):
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if hasattr(value, "to_list"):
        return value.to_list()
    try:
        return list(value)
    except TypeError:
        return str(value)


def custom_properties(owner) -> dict:
    return {key: json_value(owner[key]) for key in owner.keys() if key != "_RNA_UI"}


def infer_role(obj) -> str:
    props = custom_properties(obj)
    for key in ("semantic_type", "role", "object_type", "category", "kind", "type"):
        value = props.get(key)
        if isinstance(value, str):
            lower = value.lower()
            for word in STRUCTURAL_ROLES | {"stair", "landing", "tread", "guardrail"}:
                if word in lower:
                    return word
    lower_name = obj.name.lower()
    for word in ARCH_WORDS:
        if word in lower_name:
            if word in ("guard", "rail"):
                return "guardrail"
            return word
    return "other"


def is_architectural(obj) -> bool:
    if obj.type != "MESH" or obj.hide_render:
        return False
    role = infer_role(obj)
    if role != "other":
        return True
    collections = " ".join(c.name.lower() for c in obj.users_collection)
    return any(word in collections for word in ("shell", "wall", "glass", "floor", "structure", "roof"))


def evaluated_geometry(obj, depsgraph):
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh(preserve_all_data_layers=False, depsgraph=depsgraph)
    matrix = evaluated.matrix_world.copy()
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.transform(matrix)
    verts = [v.co.copy() for v in bm.verts]
    xs = [v.x for v in verts]
    ys = [v.y for v in verts]
    zs = [v.z for v in verts]
    bounds = [min(xs), min(ys), min(zs), max(xs), max(ys), max(zs)] if verts else [0.0] * 6
    non_manifold = sum(1 for edge in bm.edges if len(edge.link_faces) != 2)
    degenerate = sum(1 for face in bm.faces if face.calc_area() <= 1e-10)
    signed_volume = None
    if non_manifold == 0 and bm.faces:
        try:
            signed_volume = bm.calc_volume(signed=True)
        except ValueError:
            signed_volume = None
    unseen = set(v.index for v in bm.verts)
    adjacency = {v.index: {e.other_vert(v).index for e in v.link_edges} for v in bm.verts}
    components = 0
    while unseen:
        components += 1
        stack = [unseen.pop()]
        while stack:
            for neighbour in adjacency[stack.pop()]:
                if neighbour in unseen:
                    unseen.remove(neighbour)
                    stack.append(neighbour)
    signature_data = sorted((round(v.x, 5), round(v.y, 5), round(v.z, 5)) for v in verts)
    signature = hashlib.sha256(repr(signature_data).encode("utf-8")).hexdigest()
    triangles = sum(max(0, len(face.verts) - 2) for face in bm.faces)
    bm.free()
    evaluated.to_mesh_clear()
    return {
        "bounds_m": [round(value, 6) for value in bounds],
        "vertices": len(verts),
        "triangles": triangles,
        "components": components,
        "non_manifold_edges": non_manifold,
        "degenerate_faces": degenerate,
        "signed_volume_m3": None if signed_volume is None else round(signed_volume, 8),
        "signature": signature,
    }


def aabb_overlap(a, b):
    depths = [min(a[i + 3], b[i + 3]) - max(a[i], b[i]) for i in range(3)]
    volume = math.prod(max(0.0, value) for value in depths)
    return depths, volume


def _rectangles(record, key):
    raw = record["custom_properties"].get(key, "[]")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return []
    return raw if isinstance(raw, list) else []


def actual_plan_overlap_area(first, second):
    """Exact 2D overlap using the constructive footprints stored in each scene."""
    ar = _rectangles(first, "footprint_rectangles_world")
    ac = _rectangles(first, "subtracted_rectangles_world")
    br = _rectangles(second, "footprint_rectangles_world")
    bc = _rectangles(second, "subtracted_rectangles_world")
    if not ar or not br:
        a, b = first["bounds_m"], second["bounds_m"]
        return max(0.0, min(a[3], b[3]) - max(a[0], b[0])) * max(
            0.0, min(a[4], b[4]) - max(a[1], b[1])
        )
    xs = sorted({value for rect in ar + ac + br + bc for value in (rect[0], rect[2])})
    ys = sorted({value for rect in ar + ac + br + bc for value in (rect[1], rect[3])})

    def contains(rects, x, y):
        return any(rect[0] < x < rect[2] and rect[1] < y < rect[3] for rect in rects)

    area = 0.0
    for ix in range(len(xs) - 1):
        for iy in range(len(ys) - 1):
            x = (xs[ix] + xs[ix + 1]) / 2
            y = (ys[iy] + ys[iy + 1]) / 2
            in_a = contains(ar, x, y) and not contains(ac, x, y)
            in_b = contains(br, x, y) and not contains(bc, x, y)
            if in_a and in_b:
                area += (xs[ix + 1] - xs[ix]) * (ys[iy + 1] - ys[iy])
    return area


def rect_distance(a, b):
    dx = max(a[0] - b[3], b[0] - a[3], 0.0)
    dy = max(a[1] - b[4], b[1] - a[4], 0.0)
    return math.hypot(dx, dy), dx, dy


def overlapping_projection(a, b):
    x_overlap = min(a[3], b[3]) - max(a[0], b[0])
    y_overlap = min(a[4], b[4]) - max(a[1], b[1])
    return x_overlap, y_overlap


def candidate(identifier, classification, objects, evidence, rationale):
    return {
        "id": identifier,
        "classification": classification,
        "objects": objects,
        "evidence": evidence,
        "decision": "REVIEW_REQUIRED",
        "reference_files": [],
        "rationale": rationale,
    }


def opening_classification(text: str) -> str:
    lower = text.lower()
    if "stair" in lower:
        return "INTENTIONAL_STAIR_OPENING"
    if "terrace" in lower or "porch" in lower:
        return "INTENTIONAL_TERRACE_OPENING"
    if "glass" in lower or "glaz" in lower:
        return "INTENTIONAL_GLASS_TRANSITION"
    if "circulation" in lower or "connection" in lower or "open_to" in lower or "atrium" in lower:
        return "INTENTIONAL_CIRCULATION"
    return "INTENTIONAL_DOOR"


def extract_intentional_openings() -> list[dict]:
    records = []
    seen = set()
    for obj in bpy.data.objects:
        lower = obj.name.lower()
        if any(token in lower for token in ("opening", "void", "connection")):
            classification = opening_classification(obj.name)
            key = (obj.name, classification)
            if key not in seen:
                seen.add(key)
                records.append({
                    "name": obj.name,
                    "classification": classification,
                    "source": "scene_object",
                    "preserved": True,
                })
    for key in bpy.context.scene.keys():
        if "opening" not in key.lower() and "door" not in key.lower():
            continue
        raw = bpy.context.scene[key]
        text = raw if isinstance(raw, str) else str(raw)
        try:
            parsed = json.loads(text)
        except (TypeError, json.JSONDecodeError):
            parsed = text
        entries = parsed if isinstance(parsed, list) else [parsed]
        for index, entry in enumerate(entries):
            label = entry.get("name", f"{key}_{index}") if isinstance(entry, dict) else f"{key}_{index}"
            blob = json.dumps(entry, sort_keys=True) if isinstance(entry, (dict, list)) else str(entry)
            classification = opening_classification(blob)
            record_key = (label, classification)
            if record_key not in seen:
                seen.add(record_key)
                records.append({
                    "name": label,
                    "classification": classification,
                    "source": f"scene_property:{key}",
                    "preserved": True,
                })
    return sorted(records, key=lambda item: (item["classification"], item["name"]))


def audit(args: argparse.Namespace) -> dict:
    depsgraph = bpy.context.evaluated_depsgraph_get()
    object_records = []
    by_name = {}
    for obj in sorted((item for item in bpy.data.objects if is_architectural(item)), key=lambda item: item.name):
        geometry = evaluated_geometry(obj, depsgraph)
        record = {
            "name": obj.name,
            "role": infer_role(obj),
            **geometry,
            "custom_properties": custom_properties(obj),
        }
        object_records.append(record)
        by_name[obj.name] = record

    candidates = []
    signatures = {}
    slab_records = [record for record in object_records
                    if record["role"] in {"slab", "floor", "terrace"}]
    for record in object_records:
        signatures.setdefault(record["signature"], []).append(record["name"])
        declared_footprints = _rectangles(record, "footprint_rectangles_world")
        if (record["components"] > 1 and not declared_footprints
                and record["role"] in {"wall", "glass", "column", "parapet"}):
            candidates.append(candidate(
                f"components:{record['name']}", "FLOATING_GEOMETRY", [record["name"]],
                {"connected_components": record["components"]},
                "A wall-like object contains disconnected mesh islands and needs reference review.",
            ))
        if record["non_manifold_edges"] or record["degenerate_faces"]:
            candidates.append(candidate(
                f"topology:{record['name']}", "UNKNOWN", [record["name"]],
                {"non_manifold_edges": record["non_manifold_edges"],
                 "degenerate_faces": record["degenerate_faces"]},
                "Mesh topology is not a closed, non-degenerate architectural solid.",
            ))
        bottom = record["bounds_m"][2]
        supported_by_slab = any(
            abs(slab["bounds_m"][5] - bottom) <= 0.021
            and actual_plan_overlap_area(record, slab) > 1e-8
            for slab in slab_records
        )
        if (bottom > 0.021 and not supported_by_slab
                and record["role"] in {"wall", "glass", "column", "parapet"}):
            candidates.append(candidate(
                f"support:{record['name']}", "FLOATING_GEOMETRY", [record["name"]],
                {"bottom_z_m": bottom},
                "A vertical architectural object starts more than 0.02 m above the local floor datum.",
            ))
    for signature, names in signatures.items():
        if len(names) > 1:
            candidates.append(candidate(
                f"duplicate:{signature[:12]}", "OVERLAPPING_GEOMETRY", names,
                {"identical_world_vertex_signature": signature},
                "Objects have identical evaluated world-space vertex sets.",
            ))

    pair_records = [r for r in object_records if r["role"] in ENDPOINT_ROLES]
    for index, first in enumerate(pair_records):
        a = first["bounds_m"]
        for second in pair_records[index + 1:]:
            b = second["bounds_m"]
            depths, volume = aabb_overlap(a, b)
            exact_area = actual_plan_overlap_area(first, second) if volume > 1e-5 else 0.0
            if exact_area > 1e-8 and depths[2] > 1e-6:
                candidates.append(candidate(
                    f"overlap:{first['name']}:{second['name']}", "OVERLAPPING_GEOMETRY",
                    [first["name"], second["name"]],
                    {"aabb_overlap_depths_m": [round(v, 6) for v in depths],
                     "aabb_overlap_volume_m3": round(volume, 8),
                     "actual_plan_overlap_area_m2": round(exact_area, 8)},
                    "Stored constructive footprints confirm positive plan-area overlap.",
                ))
                continue
            distance, dx, dy = rect_distance(a, b)
            x_projection, y_projection = overlapping_projection(a, b)
            projections_touch = x_projection >= -1e-5 or y_projection >= -1e-5
            if 1e-5 < distance <= 0.150001 and projections_touch:
                roles = {first["role"], second["role"]}
                classification = "WALL_GLASS_CRACK" if "glass" in roles else "WALL_WALL_CRACK"
                candidates.append(candidate(
                    f"endpoint:{first['name']}:{second['name']}", classification,
                    [first["name"], second["name"]],
                    {"plan_gap_m": round(distance, 6), "dx_m": round(dx, 6), "dy_m": round(dy, 6)},
                    "Objects stop within the endpoint-crack tolerance and have overlapping plan projection.",
                ))
            if 0.10 <= distance < 0.40 and (x_projection > 0.50 or y_projection > 0.50):
                candidates.append(candidate(
                    f"sliver:{first['name']}:{second['name']}", "UNWALKABLE_SLIVER",
                    [first["name"], second["name"]],
                    {"clear_width_candidate_m": round(distance, 6),
                     "x_projection_m": round(x_projection, 6), "y_projection_m": round(y_projection, 6)},
                    "Parallel/adjacent structural bounds form a 0.10-0.40 m free-space candidate.",
                ))

    role_counts = {}
    for record in object_records:
        role_counts[record["role"]] = role_counts.get(record["role"], 0) + 1
    all_bounds = [record["bounds_m"] for record in object_records]
    scene_bounds = None
    if all_bounds:
        scene_bounds = [
            min(b[0] for b in all_bounds), min(b[1] for b in all_bounds), min(b[2] for b in all_bounds),
            max(b[3] for b in all_bounds), max(b[4] for b in all_bounds), max(b[5] for b in all_bounds),
        ]
    return {
        "floor": args.floor,
        "blend": str(Path(bpy.data.filepath).resolve()),
        "objects": object_records,
        "candidates": sorted(candidates, key=lambda item: item["id"]),
        "intentional_openings": extract_intentional_openings(),
        "metrics": {
            "architectural_meshes": len(object_records),
            "role_counts": role_counts,
            "scene_bounds_m": scene_bounds,
            "candidate_counts": {
                key: sum(1 for item in candidates if item["classification"] == key)
                for key in sorted({item["classification"] for item in candidates})
            },
        },
        "warnings": [
            "Broad-phase overlap and sliver candidates require comparison with the floor-plan references.",
            "No candidate is automatically repaired by this audit.",
        ],
        "status": "AUDIT_COMPLETE",
    }


def main() -> None:
    args = parse_args()
    if args.blend and Path(args.blend).resolve() != Path(bpy.data.filepath).resolve():
        raise SystemExit(f"loaded blend differs from --blend: {bpy.data.filepath}")
    result = audit(args)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    print(f"VILLA_AUDIT floor={args.floor} objects={len(result['objects'])} candidates={len(result['candidates'])}")


if __name__ == "__main__":
    main()
