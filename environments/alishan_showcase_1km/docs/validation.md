# V1 validation report

Validated on **2026-09-11** with Gazebo Sim **8.15.0**, OGRE2, and the installed
default DART physics engine. This report covers the final generated showcase.

## Results

| Check | Result |
|---|---|
| Python acceptance tests | 6/6 passed |
| Native Gazebo mesh importer | 69/69 meshes passed |
| Native terrain indices | 375,000 indices, representing 125,000 triangles |
| Terrain extent | Exactly 1,000 × 1,000 m |
| Elevation range / relief | 45.581–375.159 m / 329.578 m |
| Visual geometry | 1,007,178 triangles; finite coordinates, valid indices, no degenerate triangles |
| SDF validation | Valid, including resolved local model references |
| Server smoke test | Initialized and completed 125 iterations; exit code 0 |
| GUI rendering | Terrain, forest, roads, cabins, tea rows and launch pads visible |
| Resource errors | None found in final server or GUI logs |
| Maximum road centreline grade | 14.89% |
| Asphalt surface above terrain | 0.117–0.142 m in triangle sampling |
| Gravel surface above terrain | 0.042–0.068 m in triangle sampling |
| Launch areas | Two flat 28 m pads, connected and clear of vegetation |
| Terrain physical contact | Test sphere settled within 0.012 m of expected contact height |
| Launch-pad physical contact | Test sphere settled within 0.012 m of expected contact height |

Terrain height data and exported vertices agree within 0.000005 m. Tests sample
triangle interiors as well as vertices. Independent review confirmed cabin
roofs clear the road shoulders by at least 15.29 m and tree canopies clear the
launch-pad edges by at least 21.39 m.

Temporary collision spheres were removed after testing and are not part of the
world. The live check reads `/world/alishan_showcase/pose/info`; `scene/info`
contains construction poses rather than current physics poses.

Machine-readable evidence:

- [Geometry, native importer and server checks](../data/processed/validation.json)
- [Physical contact checks](../data/processed/collision_validation.json)
- [Protected-directory comparison](../data/processed/protected_paths_check.json)
- [Complete file inventory](../data/processed/files_created.txt)

Local logs are in ignored `data/processed/validation_runtime/` and `.runtime/`.

## Visual evidence

These images were captured from the actual Gazebo GUI. The site plan is a
separate procedural map, not a rendering claim.

- [Overview](../data/processed/previews/overview.png)
- [Aerial layout](../data/processed/previews/aerial.png)
- [Basecamp, cabins and launch pad](../data/processed/previews/basecamp.png)
- [Tea slope and road](../data/processed/previews/tea.png)
- [Cloud Ridge](../data/processed/previews/ridge.png)
- [Site plan](../data/processed/site_plan.png)

## Reproduce

```bash
python3 scripts/validate_environment.py --native --server
./scripts/launch.sh
# In another terminal after the GUI is ready:
python3 scripts/view.py basecamp --capture
/usr/bin/python3 tests/check_live_collision.py
python3 scripts/view.py overview
```

The optional live collision check needs Gazebo's Python transport/protobuf
bindings, available here through `/usr/bin/python3`. It unpauses this showcase,
creates two temporary spheres, waits for contact, and removes them. It does not
change the saved world. It uses the same optional `ALISHAN_SHOWCASE_PARTITION`
setting as the launcher.

## DAE import correction

The initial exporter used one shared offset for position, normal and UV
indices. Gazebo's COLLADA reader counted all three inputs when advancing its
index stream, importing only **125,000** terrain indices instead of **375,000**.
XML parsing alone did not detect this renderer compatibility problem.

The exporter now uses distinct offsets **0 / 1 / 2** and explicit interleaved
`position normal uv` tuples. The initial conversion preserved all source
position, normal and UV arrays; no assets were deleted or redesigned. The native
regression test verifies triangle counts and the full kilometre extent. Final
assets were also regenerated through the corrected exporter and revalidated.

## Scope and limitations

This is an artistic mountain showcase, with low-poly vegetation and stylized
terrain cuts. It is not GIS accurate. Forest, tea plants, benches and road posts
have no collision; cabins use simplified boxes. Roads use the underlying terrain
for physical contact. There are no vehicles, sensors, PX4, ROS or mission systems.

All six groups are static and the forest is batched into 64 tiles. There is no
distance-based LOD or hardware instancing. Model resources occupy roughly 97 MB
with 1.01 million visual triangles. FPS and memory use were not formally
benchmarked across hardware.

## Change scope and Git

All project files were created under `environments/alishan_showcase_1km`.
The parent Drone repository reports this new project as **untracked**. No commit,
staging operation, branch change, or shell configuration edit was made.

`alishan_shizhuo` has the same 68-file metadata fingerprint and the same existing
Git changes as the starting snapshot. None of its files were edited.

No showcase command modified PX4-Autopilot. Its tracked source tree remains
clean. A whole-directory comparison observed changes to unrelated PX4 runtime
`.ulg` logs and parameter BSON files under `build/px4_sitl_default/rootfs/fs/`
during the session, so an unchanged fingerprint for the entire runtime directory
is not claimed.
