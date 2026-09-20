"""Validate the saved whole-building Blender assembly."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import bpy


EXPECTED = {"B1": -3.2, "1F": 0.0, "2F": 3.2, "3F": 6.4, "Roof": 9.6}


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    scene = bpy.context.scene
    checks = []

    def check(name, passed, detail=None):
        checks.append({"name": name, "pass": bool(passed), "detail": detail})

    recorded = json.loads(scene.get("floor_elevations_json", "{}"))
    check("All required floor elevations are recorded", recorded == EXPECTED, recorded)
    per_floor = {}
    for floor, elevation in EXPECTED.items():
        collection = bpy.data.collections.get(f"FLOOR_{floor}")
        objects = list(collection.objects) if collection else []
        architectural = [obj for obj in objects if obj.type == "MESH" and obj.get("shell_geometry")]
        errors = [obj.name for obj in architectural
                  if obj.get("assembly_floor") != floor
                  or abs(float(obj.get("assembly_floor_elevation_m", 999)) - elevation) > 1e-9
                  or abs(obj.matrix_world.translation.z
                         - float(obj.get("assembly_source_local_origin_z_m", 0)) - elevation) > 1e-6]
        per_floor[floor] = {"objects": len(architectural), "transform_errors": errors}
        check(f"{floor} collection is populated and translated exactly once", bool(architectural) and not errors,
              per_floor[floor])
    check("Inspection render is configured at 1920x1080",
          scene.render.resolution_x == 1920 and scene.render.resolution_y == 1080,
          [scene.render.resolution_x, scene.render.resolution_y])
    check("Inspection camera exists", bool(scene.camera and scene.camera.type == "CAMERA"),
          scene.camera.name if scene.camera else None)
    failed = sum(not item["pass"] for item in checks)
    report = {"status": "PASS" if not failed else "FAIL", "passed": len(checks) - failed,
              "failed": failed, "floor_elevations_m": EXPECTED, "per_floor": per_floor,
              "checks": checks}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"VILLA_ASSEMBLY_VALIDATION {report['status']}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
