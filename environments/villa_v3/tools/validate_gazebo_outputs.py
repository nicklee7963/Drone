#!/usr/bin/env python3
"""Validate Villa V3 model resources, visual/collision meshes, and world stacking."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

from villa_validation_core import FLOOR_Z, validate_sdf_tree


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    gazebo = root / "gazebo"
    issues = []
    models = {}
    for floor in FLOOR_Z:
        directory = gazebo / f"villa_{floor}"
        sdf = directory / "model.sdf"
        config = directory / "model.config"
        mesh = directory / "meshes" / f"villa_{floor}.obj"
        local_issues = validate_sdf_tree(sdf)
        if not config.is_file():
            local_issues.append({"code": "MISSING_MODEL_CONFIG", "path": str(config), "detail": floor})
        if not mesh.is_file() or mesh.stat().st_size == 0:
            local_issues.append({"code": "MISSING_MESH", "path": str(mesh), "detail": floor})
        else:
            text = mesh.read_text(encoding="utf-8", errors="replace")
            if "\nv " not in "\n" + text or "\nf " not in "\n" + text:
                local_issues.append({"code": "EMPTY_OBJ_GEOMETRY", "path": str(mesh), "detail": floor})
        models[floor] = {"model_sdf": str(sdf), "mesh": str(mesh),
                         "mesh_bytes": mesh.stat().st_size if mesh.exists() else 0,
                         "issues": local_issues}
        issues.extend(local_issues)

    world_path = gazebo / "worlds" / "villa_v3.sdf"
    world_poses = {}
    if not world_path.is_file():
        issues.append({"code": "MISSING_WORLD", "path": str(world_path), "detail": "villa_v3"})
    else:
        try:
            world = ET.parse(world_path).getroot()
            engine = world.findtext(".//plugin[@filename='gz-sim-physics-system']/engine/filename", "")
            if engine != "gz-physics-bullet-featherstone-plugin":
                issues.append({"code": "UNSUPPORTED_COLLISION_ENGINE", "path": str(world_path),
                               "detail": f"expected Bullet Featherstone, got {engine!r}"})
            for include in world.findall(".//include"):
                uri = include.findtext("uri", "")
                if uri.startswith("model://villa_"):
                    floor = uri.removeprefix("model://villa_")
                    pose = [float(value) for value in include.findtext("pose", "").split()]
                    world_poses[floor] = pose
            for floor, elevation in FLOOR_Z.items():
                pose = world_poses.get(floor)
                if not pose or len(pose) != 6 or abs(pose[2] - elevation) > 1e-9:
                    issues.append({"code": "BAD_FLOOR_POSE", "path": str(world_path),
                                   "detail": f"{floor}: expected Z={elevation}, got {pose}"})
        except (ET.ParseError, OSError, ValueError) as exc:
            issues.append({"code": "INVALID_WORLD", "path": str(world_path), "detail": str(exc)})

    report = {"status": "PASS" if not issues else "FAIL", "models": models,
              "world": str(world_path), "world_floor_poses": world_poses,
              "physics_engine": "gz-physics-bullet-featherstone-plugin",
              "visual_collision_policy": "same cleaned shell OBJ used for both",
              "issues": issues}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"VILLA_GAZEBO_VALIDATION {report['status']}")
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
