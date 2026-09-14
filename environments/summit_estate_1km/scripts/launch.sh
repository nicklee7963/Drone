#!/usr/bin/env bash
set -euo pipefail
project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
export GZ_SIM_RESOURCE_PATH="${project_root}/gazebo/models${GZ_SIM_RESOURCE_PATH:+:${GZ_SIM_RESOURCE_PATH}}"
export GZ_PARTITION="${SUMMIT_GZ_PARTITION:-summit_estate_v1}"
# A project-specific GUI configuration is embedded in the SDF.
# Override partition with SUMMIT_GZ_PARTITION to run more than one estate server.
exec gz sim -r "${project_root}/gazebo/worlds/summit_estate.sdf" "$@"
