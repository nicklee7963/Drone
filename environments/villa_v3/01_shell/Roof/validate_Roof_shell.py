"""Independent geometry and alignment audit for the standalone villa roof."""
import bpy
import bmesh
import hashlib
import json
import math
import sys
from pathlib import Path
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view


OUT = Path(__file__).resolve().parent
THREE_F_BLEND = OUT.parent / '3F' / '3F_shell.blend'
EXPECTED_3F_SHA256 = '30011cc91aa447ef3e2eec924eaeafa0fcf5348222b4d31bd54956343722d2de'

# Hand-derived from the established 3F plan calibration. The roof intentionally
# closes the 3F stair aperture but does not extend over the private terrace.
EXPECTED_RECTS = [
    [-18.770230607966457, -6.298148148148148, 17.650733752620546, 7.318518518518519],
    [-17.650733752620546, -9.570370370370371, -0.8582809224318658, -6.298148148148148],
    [5.373584905660378, -9.570370370370371, 16.68050314465409, -6.298148148148148],
    [-0.8582809224318658, -9.042592592592593, 5.373584905660378, -5.735185185185186],
]
EXPECTED_BOUNDS = [-18.770230607966457, -9.570370370370371,
                   17.650733752620546, 7.318518518518519]
INDOOR_SAMPLES = [(-18.0, 0.0), (0.0, 0.0), (17.0, 0.0),
                  (-10.0, -8.0), (2.25, -8.5), (10.0, -8.0)]
TERRACE_SAMPLES = [(0.0, 9.0), (-12.0, 9.0), (12.0, 9.0)]

CHECKS = []


def check(name, passed, detail=None):
    CHECKS.append({'name': name, 'pass': bool(passed), 'detail': detail})


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def bounds(obj):
    points = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    return [[min(point[i] for point in points), max(point[i] for point in points)]
            for i in range(3)]


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


def manifold_status(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    non_manifold = sum(not edge.is_manifold for edge in bm.edges)
    volume = abs(bm.calc_volume(signed=True))
    bm.free()
    return non_manifold, volume


def top_surface_contains(obj, x, y):
    inverse = obj.matrix_world.inverted()
    origin = inverse @ Vector((x, y, 10.0))
    direction = inverse.to_3x3() @ Vector((0.0, 0.0, -1.0))
    hit, _location, _normal, _index = obj.ray_cast(origin, direction)
    return bool(hit)


def close_list(actual, expected, tolerance=1e-5):
    return len(actual) == len(expected) and all(
        abs(float(a) - float(e)) <= tolerance for a, e in zip(actual, expected))


def run():
    global CHECKS
    CHECKS = []
    scene = bpy.context.scene
    slab = bpy.data.objects.get('Roof_Slab')
    parapet = bpy.data.objects.get('Roof_Parapet')
    connection = bpy.data.objects.get('Roof_Connection_3F')
    top_camera = bpy.data.objects.get('Roof_Camera_Top_Orthographic')
    corner_camera = bpy.data.objects.get('Roof_Camera_Perspective_Corner')
    meshes = [obj for obj in scene.objects
              if obj.type == 'MESH' and obj.get('shell_geometry')]

    check('Blender file opens with expected standalone roof scene',
          scene.get('floor_id') == 'ROOF', scene.get('floor_id'))
    check('Scene uses meters at unit scale 1',
          scene.unit_settings.system == 'METRIC' and
          abs(scene.unit_settings.scale_length - 1.0) < 1e-9)
    required = ['Roof_Slab', 'Roof_Parapet', 'Roof_Connection_3F',
                'Roof_Camera_Top_Orthographic', 'Roof_Camera_Perspective_Corner']
    check('Required roof geometry, connection marker, and cameras exist',
          all(name in bpy.data.objects for name in required), required)
    check('Only the slab and parapet are exportable architectural meshes',
          sorted(obj.name for obj in meshes) == ['Roof_Parapet', 'Roof_Slab'],
          sorted(obj.name for obj in meshes))
    check('All architectural object scales are unit',
          all(max(abs(value - 1.0) for value in obj.scale) < 1e-7 for obj in meshes))

    slab_bounds = bounds(slab) if slab else [[math.nan, math.nan]] * 3
    parapet_bounds = bounds(parapet) if parapet else [[math.nan, math.nan]] * 3
    slab_xyxy = ([slab_bounds[0][0], slab_bounds[1][0],
                  slab_bounds[0][1], slab_bounds[1][1]] if slab else [])
    check('Roof slab XY bounds match the approved 3F indoor body',
          close_list(slab_xyxy, EXPECTED_BOUNDS),
          {'actual': slab_xyxy, 'expected': EXPECTED_BOUNDS})
    check('Roof underside is the local assembly datum and slab is 0.20 m thick',
          bool(slab and close_list(slab_bounds[2], [0.0, 0.20])),
          slab_bounds[2] if slab else None)
    check('Parapet rises 0.30 m above the roof surface',
          bool(parapet and close_list(parapet_bounds[2], [0.20, 0.50])),
          parapet_bounds[2] if parapet else None)

    slab_rects = []
    if slab:
        try:
            slab_rects = json.loads(slab.get('footprint_rectangles_world', '[]'))
        except (TypeError, json.JSONDecodeError):
            slab_rects = []
    rects_match = len(slab_rects) == len(EXPECTED_RECTS) and all(
        close_list(actual, expected) for actual, expected in zip(slab_rects, EXPECTED_RECTS))
    check('Slab footprint uses the approved 3F indoor rectangles without a stair cut',
          rects_match and not json.loads(slab.get('subtracted_rectangles_world', '[]'))
          if slab else False,
          slab_rects)
    check('Representative 3F indoor points are covered by the roof',
          bool(slab and all(top_surface_contains(slab, x, y) for x, y in INDOOR_SAMPLES)),
          INDOOR_SAMPLES)
    check('Private-terrace sample points are not covered by the roof',
          bool(slab and not any(top_surface_contains(slab, x, y) for x, y in TERRACE_SAMPLES)),
          TERRACE_SAMPLES)

    geometry_quality = {}
    for obj in meshes:
        non_manifold, volume = manifold_status(obj)
        geometry_quality[obj.name] = {
            'non_manifold_edges': non_manifold,
            'volume_m3': volume,
            'components': mesh_components(obj),
        }
    check('Roof meshes are closed solids with positive volume',
          bool(meshes and all(item['non_manifold_edges'] == 0 and item['volume_m3'] > 0
                              for item in geometry_quality.values())),
          geometry_quality)
    check('Roof slab is one connected solid',
          bool(slab and mesh_components(slab) == 1),
          mesh_components(slab) if slab else None)
    check('Roof parapet is one connected union without overlapping box components',
          bool(parapet and mesh_components(parapet) == 1),
          mesh_components(parapet) if parapet else None)

    connection_ok = bool(connection and
                         max(abs(value) for value in connection.location) < 1e-7 and
                         connection.get('paired_object') == '3F wall-top datum Z=3.20 m')
    check('Roof carries an origin-aligned 3F assembly marker', connection_ok,
          {'location': list(connection.location) if connection else None,
           'paired_object': connection.get('paired_object') if connection else None})
    check('Saved top camera is truly orthographic',
          bool(top_camera and top_camera.type == 'CAMERA' and
               top_camera.data.type == 'ORTHO' and
               abs(top_camera.rotation_euler.x) < 1e-7 and
               abs(top_camera.rotation_euler.y) < 1e-7))
    check('Perspective validation camera exists',
          bool(corner_camera and corner_camera.type == 'CAMERA'))
    perspective_frame = None
    if corner_camera and meshes:
        projected = [world_to_camera_view(scene, corner_camera,
                     obj.matrix_world @ Vector(corner))
                     for obj in meshes for corner in obj.bound_box]
        perspective_frame = {
            'x_min': min(point.x for point in projected),
            'x_max': max(point.x for point in projected),
            'y_min': min(point.y for point in projected),
            'y_max': max(point.y for point in projected),
            'minimum_depth': min(point.z for point in projected),
        }
    check('Perspective camera contains the complete roof with safe margins',
          bool(perspective_frame and perspective_frame['minimum_depth'] > 0 and
               perspective_frame['x_min'] >= 0.035 and
               perspective_frame['x_max'] <= 0.965 and
               perspective_frame['y_min'] >= 0.035 and
               perspective_frame['y_max'] <= 0.965),
          perspective_frame)
    check('Live 3F source blend remains byte-identical',
          THREE_F_BLEND.exists() and sha(THREE_F_BLEND) == EXPECTED_3F_SHA256,
          sha(THREE_F_BLEND) if THREE_F_BLEND.exists() else None)

    names = [obj.name for obj in scene.objects]
    check('No duplicate object names', len(names) == len(set(names)))
    banned = ('furniture', 'chair', 'table', 'solar', 'tree', 'landscape', 'terrace')
    check('No furniture, equipment, landscaping, or terrace geometry exists',
          not [obj.name for obj in meshes
               if any(word in obj.name.lower() for word in banned)])

    render_names = ['Roof_shell_top.png', 'Roof_shell_perspective_corner.png']
    build_started = float(scene.get('build_started_unix_s', 0.0))
    render_status = {
        name: {
            'exists': (OUT / name).exists(),
            'bytes': (OUT / name).stat().st_size if (OUT / name).exists() else 0,
            'modified_unix_s': (OUT / name).stat().st_mtime if (OUT / name).exists() else 0,
            'from_current_build': bool((OUT / name).exists() and
                                       (OUT / name).stat().st_mtime >= build_started),
        }
        for name in render_names
    }
    if '--require-renders' in sys.argv:
        check('Required validation renders exist and are nonempty',
              all(item['exists'] and item['bytes'] > 10000 and item['from_current_build']
                  for item in render_status.values()), render_status)

    result = {
        'checks': CHECKS,
        'passed': sum(item['pass'] for item in CHECKS),
        'failed': sum(not item['pass'] for item in CHECKS),
        'mesh_objects': len(meshes),
        'object_count_total': len(scene.objects),
        'triangles': sum(len(poly.vertices) - 2 for obj in meshes for poly in obj.data.polygons),
        'bounds_m': {
            'min': [slab_bounds[i][0] for i in range(3)] if slab else None,
            'max': [slab_bounds[i][1] for i in range(3)] if slab else None,
        },
        'assembly': {
            'roof_local_underside_z_m': 0.0,
            'recommended_3f_relative_pose_z_m': 3.2,
            'assembled_roof_top_z_m': 3.4,
            'assembled_parapet_top_z_m': 3.7,
        },
        'source_3f_sha256': sha(THREE_F_BLEND) if THREE_F_BLEND.exists() else None,
        'geometry_quality': geometry_quality,
        'validation_images': render_status,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'Roof_shell_validation.json').write_text(json.dumps(result, indent=2))
    print(f"VALIDATION: {result['passed']} passed; {result['failed']} failed")
    for item in CHECKS:
        print(('PASS ' if item['pass'] else 'FAIL ') + item['name'])
    if result['failed']:
        raise AssertionError('Roof shell validation failed; see Roof_shell_validation.json')
    return result


if __name__ == '__main__':
    run()
