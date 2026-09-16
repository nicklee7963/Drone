# Villa V3 Geometry Cleanup Design

## Purpose

Create `villa_v3` as a preserved copy of `villa_v2`, then perform a conservative, evidence-based geometry cleanup across B1, 1F, 2F, 3F, and Roof. The result must retain the existing architecture while providing validated Blender shells, a stacked whole-building scene and inspection render, and a Gazebo Harmonic world with visual and collision geometry.

## Non-negotiable constraints

- `villa_v2` is immutable. Record a complete pre-copy SHA-256 manifest and prove it is unchanged at completion.
- Begin from a filesystem copy of `villa_v2`; do not reconstruct the project or floors from scratch.
- Modify only confirmed defects in copied shell files. Preserve rooms, stairs, terraces, glazing, major walls, dimensions, coordinate systems, and scale.
- Treat the floor-plan reference images as authoritative when an opening or isolated element is unclear.
- Prefer named-object endpoint/vertex corrections and removal of confirmed fragments or duplicates. Generic filler objects are prohibited unless no cleaner correction exists and the report explains why.
- Storeys remain at B1 `-3.2 m`, 1F `0 m`, 2F `3.2 m`, 3F `6.4 m`, and Roof `9.6 m`.
- Exterior endpoint defects must be reduced to at most `0.02 m`; the preferred result is exact contact without volume overlap.
- Normal circulation narrower than `0.85 m` is a review candidate, not an automatic edit. Reference-backed narrow openings remain unchanged.
- Run the copied existing validator and the new unified validator after each floor repair.

## Existing project observations

The live shell files are:

- `01_shell/B1/B1_shell.blend`
- `01_shell/1F/1F_shell.blend`
- `01_shell/2F/2F_shell.blend`
- `01_shell/3F/3F_shell.blend`
- `01_shell/Roof/Roof_shell.blend`

Each floor has a Python builder and validator. Existing reports claim zero failures, so they are a regression baseline, not proof that the requested defect classes are absent. The existing Gazebo exporter produces one OBJ-backed visual and collision mesh per floor. The complete V2 world establishes the required storey poses.

## Chosen approach

Use object-specific repair scripts against copied `.blend` files, backed by a new geometry-audit layer. Do not regenerate entire floors from the builder scripts. Existing builders remain useful documentation of source rectangles, intended openings, and object roles; existing validators remain regression checks.

The workflow is:

1. Hash `villa_v2` and copy it with metadata to `villa_v3`.
2. Replace V2-specific absolute paths only in copied tooling.
3. Run a read-only Blender audit per floor and render diagnostics in `villa_v3`.
4. Classify each candidate against object metadata, existing opening schedules, validation reports, top/perspective renders, and floor-plan reference images.
5. Record confirmed defects in a data-driven repair manifest keyed by exact object name.
6. Demonstrate each confirmed defect with an audit failure, apply one local correction, and rerun the floor's existing and unified validators.
7. Validate cross-floor stair/slab alignment and assemble the accepted shells without altering local coordinates.
8. Render the whole villa, export all five floor models, generate the complete world, validate SDF/resources/collisions, and perform a bounded headless simulator load.
9. Produce a machine-readable combined report and prove the V2 hash manifest is unchanged.

## Audit architecture

`tools/villa_geometry_audit.py` runs inside Blender and emits JSON. It evaluates only architectural mesh objects and uses world-space evaluated meshes. It reports:

- object bounds, mesh components, non-manifold edges, degenerate faces, signed volume, and slab support;
- exact mesh duplicates and near-identical coplanar objects;
- positive-volume overlaps using broad-phase AABBs followed by BVH evidence;
- wall, column, and glass endpoint distances in plan view;
- unsupported/floating objects and disconnected wall fragments;
- narrow free-space candidates and small enclosed void candidates from a 2D occupancy grid at representative flight/person heights;
- floor/slab coverage and unexpected holes, excluding declared stair, atrium, and double-height openings;
- candidate openings with one of the required classifications.

Automatic results are candidates unless the condition is mechanically decisive, such as an exact duplicate, disconnected fragment, positive-volume overlap, or an endpoint miss below the intentional-opening threshold. Classification records include evidence, reference consulted, decision, and any repair ID.

## Repair architecture

`tools/apply_geometry_repairs.py` consumes a checked-in JSON repair manifest. Supported operations are deliberately narrow:

- move a named endpoint by modifying only vertices on one terminal plane;
- align one terminal plane to a named target object's boundary;
- remove an exact duplicate or confirmed accidental named object;
- merge/remove a disconnected component within a named mesh;
- correct local slab boundary vertices around a confirmed unintended hole;
- set a named object's local transform only when the transform itself is the confirmed defect.

Each operation includes expected preconditions, old coordinates, new coordinates, maximum displacement, and reason. A mismatch aborts rather than editing an unexpected scene. The script saves a pre-cleanup backup inside `villa_v3`, updates the live copied blend, and emits an applied-repair receipt.

## Intentional openings

Preserved openings are taken from the copied scenes' custom metadata and existing validator schedules, then checked against reference plans. They include named doors, circulation connections, stair openings, atrium/open-to-below regions, terraces, and glazing transitions. The final report lists them per floor using these classes:

- `INTENTIONAL_DOOR`
- `INTENTIONAL_CIRCULATION`
- `INTENTIONAL_STAIR_OPENING`
- `INTENTIONAL_GLASS_TRANSITION`
- `INTENTIONAL_TERRACE_OPENING`

Unresolved candidates use `UNKNOWN` and prevent an unconditional PASS.

## Assembly and render

`tools/build_full_assembly.py` appends accepted architectural meshes into per-floor collections and applies only the established collection-level Z offsets: `-3.2`, `0`, `3.2`, `6.4`, and `9.6 m`. It creates neutral materials, sun/area lighting, a ground plane used only for rendering, and a perspective camera fitted from evaluated whole-building bounds. It saves `02_assembly/villa_v3_full.blend` and renders `02_assembly/villa_v3_full.png` at 1920×1080 or higher.

The assembly validator checks collection membership, source object counts, XY preservation, exact Z offsets, total bounds, and stair/opening alignment before rendering.

## Gazebo output

The copied `tools/export_floor_to_gazebo.sh` is retained but made root-relative and V3-specific. It supports all five floor names, exports only renderable architectural meshes, and writes an OBJ-backed visual and collision geometry to each model SDF.

`tools/build_villa_v3_gazebo.sh` runs all five exports, writes `gazebo/worlds/villa_v3.sdf`, and validates every model and the world with `gz sdf -k`. The world includes the five models at the approved Z poses. Validation additionally parses every SDF to confirm each floor link has at least one visual and one collision element and checks that every referenced mesh exists and is nonempty.

The headless load uses a unique Gazebo partition and a bounded server-only run. Logs are scanned for missing resources, mesh errors, and SDF errors. A timeout after successful startup is acceptable and is reported distinctly from a startup failure.

## Reporting and pass criteria

`villa_v3_validation.json` contains a project summary and one record for each floor with:

- counts for each requested defect class;
- classified intentional openings;
- confirmed defects and their evidence;
- exact repairs and maximum displacement;
- existing-validator results;
- unified-validator results;
- remaining warnings and status.

A floor is PASS only when both validators pass, no confirmed defect remains, and no `UNKNOWN` candidate affects architectural closure, traversal, slab safety, or inter-floor alignment. The project passes only when all floors pass, the assembly validates, Gazebo SDF/resource/collision checks pass, the headless load reaches successful startup, and the final V2 hash matches the baseline.

## Failure handling

- An ambiguous opening is left untouched, marked `UNKNOWN`, and escalated only if references and metadata cannot resolve it.
- A failed repair precondition aborts that floor without saving.
- A validator regression restores the V3 pre-cleanup backup and the repair is re-investigated.
- Export or simulator errors are traced to the producing floor/model before any additional geometry change.

