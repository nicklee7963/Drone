#!/usr/bin/env bash
set -euo pipefail
SHOWCASE_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
export GZ_SIM_RESOURCE_PATH="$SHOWCASE_ROOT/gazebo/models${GZ_SIM_RESOURCE_PATH:+:$GZ_SIM_RESOURCE_PATH}"
export GZ_PARTITION="${ALISHAN_SHOWCASE_PARTITION:-alishan_showcase_1km}"
export GZ_LOG_PATH="$SHOWCASE_ROOT/.runtime/log"
mkdir -p "$GZ_LOG_PATH"
if ! command -v gz >/dev/null 2>&1; then
  echo 'Gazebo Harmonic (gz sim 8) is required.' >&2
  exit 1
fi
if [[ ! -f "$SHOWCASE_ROOT/gazebo/models/showcase_terrain/meshes/terrain.dae" ]]; then
  echo 'Generate the environment first: python3 scripts/generate_environment.py' >&2
  exit 1
fi
exec gz sim -r "$SHOWCASE_ROOT/gazebo/worlds/alishan_showcase.sdf" "$@"
