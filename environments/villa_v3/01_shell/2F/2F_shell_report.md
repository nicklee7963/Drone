# Second-floor shell implementation report

Created `/home/nicklee/Phenix_Project/Drone/environments/villa_v2/01_shell/2F/2F_shell.blend` with Blender 4.5.13 LTS. This is an independent second-floor shell whose finished floor is local `Z=0`; it contains no appended 1F scene and no 3F room/slab model.

## Deliverables

- [2F Blender shell](2F_shell.blend)
- [Reproducible generator](build_2F_shell.py)
- [Validation script](validate_2F_shell.py)
- [Machine-readable validation](2F_shell_validation.json)
- [Validation log](validation_2F_shell.log)
- [Top orthographic render](2F_shell_top.png) — 2400 × 1700
- [Front perspective render](2F_shell_perspective_front.png) — 1800 × 1300
- [Elevated corner render](2F_shell_perspective_corner.png) — 1800 × 1300
- [Open-to-below validation render](2F_open_to_below_validation.png) — 1800 × 1300
- [Family Terrace validation render](2F_family_terrace_validation.png) — 1800 × 1300
- [Source/model overlay](2F_shell_source_overlay.svg)
- [Source/model overlay PNG](2F_shell_source_overlay.png)
- [1F/2F alignment view](2F_vs_1F_alignment.png)
- [Implementation plan](IMPLEMENTATION_PLAN.md)

## Measured scale and geometry

The shell reuses the validated 1F transform exactly: source `(585,513)` maps to world `(0,0)`, X is east, Y is north, `SX=0.037316562 m/pixel`, and `SY=0.035185185 m/pixel`. The explicit 35.6 m × 22.8 m anchors therefore occupy the same world axes as 1F. The revised 2F sheet's own drawn dimension-tick spans are raster-distorted under that transform (36.010 m × 21.322 m), so they were not used to shift or rescale the second floor independently.

All architectural mesh bounds are minimum **(-18.919497, -12.948148, -0.400000) m**, maximum **(18.695597, 11.707407, 3.200000) m**, dimensions **37.615 × 24.656 × 3.600 m**. The X/Y envelope includes the source-drawn façade and Family Terrace projections; the printed dimensions are architectural anchors rather than a forced outer bounding box.

The Family Terrace correction leaves all non-terrace architectural XY bounds unchanged within **0.000000 m**. The north envelope changes only because the former oversized terrace projection was replaced with the measured 27 m² platform and its low guardrail.

## Construction

- Standard wall height: **3.200 m**.
- Main, bridge, and terrace slab thickness: **0.200 m**, top at local `Z=0`.
- Exterior walls: **0.280 m**.
- Interior partitions: **0.180 m**.
- Stair/special walls: **0.220 m**.
- Floor-to-ceiling glazing: **0.020 m**, separate objects.
- Structural columns: **10** solid-black façade/junction blocks traced as separate objects. Light void-corner marks were not promoted to full-height columns.
- Door openings are full-height shell gaps because no elevation or door-head dimensions were supplied.

## Guardrail correction

The shell contains nine frameless-glass guard sections and nine thin top rails: six retained around OPEN TO BELOW/stairs and three added at the Family Terrace. Glass is **0.020 m thick** and **1.050 m high**; the top rail brings the exact finished guard height to **1.100 m**. Every part is closed mesh geometry with unit scale and is tagged for visual and collision export.

- `2F_Railing_OpenToBelow_North`
- `2F_Railing_OpenToBelow_South`
- `2F_Railing_OpenToBelow_East`
- `2F_Railing_OpenToBelow_West`
- `2F_Railing_Stair_001_West`
- `2F_Railing_Stair_002_East_North`
- `2F_Railing_FamilyTerrace_North`
- `2F_Railing_FamilyTerrace_West`
- `2F_Railing_FamilyTerrace_East`
- `2F_Railing_OpenToBelow_North_TopRail`
- `2F_Railing_OpenToBelow_South_TopRail`
- `2F_Railing_OpenToBelow_East_TopRail`
- `2F_Railing_OpenToBelow_West_TopRail`
- `2F_Railing_Stair_001_West_TopRail`
- `2F_Railing_Stair_002_East_North_TopRail`
- `2F_Railing_FamilyTerrace_North_TopRail`
- `2F_Railing_FamilyTerrace_West_TopRail`
- `2F_Railing_FamilyTerrace_East_TopRail`

The four central panels follow every exposed OPEN TO BELOW edge and sit entirely on the floor side of the original opening boundary, preserving the void dimensions. Coverage ratios are north/south **99.2%** and east/west **98.9%** after 0.040 m end clearances. Remaining bridge clear widths are **2.144 m west**, **2.182 m east**, and **1.528 m south**.

The stair guard follows the west side of the full 1F→2F aperture and the east side of the active flight. The east panel stops before the south terminal landing, leaving the measured +X landing exit unobstructed. No rail crosses the north stair approach or south landing.

The source-drawn OPEN TO BELOW rectangle is `(443,408)..(714,606)`, world X `-5.298952..4.813836 m`, Y `-3.272222..3.694444 m`. A 5×5 ray grid found no floor face there. It overlaps **84.3%** of its area with the provisional 1F Great Room helper and extends **1.091 m south** of that helper. The 2F source controls the actual opening; clipping it to the provisional 1F helper would add an unsupported collision ledge.

Measured OPEN TO BELOW clear dimensions remain **10.113 × 6.967 m**. The Bridge / Upper Gallery traced envelope is **14.479 × 8.515 m**; its west/east/south walkable strips retain the clear widths listed above.

The Bridge / Upper Gallery is `2F_Floor_Bridge`, split from the main slab without coplanar duplication. Its west, east, and south strips border the opening and remain open toward the Family Lounge as drawn. The new low guardrails follow only the drop edges; no full-height wall or ceiling was added.

## Stair and XY alignment

The 1F→2F aperture matches the measured 1F `1F_Opening_StairB` at X `4.589937..6.940881 m`, Y `-10.837037..-4.890741 m`. Maximum XY error is **0.000000 m**. The already-modeled 1F flight is not duplicated in this independent 2F export; `2F_Opening_DownTo1F` and `2F_Connection_1F` define the interface.

The stair aperture remains **2.351 × 5.946 m**. Stair center, width, and depth errors against the live 1F Blender geometry are **0.000000 m**, **0.000000 m**, and **0.000000 m**.

Shared main-envelope X anchors differ by at most **0.112 m** because the revised black strokes move two to three source pixels. Origin/centerline error is **0.000000 m**. The revised 2F north façade is 0.457 m north of the 1F main façade, the south guest wings are set back 1.337 m, and the central Art Gallery glazing extends 0.317 m south of the 1F Entry Porch outline; these are source-drawn façade offsets, not model recentering.

The exact non-terrace XY regression error is **0.000000 m**. The origin and stair aperture errors remain **0.000000 m** and **0.000000 m**. This compares fixed architectural geometry directly and does not mistake the intentionally corrected terrace projection for a global floor offset.

## Family Terrace correction

`2F_Terrace_Family` is centered on the Family Lounge glazing and measures **10.000 × 2.700 m**. Its width/depth ratio is **3.704**, and its actual generated-mesh top area is **27.000 m²**. The slab is **0.200 m** thick with its top at local `Z=0`.

The terrace meets `2F_Glass_005_FamilyLounge_North` at world Y **9.007407 m**. Measured gap to the glazing centerline is **0.000000 m**; measured overlap with the indoor/bridge floor is **0.00000000 m²**. The terrace remains an exterior platform and does not overlap OPEN TO BELOW.

The revised 2.700 m furnishing depth and 3.703:1 proportion give the terrace enough depth for a future outdoor seating group and circulation while retaining the 27 m² schedule area. In shell form it now reads as a substantial outdoor extension of the Family Lounge rather than a narrow edge balcony, matching the approved luxury-villa design intent.

Separate 1.10 m guards protect the exposed north edge and the short west/east portions above the existing façade columns: `2F_Railing_FamilyTerrace_North`, `2F_Railing_FamilyTerrace_West`, and `2F_Railing_FamilyTerrace_East`, each with its own `_TopRail`. No full-height outer enclosure was added.

`2F_Stair_UpTo3F` occupies source `(607,676)..(684,817)`, width **2.873 m**, rises north (+Y), has **18 risers × 0.177778 m**, **17 treads × 0.260 m**, run **4.420 m**, and a **0.541 m** terminal landing at provisional `Z=+3.2 m`.

## Validation and manual review

**57 checks passed and 0 failed**. The final scene contains **78 architectural mesh objects** and approximately **2572 triangles**. All scales are unit, all shell meshes are closed positive-volume solids, and no duplicate mesh signatures or non-column wall thicknesses over 0.30 m were found.

Manual review should focus on these source ambiguities:

- The 2F “Down to 1F” arrow points south, while the validated 1F stair rises south to its upper landing. Exact aperture geometry is aligned, but the arrow-direction conflict needs an architectural stair-section decision before multi-floor export.
- Plan note 8 calls the 2F→3F stair “curved,” while the drawn plan shows a straight rectangular flight. The model follows the drawn geometry, as required when annotations and geometry conflict.
- The 2F void extends 1.091 m south of the provisional 1F Great Room helper. The source-drawn 2F void is retained to keep the collision opening conservative.
- Printed sub-dimensions and raster spans are not mutually proportional. The existing 1F transform controls stacking.
- The approved 10.0 × 2.7 m luxury proportion takes precedence over the drawing's broader 16 m structural bay while remaining centered on the source glazing and preserving the 27 m² room-schedule area.
- Light double lines and small corner blocks around OPEN TO BELOW establish the balustrade location but not a detailed post system. The correction uses frameless glass with a thin top rail and retains the source edge position.
- The source shows full-height glass but no elevation details. Glass height follows the 3.2 m wall assumption.
- Door swings establish opening positions; door leaves and heads are not modeled.

## Completion checklist

- [x] 2F_shell.blend exists and opens successfully.
- [x] Scene uses meters, unit scale 1, and local floor Z=0.
- [x] The exact 1F XY transform is reused.
- [x] The exact 1F Stair B opening is removed from the 2F slab.
- [x] The central OPEN TO BELOW contains no floor collision face.
- [x] The Bridge / Upper Gallery is a separate floor object.
- [x] Family Terrace is a separate slab.
- [x] Exterior, interior, and stair walls use the 1F thickness style.
- [x] Family Terrace is connected to lounge glazing and has 27.000 m2 usable top area.
- [x] Family Terrace uses the approved 10.0m by 2.7m luxury proportion.
- [x] Family Terrace exposed edges have separate 1.10 m glass guards.
- [x] Floor-to-ceiling glass is separate and 0.020 m thick.
- [x] The 2F→3F stair is physical, watertight geometry.
- [x] Glass guardrails protect all exposed OPEN TO BELOW edges without shrinking the void.
- [x] Stair-side guardrails preserve the active flight and +X landing exit.
- [x] No duplicate mesh or object names were found.
- [x] All architectural meshes are closed positive-volume solids.
- [x] All architectural object scales are 1,1,1.
- [x] No ceiling, furniture, fixtures, decoration, landscaping, B1, 1F room model, or 3F room model was added.
- [x] Top, front, corner, source-overlay, and 1F/2F alignment views were generated.

## Rebuild

Run from `01_shell/2F/`:

```bash
blender -b --factory-startup --python-exit-code 1 --python build_2F_shell.py
blender -b 2F_shell.blend --python-exit-code 1 --python validate_2F_shell.py
blender -b 2F_shell.blend --python-exit-code 1 --python export_2F_report.py
python3 render_2F_alignment.py
```
