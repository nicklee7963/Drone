"""Rebuild the first-floor architectural shell from the calibrated 1F.png.

Usage: blender -b --python build_1F_shell.py [-- --skip-renders]
All trace coordinates below are pixels in the ORIGINAL 1448 x 1086 image.
Pixel X increases right; pixel Y increases down. World north is +Y.
The overall dimension ticks, not the full paper or schedule, set the scale.
No pip dependencies: Blender's bpy, bmesh, and mathutils only.
"""
import bpy
import bmesh
import json
import math
import sys
from pathlib import Path
from mathutils import Vector

OUT = Path(__file__).resolve().parent
IMAGE = OUT / '1F.png'
PX_WIDTH_MARKERS = (108.0, 1062.0)
PX_DEPTH_MARKERS = (189.0, 837.0)
ARCH_WIDTH_M, ARCH_DEPTH_M = 35.6, 22.8
SX = ARCH_WIDTH_M / (PX_WIDTH_MARKERS[1] - PX_WIDTH_MARKERS[0])
SY = ARCH_DEPTH_M / (PX_DEPTH_MARKERS[1] - PX_DEPTH_MARKERS[0])
CX, CY = 585.0, 513.0
WALL_HEIGHT = 3.2
SLAB_THICKNESS = .20
GLASS_THICKNESS = .02
GLASS_HEIGHT = WALL_HEIGHT   # Source note explicitly calls this floor-to-ceiling glazing.
EXTERIOR_WALL_THICKNESS = .28
INTERIOR_WALL_THICKNESS = .18
STAIRWELL_WALL_THICKNESS = .22
STOREY_RISE = 3.2             # Provisional: no section/elevations supplied.
STAIR_RISERS = 19
STAIR_TREAD = .27
STAIR_WAIST = .40            # Vertical underside offset; minimum web > .23 m.
STAIR_A = (388, 650, 464, 821)
STAIR_B = (708, 652, 771, 821)

# Union of source rectangles captures the stepped enclosed footprint.
# South bedroom/stair projections and north terrace-door recesses are retained.
FOOTPRINT = [
    (80,268,1089,616), (80,616,978,650), (978,616,1040,650),
    (128,650,224,813), (214,650,388,825), (365,650,487,840),
    (487,650,686,790), (686,644,799,840), (786,644,975,825),
    (958,644,1040,813), (345,219,402,275), (393,249,466,275),
    (704,249,778,275), (767,219,825,276), (104,244,131,280),
    (443,247,466,282), (704,247,728,282), (1039,244,1067,280),
]

# Structural black squares outside the usable Great Room. The former four
# internal Great Room piers (source rectangles at x451/705, y333/501) are
# intentionally absent so the double-height room is completely open.
COLUMNS = [
    ('Garage_NW', (104,244,131,279)), ('TerraceDoor_Left',(374,218,401,248)),
    ('GreatRoom_NW',(443,247,466,282)), ('GreatRoom_NE',(704,247,728,282)),
    ('TerraceDoor_Right',(767,218,795,247)), ('Kitchen_NE',(1039,244,1067,279)),
    (None, None), (None, None), (None, None), (None, None),
    ('Foyer_NW',(447,575,468,600)), ('Foyer_NE',(703,575,725,600)),
    ('Entry_W',(502,754,532,789)), ('Entry_E',(644,754,673,789)),
    ('Terrace_Main_W',(379,163,399,198)), ('Terrace_Main_E',(771,163,791,198)),
]

# Significant black wall bands. Values trace band edges rather than a
# raster threshold, which would wrongly model text, dimensions and door arcs.
EXTERIOR_WALLS = [
 ('Garage_NorthWest', [(80,268,153,282),(80,282,97,354)]),
 ('Garage_NorthEast', [(334,268,357,282),(382,268,398,282)]),
 ('Garage_WestSouth', [(80,519,98,555),(96,537,117,554)]),
 ('Storage_WestSouth',[(80,611,98,650),(98,634,147,652)]),
 ('TerraceDoor_Left',[(374,218,402,232),(389,232,402,258),(398,246,414,258)]),
 ('TerraceDoor_Right',[(767,218,795,232),(757,246,781,258),(773,232,781,310)]),
 ('Kitchen_North',[(817,268,838,282),(968,268,1003,282),(1038,268,1089,282)]),
 ('Pantry_East',[(1073,282,1089,313),(1073,463,1089,494)]),
 ('Mudroom_EastSouth',[(1073,568,1089,621),(973,603,1073,621)]),
 ('Ensuite1_West',[(128,650,145,686),(128,754,145,793)]),
 ('Ensuite1_South',[(128,793,158,813),(183,793,224,813)]),
 ('Guest1_South',[(214,805,232,825),(344,805,388,825)]),
 ('StairA_South',[(365,821,409,840),(443,821,487,840)]),
 ('Entry_West',[(477,776,532,790)]), ('Entry_East',[(644,776,707,790)]),
 ('StairB_South',[(686,821,727,840),(753,821,799,840)]),
 ('Guest2_South',[(783,806,818,825),(952,806,975,825)]),
 ('Ensuite2_South',[(961,794,1002,813)]),
 ('Ensuite2_East',[(1022,616,1040,685),(1022,754,1040,813)]),
]
INTERIOR_WALLS = [
 ('Garage_GreatRoom',[(389,258,397,501),(389,535,398,651)]),
 ('Garage_Service',[(183,545,204,554),(232,545,352,554),(373,545,397,554)]),
 ('Storage_Utility',[(190,550,198,639)]),
 ('Utility_Wine',[(283,550,291,639)]),
 ('Service_Guest1',[(145,639,331,648),(352,639,397,648)]),
 ('Guest1_Ensuite',[(215,648,224,673),(215,703,224,816)]),
 ('Corridor_Left',[(397,589,409,598),(430,589,447,598)]),
 ('StairA_West',[(374,648,388,821)]),
 ('StairA_East',[(464,648,477,779),(475,779,487,821)]),
 ('Pantry_Kitchen',[(973,282,981,310),(973,338,981,541)]),
 ('Pantry_Mudroom',[(981,469,1004,478),(1024,469,1073,478)]),
 ('Mudroom_Kitchen',[(972,568,982,617)]),
 ('Corridor_Right_North',[(773,568,781,592),(781,582,928,592),(951,582,978,592)]),
 ('Corridor_Right_West',[(831,592,839,610),(831,632,839,649)]),
 ('Corridor_Right_South',[(820,639,869,648),(890,639,1022,648)]),
 # Lower west jamb trimmed by one source pixel to avoid penetrating flight.
 ('StairB_West',[(695,652,708,776),(684,776,708,821)]),
 ('StairB_East',[(771,644,785,821)]),
 ('Powder_Guest2',[(849,648,857,750),(785,745,849,753)]),
 ('Guest2_Ensuite',[(957,648,965,675),(957,704,965,813)]),
]

# Exterior-face anchors for each traced source rectangle. N/S/W/E identify
# the face that remains fixed while excessive thickness is removed inward.
EXTERIOR_ANCHORS = {
 'Garage_NorthWest':['N','W'], 'Garage_NorthEast':['N','N'],
 'Garage_WestSouth':['W','S'], 'Storage_WestSouth':['W','S'],
 'TerraceDoor_Left':['N','E','N'], 'TerraceDoor_Right':['N','N','E'],
 'Kitchen_North':['N','N','N'], 'Pantry_East':['E','E'],
 'Mudroom_EastSouth':['E','S'], 'Ensuite1_West':['W','W'],
 'Ensuite1_South':['S','S'], 'Guest1_South':['S','S'],
 'Entry_West':['S'], 'Entry_East':['S'],
 'Guest2_South':['S','S'], 'Ensuite2_South':['S'], 'Ensuite2_East':['E','E'],
}
STAIRWELL_WALLS = {
 'StairA_South':'N', 'StairB_South':'N',
 'StairA_West':'E', 'StairA_East':'W',
 'StairB_West':'E', 'StairB_East':'W',
}

# Axis-aligned glazing centerlines. Storage's short sliding bay is parked
# open from source x151 to x183 to provide access absent a drawn door arc.
GLAZING = [
 ('Garage_North',(153,274),(334,274)),
 ('Garage_West',(88.5,354),(88.5,519)),
 ('Storage_West',(88.5,555),(88.5,611)),
 ('Storage_North_Fixed',(117,549.5),(151,549.5)),
 ('TerraceDoor_Left_West',(348,226),(348,268)),
 ('TerraceDoor_Left_North',(348,226),(374,226)),
 ('GreatRoom_NorthWest',(414,252),(443,252)),
 ('GreatRoom_North',(466,270),(704,270)),
 ('GreatRoom_NorthEast',(728,252),(757,252)),
 ('TerraceDoor_Right_North',(795,226),(821,226)),
 ('TerraceDoor_Right_East',(821,226),(821,268)),
 ('Kitchen_North',(838,274),(968,274)),
 ('Pantry_North',(1003,274),(1038,274)),
 ('Pantry_East',(1080.5,313),(1080.5,463)),
 ('Mudroom_East',(1080.5,494),(1080.5,568)),
 ('Ensuite1_West',(136.5,686),(136.5,754)),
 ('Ensuite1_South',(158,803),(183,803)),
 ('GuestSuite1_South',(232,815),(344,815)),
 ('StairA_South',(409,830),(443,830)),
 ('StairB_South',(727,830),(753,830)),
 ('GuestSuite2_South',(818,815),(952,815)),
 ('Ensuite2_South',(1002,803),(1022,803)),
    ('Ensuite2_East',(1031,685),(1031,754)),
    ('Entry_Sidelight_West',(532,783),(549,783)),
    ('Entry_Sidelight_East',(626,783),(644,783)),
]

DOORS = [
 ('Main_Entry',(585,801),(585,766)),
 ('Foyer_GreatRoom',(585,708),(585,510)),
 ('Foyer_Corridor_Left',(510,620),(410,620)),
 ('Foyer_Corridor_Right',(800,620),(860,620)),
 ('Garage_GreatRoom',(376,516),(414,516)),
 ('Garage_Utility',(218,535),(218,565)),
 ('Garage_Wine',(362,535),(362,565)),
 ('Garage_Storage_InferredSlidingAccess',(167,535),(167,568)),
 ('Guest1_Wine',(342,628),(342,664)),
 ('Guest1_Ensuite1',(201,687),(240,687)),
 ('GreatRoom_LeftCorridor',(419,575),(419,614)),
 ('Kitchen_Pantry',(956,324),(996,324)),
 ('Pantry_Mudroom',(1014,453),(1014,492)),
 ('Kitchen_Mudroom',(954,554),(997,554)),
 ('Kitchen_RightCorridor',(940,563),(940,612)),
 ('Corridor_Guest2',(879,626),(879,667)),
 ('Corridor_Powder',(803,626),(803,667)),
 ('Guest2_Ensuite2',(940,690),(987,690)),
 ('StairA_Entrance',(426,625),(426,671)),
 ('StairB_Entrance',(740,626),(740,675)),
 ('Garage_TerraceVestibule',(370,297),(370,254)),
 ('Kitchen_TerraceVestibule',(803,298),(803,253)),
]


def xy(px, py):
    return (px - CX) * SX, (CY - py) * SY


def world_rect(r):
    x0, y1 = xy(r[0], r[1])
    x1, y0 = xy(r[2], r[3])
    return x0, y0, x1, y1


def resize_source_rect(rect, thickness_m, anchor='CENTER'):
    """Return a pixel-space wall rectangle with an exact metric thickness.

    CENTER retains an interior partition's centerline. Cardinal anchors retain
    a specific architectural face. Long-axis endpoints never move, preserving
    door centers and opening widths.
    """
    x0, y0, x1, y1 = map(float, rect)
    world_w, world_h = (x1 - x0) * SX, (y1 - y0) * SY
    if anchor in {'W', 'E'} or (anchor == 'CENTER' and world_h > world_w):
        pixels = thickness_m / SX
        if anchor == 'W':
            x1 = x0 + pixels
        elif anchor == 'E':
            x0 = x1 - pixels
        else:
            center = (x0 + x1) / 2
            x0, x1 = center - pixels / 2, center + pixels / 2
    else:
        pixels = thickness_m / SY
        if anchor == 'N':
            y1 = y0 + pixels
        elif anchor == 'S':
            y0 = y1 - pixels
        else:
            center = (y0 + y1) / 2
            y0, y1 = center - pixels / 2, center + pixels / 2
    return (x0, y0, x1, y1)


def resized_wall_rects(category, label, rects):
    if category == 'stairwell':
        anchor = STAIRWELL_WALLS[label]
        return [resize_source_rect(r, STAIRWELL_WALL_THICKNESS, anchor) for r in rects]
    if category == 'exterior':
        anchors = EXTERIOR_ANCHORS[label]
        assert len(anchors) == len(rects)
        return [resize_source_rect(r, EXTERIOR_WALL_THICKNESS, a)
                for r, a in zip(rects, anchors)]
    return [resize_source_rect(r, INTERIOR_WALL_THICKNESS) for r in rects]


def alignment_records(category, label, originals, resized):
    if category == 'interior':
        anchors = ['CENTER'] * len(originals)
    elif category == 'stairwell':
        anchors = [STAIRWELL_WALLS[label]] * len(originals)
    else:
        anchors = EXTERIOR_ANCHORS[label]
    records = []
    for old, new, anchor in zip(originals, resized, anchors):
        oldw, neww = world_rect(old), world_rect(new)
        if anchor == 'CENTER':
            vertical = (old[3] - old[1]) * SY > (old[2] - old[0]) * SX
            old_value = (oldw[0] + oldw[2]) / 2 if vertical else (oldw[1] + oldw[3]) / 2
            new_value = (neww[0] + neww[2]) / 2 if vertical else (neww[1] + neww[3]) / 2
        else:
            index = {'W':0, 'S':1, 'E':2, 'N':3}[anchor]
            old_value, new_value = oldw[index], neww[index]
        records.append({'anchor':anchor, 'original_m':old_value,
                        'final_m':new_value, 'error_m':abs(new_value-old_value)})
    return records


def intersects(a, b):
    return min(a[2], b[2]) > max(a[0], b[0]) and min(a[3], b[3]) > max(a[1], b[1])


def collection(name, parent=None):
    c = bpy.data.collections.new(name)
    (parent or bpy.context.scene.collection).children.link(c)
    return c


def material(name, rgba, glass=False):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = rgba
    mat.use_nodes = True
    node = mat.node_tree.nodes.get('Principled BSDF')
    node.inputs['Base Color'].default_value = rgba
    node.inputs['Roughness'].default_value = .78
    if glass:
        node.inputs['Alpha'].default_value = .32
        node.inputs['Roughness'].default_value = .35
        mat.surface_render_method = 'DITHERED'
    return mat


def mesh_object(name, vertices, faces, coll, mat, kind):
    me = bpy.data.meshes.new(name + '_Mesh')
    me.from_pydata(vertices, [], faces)
    me.update()
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    # Remove artificial planar cell subdivisions without altering the trace.
    bmesh.ops.dissolve_limit(bm, angle_limit=.0001, verts=list(bm.verts),
                            edges=list(bm.edges), use_dissolve_boundaries=False)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    coll.objects.link(obj)
    obj.data.materials.append(mat)
    obj['shell_geometry'] = True
    obj['element_type'] = kind
    # Bake world coordinates into a mesh local to its bounding-box center.
    center = Vector(tuple((min(v.co[k] for v in me.vertices) + max(v.co[k] for v in me.vertices)) / 2 for k in range(3)))
    for v in me.vertices:
        v.co -= center
    obj.location = center
    me.update()
    return obj


def remove_orphan_wall_islands(obj, min_xy_area=.03):
    """Delete disconnected wall islands below the evidenced cleanup cutoff.

    The pre-clean audit found five trimming remnants at 0.007-0.019 m²;
    the smallest legitimate wall component is 0.063 m². The cutoff stays
    between those groups and does not simplify connected wall geometry.
    """
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    remaining = set(bm.verts)
    removals = []
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
        footprint = (max(xs) - min(xs)) * (max(ys) - min(ys))
        if footprint < min_xy_area:
            removals.append({'footprint_m2':footprint, 'vertices':len(island)})
            bmesh.ops.delete(bm, geom=list(island), context='VERTS')
    if removals:
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        bm.to_mesh(obj.data)
        obj.data.update()
        # Restore a bounds-centered origin after deleting disconnected islands.
        center = Vector(tuple((min(v.co[k] for v in obj.data.vertices) +
                               max(v.co[k] for v in obj.data.vertices)) / 2
                              for k in range(3)))
        for vertex in obj.data.vertices:
            vertex.co -= center
        obj.location += center
        obj.data.update()
        obj['removed_orphan_islands_json'] = json.dumps(removals)
    return removals


def rect_solid(name, rects, z0, z1, coll, mat, kind, subtract=()):
    """Exact orthogonal union/difference; no boolean modifiers or internal faces.

    Occupied cells share vertices. Only exterior vertical faces are emitted.
    This also handles the slab's holes without unreliable n-gon hole filling.
    """
    cuts = [r for r in subtract if any(intersects(r, a) for a in rects)]
    edges = rects + cuts
    xs = sorted(set(v for r in edges for v in (r[0], r[2])))
    ys = sorted(set(v for r in edges for v in (r[1], r[3])))
    def contains(rs, x, y):
        return any(r[0] < x < r[2] and r[1] < y < r[3] for r in rs)
    cells = {(i, j) for i in range(len(xs)-1) for j in range(len(ys)-1)
             if contains(rects, (xs[i]+xs[i+1])/2, (ys[j]+ys[j+1])/2)
             and not contains(cuts, (xs[i]+xs[i+1])/2, (ys[j]+ys[j+1])/2)}
    if not cells:
        return None
    verts, faces, indices = [], [], {}
    def vertex(i, j, k):
        key = (i, j, k)
        if key not in indices:
            indices[key] = len(verts)
            verts.append((xs[i], ys[j], z1 if k else z0))
        return indices[key]
    for i, j in sorted(cells):
        corners = [(i,j),(i+1,j),(i+1,j+1),(i,j+1)]
        low = [vertex(a,b,0) for a,b in corners]
        high = [vertex(a,b,1) for a,b in corners]
        faces += [low[::-1], high]
        for edge, neighbor in enumerate([(i,j-1),(i+1,j),(i,j+1),(i-1,j)]):
            if neighbor not in cells:
                nxt = (edge+1) % 4
                faces.append([low[edge],low[nxt],high[nxt],high[edge]])
    obj = mesh_object(name, verts, faces, coll, mat, kind)
    obj['footprint_rectangles_world'] = json.dumps(rects)
    obj['subtracted_rectangles_world'] = json.dumps(cuts)
    obj['z_min'] = z0
    obj['z_max'] = z1
    return obj


def traced_solid(name, rects, z0, z1, coll, mat, kind, subtract=()):
    obj = rect_solid(name, [world_rect(r) for r in rects], z0, z1, coll, mat, kind,
                     [world_rect(r) for r in subtract])
    if obj:
        obj['source_pixel_rectangles'] = json.dumps(rects)
    return obj


def stair(name, shaft, sign, coll, mat):
    """One watertight stepped flight and terminal landing with sloped underside."""
    x0, y0, x1, y1 = world_rect(shaft)
    riser = STOREY_RISE / STAIR_RISERS
    run = (STAIR_RISERS - 1) * STAIR_TREAD
    length = y1 - y0
    assert length - run > 1.0, 'Stair terminal landing must be at least 1 m long'
    profile = [(0,0)]
    for i in range(STAIR_RISERS-1):
        profile.extend([(i * STAIR_TREAD, sign*(i+1)*riser),
                        ((i+1)*STAIR_TREAD, sign*(i+1)*riser)])
    profile += [(run,sign*STOREY_RISE), (length,sign*STOREY_RISE),
                (length,sign*STOREY_RISE-STAIR_WAIST),
                (run,sign*STOREY_RISE-STAIR_WAIST),(0,-STAIR_WAIST)]
    n = len(profile)
    verts = [(x, y1-s, z) for x in (x0,x1) for s,z in profile]
    faces = [list(range(n-1,-1,-1)), list(range(n,2*n))]
    faces += [[i,(i+1)%n,(i+1)%n+n,i+n] for i in range(n)]
    obj = mesh_object(name, verts, faces, coll, mat, 'stair')
    obj['source_pixel_rectangles'] = json.dumps([shaft])
    for k,v in dict(xmin=x0,xmax=x1,start_y=y1,end_y=y0,
                    riser_m=riser,tread_m=STAIR_TREAD,risers=STAIR_RISERS,
                    treads=STAIR_RISERS-1,run_m=run,landing_depth_m=length-run,
                    terminal_elevation_m=sign*STOREY_RISE).items():
        obj[k] = v
    obj['direction'] = 'south (-Y), ' + ('down to B1' if sign < 0 else 'up to 2F')
    return obj


def helper(name, rect, z, height, coll):
    x0,y0,x1,y1 = world_rect(rect)
    obj = bpy.data.objects.new(name, None)
    coll.objects.link(obj)
    obj.empty_display_type = 'CUBE'
    obj.empty_display_size = 1
    obj.location = ((x0+x1)/2,(y0+y1)/2,z+height/2)
    obj.scale = ((x1-x0)/2,(y1-y0)/2,height/2)
    obj.hide_render = True
    obj.hide_set(True)
    obj['non_export_helper'] = True
    obj['source_pixel_rectangle'] = json.dumps(rect)
    obj['bounds_world_m'] = json.dumps([x0,y0,z,x1,y1,z+height])
    return obj


def camera(name, location, target, coll, ortho=None):
    data = bpy.data.cameras.new(name)
    obj = bpy.data.objects.new(name, data)
    coll.objects.link(obj)
    obj.location = location
    obj.rotation_euler = (Vector(target)-obj.location).to_track_quat('-Z','Y').to_euler()
    if ortho:
        data.type = 'ORTHO'
        data.ortho_scale = ortho
    else:
        data.lens = 43
    data.clip_end = 250
    return obj


def main():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    for c in list(bpy.data.collections):
        bpy.data.collections.remove(c)
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.length_unit = 'METERS'
    scene.unit_settings.scale_length = 1
    root = collection('1F_SHELL')
    cols = {key:collection(key, root) for key in ['1F_FLOOR','1F_WALLS_EXTERIOR',
            '1F_WALLS_INTERIOR','1F_COLUMNS','1F_GLASS','1F_STAIRS',
            '1F_TERRACES','1F_OPENINGS','1F_DEBUG']}
    refcoll = collection('REFERENCE_1F')
    views = collection('1F_VALIDATION_CAMERAS')
    mats = {
        'wall':material('Placeholder_Wall_Gray',(.13,.15,.17,1)),
        'floor':material('Placeholder_Floor_Gray',(.67,.68,.69,1)),
        'terrace':material('Placeholder_Terrace_Gray',(.78,.79,.79,1)),
        'column':material('Placeholder_Structural_DarkGray',(.20,.23,.25,1)),
        'glass':material('Placeholder_Glass_Blue',(.13,.54,.70,.32),True),
        'stair':material('Placeholder_Stair_Gray',(.49,.53,.56,1)),
    }
    image = bpy.data.images.load(str(IMAGE), check_existing=True)
    image.pack()
    ref = bpy.data.objects.new('1F_Reference_Plan', None)
    refcoll.objects.link(ref)
    ref.empty_display_type = 'IMAGE'
    ref.data = image
    ref.empty_display_size = image.size[0] * SX
    # An image empty lies in its local XY plane. Correct aspect anisotropy
    # encodes the independently dimension-calibrated vertical pixel scale.
    ref.scale = (1, SY/SX, 1)
    ref.location = (*xy(image.size[0]/2, image.size[1]/2), -.24)
    ref.color[3] = .65
    ref.empty_image_depth = 'BACK'
    ref.hide_render = True
    ref.hide_select = True
    ref.lock_location = (True,True,True)
    ref.lock_rotation = (True,True,True)
    ref.lock_scale = (True,True,True)
    ref['meters_per_pixel_x'],ref['meters_per_pixel_y'] = SX,SY
    ref['calibration'] = 'Width x108..1062 =35.6m; depth y189..837 =22.8m; original 1448x1086'
    footprint = FOOTPRINT + [r for _,r in COLUMNS[:6]]
    traced_solid('1F_Floor_Main', footprint, -.20, 0, cols['1F_FLOOR'], mats['floor'],
                 'floor', [STAIR_A,STAIR_B])
    terraces = [
       ('1F_Terrace_Main',[(374,159,797,270)]),
       ('1F_Terrace_Left',[(103,182,374,275)]),
       ('1F_Terrace_Dining',[(797,182,1068,275)]),
       ('1F_Entry_Porch',[(487,790,686,868)]),
    ]
    for name,rs in terraces:
        traced_solid(name,rs,-SLAB_THICKNESS,0,cols['1F_TERRACES'],mats['terrace'],
                     'terrace',footprint)
    occupied = []
    for i,(label,rect) in enumerate(COLUMNS,1):
        if label is None:
            continue
        traced_solid(f'1F_Column_{i:03d}_{label}',[rect],0,WALL_HEIGHT,
                     cols['1F_COLUMNS'],mats['column'],'column')
        occupied.append(rect)
    wall_changes = []
    for category,specs in [('Exterior',EXTERIOR_WALLS),('Interior',INTERIOR_WALLS)]:
        for i,(label,rs) in enumerate(specs,1):
            wall_class = ('stairwell' if label in STAIRWELL_WALLS else category.lower())
            resized = resized_wall_rects(wall_class, label, rs)
            obj = traced_solid(f'1F_Wall_{category}_{i:03d}_{label}',resized,0,WALL_HEIGHT,
                      cols['1F_WALLS_'+category.upper()],mats['wall'],'wall',occupied)
            if obj:
                obj['height_assumption_m'] = WALL_HEIGHT
                obj['wall_class'] = wall_class
                obj['nominal_thickness_m'] = ({'exterior':EXTERIOR_WALL_THICKNESS,
                    'interior':INTERIOR_WALL_THICKNESS,
                    'stairwell':STAIRWELL_WALL_THICKNESS}[wall_class])
                obj['original_source_pixel_rectangles'] = json.dumps(rs)
                obj['alignment_rule'] = ('preserve stair opening face' if wall_class == 'stairwell'
                    else ('preserve exterior face' if wall_class == 'exterior'
                          else 'preserve wall centerline'))
                obj['alignment_records_json'] = json.dumps(
                    alignment_records(wall_class, label, rs, resized))
                remove_orphan_wall_islands(obj)
                wall_changes.append(obj.name)
            occupied.extend(resized)
    # Keep the existing glass endpoints unchanged. Glass is trimmed against
    # the original wall bands, independently of the corrected wall solids.
    original_glazing_cuts = [r for label,r in COLUMNS if label is not None]
    original_glazing_cuts += [r for _,rects in EXTERIOR_WALLS + INTERIOR_WALLS for r in rects]
    glazing_occupied = [world_rect(r) for r in original_glazing_cuts]
    for i,(label,a,b) in enumerate(GLAZING,1):
        x0,y0 = xy(*a)
        x1,y1 = xy(*b)
        if abs(x1-x0) < 1e-6:
            r = (x0-GLASS_THICKNESS/2,min(y0,y1),x0+GLASS_THICKNESS/2,max(y0,y1))
        else:
            r = (min(x0,x1),y0-GLASS_THICKNESS/2,max(x0,x1),y0+GLASS_THICKNESS/2)
        obj = rect_solid(f'1F_Glass_{i:03d}_{label}',[r],0,GLASS_HEIGHT,
                         cols['1F_GLASS'],mats['glass'],'glass',glazing_occupied)
        obj['source_pixel_line'] = json.dumps([a,b])
        obj['collision_policy'] = 'Separate candidate collider; export policy to be selected later'
        glazing_occupied.append(r)
    stair_a = stair('1F_StairA_DownToB1',STAIR_A,-1,cols['1F_STAIRS'],mats['stair'])
    stair_b = stair('1F_StairB_UpTo2F',STAIR_B,1,cols['1F_STAIRS'],mats['stair'])
    helper('VOID_GreatRoom_OpenToAbove',(397,282,773,575),WALL_HEIGHT,STOREY_RISE,
            cols['1F_OPENINGS'])['instruction'] = 'Future 2F slab must exclude this provisional Great Room void; confirm against 2F plan later.'
    helper('1F_Opening_StairA',STAIR_A,-SLAB_THICKNESS,SLAB_THICKNESS,cols['1F_OPENINGS'])
    helper('1F_Opening_StairB',STAIR_B,-SLAB_THICKNESS,6.4,cols['1F_OPENINGS'])
    for letter,obj,z in [('B1',stair_a,-STOREY_RISE),('2F',stair_b,STOREY_RISE)]:
        marker = bpy.data.objects.new('1F_Connection_'+letter,None)
        cols['1F_OPENINGS'].objects.link(marker)
        marker.empty_display_type = 'ARROWS'
        marker.empty_display_size = .6
        marker.location = (obj['xmax'],obj['end_y']+obj['landing_depth_m']/2,z)
        marker['connection_elevation_m'] = z
        marker['exit_direction'] = '+X from the south terminal landing; future floor must meet landing'
        marker.hide_render = True
        marker.hide_set(True)
    paths = []
    for name,a,b in DOORS:
        paths.append({'name':name,'start':[*xy(*a),1.2],'end':[*xy(*b),1.2]})
        marker = bpy.data.objects.new('1F_Opening_'+name,None)
        cols['1F_OPENINGS'].objects.link(marker)
        marker.location = (*xy((a[0]+b[0])/2,(a[1]+b[1])/2),1.2)
        marker.empty_display_type = 'PLAIN_AXES'
        marker.empty_display_size = .15
        marker.hide_render = True
        marker.hide_set(True)
    scene['door_paths_json'] = json.dumps(paths)
    scene['reference_source'] = '1F.png only; no other floor modeled'
    scene['assumptions'] = ('Independent marker calibration; full-height temporary door/circulation gaps; '
       '3.2m walls and +/-3.2m terminal stair elevations; explicit 0.28m exterior, 0.18m partition, and 0.22m stairwell walls; '
       'Stair B provisionally ascends south from clear north mouth; Storage glazing partly open for access. '
       'No ceilings. Stair connections and Great Room void must be reconciled with future level plans.')
    scene['wall_fix_removed_objects'] = json.dumps([
        '1F_Column_007_GreatRoom_W1', '1F_Column_008_GreatRoom_E1',
        '1F_Column_009_GreatRoom_W2', '1F_Column_010_GreatRoom_E2'])
    scene['wall_fix_changed_objects'] = json.dumps(wall_changes)
    # Validation cameras: top keeps image north at screen top.
    top = camera('1F_Camera_Top_Orthographic',(0,0,55),(0,0,0),views,ortho=42.5)
    top.rotation_euler = (0,0,0)
    front = camera('1F_Camera_Perspective_Front',(0,-48,32),(0,0,0),views)
    corner = camera('1F_Camera_Perspective_Corner',(34,-38,40),(0,0,.4),views)
    greatroom = camera('1F_Camera_GreatRoom_Validation',(0,-24,25),(0,3.2,.2),views)
    greatroom.data.lens = 55
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = 24
    scene.cycles.use_denoising = True
    scene.cycles.transparent_max_bounces = 12
    scene.world.use_nodes = True
    scene.world.node_tree.nodes['Background'].inputs[0].default_value = (.85,.85,.85,1)
    scene.world.node_tree.nodes['Background'].inputs[1].default_value = .8
    ld = bpy.data.lights.new('Validation_Area_Light','AREA')
    light = bpy.data.objects.new(ld.name,ld)
    views.objects.link(light)
    light.location = (0,-5,30)
    ld.energy = 3500
    ld.size = 25
    scene.render.resolution_x = 1800
    scene.render.resolution_y = 1300
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.film_transparent = False
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'Medium High Contrast' if 'Medium High Contrast' in [i.identifier for i in scene.view_settings.bl_rna.properties['look'].enum_items] else 'None'
    scene.camera = top
    # Reference is packed and can be revealed in the Outliner for exact overlay.
    ref.hide_set(True)
    bpy.context.view_layer.update()
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                area.spaces.active.clip_end = 250
                area.spaces.active.region_3d.view_distance = 46
                area.spaces.active.region_3d.view_location = (0,0,0)
                area.spaces.active.region_3d.view_rotation = top.rotation_euler.to_quaternion()
                area.spaces.active.region_3d.view_perspective = 'ORTHO'
                area.spaces.active.shading.color_type = 'MATERIAL'
                area.spaces.active.overlay.show_floor = False
    # Save reproducibility notes inside the deliverable too.
    textblock = bpy.data.texts.new('README_1F_SHELL')
    textblock.write(__doc__ + '\n\n' + scene['assumptions'] + '\n\n' + ref['calibration'])
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'1F_shell.blend'))
    sys.path.insert(0,str(OUT))
    import validate_1F_shell
    result = validate_1F_shell.run()
    if '--skip-renders' not in sys.argv:
        for cam,filename in [(top,'1F_shell_top.png'),(front,'1F_shell_perspective_front.png'),
                              (corner,'1F_shell_perspective_corner.png'),
                              (greatroom,'1F_shell_greatroom_validation.png')]:
            scene.camera = cam
            scene.render.resolution_x = 2400 if cam == top else 1800
            scene.render.resolution_y = 1700 if cam == top else 1300
            scene.render.filepath = str(OUT/filename)
            bpy.ops.render.render(write_still=True)
        scene.camera = top
        scene.render.resolution_x,scene.render.resolution_y = 2400,1700
        scene.render.filepath = str(OUT/'1F_shell_top.png')
        bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'1F_shell.blend'))
        import export_1F_report
        export_1F_report.main()
    print('SHELL BUILD COMPLETE', json.dumps({k:v for k,v in result.items() if k not in ('checks','door_paths')}))


if __name__ == '__main__':
    main()
