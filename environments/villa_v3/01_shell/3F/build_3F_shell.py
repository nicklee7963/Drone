"""Build the independent third-floor villa shell from 3F.png.

The established 1F/2F source-pixel transform is reused without shifting the
floor.  The sole local reconciliation is the south stair-arrival bay: its slab
aperture is taken from the live 2F_Stair_UpTo3F mesh rather than the displaced
stair graphic in 3F.png.

Usage:
    blender -b --factory-startup --python-exit-code 1 --python build_3F_shell.py
    blender -b --factory-startup --python-exit-code 1 --python build_3F_shell.py -- --skip-renders
"""
import bpy
import bmesh
import json
import math
import sys
import time
from pathlib import Path
from mathutils import Vector

OUT = Path(__file__).resolve().parent
IMAGE = OUT / '3F.png'
BLEND = OUT / '3F_shell.blend'
TWO_F_BLEND = OUT.parent / '2F' / '2F_shell.blend'

SX, SY = 35.6 / 954.0, 22.8 / 648.0
CX, CY = 585.0, 513.0
WALL_HEIGHT = 3.2
SLAB_THICKNESS = .20
EXTERIOR_WALL_THICKNESS = .28
STAIRWELL_WALL_THICKNESS = .22
GLASS_THICKNESS = .020
RAILING_GLASS_THICKNESS = .020
RAILING_GLASS_HEIGHT = 1.05
RAILING_HEIGHT = 1.10
RAILING_TOPRAIL_WIDTH = .040
RAILING_END_INSET = .015

# These source-equivalent values are verified against the live 2F blend before
# construction.  They are never inferred from the displaced 3F stair symbol.
STAIR_FROM_2F = (607.0, 676.0, 684.0, 817.0)
DRAWN_3F_STAIR_CENTER_X_PX = 584.0
STAIR_RECONCILIATION_SHIFT_PX = 61.5

# Main master-residence floor.  The terrace ends at the glass façade at Y=305.
# The stair bay alone is moved east by 61.5 px; the rest of the footprint stays
# in the shared building coordinate system.
FOOTPRINT = [
    (82, 305, 1058, 692),
    (112, 692, 562, 785),
    (729, 692, 1032, 785),
    (562, 676, 729, 770),
]
# The middle 16 m bay projects north between the two center columns; the side
# bays stop farther south.  Keeping this as a union preserves the stepped edge.
PRIVATE_TERRACE = [(104, 210, 1038, 305), (363, 176, 798, 210)]

# Solid black/gray blocks shown in 3F.png.  The two small arrival posts are
# shifted with the stair bay; all other blocks retain their raster coordinates.
COLUMNS = [
    ('Terrace_NorthWest', (104, 210, 129, 280)),
    ('Terrace_CenterWest', (363, 176, 397, 221)),
    ('Terrace_CenterEast', (762, 176, 798, 221)),
    ('Terrace_NorthEast', (1014, 210, 1038, 280)),
    ('Facade_WestMid', (82, 493, 100, 531)),
    ('Facade_EastMid', (1039, 493, 1058, 531)),
    ('Facade_SouthWestStep', (364, 715, 391, 785)),
    ('Facade_SouthEastStep', (772, 715, 798, 785)),
    ('Arrival_OuterWest', (535, 693, 550, 711)),
    ('Arrival_OuterEast', (741, 692, 755, 711)),
    ('Facade_NorthWestCorner', (82, 280, 143, 305)),
    ('Facade_NorthEastCorner', (1002, 280, 1058, 305)),
    ('Facade_SouthWestCorner', (82, 642, 143, 692)),
    ('Facade_SouthEastCorner', (1002, 642, 1058, 692)),
]

# Each wall object is one connected rectangular solid.  Broad raster strokes
# are regularized to the same 0.28 m wall convention used on 1F and 2F.
EXTERIOR_WALLS = [
    ('NorthWest_Side', (82, 305, 100, 357), 'W'),
    ('NorthEast_Side', (1039, 305, 1058, 357), 'E'),
    ('SouthWest_DownReturn', (112, 692, 136, 770), 'E'),
    ('SouthEast_DownReturn', (1009, 692, 1032, 770), 'W'),
]

GLAZING = [
    ('MasterNorth_West', (143, 305), (544, 305)),
    ('MasterNorth_East', (623, 305), (1002, 305)),
    ('FacadeWest_North', (88, 357), (88, 493)),
    ('FacadeWest_South', (88, 531), (88, 642)),
    ('FacadeEast_North', (1051, 357), (1051, 493)),
    ('FacadeEast_South', (1051, 531), (1051, 642)),
    ('SouthWest_Outer', (136, 770), (364, 770)),
    ('SouthWest_Inner', (391, 770), (562, 770)),
    ('SouthEast_Inner', (729, 770), (772, 770)),
    ('SouthEast_Outer', (798, 770), (1009, 770)),
]

TERRACE_RAILS = [
    ('NorthWest', (129, 210), (363, 210)),
    ('NorthCenter', (397, 176), (762, 176)),
    ('NorthEast', (798, 210), (1014, 210)),
]


def xy(px, py):
    return (px - CX) * SX, (CY - py) * SY


def world_rect(rect):
    x0, y1 = xy(rect[0], rect[1])
    x1, y0 = xy(rect[2], rect[3])
    return x0, y0, x1, y1


def inspect_live_2f_stair():
    with bpy.data.libraries.load(str(TWO_F_BLEND), link=False) as (available, loaded):
        if '2F_Stair_UpTo3F' not in available.objects:
            raise RuntimeError('2F_Stair_UpTo3F is missing from the read-only 2F shell')
        loaded.objects = ['2F_Stair_UpTo3F']
    stair = loaded.objects[0]
    temp = bpy.data.collections.new('__TEMP_2F_ALIGNMENT__')
    bpy.context.scene.collection.children.link(temp)
    temp.objects.link(stair)
    bpy.context.view_layer.update()
    points = [stair.matrix_world @ Vector(corner) for corner in stair.bound_box]
    mesh_bounds = (min(point.x for point in points), min(point.y for point in points),
                   max(point.x for point in points), max(point.y for point in points))
    metadata_bounds = (float(stair['xmin']), float(stair['start_y']),
                       float(stair['xmax']), float(stair['end_y']))
    result = {
        'xmin': mesh_bounds[0], 'xmax': mesh_bounds[2],
        'start_y': mesh_bounds[1], 'end_y': mesh_bounds[3],
        'terminal_elevation_m': float(stair['terminal_elevation_m']),
        'landing_depth_m': float(stair['landing_depth_m']),
        'direction': stair['direction'],
    }
    bpy.data.objects.remove(stair, do_unlink=True)
    bpy.data.collections.remove(temp)
    expected = world_rect(STAIR_FROM_2F)
    error = max(abs(a - b) for a, b in zip(mesh_bounds, expected))
    if error > 1e-6:
        raise RuntimeError(f'Live 2F stair changed; source-equivalent bounds error is {error:.9f} m')
    metadata_error = max(abs(a - b) for a, b in zip(mesh_bounds, metadata_bounds))
    if metadata_error > 1e-6:
        raise RuntimeError(f'Live 2F stair metadata disagrees with evaluated mesh by {metadata_error:.9f} m')
    return result


def collection(name, parent=None):
    coll = bpy.data.collections.new(name)
    (parent or bpy.context.scene.collection).children.link(coll)
    return coll


def material(name, rgba, glass=False):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = rgba
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = rgba
    bsdf.inputs['Roughness'].default_value = .72 if not glass else .22
    if glass:
        bsdf.inputs['Alpha'].default_value = rgba[3]
        bsdf.inputs['Transmission Weight'].default_value = .12
        mat.surface_render_method = 'DITHERED'
    return mat


def mesh_object(name, vertices, faces, coll, mat, kind):
    mesh = bpy.data.meshes.new(name + '_Mesh')
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bmesh.ops.dissolve_limit(bm, angle_limit=.0001, verts=list(bm.verts),
                             edges=list(bm.edges), use_dissolve_boundaries=False)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    coll.objects.link(obj)
    obj.data.materials.append(mat)
    obj['shell_geometry'] = True
    obj['element_type'] = kind
    center = Vector(tuple((min(v.co[i] for v in mesh.vertices) +
                           max(v.co[i] for v in mesh.vertices)) / 2 for i in range(3)))
    for vert in mesh.vertices:
        vert.co -= center
    obj.location = center
    mesh.update()
    return obj


def intersects(a, b):
    return min(a[2], b[2]) > max(a[0], b[0]) and min(a[3], b[3]) > max(a[1], b[1])


def rect_solid(name, rects, z0, z1, coll, mat, kind, subtract=()):
    cuts = [rect for rect in subtract if any(intersects(rect, base) for base in rects)]
    edges = list(rects) + cuts
    xs = sorted(set(value for rect in edges for value in (rect[0], rect[2])))
    ys = sorted(set(value for rect in edges for value in (rect[1], rect[3])))

    def contains(shapes, x, y):
        return any(rect[0] < x < rect[2] and rect[1] < y < rect[3] for rect in shapes)

    cells = {(i, j) for i in range(len(xs) - 1) for j in range(len(ys) - 1)
             if contains(rects, (xs[i] + xs[i + 1]) / 2, (ys[j] + ys[j + 1]) / 2)
             and not contains(cuts, (xs[i] + xs[i + 1]) / 2, (ys[j] + ys[j + 1]) / 2)}
    if not cells:
        raise RuntimeError(f'{name} has no volume after subtraction')
    vertices, faces, vertex_ids = [], [], {}

    def vertex(i, j, upper):
        key = (i, j, upper)
        if key not in vertex_ids:
            vertex_ids[key] = len(vertices)
            vertices.append((xs[i], ys[j], z1 if upper else z0))
        return vertex_ids[key]

    for i, j in sorted(cells):
        corners = [(i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)]
        low = [vertex(x, y, False) for x, y in corners]
        high = [vertex(x, y, True) for x, y in corners]
        faces.extend([low[::-1], high])
        for edge, neighbor in enumerate(((i, j - 1), (i + 1, j), (i, j + 1), (i - 1, j))):
            if neighbor not in cells:
                nxt = (edge + 1) % 4
                faces.append([low[edge], low[nxt], high[nxt], high[edge]])
    obj = mesh_object(name, vertices, faces, coll, mat, kind)
    obj['footprint_rectangles_world'] = json.dumps(rects)
    obj['subtracted_rectangles_world'] = json.dumps(cuts)
    obj['z_min'] = z0
    obj['z_max'] = z1
    return obj


def traced_solid(name, rects, z0, z1, coll, mat, kind, subtract=()):
    obj = rect_solid(name, [world_rect(rect) for rect in rects], z0, z1, coll, mat, kind,
                     [world_rect(rect) for rect in subtract])
    obj['source_pixel_rectangles'] = json.dumps(rects)
    return obj


def resize_rect(rect, thickness, anchor):
    x0, y0, x1, y1 = map(float, rect)
    vertical = (y1 - y0) * SY > (x1 - x0) * SX
    if anchor in {'W', 'E'} or vertical:
        pixels = thickness / SX
        if anchor == 'W':
            x1 = x0 + pixels
        elif anchor == 'E':
            x0 = x1 - pixels
        else:
            center = (x0 + x1) / 2
            x0, x1 = center - pixels / 2, center + pixels / 2
    else:
        pixels = thickness / SY
        if anchor == 'N':
            y1 = y0 + pixels
        elif anchor == 'S':
            y0 = y1 - pixels
        else:
            center = (y0 + y1) / 2
            y0, y1 = center - pixels / 2, center + pixels / 2
    return x0, y0, x1, y1


def make_wall(name, source_rect, wall_class, anchor, coll, mat):
    thickness = EXTERIOR_WALL_THICKNESS if wall_class == 'exterior' else STAIRWELL_WALL_THICKNESS
    resized = resize_rect(source_rect, thickness, anchor)
    obj = traced_solid(name, [resized], 0, WALL_HEIGHT, coll, mat, 'wall')
    obj['wall_class'] = wall_class
    obj['nominal_thickness_m'] = thickness
    obj['original_source_pixel_rectangle'] = json.dumps(source_rect)
    obj['alignment_rule'] = 'preserve exterior face' if wall_class == 'exterior' else 'preserve live stair clearance face'
    return obj


def make_world_wall(name, rect, wall_class, coll, mat):
    obj = rect_solid(name, [rect], 0, WALL_HEIGHT, coll, mat, 'wall')
    obj['wall_class'] = wall_class
    obj['nominal_thickness_m'] = STAIRWELL_WALL_THICKNESS if wall_class == 'stairwell' else EXTERIOR_WALL_THICKNESS
    obj['alignment_rule'] = 'preserve live 2F stair aperture'
    return obj


def make_glass(name, a, b, coll, mat):
    x0, y0 = xy(*a)
    x1, y1 = xy(*b)
    if abs(x1 - x0) < 1e-8:
        rect = (x0 - GLASS_THICKNESS / 2, min(y0, y1),
                x0 + GLASS_THICKNESS / 2, max(y0, y1))
    else:
        rect = (min(x0, x1), y0 - GLASS_THICKNESS / 2,
                max(x0, x1), y0 + GLASS_THICKNESS / 2)
    obj = rect_solid(name, [rect], 0, WALL_HEIGHT, coll, mat, 'glass')
    obj['source_pixel_line'] = json.dumps([a, b])
    obj['nominal_thickness_m'] = GLASS_THICKNESS
    obj['collision_policy'] = 'Separate full-height visual/collision candidate for later export'
    return obj


def railing_segment(name, a, b, coll, glass_mat, top_mat):
    x0, y0 = xy(*a)
    x1, y1 = xy(*b)
    length = math.hypot(x1 - x0, y1 - y0)
    ux, uy = (x1 - x0) / length, (y1 - y0) / length
    ax, ay = x0 + ux * RAILING_END_INSET, y0 + uy * RAILING_END_INSET
    bx, by = x1 - ux * RAILING_END_INSET, y1 - uy * RAILING_END_INSET
    if abs(ax - bx) < 1e-8:
        glass_rect = (ax - RAILING_GLASS_THICKNESS / 2, min(ay, by),
                      ax + RAILING_GLASS_THICKNESS / 2, max(ay, by))
        top_rect = (ax - RAILING_TOPRAIL_WIDTH / 2, min(ay, by),
                    ax + RAILING_TOPRAIL_WIDTH / 2, max(ay, by))
    else:
        glass_rect = (min(ax, bx), ay - RAILING_GLASS_THICKNESS / 2,
                      max(ax, bx), ay + RAILING_GLASS_THICKNESS / 2)
        top_rect = (min(ax, bx), ay - RAILING_TOPRAIL_WIDTH / 2,
                    max(ax, bx), ay + RAILING_TOPRAIL_WIDTH / 2)
    panel = rect_solid(name, [glass_rect], 0, RAILING_GLASS_HEIGHT, coll, glass_mat, 'railing_glass')
    rail = rect_solid(name + '_TopRail', [top_rect], RAILING_GLASS_HEIGHT, RAILING_HEIGHT,
                      coll, top_mat, 'railing_toprail')
    for obj in (panel, rail):
        obj['railing_zone'] = 'private_terrace'
        obj['guardrail_height_m'] = RAILING_HEIGHT
        obj['edge_coverage_ratio'] = (length - 2 * RAILING_END_INSET) / length
        obj['collision_policy'] = 'Export as collision and visual geometry'
    panel['nominal_thickness_m'] = RAILING_GLASS_THICKNESS
    rail['nominal_thickness_m'] = RAILING_TOPRAIL_WIDTH
    return panel, rail


def helper(name, bounds_xyzxyz, coll):
    x0, y0, z0, x1, y1, z1 = bounds_xyzxyz
    obj = bpy.data.objects.new(name, None)
    coll.objects.link(obj)
    obj.empty_display_type = 'CUBE'
    obj.empty_display_size = 1
    obj.location = ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2)
    obj.scale = ((x1 - x0) / 2, (y1 - y0) / 2, (z1 - z0) / 2)
    obj.hide_render = True
    obj.hide_set(True)
    obj['non_export_helper'] = True
    obj['bounds_world_m'] = json.dumps(bounds_xyzxyz)
    return obj


def camera(name, location, target, coll, ortho=None):
    data = bpy.data.cameras.new(name)
    obj = bpy.data.objects.new(name, data)
    coll.objects.link(obj)
    obj.location = location
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat('-Z', 'Y').to_euler()
    if ortho is not None:
        data.type = 'ORTHO'
        data.ortho_scale = ortho
    data.lens = 48
    return obj


def add_junction(schedule, name, a, b):
    schedule.append({'name': name, 'a': a, 'b': b})


def main():
    live_stair = inspect_live_2f_stair()
    stair_xy = (live_stair['xmin'], live_stair['start_y'],
                live_stair['xmax'], live_stair['end_y'])
    source_stair_world = world_rect(STAIR_FROM_2F)
    if max(abs(a - b) for a, b in zip(stair_xy, source_stair_world)) > 1e-6:
        raise RuntimeError('Refusing to build: live 2F stair no longer matches the approved aperture')

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.length_unit = 'METERS'
    scene.unit_settings.scale_length = 1.0
    scene['floor_id'] = '3F'
    scene['build_started_unix_s'] = time.time()
    scene['local_finished_floor_z_m'] = 0.0
    scene['reference_source'] = '3F.png; live 2F_Stair_UpTo3F alignment from read-only 2F_shell.blend'
    scene['alignment_calibration_json'] = json.dumps({
        'origin_pixel': [CX, CY], 'origin_xy_m': [0.0, 0.0],
        'meters_per_pixel_x': SX, 'meters_per_pixel_y': SY,
        'x_axis': 'east/right', 'y_axis': 'north/top',
        'policy': 'Do not translate the 3F floor; reconcile only the stair-arrival bay.'})
    scene['stair_reconciliation_json'] = json.dumps({
        'drawn_3f_stair_center_x_px_approx': DRAWN_3F_STAIR_CENTER_X_PX,
        'live_2f_stair_center_source_equivalent_x_px': 645.5,
        'local_arrival_bay_shift_px': STAIR_RECONCILIATION_SHIFT_PX,
        'local_arrival_bay_shift_m': STAIR_RECONCILIATION_SHIFT_PX * SX,
        'live_2f_bounds_xyxy_m': stair_xy,
        'whole_floor_translation_m': [0.0, 0.0],
    })
    scene['assumptions'] = (
        'Independent 3F shell; finished floor Z=0; slabs -0.20..0.00m; walls/columns/glass '
        '0.00..3.20m, except the four private-terrace wall piers which match the 1.10m glass '
        'guard height. Existing stack transform retained. No interior partitions because note 3 '
        'removes them. The physical 2F-to-3F flight remains solely in 2F_shell.blend; 3F carries '
        'the exact live aperture and connection interface. The drawn full-width terrace is retained '
        'despite conflicting with the approximate 52m2 schedule. No furniture, fixtures, ceiling, '
        'roof, landscaping, or Gazebo export geometry.')
    scene['plan_ambiguities_json'] = json.dumps([
        'The 3F raster stair is approximately 2.295 m west of live 2F_Stair_UpTo3F; only the local arrival bay is shifted.',
        'The drawn full-width terrace is materially larger than the approximate 52 m2 room schedule.',
        'Blue-gray lines at the outdoor terrace perimeter are interpreted as 1.10 m guards; occupied façades use 3.20 m glazing.',
        'The 3F PNG is 1447 x 1087 while earlier sheets are nominally 1448 x 1086; the established stack transform governs.',
    ])

    root = collection('3F_SHELL')
    cols = {name: collection(name, root) for name in [
        '3F_FLOOR', '3F_WALLS_EXTERIOR', '3F_WALLS_INTERIOR', '3F_COLUMNS',
        '3F_GLASS', '3F_STAIRS', '3F_RAILINGS', '3F_TERRACES', '3F_OPENINGS', '3F_DEBUG']}
    refs = collection('REFERENCE_3F')
    views = collection('3F_VALIDATION_CAMERAS')
    mats = {
        'wall': material('Placeholder_Wall_Gray', (.13, .15, .17, 1)),
        'floor': material('Placeholder_Floor_Gray', (.67, .68, .69, 1)),
        'terrace': material('Placeholder_Terrace_Gray', (.78, .79, .79, 1)),
        'column': material('Placeholder_Structural_DarkGray', (.20, .23, .25, 1)),
        'glass': material('Placeholder_Glass_Blue', (.13, .54, .70, .32), True),
        'railing_glass': material('Placeholder_Railing_Glass', (.10, .62, .78, .38), True),
        'railing_top': material('Placeholder_Railing_TopRail', (.10, .12, .14, 1)),
    }

    image = bpy.data.images.load(str(IMAGE), check_existing=True)
    image.pack()
    reference = bpy.data.objects.new('3F_Reference_Plan', None)
    refs.objects.link(reference)
    reference.empty_display_type = 'IMAGE'
    reference.data = image
    reference.empty_display_size = image.size[0] * SX
    reference.scale = (1, SY / SX, 1)
    reference.location = (*xy(image.size[0] / 2, image.size[1] / 2), -.24)
    reference.color[3] = .62
    reference.empty_image_depth = 'BACK'
    reference.hide_render = True
    reference.hide_select = True
    reference.lock_location = (True, True, True)
    reference.lock_rotation = (True, True, True)
    reference.lock_scale = (True, True, True)
    reference['calibration'] = 'Shared origin pixel 585,513; X 108..1062=35.6m; Y 189..837=22.8m'

    main_floor = traced_solid('3F_Floor_Main', FOOTPRINT, -SLAB_THICKNESS, 0,
                              cols['3F_FLOOR'], mats['floor'], 'floor', [STAIR_FROM_2F])
    main_floor['architectural_program'] = 'Open-plan master residence; no inferred internal room boundaries'
    main_floor['stair_cut_source'] = 'Live 2F_Stair_UpTo3F bounds'
    terrace = traced_solid('3F_Terrace_Private', PRIVATE_TERRACE, -SLAB_THICKNESS, 0,
                           cols['3F_TERRACES'], mats['terrace'], 'terrace')
    terrace['architectural_program'] = 'Private outdoor terrace'
    terrace['schedule_area_m2'] = 52.0
    terrace['area_policy'] = 'Trace drawn outline; schedule explicitly says areas are approximate'

    for index, (label, rect) in enumerate(COLUMNS, 1):
        height = RAILING_HEIGHT if label.startswith('Terrace_') else WALL_HEIGHT
        obj = traced_solid(f'3F_Column_{index:03d}_{label}', [rect], 0, height,
                           cols['3F_COLUMNS'], mats['column'], 'column')
        obj['structural_interpretation'] = 'solid black/gray block in 3F.png'
        if label.startswith('Terrace_'):
            obj['height_policy'] = 'Match private-terrace glass guard top at 1.10 m'

    walls = {}
    for index, (label, rect, anchor) in enumerate(EXTERIOR_WALLS, 1):
        name = f'3F_Wall_Exterior_{index:03d}_{label}'
        walls[label] = make_wall(name, rect, 'exterior', anchor,
                                 cols['3F_WALLS_EXTERIOR'], mats['wall'])

    # Stair side faces use world values read from the 2F object, preserving the
    # clear aperture exactly.  Return stubs close the shifted south façade into
    # those side walls without crossing the opening.
    west_stair_rect = (stair_xy[0] - STAIRWELL_WALL_THICKNESS, stair_xy[1],
                       stair_xy[0], stair_xy[3])
    east_stair_rect = (stair_xy[2], stair_xy[1],
                       stair_xy[2] + STAIRWELL_WALL_THICKNESS, stair_xy[3])
    west_stair = make_world_wall('3F_Wall_Stair_001_From2F_West', west_stair_rect,
                                 'stairwell', cols['3F_WALLS_INTERIOR'], mats['wall'])
    east_stair = make_world_wall('3F_Wall_Stair_002_From2F_East', east_stair_rect,
                                 'stairwell', cols['3F_WALLS_INTERIOR'], mats['wall'])
    south_line_y = xy(0, 770)[1]
    west_stub = make_world_wall('3F_Wall_Exterior_005_Arrival_West_Return',
        (xy(562, 0)[0], south_line_y - EXTERIOR_WALL_THICKNESS / 2,
         west_stair_rect[0], south_line_y + EXTERIOR_WALL_THICKNESS / 2),
        'exterior', cols['3F_WALLS_EXTERIOR'], mats['wall'])
    east_stub = make_world_wall('3F_Wall_Exterior_006_Arrival_East_Return',
        (east_stair_rect[2], south_line_y - EXTERIOR_WALL_THICKNESS / 2,
         xy(729, 0)[0], south_line_y + EXTERIOR_WALL_THICKNESS / 2),
        'exterior', cols['3F_WALLS_EXTERIOR'], mats['wall'])

    glasses = {}
    for index, (label, a, b) in enumerate(GLAZING, 1):
        name = f'3F_Glass_{index:03d}_{label}'
        glasses[label] = make_glass(name, a, b, cols['3F_GLASS'], mats['glass'])

    for label, a, b in TERRACE_RAILS:
        railing_segment(f'3F_Railing_Terrace_{label}', a, b, cols['3F_RAILINGS'],
                        mats['railing_glass'], mats['railing_top'])

    opening_bounds = [stair_xy[0], stair_xy[1], -SLAB_THICKNESS,
                      stair_xy[2], stair_xy[3], WALL_HEIGHT]
    opening = helper('3F_Opening_From2F', opening_bounds, cols['3F_OPENINGS'])
    opening['alignment_source'] = 'Live 2F_Stair_UpTo3F custom bounds and evaluated mesh envelope'
    opening['physical_flight_owner'] = '2F/2F_shell.blend'
    connection = bpy.data.objects.new('3F_Connection_2F', None)
    cols['3F_OPENINGS'].objects.link(connection)
    connection.location = ((stair_xy[0] + stair_xy[2]) / 2, stair_xy[3], 0)
    connection.empty_display_type = 'ARROWS'
    connection.empty_display_size = .6
    connection.hide_render = True
    connection.hide_set(True)
    connection['paired_object'] = '2F_Stair_UpTo3F north arrival edge'
    connection['xy_alignment_error_m'] = 0.0

    terrace_door_sample = list(xy((544 + 623) / 2, 305))
    stair_arrival_sample = list(xy((607 + 684) / 2, 665))
    opening_schedule = [
        {'name': 'PrivateTerrace_DoubleDoor', 'classification': 'intentional_doorway',
         'aperture_source_px': [544, 296, 623, 310],
         'clear_width_m': (623 - 544) * SX,
         'sample_world_xy_m': terrace_door_sample,
         'reason': 'double door swing shown in the terrace glass wall'},
        {'name': 'StairArrival_From2F', 'classification': 'stair_opening',
         'aperture_world_xyxy_m': list(stair_xy),
         'sample_world_xy_m': stair_arrival_sample,
         'reason': 'exact live 2F stair aperture and open north arrival'},
    ]
    scene['opening_schedule_json'] = json.dumps(opening_schedule)
    for item in opening_schedule:
        marker = bpy.data.objects.new('3F_Opening_' + item['name'], None)
        cols['3F_OPENINGS'].objects.link(marker)
        marker.location = (*item['sample_world_xy_m'], 1.2)
        marker.empty_display_type = 'PLAIN_AXES'
        marker.empty_display_size = .18
        marker.hide_render = True
        marker.hide_set(True)

    junctions = []
    add_junction(junctions, 'northwest_return_to_north_glass',
                 '3F_Column_011_Facade_NorthWestCorner', glasses['MasterNorth_West'].name)
    add_junction(junctions, 'northeast_return_to_north_glass',
                 '3F_Column_012_Facade_NorthEastCorner', glasses['MasterNorth_East'].name)
    add_junction(junctions, 'northwest_side_to_west_glass',
                 walls['NorthWest_Side'].name, glasses['FacadeWest_North'].name)
    add_junction(junctions, 'northwest_corner_to_side',
                 '3F_Column_011_Facade_NorthWestCorner', walls['NorthWest_Side'].name)
    add_junction(junctions, 'west_glass_to_mid_column_north',
                 glasses['FacadeWest_North'].name, '3F_Column_005_Facade_WestMid')
    add_junction(junctions, 'west_mid_column_to_glass_south',
                 '3F_Column_005_Facade_WestMid', glasses['FacadeWest_South'].name)
    add_junction(junctions, 'west_glass_to_south_side',
                 glasses['FacadeWest_South'].name, '3F_Column_013_Facade_SouthWestCorner')
    add_junction(junctions, 'southwest_corner_to_downreturn',
                 '3F_Column_013_Facade_SouthWestCorner', walls['SouthWest_DownReturn'].name)
    add_junction(junctions, 'west_downreturn_to_outer_glass',
                 walls['SouthWest_DownReturn'].name, glasses['SouthWest_Outer'].name)
    add_junction(junctions, 'west_outer_glass_to_step_column',
                 glasses['SouthWest_Outer'].name, '3F_Column_007_Facade_SouthWestStep')
    add_junction(junctions, 'west_step_column_to_inner_glass',
                 '3F_Column_007_Facade_SouthWestStep', glasses['SouthWest_Inner'].name)
    add_junction(junctions, 'west_inner_glass_to_arrival_return',
                 glasses['SouthWest_Inner'].name, west_stub.name)
    add_junction(junctions, 'west_arrival_return_to_stair_wall', west_stub.name, west_stair.name)
    add_junction(junctions, 'northeast_side_to_east_glass',
                 walls['NorthEast_Side'].name, glasses['FacadeEast_North'].name)
    add_junction(junctions, 'northeast_corner_to_side',
                 '3F_Column_012_Facade_NorthEastCorner', walls['NorthEast_Side'].name)
    add_junction(junctions, 'east_glass_to_mid_column_north',
                 glasses['FacadeEast_North'].name, '3F_Column_006_Facade_EastMid')
    add_junction(junctions, 'east_mid_column_to_glass_south',
                 '3F_Column_006_Facade_EastMid', glasses['FacadeEast_South'].name)
    add_junction(junctions, 'east_glass_to_south_side',
                 glasses['FacadeEast_South'].name, '3F_Column_014_Facade_SouthEastCorner')
    add_junction(junctions, 'southeast_corner_to_downreturn',
                 '3F_Column_014_Facade_SouthEastCorner', walls['SouthEast_DownReturn'].name)
    add_junction(junctions, 'east_downreturn_to_outer_glass',
                 walls['SouthEast_DownReturn'].name, glasses['SouthEast_Outer'].name)
    add_junction(junctions, 'east_outer_glass_to_step_column',
                 glasses['SouthEast_Outer'].name, '3F_Column_008_Facade_SouthEastStep')
    add_junction(junctions, 'east_step_column_to_inner_glass',
                 '3F_Column_008_Facade_SouthEastStep', glasses['SouthEast_Inner'].name)
    add_junction(junctions, 'east_inner_glass_to_arrival_return',
                 glasses['SouthEast_Inner'].name, east_stub.name)
    add_junction(junctions, 'east_arrival_return_to_stair_wall', east_stub.name, east_stair.name)
    scene['junction_schedule_json'] = json.dumps(junctions)

    top = camera('3F_Camera_Top_Orthographic', (0, 0, 55), (0, 0, 0), views, 42.5)
    top.rotation_euler = (0, 0, 0)
    corner = camera('3F_Camera_Perspective_Corner', (34, -38, 37), (0, 0, .35), views)
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = 16
    scene.cycles.use_denoising = True
    if scene.world is None:
        scene.world = bpy.data.worlds.new('3F_Validation_World')
    scene.world.use_nodes = True
    scene.world.node_tree.nodes['Background'].inputs[0].default_value = (.86, .86, .86, 1)
    scene.world.node_tree.nodes['Background'].inputs[1].default_value = .8
    light_data = bpy.data.lights.new('Validation_Area_Light', 'AREA')
    light = bpy.data.objects.new(light_data.name, light_data)
    views.objects.link(light)
    light.location = (0, -4, 28)
    light_data.energy = 3000
    light_data.shape = 'DISK'
    light_data.size = 22
    scene.render.image_settings.file_format = 'PNG'
    scene.render.film_transparent = False
    scene.render.resolution_percentage = 100
    scene.view_settings.view_transform = 'Standard'
    scene.camera = top

    readme = bpy.data.texts.new('README_3F_SHELL')
    readme.write(__doc__ + '\n\n' + scene['assumptions'])
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND))

    if '--skip-renders' not in sys.argv:
        renders = [
            (top, '3F_shell_top.png', 2400, 1700),
            (corner, '3F_shell_perspective_corner.png', 1800, 1300),
        ]
        for cam, name, width, height in renders:
            scene.camera = cam
            scene.render.resolution_x = width
            scene.render.resolution_y = height
            scene.render.filepath = str(OUT / name)
            bpy.ops.render.render(write_still=True)
        scene.camera = top
        scene.render.resolution_x = 2400
        scene.render.resolution_y = 1700
        scene.render.filepath = str(OUT / '3F_shell_top.png')
        bpy.ops.wm.save_as_mainfile(filepath=str(BLEND))
    sys.path.insert(0, str(OUT))
    import validate_3F_shell
    require_added = '--skip-renders' not in sys.argv and '--require-renders' not in sys.argv
    if require_added:
        sys.argv.append('--require-renders')
    try:
        result = validate_3F_shell.run()
    finally:
        if require_added:
            sys.argv.remove('--require-renders')
    print('3F SHELL BUILD COMPLETE', json.dumps({
        'passed': result['passed'], 'failed': result['failed'],
        'meshes': result['mesh_objects'], 'bounds_m': result['bounds_m']}))


if __name__ == '__main__':
    main()
