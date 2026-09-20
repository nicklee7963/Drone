# Basement B1 Shell Implementation Plan

**Goal:** Build and validate the standalone B1 architectural shell from `B1.png` while preserving the established villa coordinate frame and the live 1F-to-B1 stair interface.

**Architecture:** Trace B1 in original image pixels and convert with the exact 1F transform. Keep the B1 plan layout fixed, but replace only its inconsistent stair bay with an aperture and arrival geometry derived from `1F_StairA_DownToB1`; the physical stair remains owned by 1F.

**Tech stack:** Blender 4.5 LTS, Python/bpy, bmesh, JSON, Cycles.

## Global constraints

- Local B1 finished floor Z is 0.0 m; slab is Z -0.20..0.00 m; walls are Z 0.00..3.20 m.
- Use the established transform: origin pixel `(585,513)`, `SX=35.6/954`, `SY=22.8/648`, +X east, +Y north.
- Treat live 1F stair bounds X `-7.351362683..-4.515303983 m`, Y `-10.837037037..-4.820370370 m` as authoritative.
- Do not duplicate the physical stair, which is already in `1F_shell.blend`.
- Model shell geometry only. Do not modify or save 1F, 2F, or 3F.

## Tasks

- [x] Create `validate_B1_shell.py` first; verify it fails on an empty Blender scene.
- [x] Create `build_B1_shell.py` with the traced footprint, courtyard subtraction, walls, columns, glazing, classified openings, exact stair interface, materials, and validation cameras.
- [x] Build `B1_shell.blend`, reopen it independently, and validate dimensions, topology, accessibility, junctions, overlaps, floating geometry, and live 1F stair alignment.
- [x] Render `B1_shell_top.png` and `B1_shell_perspective_corner.png` in the established style.
- [x] Visually compare the top render with `B1.png`, correct material discrepancies, rerun validation, and confirm the existing floor hashes remain unchanged.
