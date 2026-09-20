"""Build the standalone flat roof for the villa's enclosed third-floor body.

The roof reads the live 3F_Floor_Main footprint from 3F_shell.blend so its XY
coordinate frame stays identical to the other independent floor assets. The
private terrace is deliberately left uncovered.

Usage:
    blender -b --factory-startup --python-exit-code 1 --python build_Roof_shell.py
    blender -b --factory-startup --python-exit-code 1 --python build_Roof_shell.py -- --skip-renders
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
BLEND = OUT / 'Roof_shell.blend'
THREE_F_BLEND = OUT.parent / '3F' / '3F_shell.blend'

SLAB_THICKNESS = 0.20
PARAPET_HEIGHT = 0.30
PARAPET_WIDTH = 0.18
EXPECTED_BOUNDS = (-18.770230607966457, -9.570370370370371,
                   17.650733752620546, 7.318518518518519)


def collection(name, parent=None):
    coll = bpy.data.collections.new(name)
    (parent or bpy.context.scene.collection).children.link(coll)
    return coll


def material(name, rgba, roughness):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = rgba
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = rgba
    bsdf.inputs['Roughness'].default_value = roughness
    return mat


def inspect_live_3f_footprint():
    with bpy.data.libraries.load(str(THREE_F_BLEND), link=False) as (available, loaded):
        if '3F_Floor_Main' not in available.objects:
            raise RuntimeError('3F_Floor_Main is missing from the read-only 3F shell')
        loaded.objects = ['3F_Floor_Main']
    source = loaded.objects[0]
    temp = bpy.data.collections.new('__TEMP_3F_ROOF_ALIGNMENT__')
    bpy.context.scene.collection.children.link(temp)
    temp.objects.link(source)
    try:
        bpy.context.view_layer.update()
        rects = json.loads(source.get('footprint_rectangles_world', '[]'))
        if not rects:
            raise RuntimeError('3F_Floor_Main has no footprint rectangle metadata')
        points = [source.matrix_world @ Vector(corner) for corner in source.bound_box]
        bounds = (min(point.x for point in points), min(point.y for point in points),
                  max(point.x for point in points), max(point.y for point in points))
        error = max(abs(actual - expected)
                    for actual, expected in zip(bounds, EXPECTED_BOUNDS))
        if error > 1e-5:
            raise RuntimeError(
                f'Live 3F footprint changed; approved roof bounds error is {error:.9f} m')
        return [list(map(float, rect)) for rect in rects], list(bounds)
    finally:
        bpy.data.objects.remove(source, do_unlink=True)
        bpy.data.collections.remove(temp)


def mesh_object(name, vertices, faces, coll, mat, kind):
    mesh = bpy.data.meshes.new(name + '_Mesh')
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bmesh.ops.dissolve_limit(bm, angle_limit=0.0001, verts=list(bm.verts),
                             edges=list(bm.edges), use_dissolve_boundaries=False)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    coll.objects.link(obj)
    obj.data.materials.append(mat)
    obj['shell_geometry'] = True
    obj['element_type'] = kind
    center = Vector(tuple((min(vertex.co[i] for vertex in mesh.vertices) +
                           max(vertex.co[i] for vertex in mesh.vertices)) / 2
                          for i in range(3)))
    for vertex in mesh.vertices:
        vertex.co -= center
    obj.location = center
    mesh.update()
    return obj


def rect_solid(name, rects, z0, z1, coll, mat, kind):
    xs = sorted(set(value for rect in rects for value in (rect[0], rect[2])))
    ys = sorted(set(value for rect in rects for value in (rect[1], rect[3])))

    def contains(x, y):
        return any(rect[0] < x < rect[2] and rect[1] < y < rect[3]
                   for rect in rects)

    cells = {(i, j) for i in range(len(xs) - 1) for j in range(len(ys) - 1)
             if contains((xs[i] + xs[i + 1]) / 2,
                         (ys[j] + ys[j + 1]) / 2)}
    if not cells:
        raise RuntimeError(f'{name} has no solid cells')

    vertices = []
    faces = []
    vertex_ids = {}

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
        neighbors = ((i, j - 1), (i + 1, j), (i, j + 1), (i - 1, j))
        for edge, neighbor in enumerate(neighbors):
            if neighbor not in cells:
                nxt = (edge + 1) % 4
                faces.append([low[edge], low[nxt], high[nxt], high[edge]])

    obj = mesh_object(name, vertices, faces, coll, mat, kind)
    obj['footprint_rectangles_world'] = json.dumps(rects)
    obj['subtracted_rectangles_world'] = json.dumps([])
    obj['z_min'] = z0
    obj['z_max'] = z1
    return obj


def perimeter_rectangles(rects, width):
    """Return an inward strip along the outer boundary of a rectangle union."""
    xs = sorted(set(value for rect in rects for value in (rect[0], rect[2])))
    ys = sorted(set(value for rect in rects for value in (rect[1], rect[3])))

    def occupied(i, j):
        if i < 0 or j < 0 or i >= len(xs) - 1 or j >= len(ys) - 1:
            return False
        x = (xs[i] + xs[i + 1]) / 2
        y = (ys[j] + ys[j + 1]) / 2
        return any(rect[0] < x < rect[2] and rect[1] < y < rect[3]
                   for rect in rects)

    strips = []
    for i in range(len(xs) - 1):
        for j in range(len(ys) - 1):
            if not occupied(i, j):
                continue
            x0, x1 = xs[i], xs[i + 1]
            y0, y1 = ys[j], ys[j + 1]
            if not occupied(i, j - 1):
                strips.append((x0, y0, x1, min(y0 + width, y1)))
            if not occupied(i + 1, j):
                strips.append((max(x1 - width, x0), y0, x1, y1))
            if not occupied(i, j + 1):
                strips.append((x0, max(y1 - width, y0), x1, y1))
            if not occupied(i - 1, j):
                strips.append((x0, y0, min(x0 + width, x1), y1))

    # At each concave corner, add the small square diagonally opposite the
    # missing footprint quadrant. Without this miter fill, two inward strips
    # touch only along one vertical edge and create a non-manifold union.
    for i in range(1, len(xs) - 1):
        for j in range(1, len(ys) - 1):
            quadrants = {
                'SW': occupied(i - 1, j - 1),
                'SE': occupied(i, j - 1),
                'NE': occupied(i, j),
                'NW': occupied(i - 1, j),
            }
            missing = [name for name, value in quadrants.items() if not value]
            if len(missing) != 1:
                continue
            x, y = xs[i], ys[j]
            fills = {
                'SE': (x - width, y, x, y + width),
                'SW': (x, y, x + width, y + width),
                'NE': (x - width, y - width, x, y),
                'NW': (x, y - width, x + width, y),
            }
            strips.append(fills[missing[0]])
    return strips


def camera(name, location, target, coll, ortho=None):
    data = bpy.data.cameras.new(name)
    obj = bpy.data.objects.new(name, data)
    coll.objects.link(obj)
    obj.location = location
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat('-Z', 'Y').to_euler()
    if ortho is not None:
        data.type = 'ORTHO'
        data.ortho_scale = ortho
    data.lens = 52
    return obj


def main():
    footprint, source_bounds = inspect_live_3f_footprint()

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.length_unit = 'METERS'
    scene.unit_settings.scale_length = 1.0
    scene['floor_id'] = 'ROOF'
    scene['build_started_unix_s'] = time.time()
    scene['local_roof_underside_z_m'] = 0.0
    scene['recommended_3f_relative_pose_xyz_m'] = json.dumps([0.0, 0.0, 3.2])
    scene['reference_source'] = 'Live 3F_Floor_Main footprint from 3F/3F_shell.blend'
    scene['assumptions'] = (
        'Independent modern flat roof in the established villa XY frame. The roof underside is '
        'local Z=0 and should be placed at Z=3.20 m relative to the standalone 3F shell. The '
        '0.20 m concrete slab closes the stair opening and covers only the enclosed 3F body. '
        'The north private terrace remains uncovered. A 0.30 m high, 0.18 m wide parapet follows '
        'the slab perimeter. No furniture, solar equipment, landscaping, or Gazebo export files.'
    )
    scene['source_3f_bounds_xyxy_m'] = json.dumps(source_bounds)

    root = collection('ROOF_SHELL')
    geometry = collection('ROOF_GEOMETRY', root)
    interfaces = collection('ROOF_INTERFACES', root)
    views = collection('ROOF_VALIDATION_CAMERAS')
    slab_mat = material('Placeholder_Roof_Concrete', (0.72, 0.74, 0.75, 1), 0.78)
    parapet_mat = material('Placeholder_Roof_Parapet', (0.90, 0.90, 0.88, 1), 0.70)

    slab = rect_solid('Roof_Slab', footprint, 0.0, SLAB_THICKNESS,
                      geometry, slab_mat, 'roof_slab')
    slab['source_object'] = '3F_Floor_Main'
    slab['coverage_policy'] = 'Cover enclosed 3F footprint; close stair aperture; exclude terrace'
    slab['nominal_thickness_m'] = SLAB_THICKNESS

    parapet_rects = perimeter_rectangles(footprint, PARAPET_WIDTH)
    parapet = rect_solid('Roof_Parapet', parapet_rects, SLAB_THICKNESS,
                         SLAB_THICKNESS + PARAPET_HEIGHT,
                         geometry, parapet_mat, 'roof_parapet')
    parapet['parapet_segments_world'] = json.dumps(parapet_rects)
    parapet['nominal_width_m'] = PARAPET_WIDTH
    parapet['nominal_height_m'] = PARAPET_HEIGHT
    parapet['coverage_policy'] = 'Inward strip on union perimeter; no terrace enclosure'

    connection = bpy.data.objects.new('Roof_Connection_3F', None)
    interfaces.objects.link(connection)
    connection.location = (0.0, 0.0, 0.0)
    connection.empty_display_type = 'ARROWS'
    connection.empty_display_size = 0.8
    connection.hide_render = True
    connection.hide_set(True)
    connection['paired_object'] = '3F wall-top datum Z=3.20 m'
    connection['recommended_relative_pose_xyz_m'] = json.dumps([0.0, 0.0, 3.2])
    connection['assembly_rule'] = 'Keep XY unchanged; place roof local underside at 3F Z=3.20 m'

    top = camera('Roof_Camera_Top_Orthographic', (0, 0, 48), (0, 0, 0), views, 43.0)
    top.rotation_euler = (0, 0, 0)
    corner = camera('Roof_Camera_Perspective_Corner', (31, -35, 27),
                    (0, -0.5, 0.10), views)
    corner.data.lens = 43

    scene.render.engine = 'BLENDER_EEVEE_NEXT'
    scene.render.image_settings.file_format = 'PNG'
    scene.render.film_transparent = False
    scene.render.resolution_percentage = 100
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'Medium High Contrast'
    if scene.world is None:
        scene.world = bpy.data.worlds.new('Roof_Validation_World')
    scene.world.use_nodes = True
    scene.world.node_tree.nodes['Background'].inputs[0].default_value = (0.055, 0.070, 0.090, 1)
    scene.world.node_tree.nodes['Background'].inputs[1].default_value = 0.45

    key_data = bpy.data.lights.new('Roof_Validation_Key', 'AREA')
    key = bpy.data.objects.new(key_data.name, key_data)
    views.objects.link(key)
    key.location = (-7, -10, 24)
    key_data.energy = 2100
    key_data.shape = 'DISK'
    key_data.size = 16
    fill_data = bpy.data.lights.new('Roof_Validation_Fill', 'AREA')
    fill = bpy.data.objects.new(fill_data.name, fill_data)
    views.objects.link(fill)
    fill.location = (16, 12, 14)
    fill_data.energy = 1100
    fill_data.size = 12

    readme = bpy.data.texts.new('README_ROOF_SHELL')
    readme.write(__doc__ + '\n\n' + scene['assumptions'])
    scene.camera = top
    scene.render.resolution_x = 2000
    scene.render.resolution_y = 1450
    scene.render.filepath = str(OUT / 'Roof_shell_top.png')
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND))

    if '--skip-renders' not in sys.argv:
        renders = [
            (top, 'Roof_shell_top.png', 2000, 1450),
            (corner, 'Roof_shell_perspective_corner.png', 1800, 1300),
        ]
        for render_camera, filename, width, height in renders:
            scene.camera = render_camera
            scene.render.resolution_x = width
            scene.render.resolution_y = height
            scene.render.filepath = str(OUT / filename)
            bpy.ops.render.render(write_still=True)
        scene.camera = top
        scene.render.resolution_x = 2000
        scene.render.resolution_y = 1450
        scene.render.filepath = str(OUT / 'Roof_shell_top.png')
        bpy.ops.wm.save_as_mainfile(filepath=str(BLEND))

    sys.path.insert(0, str(OUT))
    import validate_Roof_shell
    require_added = '--skip-renders' not in sys.argv and '--require-renders' not in sys.argv
    if require_added:
        sys.argv.append('--require-renders')
    try:
        result = validate_Roof_shell.run()
    finally:
        if require_added:
            sys.argv.remove('--require-renders')
    print('ROOF SHELL BUILD COMPLETE', json.dumps({
        'passed': result['passed'],
        'failed': result['failed'],
        'meshes': result['mesh_objects'],
        'bounds_m': result['bounds_m'],
    }))


if __name__ == '__main__':
    main()
