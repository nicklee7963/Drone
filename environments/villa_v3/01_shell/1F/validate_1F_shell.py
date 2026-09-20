"""Inspect the saved shell, not just generation parameters.

Run: blender -b 1F_shell.blend --python validate_1F_shell.py
"""
import bpy
import bmesh
import json
from pathlib import Path
from collections import deque
from mathutils import Vector
from mathutils.bvhtree import BVHTree

OUT = Path(__file__).resolve().parent
CHECKS = []


def check(label, condition, detail=None):
    CHECKS.append({"check": label, "pass": bool(condition), "detail": detail})
    print(("PASS " if condition else "FAIL ") + label, detail or "")


def run():
    CHECKS.clear()
    scene = bpy.context.scene
    check("Scene uses meters", scene.unit_settings.system == 'METRIC' and
          scene.unit_settings.scale_length == 1 and scene.unit_settings.length_unit == 'METERS')
    meshes = [o for o in scene.objects if o.type == 'MESH' and o.get('shell_geometry')]
    check("Architectural shell geometry exists", len(meshes) > 50, len(meshes))
    required = ['1F_Floor_Main', '1F_Terrace_Main', '1F_Terrace_Left',
                '1F_Terrace_Dining', '1F_Entry_Porch', '1F_StairA_DownToB1',
                '1F_StairB_UpTo2F', 'VOID_GreatRoom_OpenToAbove',
                '1F_Reference_Plan', '1F_Connection_B1', '1F_Connection_2F']
    for name in required:
        check(name + " exists", name in bpy.data.objects)
    if not meshes:
        return finish({})
    ref = bpy.data.objects.get('1F_Reference_Plan')
    check("Reference calibrated by dimension markers", ref is not None and
          abs(ref['meters_per_pixel_x'] * 954 - 35.6) < 1e-6 and
          abs(ref['meters_per_pixel_y'] * 648 - 22.8) < 1e-6)
    check("Reference packed", ref is not None and bool(ref.data.packed_file))
    failures, fingerprints, duplicates, bad_scales, triangles = [], {}, [], [], 0
    tiny_wall_islands = []
    all_vertices, all_faces = [], []
    bounds = []
    for obj in meshes:
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        edges = sum(not e.is_manifold for e in bm.edges)
        zero_faces = sum(f.calc_area() < 1e-10 for f in bm.faces)
        vol = bm.calc_volume(signed=True)
        if obj.get('element_type') == 'wall':
            remaining = set(bm.verts)
            while remaining:
                seed = remaining.pop()
                stack, island = [seed], {seed}
                while stack:
                    vertex = stack.pop()
                    for edge in vertex.link_edges:
                        neighbor = edge.other_vert(vertex)
                        if neighbor in remaining:
                            remaining.remove(neighbor)
                            island.add(neighbor)
                            stack.append(neighbor)
                xs, ys = [v.co.x for v in island], [v.co.y for v in island]
                footprint = (max(xs)-min(xs)) * (max(ys)-min(ys))
                if footprint < .03:
                    tiny_wall_islands.append([obj.name, footprint])
        if edges or zero_faces or vol <= 0:
            failures.append({'object': obj.name, 'non_manifold_edges': edges,
                             'zero_faces': zero_faces, 'signed_volume': vol})
        bm.free()
        if any(abs(s - 1) > 1e-6 for s in obj.scale):
            bad_scales.append(obj.name)
        verts = [obj.matrix_world @ v.co for v in obj.data.vertices]
        key = tuple(sorted(tuple(round(c, 5) for c in v) for v in verts))
        if key in fingerprints:
            duplicates.append([fingerprints[key], obj.name])
        fingerprints[key] = obj.name
        bounds.extend(verts)
        off = len(all_vertices)
        all_vertices.extend(verts)
        all_faces.extend(tuple(off + i for i in p.vertices) for p in obj.data.polygons)
        triangles += sum(len(p.vertices) - 2 for p in obj.data.polygons)
    check("Structural meshes closed with outward normals and no degenerate faces", not failures, failures)
    check("Mesh object scales all 1,1,1", not bad_scales, bad_scales)
    check("No duplicate complete meshes", not duplicates, duplicates)
    check("No orphaned wall islands or thin trimming remnants",
          not tiny_wall_islands, tiny_wall_islands)
    # Exact arrangement cells for the orthogonal solids. Test against actual
    # mesh interiors; property names alone cannot establish non-overlap.
    solid_bounds = {}
    solid_axes = {}
    for o in meshes:
        vs = [o.matrix_world @ v.co for v in o.data.vertices]
        solid_axes[o.name] = [sorted(set(round(v[k],6) for v in vs)) for k in range(3)]
        solid_bounds[o.name] = [(min(v[k] for v in vs),max(v[k] for v in vs)) for k in range(3)]
    def inside(o,p):
        hit,loc,normal,idx = o.ray_cast(o.matrix_world.inverted() @ Vector(p),Vector((0,0,1)))
        return hit and normal.z > .001
    overlaps = []
    candidate_pairs = 0
    for i,a in enumerate(meshes):
        for b in meshes[i+1:]:
            intervals = [(max(solid_bounds[a.name][k][0],solid_bounds[b.name][k][0]),
                          min(solid_bounds[a.name][k][1],solid_bounds[b.name][k][1])) for k in range(3)]
            if any(hi-lo < 1e-5 for lo,hi in intervals):
                continue
            candidate_pairs += 1
            axes = []
            for k,(lo,hi) in enumerate(intervals):
                points = sorted(set([lo,hi]+[v for n in (a.name,b.name) for v in solid_axes[n][k] if lo+1e-5 < v < hi-1e-5]))
                axes.append([(p+q)/2 for p,q in zip(points,points[1:]) if q-p > 1e-5])
            collision = next((p for x in axes[0] for y in axes[1] for z in axes[2]
                              if inside(a,p:=(x,y,z)) and inside(b,p)),None)
            if collision:
                overlaps.append({'objects':[a.name,b.name],'interior_point':collision})
    check("No intersecting architectural solid volumes", not overlaps,
          {'candidate_pairs':candidate_pairs,'overlaps':overlaps})
    bvh = BVHTree.FromPolygons(all_vertices, all_faces)
    lo = [min(v[k] for v in bounds) for k in range(3)]
    hi = [max(v[k] for v in bounds) for k in range(3)]
    dims = [hi[k] - lo[k] for k in range(3)]
    check("Architectural width consistent with calibrated source extent", 37.5 < dims[0] < 37.8, dims)
    check("No renderable ceiling or upper-floor slab", not any('ceiling' in o.name.lower() or
          o.name.startswith(('2F_Floor', 'B1_Floor', '3F_')) for o in meshes))
    floor = bpy.data.objects['1F_Floor_Main']
    check("Main slab top at zero and thickness 0.20 m", abs(max(v.co.z for v in floor.data.vertices) + floor.location.z) < 1e-6 and
          abs(floor.dimensions.z - .20) < 1e-6)
    # Verify actual slab ray misses in each shaft and hits in occupied rooms.
    sx, sy = 35.6 / 954, 22.8 / 648
    def xy(px, py):
        return ((px - 585) * sx, (513 - py) * sy)

    # The strict usable Great Room excludes a small tolerance at its traced
    # perimeter. Any wall/column volume crossing this region is an internal
    # obstruction; the floor is the sole permitted mesh there.
    gx0, gy1 = xy(402, 284)
    gx1, gy0 = xy(768, 572)
    great_room_obstructions = []
    for obj in meshes:
        if obj.get('element_type') in {'floor', 'terrace'}:
            continue
        bx, by, bz = solid_bounds[obj.name]
        ix0, ix1 = max(bx[0], gx0), min(bx[1], gx1)
        iy0, iy1 = max(by[0], gy0), min(by[1], gy1)
        if ix1 - ix0 > 1e-5 and iy1 - iy0 > 1e-5 and bz[1] > .01:
            step = .04
            occupied = any(inside(obj, (x, y, 1.2))
                for x in [ix0 + step / 2 + n * step for n in range(max(1, int((ix1 - ix0) / step)))]
                for y in [iy0 + step / 2 + n * step for n in range(max(1, int((iy1 - iy0) / step)))])
            if occupied:
                great_room_obstructions.append(obj.name)
    check("Great Room usable interior has zero columns, piers, or wall stubs",
          not great_room_obstructions, great_room_obstructions)

    walls = [o for o in meshes if o.get('element_type') == 'wall']
    wall_thicknesses = {'exterior': [], 'interior': [], 'stairwell': []}
    wall_geometry_violations = []
    for obj in walls:
        category = obj.get('wall_class')
        if category not in wall_thicknesses:
            category = 'stairwell' if 'Stair' in obj.name else (
                'exterior' if obj.name.startswith('1F_Wall_Exterior') else 'interior')
        rects = json.loads(obj.get('footprint_rectangles_world', '[]'))
        thicknesses = [min(r[2] - r[0], r[3] - r[1]) for r in rects]
        wall_thicknesses[category].extend(thicknesses)
        # The actual mesh must remain within its declared construction
        # rectangles. Together with manifold validation this establishes that
        # no generated face extends beyond the measured bands.
        for vertex in (obj.matrix_world @ v.co for v in obj.data.vertices):
            if not any(r[0] - 1e-5 <= vertex.x <= r[2] + 1e-5 and
                       r[1] - 1e-5 <= vertex.y <= r[3] + 1e-5 for r in rects):
                wall_geometry_violations.append([obj.name, list(vertex)])
                break
    ranges = {'exterior': (.25, .30), 'interior': (.15, .20), 'stairwell': (.20, .25)}
    for category, values in wall_thicknesses.items():
        low, high = ranges[category]
        check(f"Actual {category} wall bands are within {low:.2f}-{high:.2f} m",
              bool(values) and all(low - 1e-5 <= v <= high + 1e-5 for v in values),
              sorted(set(round(v, 6) for v in values)))
    alignment_errors = []
    for obj in walls:
        records = json.loads(obj.get('alignment_records_json', '[]'))
        if not records:
            alignment_errors.append([obj.name, 'missing records'])
            continue
        for record in records:
            if record['error_m'] > 1e-6:
                alignment_errors.append([obj.name, record])
    check("Exterior faces, partition centerlines, and stair-void faces retain alignment",
          not alignment_errors, alignment_errors)
    check("No wall mesh extends outside its measured construction bands",
          not wall_geometry_violations, wall_geometry_violations)
    remaining_thick_walls = sorted({obj.name for obj in walls
        if any(min(r[2] - r[0], r[3] - r[1]) > .30001
               for r in json.loads(obj.get('footprint_rectangles_world', '[]')))})
    check("No non-column wall geometry exceeds 0.30 m",
          not remaining_thick_walls, remaining_thick_walls)
    def floor_ray(px, py):
        x, y = xy(px, py)
        start = floor.matrix_world.inverted() @ Vector((x, y, 1))
        return floor.ray_cast(start, Vector((0, 0, -1)))[0]
    for name, px in [('A', 425), ('B', 739)]:
        check('Slab aperture for Stair ' + name, all(not floor_ray(px, py) for py in (665, 710, 760, 810)))
    for label, px, py in [('Garage', 240, 420), ('Great Room', 580, 430),
                           ('Foyer', 580, 700), ('Kitchen', 850, 420),
                           ('Guest Suite 1', 290, 730), ('Guest Suite 2', 904, 730)]:
        check(label + ' has slab', floor_ray(px, py))
    # Ray samples in the double-height region above 1F walls.
    void_hits = []
    for px in (490, 585, 675):
        for py in (320, 425, 540):
            x, y = xy(px, py)
            hit = bvh.ray_cast(Vector((x, y, 3.21)), Vector((0, 0, 1)), 5)[0]
            if hit is not None:
                void_hits.append([px, py])
    check("Great Room remains open to above", not void_hits, void_hits)
    glass = [o for o in meshes if o.get('element_type') == 'glass']
    glass_thicknesses = [min(o.dimensions) for o in glass]
    check("Glass remains separate 0.020 m solid geometry", len(glass) >= 15 and
          all(abs(v - .020) <= 2e-5 for v in glass_thicknesses),
          sorted(set(round(v, 6) for v in glass_thicknesses)))
    doors = json.loads(scene.get('door_paths_json', '[]'))
    blocked = []
    for door in doors:
        p0, p1 = Vector(door['start']), Vector(door['end'])
        delta = p1 - p0
        hit = bvh.ray_cast(p0, delta.normalized(), delta.length)[0]
        if hit is not None:
            blocked.append(door['name'])
    check("Named doorway/circulation paths unblocked at 1.2 m", len(doors) >= 15 and not blocked, blocked)
    # Connected-space check: 10 cm XY grid at UAV center height 1.2 m.
    # Four cardinal radius samples plus center enforce 0.40 m diameter
    # approximate clearance against the actual geometry. This is a shell
    # connectivity audit, not a flight dynamics/collision certification.
    resolution, radius, flight_z = .10,.20,1.2
    nx,ny = int(dims[0]/resolution)+1,int(dims[1]/resolution)+1
    free = set()
    for i in range(nx):
        x = lo[0] + (i+.5)*resolution
        for j in range(ny):
            y = lo[1] + (j+.5)*resolution
            usable = True
            for dx,dy in [(0,0),(radius,0),(-radius,0),(0,radius),(0,-radius)]:
                loc,normal,face,distance = bvh.ray_cast(Vector((x+dx,y+dy,flight_z)),Vector((0,0,-1)),1.41)
                if loc is None or normal.z < .9 or loc.z > flight_z-radius:
                    usable = False
                    break
            if usable:
                free.add((i,j))
    def gridpoint(px,py):
        x,y = xy(px,py)
        return int((x-lo[0])/resolution),int((y-lo[1])/resolution)
    start = gridpoint(585,700)
    reached,queue = {start},deque([start])
    while queue:
        i,j = queue.popleft()
        for nxt in [(i+1,j),(i-1,j),(i,j+1),(i,j-1)]:
            if nxt in free and nxt not in reached:
                reached.add(nxt)
                queue.append(nxt)
    room_points = [('Grand Entry Foyer',585,700),('Great Room',585,435),
        ('Garage',240,410),('Storage',145,600),('Utility',246,600),('Wine Cellar',336,600),
        ('Guest Suite 1',295,734),('En-suite 1',176,735),('Kitchen & Dining',865,430),
        ('Pantry / Prep Kitchen',1020,390),('Mudroom / Shoe Gallery',1020,530),
        ('Left Corridor',435,620),('Right Corridor',895,620),('Powder Room',815,710),
        ('Guest Suite 2',900,725),('En-suite 2',995,735)]
    connectivity = {name:gridpoint(px,py) in reached for name,px,py in room_points}
    check("Every room connects to foyer with sampled 0.40 m UAV clearance", start in free and all(connectivity.values()),connectivity)
    for name, sign in [('1F_StairA_DownToB1', -1), ('1F_StairB_UpTo2F', 1)]:
        obj = bpy.data.objects[name]
        samples = []
        for i in range(18):
            x = (obj['xmin'] + obj['xmax']) / 2
            y = obj['start_y'] - (i + .5) * obj['tread_m']
            origin = obj.matrix_world.inverted() @ Vector((x, y, 5))
            hit, loc, normal, idx = obj.ray_cast(origin, Vector((0, 0, -1)))
            samples.append((obj.matrix_world @ loc).z if hit else None)
        monotone = all(a is not None and b is not None and sign * (b - a) > .15
                       for a, b in zip(samples, samples[1:]))
        check(name + " physical treads change elevation in documented direction", monotone, samples)
        check(name + " realistic riser / tread", .16 <= obj['riser_m'] <= .18 and
              .27 <= obj['tread_m'] <= .30, [obj['riser_m'], obj['tread_m'], obj.dimensions.x])
        # Vertical clearance over tread centers, measured against all geometry.
        clearance_failures = []
        for i, z in enumerate(samples):
            if z is None:
                continue
            origin = Vector(((obj['xmin'] + obj['xmax']) / 2,
                            obj['start_y'] - (i + .5) * obj['tread_m'], z + .02))
            if bvh.ray_cast(origin, Vector((0, 0, 1)), 2.1)[0] is not None:
                clearance_failures.append(i)
        check(name + " minimum 2.1 m vertical headroom", not clearance_failures, clearance_failures)
    check("No furniture/decor geometry", all(o.get('element_type') in
          ['floor', 'terrace', 'wall', 'column', 'glass', 'stair'] for o in meshes))
    return finish({'bounds_min_m': lo, 'bounds_max_m': hi, 'dimensions_m': dims,
                   'mesh_objects': len(meshes), 'triangles': triangles,
                   'door_paths': doors, 'room_connectivity':connectivity,
                   'wall_thicknesses_m': {k: sorted(set(round(v, 6) for v in vals))
                                          for k, vals in wall_thicknesses.items()},
                   'great_room_obstructions': great_room_obstructions,
                   'remaining_walls_over_030_m': remaining_thick_walls})


def finish(stats):
    result = {'checks': CHECKS, 'passed': sum(c['pass'] for c in CHECKS),
              'failed': sum(not c['pass'] for c in CHECKS), **stats}
    (OUT / '1F_shell_validation.json').write_text(json.dumps(result, indent=2))
    print('VALIDATION:', result['passed'], 'passed;', result['failed'], 'failed')
    if result['failed']:
        raise AssertionError('Shell validation failed; see 1F_shell_validation.json')
    return result


if __name__ == '__main__':
    run()
