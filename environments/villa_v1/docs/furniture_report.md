# Summit Estate furniture library

Implemented `scripts/furniture.py`, with no external asset dependency and no scene-clearing, camera, lighting, rendering, or world changes. Every asset returns a named Empty. Every component belongs to the supplied collection and is directly parented to that root, with local geometry measured in metres and fronts toward −Y. Stable per-name random seeds provide repeatable book and foliage variation.

Reference images opened and inspected before asset creation:

- `reference/B1/villa_v1_b1_library_2.png`: lit walnut shelving, varied spines and objects, cream sofas, cognac chairs, dark marble tables, bronze lamps, and woven egg chair.
- `reference/3F/villa_v1_3F_master_suite.png`: upholstered channel headboard, layered pale bedding, textile throw, low dark table, and rounded seating.
- `reference/3F/villa_v1_3F_closets.png`: open timber bays, bronze hanging rails, neutral coats, bags, shoes, folded textiles, drawers, boxes, and linear diffusers.

## Interface

```python
import furniture
root = furniture.build_asset(kind, name, collection, materials, **kwargs)
root.location = (x, y, floor_z)
root.rotation_euler.z = yaw_radians
```

| Kind | Supported useful parameters | Included modeled details |
|---|---|---|
| `sofa` | `width=3.6`, `seats=3`, `depth=1.05`, `material='cream'`, `throw=True` | Rounded frame, separate soft seat/back cushions, true welt curves, accent pillows, feet, walnut underframe, draped cloth |
| `armchair` | `width=.95`, `material='leather'` | Curved padded shell with actual thickness, rim welt, cushion, lumbar pillow, timber legs |
| `chair` | `width=.68`, `material='cream'` | Curved bucket shell, cushion, four legs |
| `stool` | `height=.78`, `width=.48`, `material='cream'` | Four legs, bronze foot ring, rounded seat, curved low back |
| `table` | `width=2.4`, `depth=1.0`, `height=.75`, `round=False`, `material` | Beveled wood slab and two pedestals with bronze feet; round version uses stone slab and recessed bronze drum |
| `bed` | `width=2.2`, `depth=2.35` | Upholstered plinth, mattress, channel headboard, two layers of pillows, lumbar accent, draped duvet and fringed throw |
| `cabinet` | `width=3`, `height=2.8`, `depth=.6` | Distinct reveal-separated doors, slim pulls, recessed toe, stone cap |
| `bookshelf` | `width=4`, `height=3.4`, `depth=.38` | Carcass/partitions/shelves, varying book sizes and cover/page/spine materials, gold spine bands, vases, sculptures, real LED diffuser surfaces |
| `closet` | `width=4`, `height=3.2`, `depth=.66` | Open bays, drawers/pulls, individual bronze hangers and jacket silhouettes/lapels, shoes with openings/soles, handled/clasped bags, folded textiles, boxes, LED surfaces |
| `hanging_chair` | none | Curved metal stand/base, suspension, open woven egg shell with meridians and latitude strands, bound rim, cushions and throw |
| `plant` | `height=2`, `pot_material='ceramic'` | Hollow rimmed planter, visible soil, trunk, 20 branches, 260 individually shaped curved leaves with varied directions and midribs |
| `decor` | none | Bronze tray, glass candle cups, wax and emissive flames, ceramic bud vase and leafy sprigs |
| `rug` | `width=4`, `depth=3` | Layered textile field, bound border and fine fringe |
| `lamp` | `height=1.5` | Weighted bronze base/stem, hollow linen shade with rim, separate emissive diffuser |

Round-table `width` means diameter; `depth` is ignored in that mode. Furniture dimensions are nominal: seams, padded edges, backs, throws, foliage and handles add small necessary clearance. For example the default sofa is approximately 3.63 × 1.14 × 1.11 m overall, and the 2.2 m bed has an approximately 2.55 × 2.56 m overall envelope. Rug fringe adds 90 mm to depth. The stool's height is seat height; its back extends above it.

The material dictionary accepts the agreed palette, with resilient fallback lookup for missing entries. Furnishing geometry does not add light objects: scene composition should pair shelving/lamp diffuser materials with appropriate actual light sources. Book clusters combine small book parts into one editable multi-material mesh per cluster; other useful parts remain separate. Upholstery and bedding use shaped, lightly perturbed meshes rather than placeholder boxes; textile fine texture remains the supplied material library's responsibility. Cloth is analytic geometry, without a simulation or frame dependency.

## Validation and visual inspection

`renders/assets_furniture/smoke.py` generates all 14 kinds in an isolated Blender scene and checks direct parenting, material assignment, finite realistic evaluated mesh bounds, no components below the floor, fallback materials, and unknown-kind errors. The studio preview uses approximate materials and CPU Cycles, 1600 × 1000, 24 samples. It is an asset shape preview, not a room fidelity render.

The preview was opened and visually inspected. Corrections made from the inspection: lengthened armchair feet to meet the cushion, increased leaf density, added folded closet textiles, and seated the planter base at floor level.

Outputs:

- `renders/assets_furniture/furniture_preview.png`: inspected all-kind studio render.
- `renders/assets_furniture/furniture_preview.blend`: editable standalone preview.
- `renders/assets_furniture/smoke_report.json`: evaluated dimensions and component counts.
- `renders/assets_furniture/smoke.log`: Blender process and render output.

All kinds total 424 components in the test. Default bookshelf: 101 components. Default closet: 168. Sofa: 30. Bed: 29. The module never joins entire furniture groups or rooms.

**Bounds caveat:** Blender 4.5 curve `bound_box` can overestimate these thin curves by roughly one metre. For asset QA use evaluated `to_mesh()` vertex positions transformed into root space, then `to_mesh_clear()`. `smoke.py` demonstrates this approach.

Reference bytes, root builders and other asset modules were not changed. No commits were created.
