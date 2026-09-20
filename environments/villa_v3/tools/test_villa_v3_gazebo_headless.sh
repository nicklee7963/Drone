#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
LOG="$ROOT/gazebo/gazebo_headless.log"
REPORT="$ROOT/gazebo/headless_validation.json"

export SDF_PATH="$ROOT/gazebo"
export GZ_SIM_RESOURCE_PATH="$ROOT/gazebo"
export GZ_PARTITION="villa_v3_validation_$$"

set +e
timeout 8s gz sim -s -r -v 4 "$ROOT/gazebo/worlds/villa_v3.sdf" > "$LOG" 2>&1
code=$?
set -e
python3 "$SCRIPT_DIR/validate_gazebo_headless_log.py" \
  --log "$LOG" --exit-code "$code" --output "$REPORT"
