"""Build the independent villa basement B1 architectural shell.

Usage:
    blender -b --factory-startup --python-exit-code 1 --python build_B1_shell.py
    blender -b --factory-startup --python-exit-code 1 --python build_B1_shell.py -- --skip-renders

All plan traces use original 1448x1086 B1.png pixels.  The established 1F
pixel-to-world transform is authoritative.  The B1 stair is aligned to the
live 1F mesh, while its landing ends and circulation direction are re-derived
from both floor-plan arrows.  This file deliberately creates no stair mesh.
"""
import bpy
import bmesh
import hashlib
import json
import math
import sys
from pathlib import Path
from mathutils import Vector

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
IMAGE = OUT / "B1.png"
BLEND = OUT / "B1_shell.blend"
SX = 35.6 / 954.0
SY = 22.8 / 648.0
CX, CY = 585.0, 513.0
WALL_HEIGHT = 3.2
SLAB_THICKNESS = .20
EXTERIOR_WALL_THICKNESS = .28
INTERIOR_WALL_THICKNESS = .18
STAIRWELL_WALL_THICKNESS = .22
GLASS_THICKNESS = .020
GLASS_HEIGHT = 3.2

# Authoritative evaluated 1F_StairA_DownToB1 interface.  The plans agree that
# the 1F upper landing is north, the B1 lower landing is south, and B1 ascends
# north.  The prior +X landing exit was metadata inferred during the 1F build;
# it is not architectural source evidence and is intentionally not reused.
STAIR_X0 = -7.351362683438155
STAIR_Y0 = -10.837037037037037
STAIR_X1 = -4.515303983228511
STAIR_Y1 = -4.82037037037037
STAIR_LOWER_LANDING_Y1 = -9.680370370370371
# Exact projection where the live 1F stair intersects the assembled B1 slab
# band.  The flight underside reaches B1 slab top after 4.2525 m of run.
STAIR_SLAB_OPENING_Y1 = -9.07287037037037
STAIR_CENTER_X = (STAIR_X0 + STAIR_X1) / 2
STAIR_CONNECTION = (STAIR_CENTER_X, STAIR_Y0, 0.0)
STAIR_EXIT_HALF_WIDTH = 1.00
STAIR_UNDERFLIGHT_DOOR_HALF_WIDTH = .70
STAIR_VESTIBULE_EAST_X = (550 - CX) * SX
# Preserve the 25 px clear vestibule depth drawn between the B1 lower stair
# threshold (y=765) and the inner face of its south return (y=790).
STAIR_VESTIBULE_SOUTH_Y = STAIR_Y0 - (790 - 765) * SY
STAIR_LOUNGE_SOUTH_GLASS_Y = (CY - 807.2) * SY

# The main enclosed slab stays in the source plan coordinate frame.  Only a
# local L-shaped stair vestibule is extended: first south from the plan-proven
# lower landing exit, then east/north back into the unchanged lounge.
MAIN_FOOTPRINT = [
    (74, 176, 1078, 586),
    (377, 390, 895, 815),
    (872, 586, 1078, 624),
    (872, 617, 1065, 750),
]
COURTYARD_FOOTPRINT = [(105, 586, 377, 800)]
STAIR_ARRIVAL_FLOOR_WORLD = [
    (STAIR_X0 - EXTERIOR_WALL_THICKNESS,
     STAIR_VESTIBULE_SOUTH_Y - EXTERIOR_WALL_THICKNESS,
     STAIR_VESTIBULE_EAST_X + EXTERIOR_WALL_THICKNESS,
     (CY - 815) * SY),
]

COLUMNS = [
    ("NorthWest_Step", (94, 176, 118, 235)),
    ("Shower_North", (358, 164, 387, 203)),
    ("Laundry_North", (767, 164, 795, 203)),
    ("NorthEast_Step", (1040, 176, 1062, 235)),
    ("West_GymStorage", (74, 449, 116, 489)),
    ("West_Courtyard", (74, 575, 119, 620)),
    ("Courtyard_SouthWest", (105, 785, 150, 804)),
    ("Right_ServiceOffset", (872, 617, 895, 633)),
    ("BathStorage_Mullion", (959, 737, 977, 750)),
]

# Each tuple is name, source rectangle, metric class, retained face.  Long-axis
# endpoints are kept; only raster thickness is normalized.
HORIZONTAL_WALLS = [
    ("B1_Wall_Exterior_001_Gym_North", (118, 179, 358, 192), "exterior", "N"),
    ("B1_Wall_Exterior_002_North_Center", (387, 189, 767, 203), "exterior", "N"),
    ("B1_Wall_Exterior_003_Service_North", (795, 176, 1040, 190), "exterior", "N"),
    ("B1_Wall_Exterior_009_Courtyard_SouthWest", (150, 785, 187, 804), "exterior", "S"),
    ("B1_Wall_Exterior_015_Lounge_SouthCenter", (639, 792, 713, 815), "exterior", "S"),
    ("B1_Wall_Exterior_016_Lounge_SouthEast", (843, 792, 895, 815), "exterior", "S"),
    ("B1_Wall_Exterior_020_Service_SouthWest", (895, 737, 905, 750), "exterior", "S"),
    ("B1_Wall_Exterior_022_Service_SouthEast", (1040, 737, 1065, 750), "exterior", "S"),
    ("B1_Wall_Exterior_024_StoragePowder_SouthMiddle", (194, 580, 205, 590), "exterior", "S"),
    ("B1_Wall_Exterior_025_StoragePowder_SouthEast", (337, 580, 377, 590), "exterior", "S"),
    ("B1_Wall_Interior_005_Shower_SouthWest", (384, 314, 390, 321), "interior", "CENTER"),
    ("B1_Wall_Interior_006_Shower_SouthEast", (416, 314, 468, 321), "interior", "CENTER"),
    ("B1_Wall_Interior_008_CinemaSouth_WestJamb", (475, 391, 485, 398), "interior", "CENTER"),
    ("B1_Wall_Interior_009_CinemaSouth_Center", (511, 391, 749, 398), "interior", "CENTER"),
    ("B1_Wall_Interior_010_CinemaSouth_EastJamb", (776, 391, 791, 398), "interior", "CENTER"),
    ("B1_Wall_Interior_014_TopRoomsSouth_LaundryWest", (791, 300, 809, 307), "interior", "CENTER"),
    ("B1_Wall_Interior_015_TopRoomsSouth_Main", (837, 300, 1005, 307), "interior", "CENTER"),
    ("B1_Wall_Interior_016_ServiceCorridor_South", (1038, 300, 1061, 307), "interior", "CENTER"),
    ("B1_Wall_Interior_021_Mechanical_Electrical", (888, 431, 1061, 438), "interior", "CENTER"),
    ("B1_Wall_Interior_022_Electrical_Water", (888, 516, 1061, 524), "interior", "CENTER"),
    ("B1_Wall_Interior_023_WaterBath_WestJamb", (888, 617, 900, 624), "interior", "CENTER"),
    ("B1_Wall_Interior_024_WaterBath_Center", (930, 617, 972, 624), "interior", "CENTER"),
    ("B1_Wall_Interior_025_WaterBath_EastJamb", (1002, 617, 1061, 624), "interior", "CENTER"),
    ("B1_Wall_Interior_026_GymRooms_NorthWest", (116, 479, 207, 486), "interior", "CENTER"),
    ("B1_Wall_Interior_027_GymRooms_NorthEast", (233, 479, 377, 486), "interior", "CENTER"),
]

VERTICAL_WALLS = [
    ("B1_Wall_Exterior_004_Gym_WestNorth", (74, 235, 90, 279), "exterior", "W"),
    ("B1_Wall_Exterior_005_Gym_WestSouth", (74, 489, 90, 505), "exterior", "W"),
    ("B1_Wall_Exterior_007_Courtyard_WestNorth", (104, 620, 118, 638), "exterior", "W"),
    ("B1_Wall_Exterior_008_Courtyard_WestSouth", (104, 750, 118, 785), "exterior", "W"),
    ("B1_Wall_Exterior_017_Lounge_East", (880, 750, 895, 815), "exterior", "E"),
    ("B1_Wall_Exterior_018_Services_EastLower", (1055, 620, 1065, 737), "exterior", "E"),
    ("B1_Wall_Exterior_019_Services_EastUpper", (1061, 235, 1078, 620), "exterior", "E"),
    ("B1_Wall_Interior_001_Gym_ShowerSouth", (377, 232, 384, 338), "interior", "CENTER"),
    ("B1_Wall_Interior_002_Gym_VestibuleSouth", (377, 391, 384, 428), "interior", "CENTER"),
    ("B1_Wall_Interior_003_Gym_LibrarySouth", (377, 458, 384, 564), "interior", "CENTER"),
    ("B1_Wall_Interior_004_ShowerCinema", (468, 203, 475, 392), "interior", "CENTER"),
    ("B1_Wall_Interior_007_CinemaLaundry", (784, 203, 791, 392), "interior", "CENTER"),
    ("B1_Wall_Interior_011_Laundry_Linen", (904, 190, 911, 300), "interior", "CENTER"),
    ("B1_Wall_Interior_012_Linen_CorridorNorth", (999, 190, 1005, 267), "interior", "CENTER"),
    ("B1_Wall_Interior_013_Linen_CorridorSouth", (999, 296, 1005, 300), "interior", "CENTER"),
    ("B1_Wall_Interior_017_ServiceWest_MechanicalNorth", (881, 307, 888, 333), "interior", "CENTER"),
    ("B1_Wall_Interior_018_ServiceWest_MechanicalSouth", (881, 361, 888, 452), "interior", "CENTER"),
    ("B1_Wall_Interior_019_ServiceWest_ElectricalSouth", (881, 480, 888, 525), "interior", "CENTER"),
    ("B1_Wall_Interior_020_ServiceWest_WaterSouth", (881, 553, 888, 617), "interior", "CENTER"),
    ("B1_Wall_Interior_028_StoragePowder_North", (194, 486, 201, 520), "interior", "CENTER"),
    ("B1_Wall_Interior_029_StoragePowder_South", (194, 548, 201, 580), "interior", "CENTER"),
    ("B1_Wall_Interior_030_Powder_East", (344, 486, 351, 580), "interior", "CENTER"),
    ("B1_Wall_Interior_031_BathStorage", (966, 624, 972, 737), "interior", "CENTER"),
]

GLAZING = [
    ("Gym_West", (81.7710674157, 279), (81.7710674157, 449)),
    ("Storage_West", (81.7710674157, 505), (81.7710674157, 575)),
    ("Courtyard_West", (111, 638), (111, 750)),
    ("Storage_South", (119, 584), (194, 584)),
    ("Powder_South", (205, 584), (337, 584)),
    ("Courtyard_South", (187, 800), (364, 800)),
    ("Lounge_SouthWest", (550, 807.2), (639, 807.2)),
    ("Lounge_SouthEast", (713, 807.2), (843, 807.2)),
    ("Bath_South", (905, 744), (959, 744)),
    ("StorageEast_South", (977, 744), (1040, 744)),
]

DOOR_OPENINGS = [
    ("Gym_Shower", (380.5, 218.5), "source door at shower northwest recess"),
    ("Shower_Vestibule", (403.0, 317.5), "source door swing"),
    ("Gym_Library", (380.5, 443.0), "source door swing"),
    ("Cinema_Library_West", (498.0, 394.5), "source door swing"),
    ("Cinema_Library_East", (762.5, 394.5), "source door swing"),
    ("Laundry_Main", (823.0, 303.5), "source door swing"),
    ("Linen_ServiceCorridor", (1002.0, 281.5), "door symbol at east linen bay"),
    ("Mechanical_Main", (884.5, 347.0), "source door swing"),
    ("Electrical_Main", (884.5, 466.0), "source door swing"),
    ("WaterUtility_Main", (884.5, 539.0), "source door swing"),
    ("Powder_Gym", (220.0, 482.5), "source door swing"),
    ("StorageWest_Powder_Inferred", (197.5, 534.0), "minimum access inferred because source omits a leaf"),
    ("Bath_Lounge", (915.0, 620.5), "source door swing"),
    ("StorageEast_Lounge", (987.0, 620.5), "source door swing"),
]

CIRCULATION_OPENINGS = [
    ("Gym_ShowerVestibule", (380.5, 364.0), "wide source-drawn wall interruption"),
    ("ServiceCorridor_Main", (1021.5, 303.5), "open service vestibule connection"),
]

ROOM_SAMPLES_PX = {
    "Gym / Fitness Room": (240, 330),
    "Shower / Changing": (430, 260),
    "Cinema / Theater Room": (620, 290),
    "Library / Wine Tasting Lounge": (610, 500),
    "Bar / Pantry": (820, 500),
    "Lounge": (700, 650),
    "Laundry": (850, 250),
    "Linen / Storage": (950, 250),
    "Mechanical / Plant Room": (960, 380),
    "Electrical Room": (960, 480),
    "Water Tank / Utility": (960, 570),
    "Bath": (920, 680),
    "Storage East": (1010, 680),
    "Powder Room": (280, 530),
    "Storage West": (150, 530),
}


def xy(px, py):
    return (px - CX) * SX, (CY - py) * SY


def world_rect(rect):
    x0, y1 = xy(rect[0], rect[1])
    x1, y0 = xy(rect[2], rect[3])
    return x0, y0, x1, y1


def intersects(a, b):
    return min(a[2], b[2]) > max(a[0], b[0]) and min(a[3], b[3]) > max(a[1], b[1])


def resize_rect(rect, thickness, anchor="CENTER"):
    x0, y0, x1, y1 = map(float, rect)
    vertical = (y1 - y0) * SY > (x1 - x0) * SX
    if anchor in {"W", "E"} or (anchor == "CENTER" and vertical):
        pixels = thickness / SX
        if anchor == "W":
            x1 = x0 + pixels
        elif anchor == "E":
            x0 = x1 - pixels
        else:
            center = (x0 + x1) / 2
            x0, x1 = center - pixels / 2, center + pixels / 2
    else:
        pixels = thickness / SY
        if anchor == "N":
            y1 = y0 + pixels
        elif anchor == "S":
            y0 = y1 - pixels
        else:
            center = (y0 + y1) / 2
            y0, y1 = center - pixels / 2, center + pixels / 2
    return x0, y0, x1, y1


def collection(name, parent=None):
    coll = bpy.data.collections.new(name)
    (parent or bpy.context.scene.collection).children.link(coll)
    return coll


def material(name, rgba, glass=False):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = rgba
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = rgba
    bsdf.inputs["Roughness"].default_value = .35 if glass else .75
    if glass:
        bsdf.inputs["Alpha"].default_value = rgba[3]
        bsdf.inputs["Transmission Weight"].default_value = 0.0
        mat.surface_render_method = "DITHERED"
    return mat


def mesh_object(name, vertices, faces, coll, mat, kind):
    mesh = bpy.data.meshes.new(name + "_Mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bmesh.ops.dissolve_limit(bm, angle_limit=.0001, verts=list(bm.verts), edges=list(bm.edges), use_dissolve_boundaries=False)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    coll.objects.link(obj)
    obj.data.materials.append(mat)
    obj["shell_geometry"] = True
    obj["element_type"] = kind
    center = Vector(tuple((min(v.co[k] for v in mesh.vertices) + max(v.co[k] for v in mesh.vertices)) / 2 for k in range(3)))
    for vertex in mesh.vertices:
        vertex.co -= center
    obj.location = center
    mesh.update()
    return obj


def rect_solid(name, rects, z0, z1, coll, mat, kind, subtract=()):
    cuts = [cut for cut in subtract if any(intersects(cut, rect) for rect in rects)]
    edges = list(rects) + cuts
    xs = sorted(set(value for rect in edges for value in (rect[0], rect[2])))
    ys = sorted(set(value for rect in edges for value in (rect[1], rect[3])))

    def contains(items, x, y):
        return any(rect[0] < x < rect[2] and rect[1] < y < rect[3] for rect in items)

    cells = {(i, j) for i in range(len(xs) - 1) for j in range(len(ys) - 1)
             if contains(rects, (xs[i] + xs[i + 1]) / 2, (ys[j] + ys[j + 1]) / 2)
             and not contains(cuts, (xs[i] + xs[i + 1]) / 2, (ys[j] + ys[j + 1]) / 2)}
    if not cells:
        return None
    vertices, faces, indices = [], [], {}

    def vertex(i, j, k):
        key = i, j, k
        if key not in indices:
            indices[key] = len(vertices)
            vertices.append((xs[i], ys[j], z1 if k else z0))
        return indices[key]

    for i, j in sorted(cells):
        corners = [(i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)]
        low = [vertex(a, b, 0) for a, b in corners]
        high = [vertex(a, b, 1) for a, b in corners]
        faces.extend([low[::-1], high])
        for edge, neighbor in enumerate(((i, j - 1), (i + 1, j), (i, j + 1), (i - 1, j))):
            if neighbor not in cells:
                nxt = (edge + 1) % 4
                faces.append([low[edge], low[nxt], high[nxt], high[edge]])
    obj = mesh_object(name, vertices, faces, coll, mat, kind)
    obj["footprint_rectangles_world"] = json.dumps(rects)
    obj["subtracted_rectangles_world"] = json.dumps(cuts)
    obj["z_min"] = z0
    obj["z_max"] = z1
    return obj


def traced_solid(name, rects, z0, z1, coll, mat, kind, subtract=()):
    obj = rect_solid(name, [world_rect(rect) for rect in rects], z0, z1, coll, mat, kind, subtract)
    if obj:
        obj["source_pixel_rectangles"] = json.dumps(rects)
    return obj


def helper_world(name, rect, z0, z1, coll):
    x0, y0, x1, y1 = rect
    obj = bpy.data.objects.new(name, None)
    coll.objects.link(obj)
    obj.empty_display_type = "CUBE"
    obj.empty_display_size = 1
    obj.location = ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2)
    obj.scale = ((x1 - x0) / 2, (y1 - y0) / 2, (z1 - z0) / 2)
    obj.hide_render = True
    obj.hide_set(True)
    obj["non_export_helper"] = True
    obj["bounds_world_m"] = json.dumps([x0, y0, z0, x1, y1, z1])
    return obj


def camera(name, location, target, coll, ortho=None):
    data = bpy.data.cameras.new(name)
    obj = bpy.data.objects.new(name, data)
    coll.objects.link(obj)
    obj.location = location
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()
    if ortho:
        data.type = "ORTHO"
        data.ortho_scale = ortho
    else:
        data.lens = 45
    data.clip_end = 250
    return obj


def main():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for coll in list(bpy.data.collections):
        bpy.data.collections.remove(coll)

    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.length_unit = "METERS"
    scene.unit_settings.scale_length = 1
    scene["floor_id"] = "B1"
    scene["local_finished_floor_z_m"] = 0.0
    scene["reference_source"] = "B1.png + 1F.png direction evidence with exact live 1F Stair A mesh interface"
    scene["alignment_calibration_json"] = json.dumps({
        "origin_pixel": [CX, CY], "origin_xy_m": [0.0, 0.0],
        "meters_per_pixel_x": SX, "meters_per_pixel_y": SY,
        "x_axis": "east/right", "y_axis": "north/up",
    })
    scene["protected_floor_hashes_json"] = json.dumps({
        path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (ROOT / "01_shell/1F/1F_shell.blend", ROOT / "01_shell/2F/2F_shell.blend", ROOT / "01_shell/3F/3F_shell.blend")
    })
    scene["source_ambiguities_json"] = json.dumps([
        "B1.png's written 33.2 m width conflicts with the established 1F pixel transform; the shared transform governs stacking.",
        "The B1 raster stair is north of the live 1F stair; only the stair bay and an L-shaped south-exit vestibule are locally adapted.",
        "The straight south exit drawn in B1 cannot meet the unchanged lounge after exact 1F XY alignment; the local vestibule therefore turns east then north back into the lounge.",
        "The west Storage has no legible door leaf; a 0.986 m internal opening to Powder is inferred to provide required access.",
        "The Linen / Storage door graphic is crowded by its east service vestibule; the visible east-side doorway is retained.",
    ])

    root = collection("B1_SHELL")
    cols = {name: collection(name, root) for name in (
        "B1_FLOOR", "B1_WALLS_EXTERIOR", "B1_WALLS_INTERIOR", "B1_COLUMNS",
        "B1_GLASS", "B1_STAIRS", "B1_TERRACES", "B1_OPENINGS", "B1_DEBUG")}
    refs = collection("REFERENCE_B1")
    views = collection("B1_VALIDATION_CAMERAS")
    mats = {
        "wall": material("Placeholder_Wall_Gray", (.13, .15, .17, 1)),
        "floor": material("Placeholder_Floor_Gray", (.67, .68, .69, 1)),
        "terrace": material("Placeholder_Terrace_Gray", (.78, .79, .79, 1)),
        "column": material("Placeholder_Structural_DarkGray", (.20, .23, .25, 1)),
        "glass": material("Placeholder_Glass_Blue", (.13, .54, .70, .32), True),
    }

    image = bpy.data.images.load(str(IMAGE), check_existing=True)
    image.pack()
    ref = bpy.data.objects.new("B1_Reference_Plan", None)
    refs.objects.link(ref)
    ref.empty_display_type = "IMAGE"
    ref.data = image
    ref.empty_display_size = image.size[0] * SX
    ref.scale = (1, SY / SX, 1)
    ref.location = (*xy(image.size[0] / 2, image.size[1] / 2), -.24)
    ref.color[3] = .65
    ref.empty_image_depth = "BACK"
    ref.hide_render = True
    ref.hide_select = True
    ref.hide_set(True)
    ref.lock_location = ref.lock_rotation = ref.lock_scale = (True, True, True)
    ref["meters_per_pixel_x"] = SX
    ref["meters_per_pixel_y"] = SY
    ref["calibration"] = "Exact 1F transform: origin pixel 585,513; X 108..1062=35.6m; Y 189..837=22.8m"

    stair_cut = (STAIR_X0, STAIR_Y0, STAIR_X1, STAIR_SLAB_OPENING_Y1)
    main_floor_rects = [world_rect(rect) for rect in MAIN_FOOTPRINT] + STAIR_ARRIVAL_FLOOR_WORLD
    floor = rect_solid("B1_Floor_Main", main_floor_rects, -SLAB_THICKNESS, 0,
                       cols["B1_FLOOR"], mats["floor"], "floor", [stair_cut])
    floor["source_pixel_rectangles"] = json.dumps(MAIN_FOOTPRINT)
    floor["local_stair_adaptation_world_rectangles"] = json.dumps(STAIR_ARRIVAL_FLOOR_WORLD)
    floor["slab_thickness_m"] = SLAB_THICKNESS
    courtyard = traced_solid("B1_Terrace_Courtyard", COURTYARD_FOOTPRINT, -SLAB_THICKNESS, 0,
                             cols["B1_TERRACES"], mats["terrace"], "terrace")
    courtyard["architectural_program"] = "Terrace Garden / Open Air Courtyard"

    occupied = []
    for index, (label, source_rect) in enumerate(COLUMNS, 1):
        rect = world_rect(source_rect)
        obj = rect_solid(f"B1_Column_{index:03d}_{label}", [rect], 0, WALL_HEIGHT,
                         cols["B1_COLUMNS"], mats["column"], "column")
        obj["source_pixel_rectangles"] = json.dumps([source_rect])
        obj["height_m"] = WALL_HEIGHT
        occupied.append(rect)

    wall_objects = {}

    def add_source_wall(name, source_rect, wall_class, anchor):
        thickness = {"exterior": EXTERIOR_WALL_THICKNESS, "interior": INTERIOR_WALL_THICKNESS,
                     "stairwell": STAIRWELL_WALL_THICKNESS}[wall_class]
        resized = resize_rect(source_rect, thickness, anchor)
        rect = world_rect(resized)
        coll = cols["B1_WALLS_EXTERIOR"] if wall_class == "exterior" else cols["B1_WALLS_INTERIOR"]
        obj = rect_solid(name, [rect], 0, WALL_HEIGHT, coll, mats["wall"], "wall", occupied)
        if not obj:
            raise RuntimeError(f"Wall {name} was fully removed")
        obj["wall_class"] = wall_class
        obj["nominal_thickness_m"] = thickness
        obj["source_pixel_rectangles"] = json.dumps([resized])
        obj["original_source_pixel_rectangles"] = json.dumps([source_rect])
        obj["alignment_rule"] = "preserve exterior face" if wall_class == "exterior" else "preserve centerline"
        occupied.append(rect)
        wall_objects[name] = obj
        return obj

    for spec in HORIZONTAL_WALLS + VERTICAL_WALLS:
        add_source_wall(*spec)

    def add_world_wall(name, rect, wall_class="stairwell"):
        coll = cols["B1_WALLS_EXTERIOR"] if wall_class == "exterior" else cols["B1_WALLS_INTERIOR"]
        obj = rect_solid(name, [rect], 0, WALL_HEIGHT, coll, mats["wall"], "wall", occupied)
        obj["wall_class"] = wall_class
        obj["nominal_thickness_m"] = STAIRWELL_WALL_THICKNESS if wall_class == "stairwell" else EXTERIOR_WALL_THICKNESS
        obj["alignment_rule"] = "exact live 1F stair face"
        obj["source_override"] = "Local B1 stair bay adaptation"
        occupied.append(rect)
        wall_objects[name] = obj
        return obj

    # Exact shaft faces.  Both run the full physical flight because the plans
    # show a straight stair enclosure.  The B1 lower landing exits through a
    # centered opening at the south end, as drawn in B1.png.
    add_world_wall("B1_Wall_Stair_001_From1F_West",
                   (STAIR_X0 - STAIRWELL_WALL_THICKNESS, STAIR_Y0, STAIR_X0, STAIR_Y1))
    add_world_wall("B1_Wall_Stair_002_From1F_East",
                   (STAIR_X1, STAIR_Y0, STAIR_X1 + STAIRWELL_WALL_THICKNESS, STAIR_Y1))
    # North under-flight access door shown in B1.png.
    add_world_wall("B1_Wall_Stair_003_NorthUnderflight_West",
                   (STAIR_X0, STAIR_Y1, STAIR_CENTER_X - STAIR_UNDERFLIGHT_DOOR_HALF_WIDTH,
                    STAIR_Y1 + STAIRWELL_WALL_THICKNESS))
    add_world_wall("B1_Wall_Stair_004_NorthUnderflight_East",
                   (STAIR_CENTER_X + STAIR_UNDERFLIGHT_DOOR_HALF_WIDTH, STAIR_Y1, STAIR_X1,
                    STAIR_Y1 + STAIRWELL_WALL_THICKNESS))
    # South lower-landing threshold, with the source's broad near-full-width
    # opening (normalized here to 2.00 m within the exact live shaft width).
    add_world_wall("B1_Wall_Stair_005_LowerThreshold_West",
                   (STAIR_X0, STAIR_Y0 - STAIRWELL_WALL_THICKNESS,
                    STAIR_CENTER_X - STAIR_EXIT_HALF_WIDTH, STAIR_Y0))
    add_world_wall("B1_Wall_Stair_006_LowerThreshold_East",
                   (STAIR_CENTER_X + STAIR_EXIT_HALF_WIDTH, STAIR_Y0 - STAIRWELL_WALL_THICKNESS,
                    STAIR_X1, STAIR_Y0))
    # Minimal local exterior wrap for the south-first circulation required by
    # B1.png.  Its east/north end remains open to the unchanged lounge slab.
    add_world_wall("B1_Wall_Exterior_011_StairVestibule_West",
                   (STAIR_X0 - EXTERIOR_WALL_THICKNESS, STAIR_VESTIBULE_SOUTH_Y,
                    STAIR_X0, STAIR_Y0), "exterior")
    add_world_wall("B1_Wall_Exterior_012_StairVestibule_South",
                   (STAIR_X0 - EXTERIOR_WALL_THICKNESS,
                    STAIR_VESTIBULE_SOUTH_Y - EXTERIOR_WALL_THICKNESS,
                    STAIR_VESTIBULE_EAST_X + EXTERIOR_WALL_THICKNESS,
                    STAIR_VESTIBULE_SOUTH_Y), "exterior")
    add_world_wall("B1_Wall_Exterior_013_StairVestibule_EastReturn",
                   (STAIR_VESTIBULE_EAST_X, STAIR_VESTIBULE_SOUTH_Y,
                    STAIR_VESTIBULE_EAST_X + EXTERIOR_WALL_THICKNESS,
                    STAIR_LOUNGE_SOUTH_GLASS_Y), "exterior")

    glass_objects = {}

    def add_glass(label, a, b, explicit_name=None):
        x0, y0 = xy(*a)
        x1, y1 = xy(*b)
        if abs(x1 - x0) < 1e-8:
            rect = (x0 - GLASS_THICKNESS / 2, min(y0, y1) - .04,
                    x0 + GLASS_THICKNESS / 2, max(y0, y1) + .04)
        else:
            rect = (min(x0, x1) - .04, y0 - GLASS_THICKNESS / 2,
                    max(x0, x1) + .04, y0 + GLASS_THICKNESS / 2)
        name = explicit_name or f"B1_Glass_{len(glass_objects) + 1:03d}_{label}"
        obj = rect_solid(name, [rect], 0, GLASS_HEIGHT, cols["B1_GLASS"], mats["glass"], "glass", occupied)
        if not obj:
            raise RuntimeError(f"Glass {name} was fully removed")
        obj["source_pixel_line"] = json.dumps([a, b])
        obj["nominal_thickness_m"] = GLASS_THICKNESS
        obj["collision_policy"] = "Separate collision candidate; export policy deferred"
        occupied.append(rect)
        glass_objects[label] = obj
        return obj

    for label, a, b in GLAZING:
        add_glass(label, a, b)
    stair_opening = helper_world("B1_Opening_Stair_From1F", stair_cut, -SLAB_THICKNESS, WALL_HEIGHT,
                                 cols["B1_OPENINGS"])
    stair_opening["classification"] = "stair_opening"
    stair_opening["physical_stair_owner"] = "01_shell/1F/1F_shell.blend"
    stair_opening["opening_basis"] = "exact projection of live 1F stair intersection with B1 slab band"
    connection = bpy.data.objects.new("B1_Connection_1F", None)
    cols["B1_OPENINGS"].objects.link(connection)
    connection.empty_display_type = "ARROWS"
    connection.empty_display_size = .6
    connection.location = STAIR_CONNECTION
    connection.hide_render = True
    connection.hide_set(True)
    connection["connection_elevation_local_m"] = 0.0
    connection["assembled_B1_world_z_m"] = -3.2
    connection["upper_landing_end"] = "north (+Y) at 1F"
    connection["lower_landing_end"] = "south (-Y) at B1"
    connection["travel_direction"] = "north (+Y), up to 1F"
    connection["exit_direction"] = "south (-Y) through lower-end opening"

    opening_schedule = []
    for name, source_point, reason in DOOR_OPENINGS:
        point = xy(*source_point)
        opening_schedule.append({"name": name, "classification": "doorway",
                                 "sample_world_xy_m": point, "reason": reason})
        marker = bpy.data.objects.new("B1_Opening_" + name, None)
        cols["B1_OPENINGS"].objects.link(marker)
        marker.location = (*point, 1.2)
        marker.empty_display_type = "PLAIN_AXES"
        marker.empty_display_size = .15
        marker.hide_render = True
        marker.hide_set(True)
    for name, source_point, reason in CIRCULATION_OPENINGS:
        point = xy(*source_point)
        opening_schedule.append({"name": name, "classification": "circulation_opening",
                                 "sample_world_xy_m": point, "reason": reason})
        marker = bpy.data.objects.new("B1_Opening_" + name, None)
        cols["B1_OPENINGS"].objects.link(marker)
        marker.location = (*point, 1.2)
        marker.empty_display_type = "PLAIN_AXES"
        marker.empty_display_size = .15
        marker.hide_render = True
        marker.hide_set(True)
    opening_schedule.append({"name": "Stair_From1F", "classification": "stair_opening",
                             "bounds_world_xyxy_m": stair_cut, "physical_stair_owner": "1F_shell.blend"})
    opening_schedule.append({"name": "Stair_Underflight_Access", "classification": "doorway",
                             "sample_world_xy_m": [STAIR_CENTER_X, STAIR_Y1 + STAIRWELL_WALL_THICKNESS / 2],
                             "reason": "north under-flight door shown in B1.png"})
    opening_schedule.append({"name": "Stair_Lounge_Arrival", "classification": "circulation_opening",
                             "sample_world_xy_m": [STAIR_CENTER_X, STAIR_Y0 - STAIRWELL_WALL_THICKNESS / 2],
                             "reason": "south lower-end exit proven by B1 stair arrow and threshold"})
    for label, _, _ in GLAZING:
        opening_schedule.append({"name": label, "classification": "glazing", "object": glass_objects[label].name})
    scene["opening_schedule_json"] = json.dumps(opening_schedule)
    scene["room_samples_json"] = json.dumps({name: xy(*point) for name, point in ROOM_SAMPLES_PX.items()})

    junctions = [
        ("NorthWestColumn_GymNorth", "wall_to_column", "B1_Column_001_NorthWest_Step", "B1_Wall_Exterior_001_Gym_North"),
        ("GymNorth_ShowerColumn", "wall_to_column", "B1_Wall_Exterior_001_Gym_North", "B1_Column_002_Shower_North"),
        ("ShowerColumn_NorthCenter", "wall_to_column", "B1_Column_002_Shower_North", "B1_Wall_Exterior_002_North_Center"),
        ("NorthCenter_LaundryColumn", "wall_to_column", "B1_Wall_Exterior_002_North_Center", "B1_Column_003_Laundry_North"),
        ("LaundryColumn_ServiceNorth", "wall_to_column", "B1_Column_003_Laundry_North", "B1_Wall_Exterior_003_Service_North"),
        ("ServiceNorth_NorthEastColumn", "wall_to_column", "B1_Wall_Exterior_003_Service_North", "B1_Column_004_NorthEast_Step"),
        ("GymWestNorth_GymGlass", "wall_to_glass", "B1_Wall_Exterior_004_Gym_WestNorth", glass_objects["Gym_West"].name),
        ("GymGlass_WestColumn", "wall_to_column", glass_objects["Gym_West"].name, "B1_Column_005_West_GymStorage"),
        ("StorageWestGlass_LowerColumn", "wall_to_glass", glass_objects["Storage_West"].name, "B1_Column_006_West_Courtyard"),
        ("CourtyardWestGlass_NorthWall", "wall_to_glass", glass_objects["Courtyard_West"].name, "B1_Wall_Exterior_007_Courtyard_WestNorth"),
        ("CourtyardWestGlass_SouthWall", "wall_to_glass", glass_objects["Courtyard_West"].name, "B1_Wall_Exterior_008_Courtyard_WestSouth"),
        ("CourtyardSouthGlass_WestWall", "wall_to_glass", glass_objects["Courtyard_South"].name, "B1_Wall_Exterior_009_Courtyard_SouthWest"),
        ("LoungeGlassWest_CenterWall", "wall_to_glass", glass_objects["Lounge_SouthWest"].name, "B1_Wall_Exterior_015_Lounge_SouthCenter"),
        ("LoungeCenterWall_EastGlass", "wall_to_glass", "B1_Wall_Exterior_015_Lounge_SouthCenter", glass_objects["Lounge_SouthEast"].name),
        ("BathGlass_Mullion", "wall_to_column", glass_objects["Bath_South"].name, "B1_Column_009_BathStorage_Mullion"),
        ("Mullion_StorageEastGlass", "wall_to_column", "B1_Column_009_BathStorage_Mullion", glass_objects["StorageEast_South"].name),
        ("StairWest_VestibuleWest", "wall_to_wall", "B1_Wall_Stair_001_From1F_West", "B1_Wall_Exterior_011_StairVestibule_West"),
        ("StairEast_LowerThreshold", "wall_to_wall", "B1_Wall_Stair_002_From1F_East", "B1_Wall_Stair_006_LowerThreshold_East"),
        ("VestibuleWest_South", "wall_to_wall", "B1_Wall_Exterior_011_StairVestibule_West", "B1_Wall_Exterior_012_StairVestibule_South"),
        ("VestibuleSouth_East", "wall_to_wall", "B1_Wall_Exterior_012_StairVestibule_South", "B1_Wall_Exterior_013_StairVestibule_EastReturn"),
        ("VestibuleEast_LoungeGlass", "wall_to_glass", "B1_Wall_Exterior_013_StairVestibule_EastReturn", glass_objects["Lounge_SouthWest"].name),
        ("CinemaSouthEast_CinemaLaundry", "wall_to_wall", "B1_Wall_Interior_010_CinemaSouth_EastJamb", "B1_Wall_Interior_007_CinemaLaundry"),
    ]
    scene["junction_schedule_json"] = json.dumps([
        {"name": name, "type": kind, "a": a, "b": b} for name, kind, a, b in junctions])

    scene["stair_alignment_json"] = json.dumps({
        "physical_stair_bounds_xyxy_m": [STAIR_X0, STAIR_Y0, STAIR_X1, STAIR_Y1],
        "slab_opening_xyxy_m": stair_cut,
        "lower_landing_bounds_xyxy_m": [STAIR_X0, STAIR_Y0, STAIR_X1, STAIR_LOWER_LANDING_Y1],
        "arrival_threshold_local_xyz_m": STAIR_CONNECTION,
        "upper_landing_end": "north (+Y) at 1F",
        "lower_landing_end": "south (-Y) at B1",
        "B1_travel_direction": "north (+Y), up to 1F",
        "B1_exit_direction": "south (-Y) through lower-end opening",
        "physical_stair_owner": "01_shell/1F/1F_shell.blend",
        "duplicate_stair_policy": "No B1 stair mesh",
        "local_adaptation": "Exact 1F shaft retained; local B1 exit goes south, then east/north through a stair-only vestibule to the unchanged lounge",
    })
    scene["assumptions"] = ("Local finished floor Z=0; slab 0.20m; wall height 3.20m; exterior/interior/stair wall thicknesses "
                            "0.28/0.18/0.22m; glass 0.020m and full height. Door gaps are full-height shell openings. "
                            "The physical stair remains in 1F. No ceilings, furniture, equipment, fixtures, or decorations.")

    top = camera("B1_Camera_Top_Orthographic", (0, 0, 55), (0, 0, 0), views, ortho=42.5)
    top.rotation_euler = (0, 0, 0)
    corner = camera("B1_Camera_Perspective_Corner", (34, -38, 40), (0, 0, .4), views)
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 48
    scene.cycles.use_denoising = True
    scene.cycles.transparent_max_bounces = 12
    scene.world.use_nodes = True
    scene.world.node_tree.nodes["Background"].inputs[0].default_value = (.85, .85, .85, 1)
    scene.world.node_tree.nodes["Background"].inputs[1].default_value = .8
    light_data = bpy.data.lights.new("Validation_Area_Light", "AREA")
    light = bpy.data.objects.new(light_data.name, light_data)
    views.objects.link(light)
    light.location = (0, -5, 30)
    light_data.energy = 3500
    light_data.size = 25
    scene.render.resolution_x = 2400
    scene.render.resolution_y = 1700
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.camera = top

    readme = bpy.data.texts.new("README_B1_SHELL")
    readme.write(__doc__ + "\n\n" + scene["assumptions"] + "\n\n" + ref["calibration"])
    bpy.context.view_layer.update()
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND))

    sys.path.insert(0, str(OUT))
    import validate_B1_shell
    result = validate_B1_shell.run()
    if result["summary"]["failed"]:
        raise RuntimeError(f"B1 validation failed: {result['summary']}")

    if "--skip-renders" not in sys.argv:
        for camera_obj, filename, resolution in (
            (top, "B1_shell_top.png", (2400, 1700)),
            (corner, "B1_shell_perspective_corner.png", (1800, 1300)),
        ):
            scene.camera = camera_obj
            scene.render.resolution_x, scene.render.resolution_y = resolution
            scene.render.filepath = str(OUT / filename)
            bpy.ops.render.render(write_still=True)
    scene.camera = top
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND))
    print("B1_BUILD_COMPLETE", json.dumps(result["summary"], sort_keys=True))


if __name__ == "__main__":
    main()
