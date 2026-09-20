# Second-floor shell implementation plan

## Scope and invariants

- Build only `2F_shell.blend` with its own finished-floor level at local `Z=0`.
- Write only inside `01_shell/2F/`; treat every `01_shell/1F/` file as read-only and verify its SHA-256 hashes after completion.
- Use meters, `scale_length=1`, +X east, +Y north, +Z up.
- Reuse the validated 1F pixel-to-world transform: source pixel `(585,513)` is world `(0,0)`, `SX=35.6/954`, and `SY=22.8/648`. This preserves the current stack coordinates even where the revised 2F sheet's printed dimension graphics do not have perfectly proportional pixel spacing.

## Measured 1F anchors

- Architectural mesh bounds: X `-18.844864..18.807549 m`, Y `-12.490741..12.455556 m`.
- Stair B opening: source `(708,652)..(771,821)`, world X `4.589937..6.940881 m`, Y `-10.837037..-4.890741 m`.
- Great Room reference void: source `(397,282)..(773,575)`, world X `-7.015514..7.015514 m`, Y `-2.181481..8.127778 m`.
- The 2F open-to-below rectangle is traced independently from `2F.png` and must remain inside the 1F Great Room reference void.

## Geometry construction

1. Trace the stepped 2F occupied floor footprint as an orthogonal union, with the large source-drawn open-to-below rectangle and exact 1F Stair B opening subtracted from the actual slab mesh.
2. Create the Family Terrace as an independent slab without coplanar overlap with the enclosed floor.
3. Trace major exterior wall bands, interior partitions, and stair walls as separate watertight solids. Rebuild their cross-sections to 0.28 m exterior, 0.18 m interior, and 0.22 m stair/special wall thickness while retaining source centerlines or exterior faces.
4. Preserve visible door gaps as full-height shell openings because no elevation/door-head information was supplied.
5. Create structural façade columns shown by solid black blocks; do not turn the light void-corner/balustrade marks into full-height columns.
6. Create each cyan floor-to-ceiling boundary as a separate 0.020 m thick glass solid.
7. Represent the existing 1F→2F stair only by its exact slab opening, hidden interface helper, and connection marker. The physical flight already exists in `1F_shell.blend`, so duplicating it would create overlapping export geometry.
8. Create the separate source-drawn 2F→3F stair as a low-density watertight stepped solid rising north (+Y) from the Art Gallery. Use 18 risers over the provisional 3.2 m storey rise and 0.26 m treads so the flight fits its drawn shaft.
9. Add hidden helpers for the open-to-below volume, both stair interfaces, and checked circulation openings.

## Validation-first workflow

1. Write `validate_2F_shell.py` before the generator and confirm it fails against an empty Blender scene.
2. Build with `build_2F_shell.py`, save, reopen, and run validation independently.
3. Validate units, object names/scales, bounds, wall/glass dimensions, manifold volumes, horizontal floors, vertical walls, duplicate meshes, open-to-below rays, stair-opening rays, 1F/2F source transform, exact Stair B bounds, shared major X anchors, and coordinate sanity.
4. Record all results and a machine-readable alignment block in `2F_shell_validation.json`; capture Blender output in `validation_2F_shell.log`.
5. Render top, front, and elevated-corner views. Export a calibrated source overlay and a color-coded 1F/2F XY alignment image from measured geometry.
6. Inspect all validation images and repeat build/validation after correcting any material error.

## Known source ambiguity to preserve in the report

- The 2F arrow labeled “Down to 1F” points south on the revised sheet, while the validated 1F stair currently rises south to its 2F terminal landing. The shell will retain the exact 1F opening and terminal connection rather than create a contradictory duplicate flight.
- The revised plan's drawn dimension-line pixel spans are not uniformly proportional to the written 35.6 m / 22.8 m and segment labels. The established 1F transform governs stack alignment; the 2F trace remains attached to the original source pixels and the mismatch will be quantified.
- The light double-line marks at the open-to-below perimeter read as an edge/balustrade graphic. No low railing is added at shell stage, consistent with the task instruction.
- Note 8 calls the 2F→3F stair “curved,” while the actual drawn flight is straight and rectangular. The model follows the drawn geometry, per the instruction to prefer drawn floor geometry over contradictory text.

## Targeted guardrail correction

- Preserve all existing floor, wall, terrace, glazing, column, stair, void, and XY trace coordinates.
- Add frameless 0.020 m glass along the four exposed OPEN TO BELOW edges, entirely on the floor side so the void is not reduced.
- Use 1.050 m glass with a thin top rail reaching 1.100 m overall.
- Protect the west side of the 1F→2F stair aperture and the east side of the flight. Stop the east guard before the south terminal landing so the +X exit remains open; do not rail across either stair travel end.
- Add a dedicated open-to-below camera and extend numerical checks for guard height, edge coverage, bridge clearance, stair clearance, Family Terrace, and live 1F anchor measurements.
