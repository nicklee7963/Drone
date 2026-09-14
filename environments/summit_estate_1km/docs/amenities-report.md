# Summit Estate outdoor amenities

Implemented by `scripts/amenities.py` through the shared geometry API. The builder
returns `features`, `excavations`, and `flight_routes`; it creates six named models.
The supplied reference image drove the formal stone-and-iron entry, circular
fountain arrival, east-side pool and court, southeast fire lounge, and lake pavilion.
All coordinates and dimensions below are metres in the project world frame.

## Included features

| Model | Composition and details | Collision behavior |
|---|---|---|
| `estate_entrance` | Stone piers with caps, warm lantern details, wrought-iron pickets with brass finials, stone wings, THE SUMMIT / ESTATE signage, cypress planting and flower planters | Open leaves run parallel to the approach. Minimum gap is 12.1 m at the pier bases and 12.6 m between the piers. Piers, rails, pickets, trunks and planters collide. |
| `estate_arrival` | 26–37 m annular asphalt drive, paving bands and curb, 12 m fountain, three basins, 49 jet/plume/spill streams, clipped shrubs and cypresses, broad north entry path | Drive, fountain structure and paving collide. Fountain water, jets, flowers and fine foliage are visual only. |
| `estate_pool` | Recessed 36 × 20 m pool, five broad underwater entry steps, four separate basin walls, coping, large stone deck, six loungers with tables, two furnished cabanas, flower planters and a link to the villa | Floor, walls, steps, coping, deck, cabanas and furniture frames collide. Water at z79.9 has no collision. |
| `estate_basketball` | Navy court with contrasting keys; boundary, centre line/circle, free-throw lines and semicircles, dashed inner arcs, three-point arcs and corners, no-charge arcs, lane ticks; two glazed backboards, rims and nets; perimeter fence and benches | Court floor, hoop structure, rails/posts and benches collide. Painted markings, net strands and fine fence detail are visual only. |
| `estate_fire_lounge` | Circular paved terrace, stone fire bowl and hearth, sculpted coals/flames, six three-seat sofas, side tables and ornamental planters | Structure and furniture collide. Fire and fine cushions/foliage are visual only. |
| `estate_lake_pavilion` | Wood dock and walkway, piles, deck joints, open timber pavilion with hipped roof, facing sofas and table, outer rails and overhead warm panel | Platform, walkway, piles, posts, roof, rails and furniture collide. The east walkway opening is clear. |

The court uses a 28 × 15 m playing area inside the supplied 32 × 19 m runoff
surface, 5 cm lines, 6.75 m three-point outer radius, and 3.05 m rim height above
the court surface. Marking dimensions were checked against the [FIBA Official
Basketball Rules 2024 court diagram](https://assets.fiba.basketball/image/upload/documents-corporate-fiba-official-rules-2024-v10a.pdf).

## Terrain and architecture integration

- Pool excavation: horizontal bounds **[148.3, 185.7, 138.3, 159.7]**, terrain
  height **77.3**. The floor collision spans the entire basin, bottom **77.34**,
  top **77.7**. The water plane is **79.9**. Terrain must use the returned
  excavation; leaving the plateau underneath would falsely fill the basin.
- Pool deck occupies **x132..202, y128..172**, with an actual central opening.
  Its top is **80.18**; coping tops are **80.23**. The villa link meets the east
  facade at **x126, y149**, top **80.2**.
- Arrival loop is centred on **(78,58,80)**. The entry walk is **x72..84,
  y92..115**, top **80.2**, and ends at the supplied **(78,115,80.2)** villa sill.
- The reserved basement access corridor **x8..30, y125..153** remains clear of
  amenity structures. Main entry airspace **x75..81, y95..115, above z81** is clear.
- Pavilion platform is centred on **(-75,100)**, top **49.55**. Its 4.5 m wide
  walkway reaches **(-45,100,49.55)**, which is also returned as `shore_connection`.
  The terrain controller confirmed a matching shore connection. Pavilion clear
  height to the eave underside is **3.6 m**.
- Entrance uses the supplied **(-185,-390,26.4)** gate location. Approach planters
  follow the road's local rise; the road is left open through the gate.

Three short air routes are returned for the open gate, villa approach and dock
approach. These routes describe amenity clearance; final terrain and villa route
checks belong to the integrated world validation.

## Geometry inventory

The following counts are from an in-memory build with the checked-in estate config.
The shared exporter batches all visual objects again by model and material.

| Model | Scene objects | Collidable objects | Explicit mesh triangles |
|---|---:|---:|---:|
| Entrance | 85 | 72 | 4,534 |
| Arrival | 35 | 26 | 21,424 |
| Pool | 59 | 52 | 1,630 |
| Basketball | 43 | 38 | 2,464 |
| Fire lounge | 37 | 30 | 4,178 |
| Lake pavilion | 34 | 30 | 294 |
| Total | 293 | 248 | 34,524 |

Explicit mesh triangle counts exclude triangles the exporter later creates for
box and cylinder visuals. Water jets, shrubs, flowers, cushions, painted lines,
fence detail, deck joints and net strands are collected by material, rather than
creating one object for each small detail. Physical structure uses simple boxes,
cylinders and ring meshes, with exact open basin/deck geometry.

## Verification

Command: `python3 -m unittest discover -s tests -p test_amenities.py -v`

Result: **8 tests passed** against the real shared `Scene` implementation.

The tests check:

1. Pool water is noncollidable, the floor is recessed and collidable, excavation
   covers the basin, and the central water column has no obstruction.
2. The gate leaves are open and the full 12 m approach passage is unobstructed.
3. The west basement corridor and main entry approach remain clear.
4. The court has the required dimensions, markings, two hoops and a collision floor.
5. The annular arrival and three-basin fountain exist with visual-only water.
6. Required amenities exist and the pavilion includes a usable collision platform.
7. Every explicit mesh has finite vertices, valid indices and nondegenerate triangles.
8. Court paint triangles face upward, including arcs and both colored keys.

The initial seven tests were observed failing before the builder existed. The
eighth test was observed failing on reversed arc faces; extending it to the key
paint exposed the mirrored east-key winding as well. Both were corrected and the
complete eight-test suite passed afterward.

This module has not exported the full scene or launched Gazebo independently,
per the integration assignment. Final Gazebo loading and rendered visual
inspection are handled by the controller. Fountain streams and fire are static
geometry; water has no hydrodynamics, matching the agreed dry-physics design.
