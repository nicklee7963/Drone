"""Patch only the audited 2F wall gaps and wall/glass endpoint cracks.

Run with:
    blender -b 2F_shell.blend --python-exit-code 1 --python repair_2F_wall_openings.py
"""
import bpy
import json
import math
import sys
from pathlib import Path

from mathutils import Vector

OUT = Path(__file__).resolve().parent
TARGET = OUT / '2F_shell.blend'
BACKUP = OUT / '2F_shell_before_opening_gap_repair.blend'
OVERVIEW = OUT / '2F_shell_openings_repaired_overview.png'

sys.path.insert(0, str(OUT))
import build_2F_shell as spec


def world_top_rectangles(obj):
    records = []
    for face in obj.data.polygons:
        if (obj.matrix_world.to_3x3() @ face.normal).z < .999:
            continue
        points = [obj.matrix_world @ obj.data.vertices[i].co for i in face.vertices]
        records.append((min(p.x for p in points), min(p.y for p in points),
                        max(p.x for p in points), max(p.y for p in points)))
    return records


def replace_with_world_box(obj, rect, z0=0.0, z1=3.2):
    """Replace one object's mesh with a clean, manifold world-aligned prism."""
    x0, y0, x1, y1 = rect
    inv = obj.matrix_world.inverted()
    world_vertices = [
        (x0,y0,z0), (x1,y0,z0), (x1,y1,z0), (x0,y1,z0),
        (x0,y0,z1), (x1,y0,z1), (x1,y1,z1), (x0,y1,z1),
    ]
    vertices = [tuple(inv @ Vector(point)) for point in world_vertices]
    faces = [
        (3,2,1,0), (4,5,6,7),
        (0,1,5,4), (1,2,6,5), (2,3,7,6), (3,0,4,7),
    ]
    old_mesh = obj.data
    materials = [slot.material for slot in obj.material_slots if slot.material]
    if not materials:
        fallback = {'wall':'Placeholder_Wall_Gray','glass':'Placeholder_Glass_Blue'}.get(
            obj.get('element_type'))
        if fallback and bpy.data.materials.get(fallback):
            materials = [bpy.data.materials[fallback]]
    mesh = bpy.data.meshes.new(f'{obj.name}_RepairedMesh')
    mesh.from_pydata(vertices, [], faces)
    mesh.update(calc_edges=True)
    for material in materials:
        mesh.materials.append(material)
    obj.data = mesh
    if old_mesh.users == 0:
        bpy.data.meshes.remove(old_mesh)
    obj['footprint_rectangles_world'] = json.dumps([list(rect)])
    obj['subtracted_rectangles_world'] = '[]'
    obj['z_min'] = z0
    obj['z_max'] = z1


def update_opening_metadata(scene):
    schedule = []
    for item in spec.WALL_OPENING_SCHEDULE:
        record = dict(item)
        if item['classification'] == 'intentional_doorway':
            rect = item['aperture_px']
            record['width_m'] = ((rect[2]-rect[0])*spec.SX if item['width_axis'] == 'x'
                                 else (rect[3]-rect[1])*spec.SY)
            record['aperture_world_xyxy_m'] = spec.world_rect(rect)
            if item.get('clear_aperture_px'):
                record['clear_aperture_world_xyxy_m'] = spec.world_rect(item['clear_aperture_px'])
        else:
            a, b = item['marker_path_px']
            record['marker_center_world_xy_m'] = spec.xy((a[0]+b[0])/2, (a[1]+b[1])/2)
            record['aperture_world_xyxy_m'] = spec.world_rect(item['aperture_px'])
        schedule.append(record)
    scene['wall_opening_schedule_json'] = json.dumps(schedule)
    scene['wall_topology_corrections_json'] = json.dumps(spec.WALL_TOPOLOGY_CORRECTIONS)
    scene['opening_gap_repair'] = (
        '2026-09-14: closed two accidental B-service wall gaps and extended only '
        'the eight audited glazing objects to their intended wall/column faces.'
    )


def look_at(obj, target):
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()


def render_overview(scene):
    camera = bpy.data.objects.get('2F_Camera_Openings_Repaired_Overview')
    if camera is None:
        data = bpy.data.cameras.new('2F_Camera_Openings_Repaired_Overview')
        camera = bpy.data.objects.new('2F_Camera_Openings_Repaired_Overview', data)
        collection = bpy.data.collections.get('2F_VALIDATION_CAMERAS') or scene.collection
        collection.objects.link(camera)
    camera.data.type = 'PERSP'
    camera.data.lens = 52
    camera.data.sensor_width = 36
    camera.location = (32.0, -38.0, 46.0)
    look_at(camera, (0.0, -1.0, .35))
    scene.camera = camera
    scene.render.resolution_x = 2400
    scene.render.resolution_y = 1700
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.filepath = str(OVERVIEW)
    if scene.render.engine == 'CYCLES':
        scene.cycles.samples = 64
        scene.cycles.use_denoising = True
    bpy.ops.render.render(write_still=True)


def main():
    if Path(bpy.data.filepath).resolve() != TARGET.resolve():
        raise RuntimeError(f'Open {TARGET.name} before running this patch')
    # Save an exact copy before mutating any datablock.
    if not BACKUP.exists():
        bpy.ops.wm.save_as_mainfile(filepath=str(BACKUP), copy=True)

    wall = bpy.data.objects['2F_Wall_Interior_011_BService_Corridor']
    old_rects = world_top_rectangles(wall)
    if len(old_rects) not in {1,3}:
        raise RuntimeError(f'Expected one repaired or three defective B-service segments, found {len(old_rects)}')
    repaired_wall_rect = (min(r[0] for r in old_rects), min(r[1] for r in old_rects),
                          max(r[2] for r in old_rects), max(r[3] for r in old_rects))
    replace_with_world_box(wall, repaired_wall_rect)
    resized_source = spec.resize_rect((773,560,1086,567), spec.INTERIOR_WALL_THICKNESS, 'CENTER')
    wall['source_pixel_rectangles'] = json.dumps([resized_source])
    wall['original_source_pixel_rectangles'] = json.dumps([[773,560,1086,567]])
    wall['measured_thicknesses_m'] = json.dumps([spec.INTERIOR_WALL_THICKNESS])

    affected = {
        'GuestA_West_North', 'GuestA_West_South', 'FamilyLounge_North',
        'Gaming_East_North', 'Gaming_East_South', 'Ensuite1_West',
        'Ensuite2_East', 'ArtGallery_South',
    }
    glazing_by_label = {label:(index,a,b) for index,(label,a,b) in enumerate(spec.GLAZING,1)}
    repaired_glass = []
    for label in sorted(affected):
        index, a, b = glazing_by_label[label]
        obj = bpy.data.objects[f'2F_Glass_{index:03d}_{label}']
        x0, y0 = spec.xy(*a)
        x1, y1 = spec.xy(*b)
        if math.isclose(x0, x1, abs_tol=1e-8):
            rect = (x0-spec.GLASS_THICKNESS/2, min(y0,y1),
                    x0+spec.GLASS_THICKNESS/2, max(y0,y1))
            if label.startswith('Gaming_East_'):
                east_wall = bpy.data.objects['2F_Wall_Exterior_008_RightCorridor_East']
                east_wall_inner_face = min(r[0] for r in world_top_rectangles(east_wall))
                rect = (east_wall_inner_face-spec.GLASS_THICKNESS, min(y0,y1),
                        east_wall_inner_face, max(y0,y1))
        else:
            rect = (min(x0,x1), y0-spec.GLASS_THICKNESS/2,
                    max(x0,x1), y0+spec.GLASS_THICKNESS/2)
        replace_with_world_box(obj, rect)
        obj['source_pixel_line'] = json.dumps([a,b])
        obj['nominal_thickness_m'] = spec.GLASS_THICKNESS
        repaired_glass.append(obj.name)

    update_opening_metadata(bpy.context.scene)
    bpy.context.scene['opening_gap_repaired_objects_json'] = json.dumps([wall.name] + repaired_glass)
    bpy.ops.wm.save_as_mainfile(filepath=str(TARGET))

    # The validator reads actual evaluated mesh geometry and raises on failure.
    import validate_2F_shell
    result = validate_2F_shell.run()
    render_overview(bpy.context.scene)
    bpy.ops.wm.save_as_mainfile(filepath=str(TARGET))
    print('OPENING_GAP_REPAIR_COMPLETE=' + json.dumps({
        'backup': str(BACKUP),
        'blend': str(TARGET),
        'overview': str(OVERVIEW),
        'validation_passed': result['passed'],
        'validation_failed': result['failed'],
        'repaired_wall': wall.name,
        'repaired_glass': repaired_glass,
    }))


if __name__ == '__main__':
    main()
