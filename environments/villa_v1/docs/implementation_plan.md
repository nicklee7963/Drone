# Summit Estate implementation plan

**Goal:** An editable, metrically coherent Blender master and inspected room renders grounded in the 30 supplied images.
**Architecture:** One assembled building with floor and room collections, separate component disciplines, reusable detailed asset builders and recoverable phase checkpoints. Scene geometry remains the source of truth for renders.
**Tech stack:** Locally contained Blender 4.5.3 LTS, Python/bpy, Cycles GPU, procedural PBR materials.
**Spec:** `docs/reference_interpretation.md` and the user's full task brief.

## Constraints

Only write inside villa_v1; preserve reference bytes. No PX4/ROS/Gazebo/SDF/sensors/collision integration. No pets, no 3F computer room, no 3F atrium, no indoor spa terrace. Metric dimensions, genuine openings and traversable stairs. Modularity and quality take priority over object-count reduction.

## Sequence and outputs

- [x] Phase 1: Inspect every reference; write interpretation, contradictions and inventory. `docs/reference_interpretation.md`, `docs/reference_inventory.json`.
- [ ] Phase 2: Build shell with separate slab segments, thick walls and real gaps, glazed openings, stairs, elevator cores, privacy door, garage transition, courtyard and stepped roofs. `scripts/architecture.py`, `scripts/build_estate.py`, `blender/checkpoints/02_shell.blend`.
- [ ] Phase 3: Verify slab at 3F, atrium ceiling, covered/uncovered terrace boundary, stair rise/run/headroom, openings, clear circulation and room area metadata. `scripts/validate_estate.py`, `docs/qa_shell.json` and shell renders.
- [ ] Phase 4: Detail B1: gym equipment; six-seat cinema with vestibule/riser; books, hanging chair and reading table; wine racks/tasting; lounge/bar; laundry and wet/service rooms; planted courtyard. Render and inspect B1 before 1F.
- [ ] Phase 5: Detail 1F: foyer ring chandelier/piano/art, living TV/fireplace and soft seating, dining 12 places, functional show/prep kitchens and pantry, shoe/coat gallery, powder, flex room, six-car garage. Render and inspect before 2F.
- [ ] Phase 6: Detail 2F: gallery art, family seating, console lounge, two furnished guest suites with bathroom and wardrobe. Render and inspect before 3F.
- [ ] Phase 7: Detail 3F: secure arrival, open sleeping/closet/bath, view-facing tub, actual outdoor terrace spa/seating/planting. Render and inspect.
- [ ] Phase 8: Balance actual lights and emissive fixtures; complete daylight and dusk presets, stair/shelf/task/display/exterior layers.
- [ ] Phase 9: Refine PBR material scale, veining, fabric texture, timber grain, reflectivity and glazing. Preserve useful parameters; save material library.
- [ ] Phase 10: Render all fixed cameras; inspect and fix visible defects; run scene QA; save master, README, discrepancies and contact index.

## Builder interfaces / independent asset work

`materials.build_materials() -> dict[str, Material]` supplies stable palette keys.
`furniture.build_asset(kind, name, collection, materials, **kwargs) -> Object` returns an Empty root; children have geometry in metres and meaningful names. Origin at floor, front facing −Y. Kinds: sofa, armchair, chair, stool, table, bed, cabinet, bookshelf, closet, hanging_chair, plant, decor, rug, lamp.
`equipment.build_asset(kind, name, collection, materials, **kwargs) -> Object` same contract. Kinds: piano, treadmill, dumbbell_rack, power_rack, cable_machine, gym_bench, cinema_seat, car, kitchen, laundry, tub, hot_tub, vanity, shower, toilet, shoe_display.
Root script places assets and owns scene composition; asset modules never clear scene or change render settings. Repeated assets can share mesh data. Floor work remains sequential even when independent reusable asset libraries are authored concurrently.

## Verification

Blender process must finish with exit 0; reopen saved file and inspect evaluated bounds, transforms, scene units, critical ray casts and collection/camera inventory. Preserve SHA-256 hashes for all references. Save JSON measurements and a discrepancy list. Actual camera PNGs are reviewed; automated geometry checks do not certify visual fidelity or construction engineering.
