# Alishan Shizhuo Gazebo Terrain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and validate a terrain-only Gazebo Harmonic model and world that load the validated 20 m Alishan Shizhuo GeoTIFF DEM directly.

**Architecture:** A static Gazebo model contains paired visual and collision heightmaps that reference a symbolic link to the existing GIS-quality GeoTIFF. A minimal world includes only simulation systems, illumination, and that model. A focused Python standard-library validator checks the SDF contract and confirms the source terrain asset checksum is unchanged.

**Tech Stack:** Gazebo Harmonic / gz-sim8, SDFormat 1.10, GDAL-backed GeoTIFF DEM loading, Python 3 standard library `argparse`, `hashlib`, and `xml.etree.ElementTree`, standard-library `unittest`.

**Spec:** `docs/superpowers/specs/2026-09-10-alishan-shizhuo-gazebo-terrain-design.md`

## Global Constraints

- Load `data/processed/alishan_shizhuo_terrain_20m.tif` directly through a `model://` URI and preserve it byte-for-byte.
- Use the exact heightmap size `500 500 229.830` and position `0 0 -1330.340`.
- Interpret local elevation as `TWVD2001 elevation - 1330.340 m` with no vertical exaggeration.
- Keep V0 terrain-only: no PX4, ROS 2, QGroundControl, roads, buildings, vegetation, Blender, imagery, weather, or navigation work.
- Omit `spherical_coordinates` until a TWVD2001-to-world-elevation datum conversion is established.
- Do not modify `PX4-Autopilot/` and do not commit changes unless explicitly requested.

---

### Task 1: SDF contract validator

**Files:**
- Create: `tests/test_gazebo_terrain.py`
- Create: `scripts/validate_gazebo_terrain.py`

**Interfaces:**
- Produces: `validate_terrain_model(model_sdf: Path, expected_tiff: Path) -> TerrainModelReport`.
- Produces: CLI `python3 scripts/validate_gazebo_terrain.py --model-sdf gazebo/models/alishan_shizhuo_terrain/model.sdf --source-tiff data/processed/alishan_shizhuo_terrain_20m.tif`.
- Consumes: an SDF with one collision and one visual `<heightmap>`, and the canonical GeoTIFF path.

- [x] **Step 1: Write failing validator tests**

```python
report = validator.validate_terrain_model(FIXTURE_MODEL_SDF, SOURCE_TIFF)
self.assertEqual(report.heightmap_size_m, (500.0, 500.0, 229.83))
self.assertEqual(report.heightmap_position_m, (0.0, 0.0, -1330.34))
self.assertEqual(report.local_center_elevation_m, 111.1)
```

Create `FIXTURE_MODEL_SDF` and a terrain symbolic link beneath `TemporaryDirectory()` so the test owns its complete input fixture. Add a second test that substitutes a nonexistent GeoTIFF path in that copied SDF and asserts `TerrainValidationError` includes `does not exist`.

- [x] **Step 2: Run the focused tests and verify the intended red failure**

Run: `python3 -B -m unittest tests/test_gazebo_terrain.py -v`

Expected: FAIL because `scripts/validate_gazebo_terrain.py` does not exist.

- [x] **Step 3: Implement the smallest SDF parser and contract checks**

```python
HEIGHTMAP_SIZE_M = (500.0, 500.0, 229.830)
HEIGHTMAP_POSITION_M = (0.0, 0.0, -1330.340)
SOURCE_MIN_ELEVATION_M = 1330.340
SOURCE_CENTER_ELEVATION_M = 1441.440

def local_z(elevation_m: float) -> float:
    return elevation_m - SOURCE_MIN_ELEVATION_M
```

Use `ElementTree` to require exactly two `<heightmap>` elements, require their `uri`, `size`, `pos`, and `sampling` values to agree, resolve the URI relative to `model.sdf`, verify it resolves to the expected terrain file, and compare SHA-256 digests through the symbolic link and source path. Raise `TerrainValidationError` for each malformed condition.

- [x] **Step 4: Run focused tests and the full existing suite**

Run: `python3 -B -m unittest tests/test_gazebo_terrain.py -v && python3 -B -m unittest discover -s tests -v`

Expected: all new and existing tests PASS without requiring the production Gazebo model.

### Task 2: Direct-DEM model and terrain-only world

**Files:**
- Create: `gazebo/models/alishan_shizhuo_terrain/model.config`
- Create: `gazebo/models/alishan_shizhuo_terrain/model.sdf`
- Create: `gazebo/models/alishan_shizhuo_terrain/terrain/alishan_shizhuo_terrain_20m.tif` (relative symbolic link)
- Create: `gazebo/worlds/alishan_shizhuo.sdf`

**Interfaces:**
- Consumes: the processed one-band EPSG:3826 GeoTIFF.
- Produces: model URI `model://alishan_shizhuo_terrain`.
- Produces: terrain model geometry of 500 m by 500 m and 229.830 m local relief.

- [x] **Step 1: Add the failing SDF asset path expected by Task 1**

Create the model directory and relative terrain symlink, but do not copy the GeoTIFF. The link target must be `../../../../data/processed/alishan_shizhuo_terrain_20m.tif` when evaluated from `gazebo/models/alishan_shizhuo_terrain/terrain/`.

- [x] **Step 2: Create the static model with paired DEM geometry**

```xml
<model name="alishan_shizhuo_terrain">
  <static>true</static>
  <link name="terrain_link">
    <collision name="terrain_collision"><geometry><heightmap>...</heightmap></geometry></collision>
    <visual name="terrain_visual"><geometry><heightmap>...</heightmap></geometry></visual>
  </link>
</model>
```

Each heightmap uses `model://alishan_shizhuo_terrain/terrain/alishan_shizhuo_terrain_20m.tif`, `<size>500 500 229.830</size>`, `<pos>0 0 -1330.340</pos>`, and `<sampling>1</sampling>`. The collision link additionally has `<pose>0 0 -1330.340 0 0 0</pose>` because Gazebo Harmonic DART attaches its collider from that pose. Use a single neutral diffuse-only terrain texture declaration only if Gazebo requires it during the runtime test; do not add image assets.

- [x] **Step 3: Create the terrain-only world**

```xml
<world name="alishan_shizhuo">
  <gravity>0 0 -9.81</gravity>
  <physics name="1ms" type="ignored"><max_step_size>0.001</max_step_size></physics>
  <plugin filename="gz-sim-physics-system" name="gz::sim::systems::Physics"/>
  <plugin filename="gz-sim-user-commands-system" name="gz::sim::systems::UserCommands"/>
  <plugin filename="gz-sim-scene-broadcaster-system" name="gz::sim::systems::SceneBroadcaster"/>
  <include><uri>model://alishan_shizhuo_terrain</uri></include>
</world>
```

Add a directional sun, neutral scene colour, and a MinimalScene GUI overview camera. Do not add `spherical_coordinates`, a vehicle, or a ground plane.

- [x] **Step 4: Run the validator and verify direct-asset preservation**

Run: `python3 -B scripts/validate_gazebo_terrain.py --model-sdf gazebo/models/alishan_shizhuo_terrain/model.sdf --source-tiff data/processed/alishan_shizhuo_terrain_20m.tif`

Expected: reports matching collision and visual entries, the 500 m by 500 m by 229.830 m heightmap, local range 0.000–229.830 m, center 111.100 m, reachable asset, and identical SHA-256 digests.

### Task 3: Documentation and runtime validation

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: model URI and validation CLI from Tasks 1–2.
- Produces: reproducible launch and validation commands plus documented coordinate limits.

- [x] **Step 1: Document the direct GeoTIFF model and local elevation convention**

Add a concise `Gazebo terrain` section with source resolution, physical size, TWVD2001 range, local-Z equation, 20 m sampling limitation, deferred geographic anchor, resource-path environment variable, server-only launch command, GUI launch command, and validation command.

- [x] **Step 2: Validate SDF syntax without launching the GUI**

Run: `gz sdf -k gazebo/models/alishan_shizhuo_terrain/model.sdf`

Expected: SDFormat parses the model without errors. Standalone `gz sdf` cannot resolve a world `model://` URI from `GZ_SIM_RESOURCE_PATH`; Gazebo Sim resolves it at runtime.

- [x] **Step 3: Run a bounded server-only simulation**

Run: `GZ_PARTITION=alishan_shizhuo GZ_SIM_RESOURCE_PATH="$PWD/gazebo/models" timeout 15s gz sim -v 4 -r -s gazebo/worlds/alishan_shizhuo.sdf`

Expected: timeout exit code 124 after a running simulation; output contains no fatal, GDAL, DEM, heightmap, collision, rendering, or resource-path errors. Compare the source GeoTIFF SHA-256 before and after.

- [x] **Step 4: Run bounded headless rendering and optional GUI rendering**

Run: `GZ_PARTITION=alishan_shizhuo GZ_SIM_RESOURCE_PATH="$PWD/gazebo/models" timeout 15s gz sim -v 4 -r --headless-rendering gazebo/worlds/alishan_shizhuo.sdf`

Then use the same command without `--headless-rendering` only when a display server is available. Record warnings verbatim and distinguish server validation from human visual inspection.

- [x] **Step 5: Run final regression checks**

Run: `python3 -B -m unittest discover -s tests -v && python3 -B scripts/validate_gazebo_terrain.py --model-sdf gazebo/models/alishan_shizhuo_terrain/model.sdf --source-tiff data/processed/alishan_shizhuo_terrain_20m.tif && git -C /home/nicklee/Phenix_Project/Drone/PX4-Autopilot status --short`

Expected: all tests and validator checks PASS; PX4 command prints no changes.
