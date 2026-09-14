# First-floor shell implementation report

Created: `/home/nicklee/Phenix_Project/Drone/environments/villa_v2/01_shell/1F/1F_shell.blend` using Blender 4.5.3 LTS.

The deliverable contains the first-floor shell and its two inter-floor stair continuations only. There are no other-floor room/slab models, ceilings, furniture, fixtures, textures, or landscaping.

## Files and inspection

- [Blender scene](1F_shell.blend)
- [Pre-correction backup](1F_shell_before_wall_fix.blend) — retained unchanged.
- [Top orthographic render](1F_shell_top.png) — 2400 × 1700; north is up.
- [Front perspective render](1F_shell_perspective_front.png) — 1800 × 1300.
- [Elevated corner render](1F_shell_perspective_corner.png) — 1800 × 1300.
- [Great Room validation render](1F_shell_greatroom_validation.png) — 1800 × 1300.
- [Actual mesh/source overlay](1F_shell_source_overlay.svg) — open in a browser for a zoomable comparison with object names on hover.
- [Reproducible generator](build_1F_shell.py), [geometry verifier](validate_1F_shell.py), [report exporter](export_1F_report.py).
- [Machine-readable audit](1F_shell_validation.json).
- [Backup invariant comparison](1F_wall_fix_comparison.json).

## Scale and measured bounds

The source is 1448 × 1086 pixels. Horizontal dimension ticks at X=108 and X=1062 calibrate to 35.6 m. Vertical ticks at Y=189 and Y=837 calibrate to 22.8 m. These yield X=0.037316562 m/pixel and Y=0.035185185 m/pixel. The reference therefore has a disclosed approximately 5.7% aspect correction; a uniform scale cannot satisfy both drawn dimensions. Dimension-marker center (585,513) maps to world (0,0). Source north maps to +Y.

| Geometry measured | X width | Y depth |
| --- | ---: | ---: |
| Dimension-marker span | 35.600 m | 22.800 m |
| Enclosed first-floor slab, including structural projections | 37.652 m | 21.885 m |
| All architectural meshes, including terraces and Entry Porch | 37.652 m | 24.946 m |

Full mesh bounds: minimum **(-18.844864, -12.490741, -3.600000) m**, maximum **(18.807549, 12.455556, 3.200000) m**. Reference, cameras, lights and helpers are excluded. Z reaches -3.600 m because of Stair A's underside; the lower walking surface is -3.200 m.

**The modeled envelope is deliberately not forced to 35.6 × 22.8 m.** Black outer strokes extend to source X=80..1089; rear terrace and porch extend to Y=159..868. They exceed the dimension-marker extent. The sub-dimension proportions and printed room areas also disagree with the raster; as requested, room areas were not used to distort the trace. Confirm authoritative dimensions before aligning subsequent floors.

## Construction assumptions

- Wall tops: **Z=3.200 m**, all standard walls and piers; no global ceiling.
- Slabs: **0.200 m**, from Z=-0.200 to 0.000. Terrace and porch top surfaces also Z=0; no site elevations are supplied.
- Wall thickness is explicit metric geometry: **0.280 m exterior**, **0.180 m interior partition**, and **0.220 m stairwell**. Exterior faces remain at their pre-fix coordinates; partition centerlines remain unchanged; stair-void faces remain unchanged. Long-axis endpoints remain fixed, preserving door centers and opening widths.
- Four small internal Great Room piers were removed. The 12 remaining façade, terrace, entry, corner, and perimeter piers retain their source rectangles. Terrace pier height remains provisionally 3.2 m.
- Door/circulation gaps are temporarily **full wall height (3.2 m)**. Door heads and panels have not been invented from a plan with no elevation information. Visible swing arcs are not geometry. Source door widths are retained, including narrow approximately 0.75–0.85 m openings; the main entry is approximately 2.87 m wide.
- Glass: **0.020 m thick, 3.200 m high**, from Z=0 to the assumed wall top, matching the source note's floor-to-ceiling glazing; placeholder blue transparent material. Glazing remains separate for later collision/material decisions.
- Structural wall joints are rebuilt as clean, closed solids and trimmed into non-overlapping volumes. Components meet only at intentional construction interfaces. No thin intersection remnants or non-column wall bands over 0.30 m remain.

## Great Room and wall correction

The usable Great Room footprint was tested against actual mesh interiors at Z=1.2 m. It contains only the first-floor slab: **zero columns, zero piers, zero freestanding walls, and zero wall stubs**. The north glazing remains separate and unchanged, and the space remains open above the 3.2 m first-floor wall height.

Removed objects (4):

- `1F_Column_007_GreatRoom_W1`
- `1F_Column_008_GreatRoom_E1`
- `1F_Column_009_GreatRoom_W2`
- `1F_Column_010_GreatRoom_E2`

All 38 generated wall objects had their cross-sectional thickness rebuilt while preserving the category-specific alignment rule:

- `1F_Wall_Exterior_001_Garage_NorthWest`
- `1F_Wall_Exterior_002_Garage_NorthEast`
- `1F_Wall_Exterior_003_Garage_WestSouth`
- `1F_Wall_Exterior_004_Storage_WestSouth`
- `1F_Wall_Exterior_005_TerraceDoor_Left`
- `1F_Wall_Exterior_006_TerraceDoor_Right`
- `1F_Wall_Exterior_007_Kitchen_North`
- `1F_Wall_Exterior_008_Pantry_East`
- `1F_Wall_Exterior_009_Mudroom_EastSouth`
- `1F_Wall_Exterior_010_Ensuite1_West`
- `1F_Wall_Exterior_011_Ensuite1_South`
- `1F_Wall_Exterior_012_Guest1_South`
- `1F_Wall_Exterior_013_StairA_South`
- `1F_Wall_Exterior_014_Entry_West`
- `1F_Wall_Exterior_015_Entry_East`
- `1F_Wall_Exterior_016_StairB_South`
- `1F_Wall_Exterior_017_Guest2_South`
- `1F_Wall_Exterior_018_Ensuite2_South`
- `1F_Wall_Exterior_019_Ensuite2_East`
- `1F_Wall_Interior_001_Garage_GreatRoom`
- `1F_Wall_Interior_002_Garage_Service`
- `1F_Wall_Interior_003_Storage_Utility`
- `1F_Wall_Interior_004_Utility_Wine`
- `1F_Wall_Interior_005_Service_Guest1`
- `1F_Wall_Interior_006_Guest1_Ensuite`
- `1F_Wall_Interior_007_Corridor_Left`
- `1F_Wall_Interior_008_StairA_West`
- `1F_Wall_Interior_009_StairA_East`
- `1F_Wall_Interior_010_Pantry_Kitchen`
- `1F_Wall_Interior_011_Pantry_Mudroom`
- `1F_Wall_Interior_012_Mudroom_Kitchen`
- `1F_Wall_Interior_013_Corridor_Right_North`
- `1F_Wall_Interior_014_Corridor_Right_West`
- `1F_Wall_Interior_015_Corridor_Right_South`
- `1F_Wall_Interior_016_StairB_West`
- `1F_Wall_Interior_017_StairB_East`
- `1F_Wall_Interior_018_Powder_Guest2`
- `1F_Wall_Interior_019_Guest2_Ensuite`

Final measured wall bands: exterior **0.280 m**, interior partitions **0.180 m**, stairwell walls **0.220 m**, and glass **0.020 m**. Remaining non-column walls over 0.30 m: **none**.

## Stairs and future-level interfaces

Both straight flights have **19 risers × 0.168421 m**, **18 treads × 0.270 m**, and **4.860 m horizontal run**. Undersides are sloped with a 0.400 m vertical profile offset; the minimum web is above 0.23 m. These are low-density closed solids, not overlapping step boxes.

| Stair | Clear width | Flight run | Terminal landing depth | Terminal walking Z | Direction |
| --- | ---: | ---: | ---: | ---: | --- |
| 1F_StairA_DownToB1 | 2.836 m | 4.860 m | 1.157 m | -3.200 m | south (-Y), down to B1 |
| 1F_StairB_UpTo2F | 2.351 m | 4.860 m | 1.086 m | +3.200 m | south (-Y), up to 2F |

Stair A occupies source rectangle (388,650)..(464,821), world X=-7.351363..-4.515304 m, Y=-10.837037..-4.820370 m. It starts at the north corridor at Z=0, descends south, and has a side connection toward +X from its south lower landing. Walls are not extended through that basement connection. Only the stair/landing is modeled below 1F.

Stair B occupies source rectangle (708,652)..(771,821), world X=4.589937..6.940881 m, Y=-10.837037..-4.890741 m. It starts at the north corridor at Z=0 and ascends south. Its upper landing meets Z=3.2; the future 2F connection is toward +X, above the current first-floor wall top. No 2F slab was added.

**Stair B direction requires manual confirmation.** The source symbol contains arrowheads in both directions. The north end is the clear accessible mouth, so southbound ascent is the provisional interpretation raised during modeling. The drawn tread cluster is too short to represent a complete 3.2 m flight; treads have been redistributed within the same shaft to obtain realistic rise/run. No shaft or room was relocated.

`1F_Connection_B1` and `1F_Connection_2F` store the terminal connection points. `1F_Opening_StairA`, `1F_Opening_StairB`, and `VOID_GreatRoom_OpenToAbove` are hidden, non-rendering helpers. The Great Room helper follows source rectangle (397,282)..(773,575); its upper-floor exclusion must be reconciled with an authoritative 2F plan later. There is no roof or slab over this region.

## Glazing interpretation

Blue-gray/white narrow lines were interpreted as glass at the garage north/west, Storage west/north, the two north terrace-entry recesses, the Great Room's stepped north edge, kitchen/pantry north, pantry/mudroom east, both guest-suite and en-suite external edges, stair south ends, and the main-entry sidelights.

**Storage access is inferred:** its north boundary has glazing but no clear door arc. The fixed section follows source X=117..151 at Y=549.5; X=151..183 remains an approximately 1.194 m clear sliding-glass access. This is the only deliberately inferred operable bay. Guest Suite 1's shown north doorway opens through the Wine Cellar; that unusual circulation has been retained.

All 25 glazing objects and their original source endpoints:

- `1F_Glass_001_Garage_North` — source line `[[153, 274], [334, 274]]`.
- `1F_Glass_002_Garage_West` — source line `[[88.5, 354], [88.5, 519]]`.
- `1F_Glass_003_Storage_West` — source line `[[88.5, 555], [88.5, 611]]`.
- `1F_Glass_004_Storage_North_Fixed` — source line `[[117, 549.5], [151, 549.5]]`.
- `1F_Glass_005_TerraceDoor_Left_West` — source line `[[348, 226], [348, 268]]`.
- `1F_Glass_006_TerraceDoor_Left_North` — source line `[[348, 226], [374, 226]]`.
- `1F_Glass_007_GreatRoom_NorthWest` — source line `[[414, 252], [443, 252]]`.
- `1F_Glass_008_GreatRoom_North` — source line `[[466, 270], [704, 270]]`.
- `1F_Glass_009_GreatRoom_NorthEast` — source line `[[728, 252], [757, 252]]`.
- `1F_Glass_010_TerraceDoor_Right_North` — source line `[[795, 226], [821, 226]]`.
- `1F_Glass_011_TerraceDoor_Right_East` — source line `[[821, 226], [821, 268]]`.
- `1F_Glass_012_Kitchen_North` — source line `[[838, 274], [968, 274]]`.
- `1F_Glass_013_Pantry_North` — source line `[[1003, 274], [1038, 274]]`.
- `1F_Glass_014_Pantry_East` — source line `[[1080.5, 313], [1080.5, 463]]`.
- `1F_Glass_015_Mudroom_East` — source line `[[1080.5, 494], [1080.5, 568]]`.
- `1F_Glass_016_Ensuite1_West` — source line `[[136.5, 686], [136.5, 754]]`.
- `1F_Glass_017_Ensuite1_South` — source line `[[158, 803], [183, 803]]`.
- `1F_Glass_018_GuestSuite1_South` — source line `[[232, 815], [344, 815]]`.
- `1F_Glass_019_StairA_South` — source line `[[409, 830], [443, 830]]`.
- `1F_Glass_020_StairB_South` — source line `[[727, 830], [753, 830]]`.
- `1F_Glass_021_GuestSuite2_South` — source line `[[818, 815], [952, 815]]`.
- `1F_Glass_022_Ensuite2_South` — source line `[[1002, 803], [1022, 803]]`.
- `1F_Glass_023_Ensuite2_East` — source line `[[1031, 685], [1031, 754]]`.
- `1F_Glass_024_Entry_Sidelight_West` — source line `[[532, 783], [549, 783]]`.
- `1F_Glass_025_Entry_Sidelight_East` — source line `[[626, 783], [644, 783]]`.

## Verification and limits

**49 geometry checks passed, 0 failed**, including saved-file validation. The scene has **82 architectural mesh objects**, approximately **4740 triangles** after triangulation. All structural meshes are closed, have positive signed volume, unit object scales and no degenerate faces. No complete duplicate meshes or intersecting structural volumes were detected. The overlap audit tests actual mesh interiors across orthogonal arrangement cells and the stair bounds; intentional touching joints are allowed.

The actual floor mesh is absent in both stair apertures. Physical tread samples confirm descending A and ascending B, with at least 2.1 m vertical clearance over sampled tread centers in this shell. Stair objects and apertures were not regenerated from changed parameters. The Great Room is clear internally and unobstructed above the walls. Twenty-two doorway/circulation line samples at Z=1.2 m are clear. A 0.10 m grid with center plus four radius samples connects the foyer to every room using an approximate 0.40 m UAV diameter. These are geometry checks; no Gazebo, ROS 2, PX4, dynamics or VIO testing was performed.

All four PNGs were produced from Blender geometry and visually inspected. The top render preserves full-height opening gaps and shows the actual stair geometry. The dedicated Great Room view exposes the cleared floor and retained north glazing. The SVG overlay provides an additional dimension-calibrated trace comparison. Stair A is visible below the shell in perspective because no B1 walls have been modeled.

Manual review priorities remain: source scale/dimension inconsistency; Stair B direction and both future landing elevations; Storage's sliding access; Guest Suite 1's access through Wine Cellar; full-height opening placeholders; retained perimeter/terrace pier sizes; and terrace/porch boundary strokes. The four gray piers previously traced inside the Great Room are deliberately omitted per the wall-fix requirement. The approach steps, outer front apron and narrow exterior perimeter outlines were treated as site/landscape graphics beyond the requested four exterior slabs and are not modeled.

## Required checklist

- [x] Blender scene uses meters (Metric, length Meters, unit scale 1).
- [x] Reference image calibrated using the 35.6 m width and 22.8 m depth dimension markers; packed into the .blend.
- [x] Main first-floor footprint modeled as a stepped slab, with both stair apertures.
- [x] Exterior walls modeled from significant black bands.
- [x] Interior walls modeled from significant black bands.
- [x] Glass separated from walls (25 independent thin solid objects).
- [x] Main Terrace modeled.
- [x] Left Outdoor Terrace modeled.
- [x] Dining Terrace modeled.
- [x] Entry Porch modeled.
- [x] Garage modeled as an open shell.
- [x] Grand Entry Foyer footprint, entrance gap, sidelights and circulation retained.
- [x] Great Room modeled.
- [x] Great Room remains double height.
- [x] OPEN TO ABOVE area is not covered; future-floor exclusion helper exists.
- [x] Kitchen & Dining remains open within the traced shell.
- [x] Guest Suite 1 partitions exist.
- [x] En-suite 1 partitions exist.
- [x] Storage exists; inferred operable-glazing access is disclosed below.
- [x] Utility exists.
- [x] Wine Cellar exists.
- [x] Guest Suite 2 partitions exist.
- [x] En-suite 2 partitions exist.
- [x] Powder Room exists.
- [x] Pantry / Prep Kitchen exists.
- [x] Mudroom / Shoe Gallery exists.
- [x] Stair A physically descends south toward its provisional B1 landing.
- [x] Stair B physically ascends south toward its provisional 2F landing; direction uncertainty disclosed.
- [x] Stair openings exist; actual floor rays miss both shaft interiors.
- [x] Great Room usable interior contains zero columns, piers, wall stubs, or remnants.
- [x] Four former Great Room internal piers removed; 12 exterior/perimeter structural piers retained.
- [x] Exterior walls measure 0.280 m; interior partitions 0.180 m; stairwell walls 0.220 m.
- [x] Exterior faces, partition centerlines, and stair-void faces retain their specified alignment.
- [x] No non-column wall geometry exceeds 0.300 m.
- [x] Visible door openings preserved; 22 sampled opening/circulation paths unblocked.
- [x] No furniture added.
- [x] No decorative objects added.
- [x] No accidental complete duplicate meshes; no detected intersecting solid volumes.
- [x] Normals checked: all structural meshes closed, positive signed volume, no degenerate faces.
- [x] Mesh transforms checked: all scales 1,1,1; origins at individual mesh bounds centers.
- [x] Top verification image exported and inspected.
- [x] Front verification image exported and inspected.
- [x] Corner verification image exported and inspected.
- [x] Great Room validation image exported and inspected.

## Rebuild and inspect

Run from this directory with Blender 4.5.3 LTS or a compatible bpy version:

```bash
blender -b --factory-startup --python-exit-code 1 --python build_1F_shell.py
blender -b 1F_shell.blend --python-exit-code 1 --python validate_1F_shell.py
blender -b 1F_shell.blend --python-exit-code 1 --python export_1F_report.py
```

To iterate geometry without rendering, append `-- --skip-renders` to the build command. Source rectangles and calibration constants are grouped near the top of the generator. The reference image is packed, locked and hidden under `REFERENCE_1F`; reveal it and hide shell collections for a direct top-view check. Helpers are individually hidden under `1F_OPENINGS`; reveal them for future level alignment. Every renderable mesh has `shell_geometry=True` and a separate `element_type` property for later export filtering.
