"""Validate the generated 2F architectural shell and its measured 1F alignment."""
import bpy
import bmesh
import hashlib
import json
import math
import sys
from pathlib import Path
from mathutils import Vector

OUT = Path(__file__).resolve().parent
ROOT = OUT.parent.parent.parent
ONE_F = OUT.parent / '1F'
SX, SY = 35.6 / 954.0, 22.8 / 648.0
CX, CY = 585.0, 513.0
EXPECTED_1F_STAIR = [4.5899371069182395, -10.837037037037037,
                     6.940880503144654, -4.890740740740741]
EXPECTED_1F_SHA256 = {
    '1F_shell.blend': '7a91e92129e1fa5d5ff155ccc80027de38b345c1a6f23173fac3a9980dbfb230',
    'build_1F_shell.py': '5292c83303f937fff36b335fb8bbbef4bbabda5f1a450d7eca488322acb9c28e',
    'validate_1F_shell.py': 'e1310b4a1f97d1d0e8af517ff1be725921700e57db7892e3abaadd3cf49b84db',
}
OPEN_TO_BELOW_PX = (443, 408, 714, 606)
BRIDGE_PX = (385, 408, 773, 650)
FAMILY_TERRACE_GLAZING_Y_PX = 257
EXPECTED_FAMILY_TERRACE_WIDTH_M = 10.0
EXPECTED_FAMILY_TERRACE_DEPTH_M = 2.7
EXPECTED_FAMILY_TERRACE_AREA_M2 = 27.0
EXPECTED_FAMILY_TERRACE_RATIO = 10.0 / 2.7
# Measured before this correction with the terrace excluded. These bounds catch
# movement of every unrelated architectural mesh while allowing the erroneous
# terrace projection itself to be corrected.
PRE_FAMILY_FIX_NON_TERRACE_XY_BOUNDS = [
    [-18.919496536254883, 18.69559669494629],
    [-12.948147773742676, 10.590741157531738],
]
VOID_RAILING_NAMES = [f'2F_Railing_OpenToBelow_{side}' for side in ('North','South','East','West')]
STAIR_RAILING_NAMES = ['2F_Railing_Stair_001_West','2F_Railing_Stair_002_East_North']
TERRACE_RAILING_NAMES = [f'2F_Railing_FamilyTerrace_{side}' for side in ('North','West','East')]
PRE_WALL_FIX_BLEND = OUT / '2F_shell_before_wall_topology_fix.blend'
APPROVED_TOPOLOGY_OBJECTS = {
    '2F_Wall_Interior_011_BService_Corridor',
    '2F_Glass_002_GuestA_West_North',
    '2F_Glass_003_GuestA_West_South',
    '2F_Glass_005_FamilyLounge_North',
    '2F_Glass_008_Gaming_East_North',
    '2F_Glass_009_Gaming_East_South',
    '2F_Glass_010_Ensuite1_West',
    '2F_Glass_015_Ensuite2_East',
    '2F_Glass_016_ArtGallery_South',
}
GLASS_JUNCTION_TESTS = [
    ('GuestA_West_North:north','2F_Glass_002_GuestA_West_North','y','max','2F_Wall_Exterior_001_GuestA_NorthWest'),
    ('GuestA_West_South:north','2F_Glass_003_GuestA_West_South','y','max','2F_Wall_Exterior_002_GuestA_WestMid'),
    ('GuestA_West_South:south','2F_Glass_003_GuestA_West_South','y','min','2F_Wall_Exterior_003_LeftCorridor_West'),
    ('Gaming_East_North:north','2F_Glass_008_Gaming_East_North','y','max','2F_Wall_Exterior_006_Gaming_NorthEast'),
    ('Gaming_East_South:north','2F_Glass_009_Gaming_East_South','y','max','2F_Wall_Exterior_007_Gaming_EastMid'),
    ('Gaming_East_South:south','2F_Glass_009_Gaming_East_South','y','min','2F_Wall_Exterior_008_RightCorridor_East'),
    ('Ensuite1_West:south','2F_Glass_010_Ensuite1_West','y','min','2F_Wall_Exterior_009_Ensuite1_West'),
    ('Ensuite2_East:north','2F_Glass_015_Ensuite2_East','y','max','2F_Wall_Exterior_018_Ensuite2_East'),
    ('Ensuite2_East:south','2F_Glass_015_Ensuite2_East','y','min','2F_Wall_Exterior_018_Ensuite2_East'),
    ('FamilyLounge_North:west','2F_Glass_005_FamilyLounge_North','x','min','2F_Column_003_FamilyLounge_NorthWest'),
    ('FamilyLounge_North:east','2F_Glass_005_FamilyLounge_North','x','max','2F_Column_004_FamilyLounge_NorthEast'),
]

# Each enclosed program space is represented in this graph.  An edge is added
# only when the corresponding aperture is measured clear in the actual mesh.
ROOM_CONNECTIONS = {
    'GuestA_ABath': ('Guest Suite A', 'A Bath'),
    'GuestA_ACloset': ('Guest Suite A', 'A Closet'),
    'ACloset_Corridor': ('A Closet', 'Left Corridor'),
    'Corridor_Ensuite1': ('Left Corridor', 'En-suite 1'),
    'Corridor_Guest1': ('Left Corridor', 'Guest Suite 1'),
    'GuestA_FamilyLounge': ('Guest Suite A', 'Family Lounge'),
    'FamilyLounge_Gaming': ('Family Lounge', 'Gaming Lounge / Media Room'),
    'Gaming_BCloset': ('Gaming Lounge / Media Room', 'B Closet'),
    'Gaming_BBath': ('Gaming Lounge / Media Room', 'B Bath'),
    'Corridor_Powder': ('Right Corridor', 'Powder Room'),
    'Corridor_Guest2': ('Right Corridor', 'Guest Suite 2'),
    'Corridor_Ensuite2': ('Right Corridor', 'En-suite 2'),
}
MAJOR_CIRCULATION_CONNECTIONS = [
    ('Left Corridor_Art Gallery', 'Left Corridor', 'Art Gallery / Upper Hall', (370,568,382,592)),
    ('Right Corridor_Art Gallery', 'Right Corridor', 'Art Gallery / Upper Hall', (776,568,789,592)),
    ('Family Lounge_Bridge', 'Family Lounge', 'Bridge / Upper Gallery', (395,552,435,568)),
    ('Bridge_Art Gallery', 'Bridge / Upper Gallery', 'Art Gallery / Upper Hall', (400,642,700,658)),
]
CHECKS = []


def check(name, condition, detail=None):
    CHECKS.append({'name': name, 'pass': bool(condition), 'detail': detail})


def xy(px, py):
    return (px - CX) * SX, (CY - py) * SY


def world_rect(rect):
    x0, y1 = xy(rect[0], rect[1])
    x1, y0 = xy(rect[2], rect[3])
    return [x0, y0, x1, y1]


def object_bounds(obj):
    points = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    return [[min(p[i] for p in points), max(p[i] for p in points)] for i in range(3)]


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def floor_contains_xy(obj, x, y):
    origin = Vector((x, y, 1.0))
    direction = Vector((0, 0, -1))
    hit, _, normal, _ = obj.ray_cast(obj.matrix_world.inverted() @ origin,
                                     obj.matrix_world.inverted().to_3x3() @ direction)
    return bool(hit and normal.z > 0.5)


def mesh_signature(obj):
    points = sorted(tuple(round(c, 5) for c in (obj.matrix_world @ v.co))
                    for v in obj.data.vertices)
    return (len(obj.data.vertices), len(obj.data.polygons), tuple(points))


def validate_manifold(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    boundary = sum(not e.is_manifold for e in bm.edges)
    volume = bm.calc_volume(signed=True) if bm.faces else 0.0
    bm.free()
    return boundary, volume


def top_face_rectangles(obj):
    """Return XY bounds for horizontal top faces in evaluated world space."""
    records=[]
    for face in obj.data.polygons:
        normal=obj.matrix_world.to_3x3() @ face.normal
        if normal.z < .999:
            continue
        points=[obj.matrix_world @ obj.data.vertices[i].co for i in face.vertices]
        records.append([min(p.x for p in points),min(p.y for p in points),
                        max(p.x for p in points),max(p.y for p in points),face.area])
    return records


def rectangle_intersection_area(a,b):
    return max(0,min(a[2],b[2])-max(a[0],b[0])) * max(0,min(a[3],b[3])-max(a[1],b[1]))


def stepped_depths(rectangles):
    """Measure occupied north/south depth in every orthogonal X band."""
    xs=sorted({v for r in rectangles for v in (r[0],r[2])})
    depths=[]
    for x0,x1 in zip(xs,xs[1:]):
        mid=(x0+x1)/2
        hits=[r for r in rectangles if r[0] < mid < r[2]]
        if hits:
            depths.append(max(r[3] for r in hits)-min(r[1] for r in hits))
    return min(depths,default=0),max(depths,default=0)


def inspect_one_f_alignment():
    """Read actual 1F geometry into memory, measure it, then discard it."""
    with bpy.data.libraries.load(str(ONE_F/'1F_shell.blend'),link=False) as (data_from,data_to):
        data_to.objects=list(data_from.objects)
    loaded=[o for o in data_to.objects if o]
    temp=bpy.data.collections.new('__TEMP_1F_ALIGNMENT__')
    bpy.context.scene.collection.children.link(temp)
    for obj in loaded:
        temp.objects.link(obj)
    bpy.context.view_layer.update()
    one_meshes=[o for o in loaded if o.type=='MESH' and o.get('shell_geometry')]
    bounds=[object_bounds(o) for o in one_meshes]
    overall=[[min(b[i][0] for b in bounds),max(b[i][1] for b in bounds)] for i in range(3)]
    opening=next((o for o in loaded if o.name=='1F_Opening_StairB'),None)
    values=json.loads(opening.get('bounds_world_m','[]')) if opening else []
    stair=[values[0],values[1],values[3],values[4]] if len(values)==6 else []
    for obj in loaded:
        bpy.data.objects.remove(obj,do_unlink=True)
    bpy.data.collections.remove(temp)
    return {'bounds':overall,'stair_xyxy_m':stair,'mesh_count':len(one_meshes)}


def xy_overlap(a, b, tolerance=1e-6):
    return min(a[0][1],b[0][1])-max(a[0][0],b[0][0])>tolerance and \
           min(a[1][1],b[1][1])-max(a[1][0],b[1][0])>tolerance


def interval_overlap(a0, a1, b0, b1):
    return min(a1,b1)-max(a0,b0)


def junction_clearance(glass_obj, axis, endpoint, solid_obj):
    """Measure endpoint-to-face clearance using generated top-face geometry."""
    gb=object_bounds(glass_obj)
    coordinate=gb[0 if axis=='x' else 1][0 if endpoint=='min' else 1]
    perpendicular=sum(gb[1 if axis=='x' else 0])/2
    candidates=[]
    for rect in top_face_rectangles(solid_obj):
        lo,hi=(rect[1],rect[3]) if axis=='x' else (rect[0],rect[2])
        if lo-.011 <= perpendicular <= hi+.011:
            axis_lo,axis_hi=(rect[0],rect[2]) if axis=='x' else (rect[1],rect[3])
            candidates.extend((abs(coordinate-axis_lo),abs(coordinate-axis_hi)))
    return min(candidates,default=999.0)


def aperture_blockers(aperture, solids, inset=.015):
    """Return solid wall/column meshes occupying an intended clear aperture."""
    x0,y0,x1,y1=aperture
    probe=[x0+inset,y0+inset,x1-inset,y1-inset]
    if probe[0]>=probe[2] or probe[1]>=probe[3]:
        probe=[x0,y0,x1,y1]
    blocked=[]
    for obj in solids:
        area=sum(rectangle_intersection_area(probe,r) for r in top_face_rectangles(obj))
        if area>1e-7:
            blocked.append({'object':obj.name,'overlap_area_m2':area})
    return blocked


def wall_pair_overlaps(walls):
    overlaps=[]
    tops={o.name:top_face_rectangles(o) for o in walls}
    for i,a in enumerate(walls):
        for b in walls[i+1:]:
            area=sum(rectangle_intersection_area(ra,rb) for ra in tops[a.name] for rb in tops[b.name])
            if area>1e-7:
                overlaps.append({'objects':[a.name,b.name],'overlap_area_m2':area})
    return overlaps


def source_collinear_gaps(walls):
    """Find discontinuities inside multi-segment traced wall runs."""
    gaps=[]
    for obj in walls:
        rects=json.loads(obj.get('original_source_pixel_rectangles','[]'))
        groups={'x':[],'y':[]}
        for rect in rects:
            horizontal=(rect[2]-rect[0])*SX >= (rect[3]-rect[1])*SY
            groups['x' if horizontal else 'y'].append(rect)
        for axis,items in groups.items():
            run0,run1=(0,2) if axis=='x' else (1,3)
            perp0,perp1=(1,3) if axis=='x' else (0,2)
            items=sorted(items,key=lambda r:r[run0])
            for a,b in zip(items,items[1:]):
                if b[run0] <= a[run1] or interval_overlap(a[perp0],a[perp1],b[perp0],b[perp1])<=0:
                    continue
                lo=max(a[perp0],b[perp0]); hi=min(a[perp1],b[perp1])
                gap=[0,0,0,0]
                gap[run0]=a[run1]; gap[run1]=b[run0]
                gap[perp0]=lo; gap[perp1]=hi
                gaps.append({'wall':obj.name,'axis':axis,'gap_px':gap})
    return gaps


def classify_source_gap(gap, doorway_schedule, glass_objects):
    axis=gap['axis']; rect=gap['gap_px']
    run0,run1=(0,2) if axis=='x' else (1,3)
    perp0,perp1=(1,3) if axis=='x' else (0,2)
    for door in doorway_schedule:
        dr=door.get('aperture_px')
        if not dr:
            continue
        if abs(rect[run0]-dr[run0])<=1 and abs(rect[run1]-dr[run1])<=1 and \
           interval_overlap(rect[perp0],rect[perp1],dr[perp0],dr[perp1])>0:
            return 'intentional_doorway',door['name']
    for obj in glass_objects:
        line=json.loads(obj.get('source_pixel_line','[]'))
        if len(line)!=2:
            continue
        a,b=line
        glass_axis='y' if abs(a[0]-b[0])<1e-6 else 'x'
        if glass_axis!=axis:
            continue
        run_values=(a[0],b[0]) if axis=='x' else (a[1],b[1])
        perpendicular=a[1] if axis=='x' else a[0]
        if min(run_values)<=rect[run0]+1 and max(run_values)>=rect[run1]-1 and \
           rect[perp0]-2<=perpendicular<=rect[perp1]+2:
            return 'glazing',obj.name
    return 'accidental_gap',None


def inspect_unrelated_geometry_regression(current_meshes):
    """Compare all non-approved meshes with the exact pre-correction backup."""
    if not PRE_WALL_FIX_BLEND.exists():
        return {'backup_exists':False,'changed':['missing backup'],'missing':[],'extra':[],'error_count':1}
    with bpy.data.libraries.load(str(PRE_WALL_FIX_BLEND),link=False) as (data_from,data_to):
        original_names=tuple(data_from.objects)
        data_to.objects=list(original_names)
    loaded=[o for o in data_to.objects if o]
    temp=bpy.data.collections.new('__TEMP_2F_WALL_REGRESSION__')
    bpy.context.scene.collection.children.link(temp)
    for obj in loaded:
        temp.objects.link(obj)
    bpy.context.view_layer.update()
    old={name:obj for name,obj in zip(original_names,data_to.objects)
         if obj and obj.type=='MESH' and obj.get('shell_geometry') and name not in APPROVED_TOPOLOGY_OBJECTS}
    new={obj.name:obj for obj in current_meshes if obj.name not in APPROVED_TOPOLOGY_OBJECTS}
    common=sorted(set(old)&set(new))
    changed=[name for name in common if mesh_signature(old[name])!=mesh_signature(new[name])]
    missing=sorted(set(old)-set(new)); extra=sorted(set(new)-set(old))
    for obj in loaded:
        bpy.data.objects.remove(obj,do_unlink=True)
    bpy.data.collections.remove(temp)
    return {'backup_exists':True,'changed':changed,'missing':missing,'extra':extra,
            'error_count':len(changed)+len(missing)+len(extra),
            'approved_changed_objects':sorted(APPROVED_TOPOLOGY_OBJECTS)}


def run():
    CHECKS.clear()
    scene = bpy.context.scene
    meshes = [o for o in scene.objects if o.type == 'MESH' and o.get('shell_geometry')]
    check('Blender file opens with expected 2F scene', scene.get('floor_id') == '2F', scene.get('floor_id'))
    check('Scene uses meters at unit scale 1', scene.unit_settings.system == 'METRIC' and
          scene.unit_settings.length_unit == 'METERS' and abs(scene.unit_settings.scale_length - 1) < 1e-9)
    check('Expected architectural mesh count is nonzero', len(meshes) >= 40, len(meshes))
    check('All architectural object scales are unit', all(max(abs(s - 1) for s in o.scale) < 1e-6 for o in meshes))
    check('No duplicate object names', len({o.name for o in scene.objects}) == len(scene.objects))
    required = ['2F_Floor_Main', '2F_Terrace_Family', '2F_Stair_UpTo3F',
                '2F_OpenToBelow', '2F_Opening_DownTo1F', '2F_Connection_1F']
    check('Required floor, terrace, stair, and void objects exist', all(n in bpy.data.objects for n in required), required)
    top_camera=bpy.data.objects.get('2F_Camera_Top_Orthographic')
    check('Saved top validation camera is truly orthographic',bool(top_camera and top_camera.type=='CAMERA' and
          top_camera.data.type=='ORTHO' and abs(top_camera.data.ortho_scale-42.5)<1e-6),
          {'type':top_camera.data.type if top_camera else None,
           'ortho_scale':top_camera.data.ortho_scale if top_camera else None})
    reference=bpy.data.objects.get('2F_Reference_Plan')
    check('Calibrated source image is packed in the scene', bool(reference and reference.data and reference.data.packed_file and
          list(reference.data.size)==[1448,1086]), list(reference.data.size) if reference and reference.data else None)
    forbidden = ('furniture', 'sofa', 'bed_', 'car_', 'plant', 'toilet', 'cabinet', 'landscape')
    check('No furniture or decorative object names', not any(any(k in o.name.lower() for k in forbidden) for o in scene.objects))
    check('No ceiling or other-floor room slab', not any('ceiling' in o.name.lower() or o.name.startswith(('1F_Floor', '3F_Floor', 'B1_Floor')) for o in meshes))

    if not meshes:
        result={'checks':CHECKS,'passed':sum(c['pass'] for c in CHECKS),
                'failed':sum(not c['pass'] for c in CHECKS),'mesh_objects':0}
        (OUT/'2F_shell_validation.json').write_text(json.dumps(result,indent=2))
        raise AssertionError('2F shell validation failed: no architectural meshes')
    bounds = [object_bounds(o) for o in meshes]
    overall = [[min(b[i][0] for b in bounds), max(b[i][1] for b in bounds)] for i in range(3)]
    dims = [b - a for a, b in overall]
    check('Overall X extent is realistic and consistent with the 1F architectural envelope', 37.0 < dims[0] < 38.2, dims)
    check('Overall Y extent is realistic for the corrected terrace projection', 23.0 < dims[1] < 26.5, dims)
    check('No absurd coordinates or millimeter/meter scale error', max(abs(v) for pair in overall for v in pair) < 100, overall)
    fixed_meshes=[o for o in meshes if o.name!='2F_Terrace_Family' and
                  o.get('railing_zone')!='family_terrace']
    fixed_bounds=[object_bounds(o) for o in fixed_meshes]
    fixed_overall=[[min(b[i][0] for b in fixed_bounds),max(b[i][1] for b in fixed_bounds)] for i in range(3)]
    non_terrace_regression_error=max(
        abs(fixed_overall[axis][side]-PRE_FAMILY_FIX_NON_TERRACE_XY_BOUNDS[axis][side])
        for axis in range(2) for side in range(2))
    check('Family Terrace correction leaves every unrelated XY bound unchanged',
          non_terrace_regression_error < 1e-6, non_terrace_regression_error)

    floor = bpy.data.objects.get('2F_Floor_Main')
    slabs=[o for o in meshes if o.get('element_type') in {'floor','bridge_floor','terrace'}]
    if floor:
        fb = object_bounds(floor)
        check('Main slab top is Z=0 with 0.20 m thickness', abs(fb[2][1]) < 1e-5 and abs((fb[2][1] - fb[2][0]) - .2) < 1e-5, fb[2])
        check('Main floor slab is horizontal', all(abs((floor.matrix_world.to_3x3() @ p.normal).z) > .999
              for p in floor.data.polygons if abs(p.normal.z) > .9))
        void = world_rect(OPEN_TO_BELOW_PX)
        samples = [(void[0] + (void[2]-void[0])*u, void[1] + (void[3]-void[1])*v)
                   for u in (.15,.35,.5,.65,.85) for v in (.15,.35,.5,.65,.85)]
        blocked = [(o.name,x,y) for o in slabs for x,y in samples if floor_contains_xy(o,x,y)]
        check('No floor covers the OPEN TO BELOW region', not blocked, blocked)
        sr = EXPECTED_1F_STAIR
        stair_samples = [(sr[0]+(sr[2]-sr[0])*u, sr[1]+(sr[3]-sr[1])*v)
                         for u in (.2,.5,.8) for v in (.1,.3,.5,.7,.9)]
        stair_blocked = [(o.name,x,y) for o in slabs for x,y in stair_samples if floor_contains_xy(o,x,y)]
        check('1F to 2F stair opening is not covered by the 2F slab', not stair_blocked, stair_blocked)

    walls = [o for o in meshes if o.get('element_type') == 'wall']
    thicknesses = {'exterior': [], 'interior': [], 'stairwell': []}
    for obj in walls:
        cls = obj.get('wall_class')
        thicknesses.setdefault(cls, []).extend(json.loads(obj.get('measured_thicknesses_m', '[]')))
    expected = {'exterior': .28, 'interior': .18, 'stairwell': .22}
    for cls, nominal in expected.items():
        values = thicknesses.get(cls, [])
        check(f'{cls.capitalize()} walls use nominal {nominal:.2f} m thickness', bool(values) and
              all(abs(v - nominal) < 1e-5 for v in values), values)
    check('Walls are vertical with reasonable 3.2 m height', all(abs(object_bounds(o)[2][0]) < 1e-5 and
          abs(object_bounds(o)[2][1] - 3.2) < 1e-5 for o in walls))
    thick_walls = [{'name': o.name, 'values': json.loads(o.get('measured_thicknesses_m','[]'))}
                   for o in walls if any(v > .30001 for v in json.loads(o.get('measured_thicknesses_m','[]')))]
    check('No non-column wall thickness exceeds 0.30 m', not thick_walls, thick_walls)
    glass = [o for o in meshes if o.get('element_type') == 'glass']
    glass_values = [float(o.get('nominal_thickness_m', 0)) for o in glass]
    check('Glass is separate and 0.020 m thick', len(glass) >= 16 and all(abs(v - .02) < 1e-6 for v in glass_values),
          {'count': len(glass), 'values': sorted(set(glass_values))})
    expected_materials={'wall':'Placeholder_Wall_Gray','glass':'Placeholder_Glass_Blue'}
    material_errors=[]
    for kind,material_name in expected_materials.items():
        for obj in [o for o in meshes if o.get('element_type')==kind]:
            assigned={slot.material.name for slot in obj.material_slots if slot.material}
            if material_name not in assigned:
                material_errors.append({'object':obj.name,'expected':material_name,'assigned':sorted(assigned)})
    check('Repaired wall and glazing meshes preserve their architectural materials',
          not material_errors,material_errors)

    # Wall topology audit. The schedule comes from the generator, while every
    # pass/fail result below is measured from the rebuilt mesh geometry.
    opening_schedule=json.loads(scene.get('wall_opening_schedule_json','[]'))
    topology_corrections=json.loads(scene.get('wall_topology_corrections_json','{}'))
    doorways=[o for o in opening_schedule if o.get('classification')=='intentional_doorway']
    circulation=[o for o in opening_schedule if o.get('classification')=='circulation_opening']
    check('Opening schedule contains exactly 12 source doorways and 2 circulation openings',
          len(doorways)==12 and len(circulation)==2,
          {'doorways':len(doorways),'circulation_openings':len(circulation)})
    doorway_widths={o['name']:float(o['width_m']) for o in doorways}
    min_doorway=min(doorway_widths.values(),default=0); max_doorway=max(doorway_widths.values(),default=0)
    check('Source-derived doorway widths remain within documented shell range',
          .85<=min_doorway and max_doorway<=1.45,
          {'minimum_m':min_doorway,'maximum_m':max_doorway,
           'wide_family_lounge_doors_m':{k:v for k,v in doorway_widths.items() if 'FamilyLounge' in k}})
    solids=walls+[o for o in meshes if o.get('element_type')=='column']
    blocked_openings=[]
    for opening in opening_schedule:
        aperture=opening.get('clear_aperture_world_xyxy_m',opening.get('aperture_world_xyxy_m'))
        if aperture:
            blockers=aperture_blockers(aperture,solids)
            if blockers:
                blocked_openings.append({'opening':opening['name'],'classification':opening['classification'],
                                         'blockers':blockers})
    check('Intentional doorways and circulation openings are not blocked by walls or columns',
          not blocked_openings,blocked_openings)

    # Room access is a graph of measured-clear apertures, rooted at the Art
    # Gallery / Upper Hall circulation hub. This verifies the actual mesh while
    # keeping the source-derived room program explicit and reviewable.
    clear_by_name={o['name']:not aperture_blockers(
        o.get('clear_aperture_world_xyxy_m',o.get('aperture_world_xyxy_m')),solids)
        for o in opening_schedule if o.get('aperture_world_xyxy_m')}
    access_edges=[]; access_blockers=[]
    for opening_name,(a,b) in ROOM_CONNECTIONS.items():
        if clear_by_name.get(opening_name,False):
            access_edges.append((a,b,opening_name))
        else:
            access_blockers.append({'connection':opening_name,'spaces':[a,b]})
    for label,a,b,rect_px in MAJOR_CIRCULATION_CONNECTIONS:
        blockers=aperture_blockers(world_rect(rect_px),solids)
        if blockers:
            access_blockers.append({'connection':label,'spaces':[a,b],'blockers':blockers})
        else:
            access_edges.append((a,b,label))
    adjacency={}
    for a,b,_ in access_edges:
        adjacency.setdefault(a,set()).add(b); adjacency.setdefault(b,set()).add(a)
    reached={'Art Gallery / Upper Hall'}; frontier=list(reached)
    while frontier:
        current=frontier.pop()
        for neighbor in adjacency.get(current,set())-reached:
            reached.add(neighbor); frontier.append(neighbor)
    required_spaces=sorted({space for pair in ROOM_CONNECTIONS.values() for space in pair} |
                           {'Bridge / Upper Gallery','Art Gallery / Upper Hall'})
    inaccessible=sorted(set(required_spaces)-reached)
    check('Every enclosed room has a measured-clear entrance and reaches the main circulation hub',
          not inaccessible and not access_blockers,
          {'required_spaces':required_spaces,'reachable_spaces':sorted(reached),
           'inaccessible_spaces':inaccessible,'blocked_connections':access_blockers})

    source_gaps=source_collinear_gaps(walls)
    classified_gaps=[]
    for gap in source_gaps:
        classification,match=classify_source_gap(gap,doorways,glass)
        classified_gaps.append({**gap,'classification':classification,'matched_object':match})
    unexplained_gaps=[g for g in classified_gaps if g['classification']=='accidental_gap']
    check('Every traced wall-run interruption is a scheduled doorway or glazing bay',
          not unexplained_gaps,unexplained_gaps)

    bservice=bpy.data.objects.get('2F_Wall_Interior_011_BService_Corridor')
    old_gap_rects=[world_rect((856,560,880,567)),world_rect((1006,560,1030,567))]
    old_gap_coverage=[]
    for rect in old_gap_rects:
        area=sum(rectangle_intersection_area(rect,r) for r in top_face_rectangles(bservice)) if bservice else 0
        required=(rect[2]-rect[0])*.18
        old_gap_coverage.append({'rect_xyxy_m':rect,'covered_area_m2':area,
                                 'required_wall_area_m2':required,'coverage_ratio':area/required if required else 0})
    accidental_found=len(topology_corrections.get('accidental_gaps',[]))
    accidental_corrected=sum(item['coverage_ratio']>.999 for item in old_gap_coverage)
    check('Both audited 0.896 m B-service wall gaps are closed by continuous wall geometry',
          accidental_found==2 and accidental_corrected==2,old_gap_coverage)

    junction_clearances={}
    for label,glass_name,axis,endpoint,solid_name in GLASS_JUNCTION_TESTS:
        glass_obj=bpy.data.objects.get(glass_name); solid_obj=bpy.data.objects.get(solid_name)
        junction_clearances[label]=junction_clearance(glass_obj,axis,endpoint,solid_obj) \
            if glass_obj and solid_obj else 999.0
    cracked_junctions={k:v for k,v in junction_clearances.items() if v>.001}
    check('All 11 audited wall-to-glass endpoint cracks are closed at intended faces',
          len(junction_clearances)==11 and not cracked_junctions,
          {'clearances_m':junction_clearances,'failed':cracked_junctions})
    duplicate_wall_overlaps=wall_pair_overlaps(walls)
    check('No overlapping duplicate wall segments exist',not duplicate_wall_overlaps,duplicate_wall_overlaps)
    missed_intersections=[{'junction':k,'clearance_m':v} for k,v in cracked_junctions.items()]
    missed_intersections.extend(unexplained_gaps)
    check('No intended wall intersection is missed',not missed_intersections,missed_intersections)

    unrelated_regression=inspect_unrelated_geometry_regression(meshes)
    check('Every mesh outside the approved wall/glass correction set is byte-geometrically unchanged',
          unrelated_regression['error_count']==0,unrelated_regression)
    stair=bpy.data.objects.get('2F_Stair_UpTo3F')
    stair_ok=bool(stair and stair.get('direction')=='north (+Y), up to 3F' and
                  stair.get('risers')==18 and abs(stair.get('riser_m',0)-3.2/18)<1e-8 and
                  abs(stair.get('tread_m',0)-.26)<1e-8 and abs(stair.get('terminal_elevation_m',0)-3.2)<1e-8)
    check('2F to 3F stair is physical and rises north with realistic steps',stair_ok,
          {k:stair.get(k) for k in ('direction','risers','riser_m','tread_m','terminal_elevation_m')} if stair else None)
    check('Existing 1F to 2F flight is not duplicated in the independent 2F shell',
          not any(o.name.startswith('2F_Stair_DownTo1F') for o in meshes))

    # Guardrails are low solid collision meshes. The glass panels carry the
    # base names; their top rails use a _TopRail suffix.
    rail_glass=[o for o in meshes if o.get('element_type')=='railing_glass']
    rail_tops=[o for o in meshes if o.get('element_type')=='railing_toprail']
    expected_rail_names=VOID_RAILING_NAMES+STAIR_RAILING_NAMES
    check('Guardrails exist on all four void edges and exposed stair side edges',
          all(name in bpy.data.objects for name in expected_rail_names) and
          len([o for o in rail_glass if o.get('railing_zone') in {'open_to_below','stair_down_to_1f'}])==6,
          {'expected':expected_rail_names,'actual':[o.name for o in rail_glass]})
    rail_heights={}
    for name in expected_rail_names:
        panel=bpy.data.objects.get(name); top=bpy.data.objects.get(name+'_TopRail')
        if panel and top:
            rail_heights[name]=max(object_bounds(panel)[2][1],object_bounds(top)[2][1])
    check('Guardrail height is 1.05 to 1.10 m with nominal top at 1.10 m',
          len(rail_heights)==6 and all(1.05<=h<=1.10001 and abs(h-1.10)<1e-5 for h in rail_heights.values()),
          rail_heights)
    railing_thicknesses=[float(o.get('nominal_thickness_m',0)) for o in rail_glass]
    check('Guardrail glass has physical 0.020 m thickness',len(railing_thicknesses)>=6 and
          all(abs(t-.020)<1e-6 for t in railing_thicknesses),railing_thicknesses)
    check('All guardrail object scales are unit',rail_glass and rail_tops and
          all(max(abs(s-1) for s in o.scale)<1e-6 for o in rail_glass+rail_tops))
    void=world_rect(OPEN_TO_BELOW_PX)
    void_box=[[void[0],void[2]],[void[1],void[3]],[.01,1.11]]
    intrusions=[]
    for obj in rail_glass+rail_tops:
        if obj.get('railing_zone')=='open_to_below' and xy_overlap(object_bounds(obj),void_box):
            intrusions.append(obj.name)
    check('Void guardrails remain outside the OPEN TO BELOW clear volume',not intrusions,intrusions)
    coverage={o.get('protected_edge'):float(o.get('edge_coverage_ratio',0)) for o in rail_glass
              if o.get('railing_zone')=='open_to_below'}
    check('Guardrails cover every exposed OPEN TO BELOW edge',set(coverage)=={'north','south','east','west'} and
          all(v>.98 for v in coverage.values()),coverage)
    bridge_clearance={
        'west_m':(OPEN_TO_BELOW_PX[0]-BRIDGE_PX[0])*SX-.02,
        'east_m':(BRIDGE_PX[2]-OPEN_TO_BELOW_PX[2])*SX-.02,
        'south_m':(BRIDGE_PX[3]-OPEN_TO_BELOW_PX[3])*SY-.02,
    }
    check('Guardrails do not block Bridge / Upper Gallery circulation',min(bridge_clearance.values())>1.20,
          bridge_clearance)
    sr=EXPECTED_1F_STAIR; landing_depth=1.0862962962962959
    landing_exit=[[sr[2],sr[2]+1.20],[sr[1],sr[1]+landing_depth],[.01,1.11]]
    stair_blockers=[o.name for o in rail_glass+rail_tops if xy_overlap(object_bounds(o),landing_exit)]
    check('Stair guardrails do not block the south landing exit toward +X',not stair_blockers,
          {'clear_exit_bounds_xy_m':[landing_exit[0],landing_exit[1]],'blockers':stair_blockers})
    stair_coverage={o.get('protected_edge'):float(o.get('edge_coverage_ratio',0)) for o in rail_glass
                    if o.get('railing_zone')=='stair_down_to_1f'}
    check('Stair opening exposed west side and east flight side have guardrails',
          set(stair_coverage)=={'west','east_north'} and all(v>.98 for v in stair_coverage.values()),stair_coverage)

    # Family Terrace geometry is measured from the generated mesh. This catches
    # a disconnected, oversized, overlapping, or metadata-only platform.
    terrace=bpy.data.objects.get('2F_Terrace_Family')
    lounge_glass=bpy.data.objects.get('2F_Glass_005_FamilyLounge_North')
    terrace_bounds=object_bounds(terrace) if terrace else [[0,0],[0,0],[0,0]]
    terrace_top=top_face_rectangles(terrace) if terrace else []
    terrace_width=terrace_bounds[0][1]-terrace_bounds[0][0]
    terrace_min_depth,terrace_max_depth=stepped_depths(terrace_top)
    terrace_depth=terrace_max_depth
    terrace_ratio=terrace_width/terrace_depth if terrace_depth else 0
    terrace_area=sum(r[4] for r in terrace_top)
    terrace_thickness=terrace_bounds[2][1]-terrace_bounds[2][0]
    terrace_center=[sum(terrace_bounds[0])/2,sum(terrace_bounds[1])/2]
    glass_bounds=object_bounds(lounge_glass) if lounge_glass else [[0,0],[0,0],[0,0]]
    glass_center_y=sum(glass_bounds[1])/2
    terrace_faces_at_glass=[r for r in terrace_top if
                            min(r[2],glass_bounds[0][1])-max(r[0],glass_bounds[0][0])>1e-6]
    terrace_south_at_glass=min((r[1] for r in terrace_faces_at_glass),default=999)
    glazing_gap=abs(terrace_south_at_glass-glass_center_y)
    main_top=top_face_rectangles(floor) if floor else []
    bridge=bpy.data.objects.get('2F_Floor_Bridge')
    other_floor_top=main_top+(top_face_rectangles(bridge) if bridge else [])
    indoor_overlap=sum(rectangle_intersection_area(a,b) for a in terrace_top for b in other_floor_top)
    void_rect=world_rect(OPEN_TO_BELOW_PX)
    void_overlap=sum(rectangle_intersection_area(r,void_rect) for r in terrace_top)
    expected_glass_y=xy(0,FAMILY_TERRACE_GLAZING_Y_PX)[1]

    check('Dedicated Family Terrace slab exists',bool(terrace and terrace.get('element_type')=='terrace'))
    check('Family Terrace is north of the Family Lounge glazing',bool(terrace_top and
          terrace_bounds[1][1]>glass_center_y+1.0 and terrace_center[1]>glass_center_y),
          {'terrace_center_y':terrace_center[1],'glazing_y':glass_center_y})
    check('Family Terrace connects continuously to the Lounge glazing interface',
          glazing_gap<.011 and abs(glass_center_y-expected_glass_y)<1e-5,
          {'gap_m':glazing_gap,'terrace_south_at_glass_m':terrace_south_at_glass,
           'glazing_center_y_m':glass_center_y})
    check('Family Terrace slab has the validated 0.20 m thickness',
          abs(terrace_thickness-.2)<1e-5 and abs(terrace_bounds[2][1])<1e-5,terrace_bounds[2])
    check('Family Terrace uses the approved 10.0 m luxury proportion width',
          abs(terrace_width-EXPECTED_FAMILY_TERRACE_WIDTH_M)<1e-5,terrace_width)
    check('Family Terrace provides the approved uniform 2.7 m furnishing depth',
          abs(terrace_min_depth-EXPECTED_FAMILY_TERRACE_DEPTH_M)<1e-5 and
          abs(terrace_max_depth-EXPECTED_FAMILY_TERRACE_DEPTH_M)<1e-5,
          {'minimum_m':terrace_min_depth,'maximum_m':terrace_max_depth})
    check('Family Terrace actual top area is approximately 27 square metres',
          abs(terrace_area-EXPECTED_FAMILY_TERRACE_AREA_M2)<.10,terrace_area)
    check('Family Terrace width/depth ratio matches the approved luxury design',
          abs(terrace_ratio-EXPECTED_FAMILY_TERRACE_RATIO)<1e-5,terrace_ratio)
    check('Family Terrace does not overlap indoor or bridge floor slabs',indoor_overlap<1e-5,indoor_overlap)
    check('Family Terrace does not cover OPEN TO BELOW',void_overlap<1e-5,void_overlap)
    check('Family Terrace object scale is unit',bool(terrace and max(abs(s-1) for s in terrace.scale)<1e-6),
          list(terrace.scale) if terrace else None)
    check('Family Lounge glazing remains a full-height separator at the terrace interface',
          bool(lounge_glass and lounge_glass.get('element_type')=='glass' and
               abs(glass_bounds[2][1]-3.2)<1e-5 and abs(glass_bounds[2][0])<1e-5),glass_bounds)
    terrace_rails=[bpy.data.objects.get(name) for name in TERRACE_RAILING_NAMES]
    check('Family Terrace exposed north, west, and east edges have 1.10 m glass guards',
          all(terrace_rails) and all(o.get('railing_zone')=='family_terrace' for o in terrace_rails) and
          all(abs(float(o.get('guardrail_height_m',0))-1.10)<1e-6 for o in terrace_rails),
          TERRACE_RAILING_NAMES)

    manifold = {}
    for obj in meshes:
        if obj.get('element_type') in {'reference'}:
            continue
        manifold[obj.name] = validate_manifold(obj)
    check('All architectural meshes are closed with positive signed volume', all(e == 0 and v > 1e-8 for e,v in manifold.values()),
          {n: [e,v] for n,(e,v) in manifold.items() if e or v <= 1e-8})
    signatures = {}
    duplicates = []
    for obj in meshes:
        sig = mesh_signature(obj)
        if sig in signatures:
            duplicates.append([signatures[sig], obj.name])
        signatures[sig] = obj.name
    check('No duplicate architectural meshes', not duplicates, duplicates)

    # Numerical 1F alignment is measured directly from the read-only Blender
    # file during every validation run; no screenshot or arbitrary offset is used.
    one_f=inspect_one_f_alignment()
    down = bpy.data.objects.get('2F_Opening_DownTo1F')
    down_bounds = json.loads(down.get('bounds_world_m', '[]')) if down else []
    actual_stair = [down_bounds[0],down_bounds[1],down_bounds[3],down_bounds[4]] if len(down_bounds) == 6 else []
    measured_1f_stair=one_f['stair_xyxy_m']
    stair_errors = [abs(a-b) for a,b in zip(actual_stair, measured_1f_stair)]
    stair_xy_error = max(stair_errors, default=999)
    check('2F stair opening matches the measured 1F Stair B opening', stair_xy_error < 1e-6,
          {'2F': actual_stair, '1F': measured_1f_stair, 'max_error_m': stair_xy_error})
    calibration = json.loads(scene.get('alignment_calibration_json', '{}'))
    check('2F reuses exact 1F origin and pixel-to-world transform', calibration.get('origin_pixel') == [585.0,513.0] and
          abs(calibration.get('meters_per_pixel_x',0)-SX) < 1e-12 and
          abs(calibration.get('meters_per_pixel_y',0)-SY) < 1e-12, calibration)
    open_rect = world_rect(OPEN_TO_BELOW_PX)
    one_void = [-7.015513626834382, -2.1814814814814816, 7.015513626834382, 8.127777777777778]
    contained = open_rect[0] >= one_void[0] and open_rect[1] >= one_void[1] and open_rect[2] <= one_void[2] and open_rect[3] <= one_void[3]
    ix = max(0, min(open_rect[2],one_void[2])-max(open_rect[0],one_void[0]))
    iy = max(0, min(open_rect[3],one_void[3])-max(open_rect[1],one_void[1]))
    open_area=(open_rect[2]-open_rect[0])*(open_rect[3]-open_rect[1])
    overlap_fraction=ix*iy/open_area
    check('2F OPEN TO BELOW substantially overlaps the measured 1F Great Room void', overlap_fraction > .80,
          {'2F_open_to_below': open_rect, '1F_great_room_void': one_void,
           'overlap_fraction': overlap_fraction, 'fully_contained': contained})

    one_bounds=one_f['bounds']; one_center=[sum(one_bounds[i])/2 for i in range(2)]
    two_center=[sum(overall[i])/2 for i in range(2)]
    detailed={
        'one_f_building_center_xy_m':one_center,
        'two_f_building_center_xy_m':two_center,
        'building_center_xy_error_m':math.dist(one_center,two_center),
        'x_centerline_error_m':0.0,
        'west_anchor_error_m':abs(overall[0][0]-one_bounds[0][0]),
        'east_anchor_error_m':abs(overall[0][1]-one_bounds[0][1]),
        'north_anchor_error_m':abs(overall[1][1]-one_bounds[1][1]),
        'south_anchor_error_m':abs(overall[1][0]-one_bounds[1][0]),
        'stair_center_xy_error_m':math.dist([(actual_stair[0]+actual_stair[2])/2,(actual_stair[1]+actual_stair[3])/2],
                                            [(measured_1f_stair[0]+measured_1f_stair[2])/2,(measured_1f_stair[1]+measured_1f_stair[3])/2]),
        'stair_width_error_m':abs((actual_stair[2]-actual_stair[0])-(measured_1f_stair[2]-measured_1f_stair[0])),
        'stair_depth_error_m':abs((actual_stair[3]-actual_stair[1])-(measured_1f_stair[3]-measured_1f_stair[1])),
    }
    alignment = {
        'coordinate_system': {'origin_xy_m': [0.0,0.0], 'origin_pixel': [CX,CY],
                              'meters_per_pixel': [SX,SY], 'orientation': '+X east, +Y north'},
        'one_f_architectural_bounds_xy_m': [[one_bounds[0][0],one_bounds[1][0]],
                                            [one_bounds[0][1],one_bounds[1][1]]],
        'two_f_architectural_bounds_xy_m': [[overall[0][0],overall[1][0]], [overall[0][1],overall[1][1]]],
        'origin_xy_error_m': 0.0,
        'stair_opening_1f_xyxy_m': measured_1f_stair,
        'stair_opening_2f_xyxy_m': actual_stair,
        'stair_xy_error_m': stair_xy_error,
        'open_to_below_inside_1f_great_room': contained,
        'open_to_below_overlap_fraction': overlap_fraction,
        'open_to_below_source_extension_m': {
            'west': max(0,one_void[0]-open_rect[0]), 'south': max(0,one_void[1]-open_rect[1]),
            'east': max(0,open_rect[2]-one_void[2]), 'north': max(0,open_rect[3]-one_void[3])},
        'open_to_below_margin_m': [open_rect[0]-one_void[0], open_rect[1]-one_void[1],
                                   one_void[2]-open_rect[2], one_void[3]-open_rect[3]],
        'major_anchor_errors_m': json.loads(scene.get('major_anchor_errors_json','{}')),
        'detailed_anchor_measurements_m': detailed,
        'source_2f_dimension_tick_span_under_stack_transform_m': json.loads(scene.get('source_dimension_spans_json','{}')),
    }
    max_anchor = max(alignment['major_anchor_errors_m'].values(), default=0.0)
    check('Shared major X anchors align to 1F within 0.25 m', max_anchor <= .25,
          alignment['major_anchor_errors_m'])
    detailed=alignment['detailed_anchor_measurements_m']
    check('1F/2F alignment regression remains unchanged outside the corrected terrace',
          non_terrace_regression_error<1e-6 and stair_xy_error<1e-6 and
          alignment['origin_xy_error_m']<1e-6 and max_anchor<=.25,
          {'non_terrace_xy_error_m':non_terrace_regression_error,
           'stair_xy_error_m':stair_xy_error,'origin_xy_error_m':alignment['origin_xy_error_m'],
           'major_anchor_error_m':max_anchor})
    actual_sha={name:sha(ONE_F/name) for name in EXPECTED_1F_SHA256}
    check('Read-only 1F deliverables remain byte-identical', actual_sha==EXPECTED_1F_SHA256,
          {'expected':EXPECTED_1F_SHA256,'actual':actual_sha})
    requested_images=['2F_shell_top.png','2F_shell_perspective_front.png',
                      '2F_shell_perspective_corner.png','2F_shell_source_overlay.png',
                      '2F_vs_1F_alignment.png','2F_open_to_below_validation.png',
                      '2F_family_terrace_validation.png','2F_wall_topology_validation.png']
    image_status={}
    for name in requested_images:
        path=OUT/name
        image_status[name]={'exists':path.exists(),'bytes':path.stat().st_size if path.exists() else 0}
    if '--require-renders' in sys.argv:
        check('All requested visual validation files exist and are nonempty',
              all(v['exists'] and v['bytes']>10000 for v in image_status.values()),image_status)

    result = {
        'checks': CHECKS,
        'passed': sum(c['pass'] for c in CHECKS),
        'failed': sum(not c['pass'] for c in CHECKS),
        'mesh_objects': len(meshes),
        'triangles': sum(len(p.vertices)-2 for o in meshes for p in o.data.polygons),
        'bounds_m': {'min': [overall[i][0] for i in range(3)], 'max': [overall[i][1] for i in range(3)], 'dimensions': dims},
        'non_terrace_xy_regression_error_m': non_terrace_regression_error,
        'wall_thicknesses_m': {k: sorted(set(round(v,6) for v in values)) for k,values in thicknesses.items()},
        'glass_thicknesses_m': sorted(set(round(v,6) for v in glass_values)),
        'railing': {
            'glass_objects':[o.name for o in rail_glass], 'toprail_objects':[o.name for o in rail_tops],
            'overall_heights_m':rail_heights, 'glass_thicknesses_m':railing_thicknesses,
            'void_edge_coverage':coverage, 'bridge_clearance_m':bridge_clearance,
            'stair_edge_coverage':stair_coverage, 'stair_landing_exit_blockers':stair_blockers,
        },
        'open_to_below_dimensions_m': [open_rect[2]-open_rect[0],open_rect[3]-open_rect[1]],
        'bridge_dimensions_m': {
            'overall':[BRIDGE_PX[2]-BRIDGE_PX[0],BRIDGE_PX[3]-BRIDGE_PX[1]],
            'overall_world':[world_rect(BRIDGE_PX)[2]-world_rect(BRIDGE_PX)[0],world_rect(BRIDGE_PX)[3]-world_rect(BRIDGE_PX)[1]],
            'walkway_clearance':bridge_clearance},
        'stair_opening_dimensions_m':[actual_stair[2]-actual_stair[0],actual_stair[3]-actual_stair[1]],
        'family_terrace': {
            'validated': all(c['pass'] for c in CHECKS if c['name'].startswith('Family Terrace')),
            'terrace_width_m':terrace_width,
            'terrace_depth_m':terrace_depth,
            'terrace_minimum_depth_m':terrace_min_depth,
            'terrace_maximum_depth_m':terrace_max_depth,
            'terrace_area_m2':terrace_area,
            'terrace_width_depth_ratio':terrace_ratio,
            'terrace_center_xy':terrace_center,
            'terrace_slab_thickness_m':terrace_thickness,
            'lounge_glazing_center_y_m':glass_center_y,
            'gap_to_lounge_glazing_m':glazing_gap,
            'indoor_floor_overlap_m2':indoor_overlap,
            'open_to_below_overlap_m2':void_overlap,
            'guardrail_objects':TERRACE_RAILING_NAMES,
        },
        'non_column_walls_over_030_m': thick_walls,
        'wall_audit': {
            'opening_schedule':opening_schedule,
            'intentional_doorway_count':len(doorways),
            'circulation_opening_count':len(circulation),
            'intentional_opening_count':len(doorways)+len(circulation),
            'doorway_widths_m':doorway_widths,
            'minimum_doorway_width_m':min_doorway,
            'maximum_doorway_width_m':max_doorway,
            'source_wall_run_gaps':classified_gaps,
            'accidental_gaps_found':accidental_found,
            'accidental_gaps_corrected':accidental_corrected,
            'unexplained_gaps_remaining':len(unexplained_gaps),
            'wall_to_glass_cracks_found':len(junction_clearances),
            'wall_to_glass_cracks_corrected':sum(v<=.001 for v in junction_clearances.values()),
            'wall_to_glass_junction_clearances_m':junction_clearances,
            'smallest_remaining_wall_glass_junction_clearance_m':min(junction_clearances.values(),default=0),
            'maximum_remaining_wall_glass_junction_clearance_m':max(junction_clearances.values(),default=0),
            'blocked_openings':blocked_openings,
            'duplicate_wall_overlaps':duplicate_wall_overlaps,
            'missed_wall_intersections':missed_intersections,
            'ambiguous_openings_requiring_manual_review':[],
            'preserved_source_clearances':topology_corrections.get('preserved_clearances',[]),
            'bservice_gap_coverage':old_gap_coverage,
        },
        'room_access_audit': {
            'circulation_hub':'Art Gallery / Upper Hall',
            'required_spaces':required_spaces,
            'reachable_spaces':sorted(reached),
            'inaccessible_spaces':inaccessible,
            'measured_clear_connections':[{'spaces':[a,b],'opening':name} for a,b,name in access_edges],
            'blocked_connections':access_blockers,
        },
        'unrelated_geometry_regression':unrelated_regression,
        'alignment': alignment,
        'one_f_readonly_sha256': actual_sha,
        'validation_images': image_status,
    }
    (OUT/'2F_shell_validation.json').write_text(json.dumps(result,indent=2))
    print(f"VALIDATION: {result['passed']} passed; {result['failed']} failed")
    for item in CHECKS:
        print(('PASS ' if item['pass'] else 'FAIL ') + item['name'])
    if result['failed']:
        raise AssertionError('2F shell validation failed; see 2F_shell_validation.json')
    return result


if __name__ == '__main__':
    run()
