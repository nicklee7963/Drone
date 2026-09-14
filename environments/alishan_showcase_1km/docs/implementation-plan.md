# Alishan Showcase 1km — V1 implementation plan

The user authorizes a new, self-contained procedural scenic environment in this
directory. This is an artistic Alishan-inspired park, not a GIS reconstruction.
The existing Shizhuo and PX4 trees must remain unchanged.

## Design

Use a deterministic NumPy heightfield covering [-500, 500] metres in X and Y.
Several overlapping ridges, a valley, and small-scale relief give depth. Grade a
single winding road into the hills, flatten three connected visitor clearings,
and place houses on local terraces. Export the same terrain triangles for visual
and collision use. Produce all textures and meshes locally; no Fuel dependency.

Batch repeated conifer, broadleaf, and bamboo geometry into spatial tiles. Clear
trees away from roads, pads, buildings and planted tea slopes. Ground vegetation
against the exported terrain surface. Keep terrain and buildings collidable;
vegetation is decorative in V1. Use Gazebo Harmonic, warm daylight, and an aerial
initial camera. No vehicle, sensor, ROS, PX4, or mission components.

## Execution

- [x] Write requirement-level tests for world resources, 1km extent, relief,
  clear launch areas, grounded assets, road grade, and mesh validity.
- [x] Implement `scripts/geometry.py`, `scripts/landscape.py`, and
  `scripts/generate_environment.py` with `configs/showcase.json`.
- [x] Generate `gazebo/models/`, `gazebo/worlds/`, and reproducibility metadata
  in `data/processed/`; export a map preview.
- [x] Add `scripts/launch.sh` and `scripts/validate_environment.py`. Validate
  SDF, resource paths, terrain/road/placement geometry, and Gazebo server startup.
- [x] Launch the actual GUI, inspect overview/detail views, save visual evidence,
  and correct any rendering defects.
- [x] Document commands, scope, collisions, performance, limitations, measured
  results, and protected-directory comparison in README and validation notes.

All authored and generated outputs remain in this project. Runtime logs are
ignored. No shell configuration changes, commits, or integration changes.
