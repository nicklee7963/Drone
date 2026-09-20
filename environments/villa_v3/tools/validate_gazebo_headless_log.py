#!/usr/bin/env python3
"""Turn a bounded Gazebo server run into machine-readable validation evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--exit-code", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    text = re.sub(r"\x1b\[[0-9;]*m", "", args.log.read_text(encoding="utf-8", errors="replace"))
    checks = {
        "bounded_exit": args.exit_code in {0, 124},
        "server_started": "Gazebo Sim Server" in text,
        "world_loaded": "Loading SDF world file" in text and "villa_v3.sdf" in text,
        "bullet_mesh_collision_backend_loaded": "gz::physics::bullet_featherstone::Plugin" in text,
        "world_initialized": "World [villa_v3_world] initialized" in text,
        "no_missing_resources": "Unable to find file" not in text and "could not resolve" not in text.lower(),
        "collision_shapes_created": "couldn't be created" not in text
                                    and "Mesh construction from an SDF has not been implemented" not in text,
        "no_runtime_errors": "[Err]" not in text,
    }
    report = {"status": "PASS" if all(checks.values()) else "FAIL",
              "command_mode": "headless server, run until bounded timeout",
              "exit_code": args.exit_code, "checks": checks,
              "log": str(args.log.resolve())}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"VILLA_GAZEBO_HEADLESS {report['status']}")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
