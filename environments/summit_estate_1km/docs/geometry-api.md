# Geometry interface for independently authored modules

Only write your assigned module and its tests. The controller owns geometry.py, landscape.py, generate_environment.py and integration. Do not run full scene export until integration.

`from geometry import Scene` (plus math/numpy as needed).
`build_villa(scene, config) -> dict` / `build_amenities(scene, config) -> dict`.
`m = scene.model('summit_villa')` returns Model.
`m.box(name, center=(x,y,z), size=(dx,dy,dz), material='ivory', collision=True, yaw=0.0)`.
`m.cylinder(name, center, radius, length, material, collision=True, segments=20)` vertical.
`m.sphere(name, center, radii=(rx,ry,rz), material='stone', collision=True, segments=12, rings=6)`.
`m.mesh(name, vertices, faces, material, collision=False)` faces triangles; coords world.
`m.beam(name, start, end, width, material, collision=True)` arbitrary oriented square beam.
`m.ring(name, center, inner_radius, outer_radius, height, material, collision=True, segments=64)` annular solid; collision as triangle mesh.
`m.text(name, text, origin, height, material='brass', yaw=0.0)` block vector letters on vertical XZ plane, facing -Y, no collision. origin is lower-left; text width ~0.7 * height * len(text).

Material keys: ivory, plaster, charcoal, glass (transparent blue with collision where requested), stone, paving, asphalt, grass, grass_light, grass_dark, rock, wood, brass, metal, water, pool_water, court, court_key, white, sand, fabric, dark_fabric, rubber, screen, emissive, fire, leaf0, leaf1, leaf2, trunk. Add material via `scene.materials['custom'] = {'color':[r,g,b,a], 'roughness':0.7, 'metalness':0.0}` if needed.

Each Model has `.objects` list of dicts holding `name`, `kind`, `center`, `size` or `vertices`/`faces`, `material`, `collision`, `rotation`=[roll,pitch,yaw]. Exporter handles these. Do not depend on internal storage; use methods.

Return metadata dictionary. For villa include `rooms`: list of `{name, level, bounds:[xmin,xmax,ymin,ymax,zfloor,zceiling], function, ...}`, `portals`: list `{name,center:[x,y,z],width,height,normal:[nx,ny,nz]}`, `flight_routes`: list `{name,clearance_radius,waypoints:[[x,y,z],...]}`, `excavations`: list `{bounds:[xmin,xmax,ymin,ymax],z:ground_height}`, `floor_levels`.

Config: `villa` {bounds:[30,126,115,163], main_z:80.2, basement_z:74.8, upper_z:85.8, roof_z:91.4}; `arrival` {center:[78,58,80], outer_radius:37, inner_radius:26}; `pool` {center:[167,149,80], size:[36,20]}; `court` {center:[175,83,80], size:[32,19]}; `fire_lounge` {center:[166,12,80], radius:12}; `gate` {center:[-185,-390,26.4], width:12}; `lake` {center:[-190,135], radii:[165,125], water_z:49}. These numeric values are deliberate layout decisions.

Architecture should use the full big envelope with stepped/cantilevered volumes, open double-height atrium, many glazed panels/black mullions, white slab bands and furnished balcony/rooftop. Keep east pool access. Basement needs an exterior open door in WEST wall into sunken garden; return excavation up to x=8..30, y=125..153, z=74.4. Main entry centered x78,y115, opening >=6 ×4m. Upper four bedrooms with >=2m doors. Basement horizontal center hall and vertical stairwell/atrium connect all levels; use real slab holes, never invisible pass-through collisions.

Amenities may assume flat plateau z80 (gate at provided z) and must not overlap villa or reserved access corridor x=8..30,y125..153. Fountain r12 at arrival center; annular driveway handled by amenities. Court exact regulation playing lines inside 32×19 runoffs. Pool concave basin bed z77.7 and water z79.9 with actual coping and steps; report excavation for terrain. All water surfaces collision=False. Optional rooftop helipad belongs to villa module.
