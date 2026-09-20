# First-floor shell implementation plan

**Goal:** Produce `1F_shell.blend`, its reproducible bpy generator, three validation renders, and an explicit geometry/assumption report from `1F.png` only.

**Design:** Trace architectural features in original image pixel coordinates, convert through independently calibrated X/Y scales, and retain source coordinates on objects. Use closed solid meshes for structure, independent thin glazing, a polygonal slab with the basement stair cutout, physical straight stairs, and non-rendering floor-alignment helpers. All output stays in this directory.

**Specification:** The user's 36-section first-floor modeling brief in this conversation; the reference is `1F.png` (1448 × 1086 pixels).

## Constraints

- 1 Blender unit = 1 m; Z up; reference marker center maps to X/Y origin; slab top Z = 0.
- Width markers at source X = 108 and 1062 represent 35.6 m. Depth markers at Y = 189 and 837 represent 22.8 m. Architectural outlines extend beyond these markers. Do not rescale the result to conceal this inconsistency.
- Walls approximately 3.2 m tall; thickness traced from significant black bands rather than annotations. Slab 0.20 m; glass 0.02 m.
- No ceilings, furniture, fittings, textures, landscape, or B1/2F/3F rooms/slabs.
- Stair landing target elevations ±3.2 m are provisional; the drawing has no vertical section. Steps must fit the source shaft and have realistic rise/run.
- North in the source maps to world +Y. A descends south. B direction is flagged to the user because the source arrows are ambiguous.
- Preserve all shown door gaps. Document inferred access where the image is incomplete.

## Execution

- [x] Calibrate reference and record traced footprints, walls, columns, glazing, openings, and stair shafts in `build_1F_shell.py`.
- [x] Build organized metric scene and pack the reference image. Keep floor, walls, columns, glazing, stairs, terraces, and helpers separate.
- [x] Validate closed meshes, outward normals, unit scales, duplicate geometry, slab aperture, door clearances, room circulation, and stair connections with `validate_1F_shell.py`.
- [x] Render top orthographic, front perspective, and elevated corner images. Inspect these against the source; fix defects.
- [x] Reopen the final saved file, run validation, and write `1F_shell_report.md` plus machine-readable audit results. Report measured bounding dimensions and unresolved source ambiguities.

## Review evidence

The verifier will inspect evaluated Blender geometry rather than assume generator parameters imply correctness. It will test the actual basement aperture with vertical rays, sample named door paths and room connectivity at UAV height, confirm every structural mesh is manifold and has positive signed volume, and measure scene bounds with reference/cameras/helpers excluded.
