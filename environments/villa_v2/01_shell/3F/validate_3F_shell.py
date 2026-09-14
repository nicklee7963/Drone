"""Independent geometry and alignment audit for the third-floor shell."""
import bpy
import bmesh
import hashlib
import json
import math
import sys
from pathlib import Path
from mathutils import Vector

OUT = Path(__file__).resolve().parent
ROOT = OUT.parent
TWO_F_BLEND = ROOT / '2F' / '2F_shell.blend'
SX, SY = 35.6 / 954.0, 22.8 / 648.0
CX, CY = 585.0, 513.0
EXPECTED_READONLY_SHA256 = {
    '1F/1F_shell.blend': '7a91e92129e1fa5d5ff155ccc80027de38b345c1a6f23173fac3a9980dbfb230',
    '2F/2F_shell.blend': '2e72436177fc4cc9fd8d8db4f6b9ffa42d0b9364941480874ce8612991159b46',
    '1F/1F.png': 'f40aa2ea503d22a7e08a013d72ad6e715d2e6d1c3933884dde9bbe3a8eaf0e13',
    '2F/2F.png': '1ed9ca6adba94b5af9bbc8d28b05baeeeab93663743cd52ac865bace3596c41e',
}

CHECKS = []


def check(name, passed, detail=None):
    CHECKS.append({'name': name, 'pass': bool(passed), 'detail': detail})


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def xy(px, py):
    return (px - CX) * SX, (CY - py) * SY


def world_rect(rect):
    x0, y1 = xy(rect[0], rect[1])
    x1, y0 = xy(rect[2], rect[3])
    return x0, y0, x1, y1


def line_bounds(a, b, thickness):
    x0, y0 = xy(*a)
    x1, y1 = xy(*b)
    if abs(x1 - x0) < 1e-8:
        return [x0 - thickness / 2, min(y0, y1), x0 + thickness / 2, max(y0, y1)]
    return [min(x0, x1), y0 - thickness / 2, max(x0, x1), y0 + thickness / 2]


def object_xyxy(obj):
    ob = bounds(obj)
    return [ob[0][0], ob[1][0], ob[0][1], ob[1][1]]


def bounds(obj):
    pts = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    return [[min(p[i] for p in pts), max(p[i] for p in pts)] for i in range(3)]


def inspect_live_2f_stair():
    with bpy.data.libraries.load(str(TWO_F_BLEND), link=False) as (available, loaded):
        assert '2F_Stair_UpTo3F' in available.objects
        assert '2F_Connection_3F' in available.objects
        loaded.objects = ['2F_Stair_UpTo3F', '2F_Connection_3F']
    temp = bpy.data.collections.new('__TEMP_2F_ALIGNMENT__')
    bpy.context.scene.collection.children.link(temp)
    for obj in loaded.objects:
        temp.objects.link(obj)
    bpy.context.view_layer.update()
    objects = {obj.name: obj for obj in loaded.objects}
    stair = objects['2F_Stair_UpTo3F']
    connection = objects['2F_Connection_3F']
    stair_bounds = bounds(stair)
    result = {
        'bounds_xyxy_m': [stair_bounds[0][0], stair_bounds[1][0],
                          stair_bounds[0][1], stair_bounds[1][1]],
        'metadata_bounds_xyxy_m': [float(stair['xmin']), float(stair['start_y']),
                                    float(stair['xmax']), float(stair['end_y'])],
        'terminal_elevation_m': float(stair['terminal_elevation_m']),
        'landing_depth_m': float(stair['landing_depth_m']),
        'direction': stair['direction'],
        'connection_xyz_m': list(connection.location),
    }
    for obj in objects.values():
        bpy.data.objects.remove(obj, do_unlink=True)
    bpy.data.collections.remove(temp)
    return result


def validate_manifold(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    boundary = sum(not edge.is_manifold for edge in bm.edges)
    volume = bm.calc_volume(signed=True)
    bm.free()
    return boundary, volume


def mesh_components(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    unseen = set(bm.verts)
    count = 0
    while unseen:
        count += 1
        stack = [unseen.pop()]
        while stack:
            vert = stack.pop()
            for edge in vert.link_edges:
                other = edge.other_vert(vert)
                if other in unseen:
                    unseen.remove(other)
                    stack.append(other)
    bm.free()
    return count


def mesh_signature(obj):
    coords = []
    for vert in obj.data.vertices:
        point = obj.matrix_world @ vert.co
        coords.append(tuple(round(point[i], 6) for i in range(3)))
    return tuple(sorted(coords)), len(obj.data.polygons)


def footprint_data(obj):
    try:
        rects = json.loads(obj.get('footprint_rectangles_world', '[]'))
        cuts = json.loads(obj.get('subtracted_rectangles_world', '[]'))
    except (TypeError, json.JSONDecodeError):
        return [], []
    return rects, cuts


def footprint_contains(obj, x, y):
    rects, cuts = footprint_data(obj)
    inside = any(r[0] - 1e-8 <= x <= r[2] + 1e-8 and
                 r[1] - 1e-8 <= y <= r[3] + 1e-8 for r in rects)
    cut = any(r[0] + 1e-8 < x < r[2] - 1e-8 and
              r[1] + 1e-8 < y < r[3] - 1e-8 for r in cuts)
    return inside and not cut


def positive_xy_overlap(a, b):
    ar, ac = footprint_data(a)
    br, bc = footprint_data(b)
    xs = sorted(set(v for rect in ar + ac + br + bc for v in (rect[0], rect[2])))
    ys = sorted(set(v for rect in ar + ac + br + bc for v in (rect[1], rect[3])))
    for i in range(len(xs) - 1):
        for j in range(len(ys) - 1):
            x = (xs[i] + xs[i + 1]) / 2
            y = (ys[j] + ys[j + 1]) / 2
            if footprint_contains(a, x, y) and footprint_contains(b, x, y):
                return (xs[i + 1] - xs[i]) * (ys[j + 1] - ys[j])
    return 0.0


def bbox_gap_xy(a, b):
    aa, bb = bounds(a), bounds(b)
    dx = max(aa[0][0] - bb[0][1], bb[0][0] - aa[0][1], 0.0)
    dy = max(aa[1][0] - bb[1][1], bb[1][0] - aa[1][1], 0.0)
    return math.hypot(dx, dy)


def blocker_at(objects, x, y):
    return [obj.name for obj in objects if footprint_contains(obj, x, y)]


def geometry_contains_xy(obj, x, y):
    inverse = obj.matrix_world.inverted()
    origin = inverse @ Vector((x, y, 10.0))
    direction = inverse.to_3x3() @ Vector((0.0, 0.0, -1.0))
    hit, _, _, _ = obj.ray_cast(origin, direction)
    return bool(hit)


def geometry_blocker_at(objects, x, y):
    return [obj.name for obj in objects if geometry_contains_xy(obj, x, y)]


def run():
    global CHECKS
    CHECKS = []
    scene = bpy.context.scene
    meshes = [obj for obj in scene.objects if obj.type == 'MESH' and obj.get('shell_geometry')]
    required = ['3F_Floor_Main', '3F_Terrace_Private', '3F_Opening_From2F',
                '3F_Connection_2F', '3F_Camera_Top_Orthographic']

    check('Blender file opens with expected 3F scene', scene.get('floor_id') == '3F', scene.get('floor_id'))
    check('Scene uses meters at unit scale 1', scene.unit_settings.system == 'METRIC' and
          abs(scene.unit_settings.scale_length - 1.0) < 1e-9)
    check('Required floor, terrace, stair interface, and top camera exist',
          all(name in bpy.data.objects for name in required), required)
    check('Expected architectural mesh count is nonzero', len(meshes) > 0, len(meshes))
    check('All architectural object scales are unit',
          all(max(abs(value - 1.0) for value in obj.scale) < 1e-7 for obj in meshes))
    names = [obj.name for obj in scene.objects]
    check('No duplicate object names', len(names) == len(set(names)))
    banned = ('bed', 'sofa', 'chair', 'tub', 'toilet', 'vanity', 'furniture', 'decor', 'appliance', 'landscape')
    check('No furniture, fixtures, or decorative geometry',
          not [obj.name for obj in meshes if any(word in obj.name.lower() for word in banned)])
    check('No ceiling or other-floor room geometry',
          not [obj.name for obj in meshes if 'ceiling' in obj.name.lower() or
               obj.name.startswith(('1F_', '2F_', 'B1_'))])

    top = bpy.data.objects.get('3F_Camera_Top_Orthographic')
    check('Saved top camera is truly orthographic', bool(top and top.type == 'CAMERA' and
          top.data.type == 'ORTHO' and abs(top.rotation_euler.x) < 1e-7 and
          abs(top.rotation_euler.y) < 1e-7),
          {'type': top.data.type if top else None,
           'rotation': list(top.rotation_euler) if top else None})
    reference = bpy.data.objects.get('3F_Reference_Plan')
    check('Calibrated 3F source image is packed and locked', bool(reference and reference.data and
          reference.data.packed_file and reference.hide_render and all(reference.lock_location) and
          all(reference.lock_scale)))

    overall = [[0.0, 0.0] for _ in range(3)]
    if meshes:
        overall = [[min(bounds(obj)[i][0] for obj in meshes),
                    max(bounds(obj)[i][1] for obj in meshes)] for i in range(3)]
    dims = [hi - lo for lo, hi in overall]
    check('XY bounds remain on the established villa coordinate frame', bool(meshes and
          -21.0 < overall[0][0] < -15.0 and 15.0 < overall[0][1] < 21.0 and
          -15.0 < overall[1][0] < -8.0 and 7.0 < overall[1][1] < 13.0), overall[:2])
    check('Z bounds keep local finished floor near zero', bool(meshes and
          overall[2][0] >= -0.201 and overall[2][0] <= -0.19 and
          abs(overall[2][1] - 3.2) < 1e-5), overall[2])

    floors = [obj for obj in meshes if obj.get('element_type') in {'floor', 'terrace'}]
    slab_ranges = {obj.name: bounds(obj)[2] for obj in floors}
    check('All floor and terrace slabs span Z=-0.20..0.00 m', bool(floors and all(
          abs(z[0] + .2) < 1e-5 and abs(z[1]) < 1e-5 for z in slab_ranges.values())), slab_ranges)
    main_floor = bpy.data.objects.get('3F_Floor_Main')
    terrace_floor = bpy.data.objects.get('3F_Terrace_Private')
    floor_components = {obj.name: mesh_components(obj) for obj in (main_floor, terrace_floor) if obj}
    check('Main walkable slab and private terrace are each continuous connected meshes',
          len(floor_components) == 2 and all(value == 1 for value in floor_components.values()),
          floor_components)
    slab_overlap = (positive_xy_overlap(main_floor, terrace_floor)
                    if main_floor and terrace_floor else 999.0)
    check('Main floor and terrace meet without duplicate coplanar slab area',
          slab_overlap < 1e-8, {'positive_overlap_m2': slab_overlap})
    independent_slab_bounds = {
        '3F_Floor_Main': list(world_rect((82, 305, 1058, 785))),
        '3F_Terrace_Private': list(world_rect((104, 176, 1038, 305))),
    }
    slab_bound_errors = {}
    for name, expected in independent_slab_bounds.items():
        obj = bpy.data.objects.get(name)
        actual = object_xyxy(obj) if obj else []
        slab_bound_errors[name] = {
            'actual_xyxy_m': actual, 'expected_xyxy_m': expected,
            'max_error_m': max((abs(a - b) for a, b in zip(actual, expected)), default=999.0),
        }
    check('Floor and terrace outer bounds match independent source-plan extents',
          all(item['max_error_m'] < 5e-6 for item in slab_bound_errors.values()),
          slab_bound_errors)
    physical_stairs = [obj.name for obj in meshes if obj.get('element_type') == 'stair']
    check('No duplicate physical stair or invented upward stair exists in 3F',
          not physical_stairs, physical_stairs)

    live_stair = inspect_live_2f_stair()
    opening = bpy.data.objects.get('3F_Opening_From2F')
    opening_metadata_bounds = json.loads(opening.get('bounds_world_m', '[]')) if opening else []
    opening_bounds = ([opening.location.x - abs(opening.scale.x),
                       opening.location.y - abs(opening.scale.y),
                       opening.location.z - abs(opening.scale.z),
                       opening.location.x + abs(opening.scale.x),
                       opening.location.y + abs(opening.scale.y),
                       opening.location.z + abs(opening.scale.z)] if opening else [])
    actual_stair_xy = ([opening_bounds[0], opening_bounds[1], opening_bounds[3], opening_bounds[4]]
                       if len(opening_bounds) == 6 else [])
    stair_errors = [abs(a - b) for a, b in zip(actual_stair_xy, live_stair['bounds_xyxy_m'])]
    stair_error = max(stair_errors, default=999.0)
    check('3F stair aperture exactly matches live 2F_Stair_UpTo3F XY bounds', stair_error < 1e-6,
          {'3F': actual_stair_xy, '2F': live_stair['bounds_xyxy_m'], 'max_error_m': stair_error})
    live_metadata_error = max(abs(a - b) for a, b in zip(
        live_stair['bounds_xyxy_m'], live_stair['metadata_bounds_xyxy_m']))
    opening_metadata_error = max((abs(a - b) for a, b in zip(
        opening_bounds, opening_metadata_bounds)), default=999.0)
    check('Stair alignment metadata agrees with both evaluated object transforms',
          live_metadata_error < 1e-6 and opening_metadata_error < 1e-6,
          {'2F_mesh_vs_metadata_error_m': live_metadata_error,
           '3F_transform_vs_metadata_error_m': opening_metadata_error})
    check('2F stair terminates at the 3F finished-floor datum after assembly',
          abs(live_stair['terminal_elevation_m'] - 3.2) < 1e-7 and
          live_stair['direction'] == 'north (+Y), up to 3F', live_stair)
    connection = bpy.data.objects.get('3F_Connection_2F')
    expected_north_arrival = [(live_stair['bounds_xyxy_m'][0] + live_stair['bounds_xyxy_m'][2]) / 2,
                              live_stair['bounds_xyxy_m'][3], 0.0]
    connection_error = (math.dist(list(connection.location), expected_north_arrival)
                        if connection else 999.0)
    check('3F connection marker is centered at the source-drawn north stair arrival',
          connection_error < 1e-6,
          {'3F_local': list(connection.location) if connection else None,
           'expected_north_arrival': expected_north_arrival,
           'undocumented_2F_marker': live_stair['connection_xyz_m'],
           'north_arrival_error_m': connection_error})
    if connection:
        exit_samples = [(connection.location.x, connection.location.y + distance)
                        for distance in (.05, .15, .35)]
        exit_solids = [obj for obj in meshes if obj.get('element_type') in {'wall', 'column', 'glass'}]
        landing_exit_blockers = {str(distance): geometry_blocker_at(exit_solids, x, y)
                                 for distance, (x, y) in zip((.05, .15, .35), exit_samples)}
    else:
        exit_samples = []
        landing_exit_blockers = {'missing_connection': ['3F_Connection_2F']}
    check('Source-drawn north stair arrival remains physically open on 3F',
          all(not value for value in landing_exit_blockers.values()), landing_exit_blockers)
    if len(actual_stair_xy) == 4:
        sx0, sy0, sx1, sy1 = actual_stair_xy
        samples = [(sx0 + (sx1 - sx0) * u, sy0 + (sy1 - sy0) * v)
                   for u in (.15, .5, .85) for v in (.15, .5, .85)]
        covered = [(obj.name, x, y) for obj in floors for x, y in samples
                   if geometry_contains_xy(obj, x, y)]
    else:
        samples, covered = [], [('missing opening', 0, 0)]
    check('No 3F slab covers the live 2F stair aperture', not covered, covered)

    wall_ranges = {}
    wall_thicknesses = {'exterior': [], 'stairwell': []}
    for obj in meshes:
        if obj.get('element_type') == 'wall':
            wall_ranges[obj.name] = bounds(obj)[2]
            wall_thicknesses.setdefault(obj.get('wall_class', 'unknown'), []).append(
                float(obj.get('nominal_thickness_m', 0)))
    check('Walls span Z=0.00..3.20 m', bool(wall_ranges and all(
          abs(z[0]) < 1e-5 and abs(z[1] - 3.2) < 1e-5 for z in wall_ranges.values())), wall_ranges)
    check('Exterior wall segments use nominal 0.28 m thickness', bool(wall_thicknesses['exterior'] and
          all(abs(v - .28) < 1e-7 for v in wall_thicknesses['exterior'])), wall_thicknesses['exterior'])
    check('Stairwell walls use nominal 0.22 m thickness', bool(wall_thicknesses['stairwell'] and
          all(abs(v - .22) < 1e-7 for v in wall_thicknesses['stairwell'])), wall_thicknesses['stairwell'])
    interior = [obj.name for obj in meshes if obj.name.startswith('3F_Wall_Interior_')]
    check('No unsupported interior partitions were added', not interior, interior)

    # Architectural perimeter checks use constants independently transcribed
    # from 3F.png, not builder-authored schedules or footprint properties.
    exterior_sources = {
        '3F_Wall_Exterior_001_NorthWest_Side': ((82, 305, 100, 357), 'W'),
        '3F_Wall_Exterior_002_NorthEast_Side': ((1039, 305, 1058, 357), 'E'),
        '3F_Wall_Exterior_003_SouthWest_DownReturn': ((112, 692, 136, 770), 'E'),
        '3F_Wall_Exterior_004_SouthEast_DownReturn': ((1009, 692, 1032, 770), 'W'),
    }
    expected_wall_bounds = {}
    for name, (source, anchor) in exterior_sources.items():
        x0, py0, x1, py1 = map(float, source)
        pixels = .28 / SX
        if anchor == 'W':
            x1 = x0 + pixels
        else:
            x0 = x1 - pixels
        expected_wall_bounds[name] = list(world_rect((x0, py0, x1, py1)))
    sx0, sy0, sx1, sy1 = live_stair['bounds_xyxy_m']
    south_y = xy(0, 770)[1]
    expected_wall_bounds.update({
        '3F_Wall_Stair_001_From2F_West': [sx0 - .22, sy0, sx0, sy1],
        '3F_Wall_Stair_002_From2F_East': [sx1, sy0, sx1 + .22, sy1],
        '3F_Wall_Exterior_005_Arrival_West_Return':
            [xy(562, 0)[0], south_y - .14, sx0 - .22, south_y + .14],
        '3F_Wall_Exterior_006_Arrival_East_Return':
            [sx1 + .22, south_y - .14, xy(729, 0)[0], south_y + .14],
    })
    wall_trace_errors = {}
    for name, expected in expected_wall_bounds.items():
        obj = bpy.data.objects.get(name)
        actual = object_xyxy(obj) if obj else []
        wall_trace_errors[name] = {
            'actual_xyxy_m': actual, 'expected_xyxy_m': expected,
            'max_error_m': max((abs(a - b) for a, b in zip(actual, expected)), default=999.0),
        }
    check('All exterior and stair wall runs match independent source/alignment bounds',
          len(wall_ranges) == len(expected_wall_bounds) and
          all(item['max_error_m'] < 1e-6 for item in wall_trace_errors.values()),
          wall_trace_errors)

    corner_samples = {
        'northwest': xy(116, 289), 'northeast': xy(1026, 289),
        'southwest': xy(116, 668), 'southeast': xy(1026, 668),
    }
    opaque = [obj for obj in meshes if obj.get('element_type') in {'wall', 'column'}]
    corner_coverage = {name: geometry_blocker_at(opaque, *point) for name, point in corner_samples.items()}
    check('All four source-drawn opaque facade corner blocks are structurally continuous',
          all(corner_coverage.values()), corner_coverage)

    terrace_piers = [obj for obj in meshes if obj.name.startswith(
        ('3F_Column_001_Terrace_', '3F_Column_002_Terrace_',
         '3F_Column_003_Terrace_', '3F_Column_004_Terrace_'))]
    terrace_pier_ranges = {obj.name: bounds(obj)[2] for obj in terrace_piers}
    check('All four private-terrace wall piers match the 1.10 m glass guard height',
          len(terrace_piers) == 4 and all(
              abs(z[0]) < 1e-5 and abs(z[1] - 1.10) < 1e-5
              for z in terrace_pier_ranges.values()),
          terrace_pier_ranges)
    other_columns = [obj for obj in meshes if obj.get('element_type') == 'column'
                     and obj not in terrace_piers]
    other_column_ranges = {obj.name: bounds(obj)[2] for obj in other_columns}
    check('All non-terrace structural columns remain at 3.20 m',
          bool(other_columns) and all(
              abs(z[0]) < 1e-5 and abs(z[1] - 3.20) < 1e-5
              for z in other_column_ranges.values()),
          other_column_ranges)

    glass = [obj for obj in meshes if obj.get('element_type') == 'glass']
    glass_dims = [(obj.name, float(obj.get('nominal_thickness_m', 0)), bounds(obj)[2]) for obj in glass]
    check('Full-height glazing is separate, 0.020 m thick, and 3.20 m high', bool(glass and all(
          abs(thickness - .02) < 1e-7 and abs(z[0]) < 1e-5 and abs(z[1] - 3.2) < 1e-5
          for _, thickness, z in glass_dims)), glass_dims)
    expected_glass_lines = {
        '3F_Glass_001_MasterNorth_West': ((143, 305), (544, 305)),
        '3F_Glass_002_MasterNorth_East': ((623, 305), (1002, 305)),
        '3F_Glass_003_FacadeWest_North': ((88, 357), (88, 493)),
        '3F_Glass_004_FacadeWest_South': ((88, 531), (88, 642)),
        '3F_Glass_005_FacadeEast_North': ((1051, 357), (1051, 493)),
        '3F_Glass_006_FacadeEast_South': ((1051, 531), (1051, 642)),
        '3F_Glass_007_SouthWest_Outer': ((136, 770), (364, 770)),
        '3F_Glass_008_SouthWest_Inner': ((391, 770), (562, 770)),
        '3F_Glass_009_SouthEast_Inner': ((729, 770), (772, 770)),
        '3F_Glass_010_SouthEast_Outer': ((798, 770), (1009, 770)),
    }
    glass_trace_errors = {}
    for name, (a, b) in expected_glass_lines.items():
        obj = bpy.data.objects.get(name)
        actual = object_xyxy(obj) if obj else []
        expected = line_bounds(a, b, .020)
        glass_trace_errors[name] = {
            'actual_xyxy_m': actual, 'expected_xyxy_m': expected,
            'max_error_m': max((abs(v - e) for v, e in zip(actual, expected)), default=999.0),
        }
    check('All ten glazing runs match independent source-plan bounds',
          len(glass) == len(expected_glass_lines) and
          all(item['max_error_m'] < 1e-6 for item in glass_trace_errors.values()),
          glass_trace_errors)
    rail_glass = [obj for obj in meshes if obj.get('element_type') == 'railing_glass']
    rail_top = [obj for obj in meshes if obj.get('element_type') == 'railing_toprail']
    check('Private terrace outer edge has 1.10 m collision guardrails', bool(rail_glass and rail_top and
          len(rail_glass) == len(rail_top) and all(abs(float(obj.get('guardrail_height_m', 0)) - 1.1) < 1e-7
          for obj in rail_glass + rail_top)), {'glass': len(rail_glass), 'toprails': len(rail_top)})

    # Independent source-trace spot checks for the stepped terrace edge.  These
    # deliberately inspect evaluated geometry rather than generated metadata.
    terrace_samples_px = {
        'west_side_inside': (250, 220),
        'west_side_north_outside': (250, 190),
        'center_projection_inside': (580, 190),
        'center_projection_north_outside': (580, 165),
        'east_side_inside': (900, 220),
        'east_side_north_outside': (900, 190),
    }
    terrace_sample_hits = {name: geometry_contains_xy(terrace_floor, *xy(*point))
                           if terrace_floor else False
                           for name, point in terrace_samples_px.items()}
    expected_hits = {
        'west_side_inside': True, 'west_side_north_outside': False,
        'center_projection_inside': True, 'center_projection_north_outside': False,
        'east_side_inside': True, 'east_side_north_outside': False,
    }
    check('Private terrace slab preserves the source-drawn stepped north projection',
          terrace_sample_hits == expected_hits,
          {'source_pixel_samples': terrace_samples_px, 'actual_hits': terrace_sample_hits})

    expected_column_rects = {
        '3F_Column_002_Terrace_CenterWest': (363, 176, 397, 221),
        '3F_Column_003_Terrace_CenterEast': (762, 176, 798, 221),
    }
    column_trace_errors = {}
    for name, source_rect in expected_column_rects.items():
        obj = bpy.data.objects.get(name)
        actual = ([bounds(obj)[0][0], bounds(obj)[1][0],
                   bounds(obj)[0][1], bounds(obj)[1][1]] if obj else [])
        expected = list(world_rect(source_rect))
        column_trace_errors[name] = {
            'actual_xyxy_m': actual, 'expected_xyxy_m': expected,
            'max_error_m': max((abs(a - b) for a, b in zip(actual, expected)), default=999.0),
        }
    check('Central terrace columns match the source-traced projected blocks',
          all(item['max_error_m'] < 1e-6 for item in column_trace_errors.values()),
          column_trace_errors)

    expected_rail_lines = {
        '3F_Railing_Terrace_NorthWest': ((129, 210), (363, 210)),
        '3F_Railing_Terrace_NorthCenter': ((397, 176), (762, 176)),
        '3F_Railing_Terrace_NorthEast': ((798, 210), (1014, 210)),
    }
    rail_trace_errors = {}
    for name, (a, b) in expected_rail_lines.items():
        obj = bpy.data.objects.get(name)
        ob = bounds(obj) if obj else None
        expected_x = sorted((xy(*a)[0], xy(*b)[0]))
        expected_y = xy(*a)[1]
        # Railing panels have a deliberate 15 mm end inset and 20 mm thickness.
        expected = [expected_x[0] + .015, expected_y - .010,
                    expected_x[1] - .015, expected_y + .010]
        actual = [ob[0][0], ob[1][0], ob[0][1], ob[1][1]] if ob else []
        rail_trace_errors[name] = {
            'actual_xyxy_m': actual, 'expected_xyxy_m': expected,
            'max_error_m': max((abs(v - e) for v, e in zip(actual, expected)), default=999.0),
        }
    check('Terrace guardrail segments follow all three stepped source edges',
          all(item['max_error_m'] < 1e-6 for item in rail_trace_errors.values()),
          rail_trace_errors)

    opening_schedule = json.loads(scene.get('opening_schedule_json', '[]'))
    classes = [item.get('classification') for item in opening_schedule]
    check('Opening schedule classifies one doorway and one stair opening',
          classes.count('intentional_doorway') == 1 and classes.count('stair_opening') == 1 and
          len(classes) == 2, opening_schedule)
    blockers = [obj for obj in meshes if obj.get('element_type') in {'wall', 'column', 'glass'}]
    independent_opening_samples = {
        'PrivateTerrace_DoubleDoor': xy((544 + 623) / 2, 305),
        'StairArrival_From2F': ((sx0 + sx1) / 2, sy1 + .35),
    }
    opening_blockers = {name: geometry_blocker_at(blockers, *point)
                        for name, point in independent_opening_samples.items()}
    check('Both intentional openings remain physically unobstructed',
          all(not values for values in opening_blockers.values()), opening_blockers)

    junction_schedule = json.loads(scene.get('junction_schedule_json', '[]'))
    junction_clearances = {}
    missing_junction_objects = []
    for item in junction_schedule:
        a = bpy.data.objects.get(item['a'])
        b = bpy.data.objects.get(item['b'])
        if not a or not b:
            missing_junction_objects.append(item)
            continue
        junction_clearances[item['name']] = bbox_gap_xy(a, b)
    check('Every scheduled wall/column/glass junction object exists',
          not missing_junction_objects and bool(junction_schedule), missing_junction_objects)
    check('No tiny cracks remain at audited wall-to-glass and wall-to-column junctions',
          bool(junction_clearances) and max(junction_clearances.values(), default=999) <= .001,
          junction_clearances)

    solids = [obj for obj in meshes if obj.get('element_type') in {'wall', 'column', 'glass'}]
    overlaps = []
    for index, a in enumerate(solids):
        for b in solids[index + 1:]:
            area = positive_xy_overlap(a, b)
            if area > 1e-7:
                overlaps.append({'objects': [a.name, b.name], 'area_m2': area})
    check('No positive-area structural or glazing overlaps', not overlaps, overlaps)

    manifold = {obj.name: validate_manifold(obj) for obj in meshes}
    check('All architectural meshes are closed with positive signed volume',
          all(edges == 0 and volume > 1e-8 for edges, volume in manifold.values()),
          {name: values for name, values in manifold.items() if values[0] or values[1] <= 1e-8})
    disconnected_walls = {obj.name: mesh_components(obj) for obj in meshes
                          if obj.get('element_type') == 'wall' and mesh_components(obj) != 1}
    check('No wall object contains disconnected structural fragments', not disconnected_walls,
          disconnected_walls)
    supporting_slabs = [obj for obj in floors]
    floating = []
    for obj in [o for o in meshes if o.get('element_type') in {'wall', 'column', 'glass'}]:
        ob = bounds(obj)
        center = ((ob[0][0] + ob[0][1]) / 2, (ob[1][0] + ob[1][1]) / 2)
        if not any(geometry_contains_xy(slab, *center) for slab in supporting_slabs):
            floating.append(obj.name)
    check('No walls, columns, or glazing float away from a slab footprint', not floating, floating)

    signatures = {}
    duplicates = []
    for obj in meshes:
        signature = mesh_signature(obj)
        if signature in signatures:
            duplicates.append([signatures[signature], obj.name])
        signatures[signature] = obj.name
    check('No duplicate architectural meshes', not duplicates, duplicates)

    actual_sha = {name: sha(ROOT / name) for name in EXPECTED_READONLY_SHA256}
    check('1F and 2F source/model files remain byte-identical',
          actual_sha == EXPECTED_READONLY_SHA256,
          {'expected': EXPECTED_READONLY_SHA256, 'actual': actual_sha})

    render_names = ['3F_shell_top.png', '3F_shell_perspective_corner.png']
    build_started = float(scene.get('build_started_unix_s', 0.0))
    render_status = {
        name: {
            'exists': (OUT / name).exists(),
            'bytes': (OUT / name).stat().st_size if (OUT / name).exists() else 0,
            'modified_unix_s': (OUT / name).stat().st_mtime if (OUT / name).exists() else 0,
            'sha256': sha(OUT / name) if (OUT / name).exists() else None,
            'from_current_build': bool((OUT / name).exists() and
                                       (OUT / name).stat().st_mtime >= build_started),
        }
        for name in render_names
    }
    if '--require-renders' in sys.argv:
        check('Required validation renders exist and are nonempty',
              all(item['exists'] and item['bytes'] > 10000 and item['from_current_build']
                  for item in render_status.values()),
              render_status)

    terrace = bpy.data.objects.get('3F_Terrace_Private')
    terrace_area = 0.0
    if terrace:
        for poly in terrace.data.polygons:
            normal = terrace.matrix_world.to_3x3() @ poly.normal
            if normal.z > .9:
                terrace_area += poly.area

    result = {
        'checks': CHECKS,
        'passed': sum(item['pass'] for item in CHECKS),
        'failed': sum(not item['pass'] for item in CHECKS),
        'mesh_objects': len(meshes),
        'object_count_total': len(scene.objects),
        'triangles': sum(len(poly.vertices) - 2 for obj in meshes for poly in obj.data.polygons),
        'bounds_m': {'min': [axis[0] for axis in overall],
                     'max': [axis[1] for axis in overall], 'dimensions': dims},
        'floor_slab_ranges_m': slab_ranges,
        'wall_ranges_m': wall_ranges,
        'stair_interface': {
            'live_2f_stair_bounds_xyxy_m': live_stair['bounds_xyxy_m'],
            '3f_opening_bounds_xyzxyz_m': opening_bounds,
            '3f_opening_metadata_bounds_xyzxyz_m': opening_metadata_bounds,
            'alignment_error_m': stair_error,
            'connection_alignment_error_m': connection_error,
            'landing_exit_direction': '+Y/north',
            'landing_exit_blockers': landing_exit_blockers,
            'physical_stair_mesh_duplicated_in_3f': False,
            'raster_stair_center_x_px_approx': 584.0,
            'live_2f_stair_center_source_equivalent_x_px': 645.5,
            'documented_plan_displacement_m': (645.5 - 584.0) * SX,
        },
        'wall_audit': {
            'opening_schedule': opening_schedule,
            'intentional_opening_count': len(opening_schedule),
            'blocked_openings': opening_blockers,
            'accidental_gaps_detected': 0 if all(item['pass'] for item in CHECKS
                if item['name'].startswith(('Every scheduled wall', 'No tiny cracks'))) else 1,
            'unexplained_gaps_remaining': 0 if all(item['pass'] for item in CHECKS
                if item['name'].startswith(('Every scheduled wall', 'No tiny cracks'))) else 1,
            'junction_clearances_m': junction_clearances,
            'positive_area_overlaps': overlaps,
            'disconnected_walls': disconnected_walls,
            'floating_elements': floating,
        },
        'terrace': {
            'drawn_mesh_top_area_m2': terrace_area,
            'schedule_area_m2': 52.0,
            'area_discrepancy_m2': terrace_area - 52.0,
            'policy': 'Trace drawn full-width terrace; do not distort it to the approximate room schedule.',
        },
        'ambiguities': json.loads(scene.get('plan_ambiguities_json', '[]')),
        'readonly_sha256': actual_sha,
        'validation_images': render_status,
    }
    (OUT / '3F_shell_validation.json').write_text(json.dumps(result, indent=2))
    print(f"VALIDATION: {result['passed']} passed; {result['failed']} failed")
    for item in CHECKS:
        print(('PASS ' if item['pass'] else 'FAIL ') + item['name'])
    if result['failed']:
        raise AssertionError('3F shell validation failed; see 3F_shell_validation.json')
    return result


if __name__ == '__main__':
    run()
