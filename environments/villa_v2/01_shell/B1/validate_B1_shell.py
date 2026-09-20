"""Independent geometry validation for the standalone B1 shell."""
import bpy
import bmesh
import hashlib
import json
import math
from collections import deque
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
REPORT = OUT / "B1_shell_validation.json"
ONE_F = ROOT / "01_shell" / "1F" / "1F_shell.blend"
OTHER_FLOORS = [
    ROOT / "01_shell" / "1F" / "1F_shell.blend",
    ROOT / "01_shell" / "2F" / "2F_shell.blend",
    ROOT / "01_shell" / "3F" / "3F_shell.blend",
]
SX = 35.6 / 954.0
SY = 22.8 / 648.0
CX, CY = 585.0, 513.0
EXPECTED_STAIR = [-7.351362683438155, -10.837037037037037,
                  -4.515303983228511, -4.82037037037037]
# The physical stair is owned by 1F.  At B1 slab elevation only its lower
# 0.6075 m of flight plus the terminal landing intersect the -0.20..0.00 m
# slab band.  Cutting the whole 6.017 m shaft was the original B1 error.
EXPECTED_SLAB_OPENING = [-7.351362683438155, -10.837037037037037,
                         -4.515303983228511, -9.07287037037037]
EXPECTED_CONNECTION = [-5.933333333333334, -10.837037037037037, 0.0]
EXPECTED_UPPER_LANDING_END = "north (+Y) at 1F"
EXPECTED_LOWER_LANDING_END = "south (-Y) at B1"
EXPECTED_B1_TRAVEL = "north (+Y), up to 1F"
EXPECTED_B1_EXIT = "south (-Y) through lower-end opening"


def xy(px, py):
    return (px - CX) * SX, (CY - py) * SY


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def bounds(obj):
    points = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    return ([min(p[i] for p in points) for i in range(3)],
            [max(p[i] for p in points) for i in range(3)])


def xyxy(obj):
    low, high = bounds(obj)
    return [low[0], low[1], high[0], high[1]]


def mesh_components(obj):
    mesh = obj.data
    adjacency = {vertex.index: set() for vertex in mesh.vertices}
    for edge in mesh.edges:
        a, b = edge.vertices
        adjacency[a].add(b)
        adjacency[b].add(a)
    pending = set(adjacency)
    count = 0
    while pending:
        count += 1
        todo = [pending.pop()]
        while todo:
            for neighbor in adjacency[todo.pop()]:
                if neighbor in pending:
                    pending.remove(neighbor)
                    todo.append(neighbor)
    return count


def manifold_and_volume(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.transform(obj.matrix_world)
    nonmanifold = sum(1 for edge in bm.edges if not edge.is_manifold)
    degenerate = sum(1 for face in bm.faces if face.calc_area() < 1e-10)
    volume = bm.calc_volume(signed=True)
    bm.free()
    return nonmanifold, degenerate, volume


def bvh_for(obj):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(depsgraph)
    return BVHTree.FromObject(evaluated, depsgraph)


def has_floor_at(floors, x, y):
    origin = Vector((x, y, 5.0))
    direction = Vector((0.0, 0.0, -1.0))
    for obj in floors:
        inverse = obj.matrix_world.inverted()
        hit, location, normal, _ = obj.ray_cast(inverse @ origin, inverse.to_3x3() @ direction)
        if hit and normal.z > .5:
            return True
    return False


def bbox_gap_xy(a, b):
    aa, ab = bounds(a)
    ba, bb = bounds(b)
    dx = max(ba[0] - ab[0], aa[0] - bb[0], 0.0)
    dy = max(ba[1] - ab[1], aa[1] - bb[1], 0.0)
    return math.hypot(dx, dy)


def positive_overlap_xyz(a, b):
    aa, ab = bounds(a)
    ba, bb = bounds(b)
    return [max(0.0, min(ab[i], bb[i]) - max(aa[i], ba[i])) for i in range(3)]


def actual_positive_xy_overlap(a, b):
    def shape(obj):
        rects = json.loads(obj.get("footprint_rectangles_world", "[]"))
        cuts = json.loads(obj.get("subtracted_rectangles_world", "[]"))
        return rects, cuts

    ar, ac = shape(a)
    br, bc = shape(b)
    if not ar or not br:
        return 0.0
    xs = sorted(set(value for rect in ar + ac + br + bc for value in (rect[0], rect[2])))
    ys = sorted(set(value for rect in ar + ac + br + bc for value in (rect[1], rect[3])))

    def contains(rects, x, y):
        return any(rect[0] < x < rect[2] and rect[1] < y < rect[3] for rect in rects)

    area = 0.0
    for ix in range(len(xs) - 1):
        for iy in range(len(ys) - 1):
            x = (xs[ix] + xs[ix + 1]) / 2
            y = (ys[iy] + ys[iy + 1]) / 2
            in_a = contains(ar, x, y) and not contains(ac, x, y)
            in_b = contains(br, x, y) and not contains(bc, x, y)
            if in_a and in_b:
                area += (xs[ix + 1] - xs[ix]) * (ys[iy + 1] - ys[iy])
    return area


def blocker_at(solids, x, y, radius=0.0, z=1.2):
    hits = []
    for obj in solids:
        low, high = bounds(obj)
        if low[2] <= z <= high[2] and low[0] - radius <= x <= high[0] + radius and low[1] - radius <= y <= high[1] + radius:
            hits.append(obj.name)
    return hits


def inspect_live_1f_stair():
    loaded = []
    with bpy.data.libraries.load(str(ONE_F), link=False) as (source, target):
        wanted = [name for name in ("1F_StairA_DownToB1", "1F_Opening_StairA", "1F_Connection_B1")
                  if name in source.objects]
        target.objects = wanted
    loaded = [obj for obj in target.objects if obj]
    by_name = {obj.name: obj for obj in loaded}
    stair = by_name.get("1F_StairA_DownToB1")
    opening = by_name.get("1F_Opening_StairA")
    connection = by_name.get("1F_Connection_B1")
    if not stair or not opening or not connection:
        result = {"error": "Required live 1F stair objects are missing"}
    else:
        # Appended-but-unlinked objects keep their datablock transform values,
        # but Blender does not evaluate matrix_world until they enter a view
        # layer.  The generator stored evaluated shaft faces explicitly.
        x0 = float(stair["xmin"])
        x1 = float(stair["xmax"])
        y0 = float(stair["end_y"])
        y1 = float(stair["start_y"])
        matrix = stair.matrix_basis
        points = [matrix @ vertex.co for vertex in stair.data.vertices]
        plane_z = -3.2
        section = []
        for edge in stair.data.edges:
            a, b = (points[index] for index in edge.vertices)
            if abs(a.z - plane_z) < 1e-7:
                section.append(a)
            if abs(b.z - plane_z) < 1e-7:
                section.append(b)
            if (a.z - plane_z) * (b.z - plane_z) < 0:
                factor = (plane_z - a.z) / (b.z - a.z)
                section.append(a.lerp(b, factor))
        section_bounds = ([min(point.x for point in section), min(point.y for point in section),
                           max(point.x for point in section), max(point.y for point in section)]
                          if section else [])
        north_top = max(point.z for point in points if abs(point.y - y1) < 1e-5)
        south_top = max(point.z for point in points if abs(point.y - y0) < 1e-5)
        result = {
            "bounds_xyxy_m": [x0, y0, x1, y1],
            "opening_metadata_bounds_m": json.loads(opening.get("bounds_world_m", "[]")),
            "connection_world_xyz_m": list(connection.location),
            "terminal_elevation_m": stair.get("terminal_elevation_m"),
            "landing_depth_m": stair.get("landing_depth_m"),
            "run_m": stair.get("run_m"),
            "start_y": stair.get("start_y"),
            "end_y": stair.get("end_y"),
            "direction": stair.get("direction"),
            "exit_direction": connection.get("exit_direction"),
            "slab_top_cross_section_xyxy_m": section_bounds,
            "north_end_top_z_m": north_top,
            "south_end_top_z_m": south_top,
        }
    for obj in loaded:
        bpy.data.objects.remove(obj, do_unlink=True)
    return result


def validate_accessibility(floors, obstacles, room_samples):
    resolution = 0.20
    radius = 0.20
    floor_bounds = [bounds(obj) for obj in floors]
    xmin = min(item[0][0] for item in floor_bounds)
    ymin = min(item[0][1] for item in floor_bounds)
    xmax = max(item[1][0] for item in floor_bounds)
    ymax = max(item[1][1] for item in floor_bounds)
    nx = int(math.ceil((xmax - xmin) / resolution)) + 1
    ny = int(math.ceil((ymax - ymin) / resolution)) + 1

    def cell(point):
        return (round((point[0] - xmin) / resolution), round((point[1] - ymin) / resolution))

    obstacle_bounds = [(obj.name, *bounds(obj)) for obj in obstacles]

    def walkable(ix, iy):
        if ix < 0 or iy < 0 or ix >= nx or iy >= ny:
            return False
        x, y = xmin + ix * resolution, ymin + iy * resolution
        if not has_floor_at(floors, x, y):
            return False
        for _, low, high in obstacle_bounds:
            if low[2] <= 1.2 <= high[2] and low[0] - radius <= x <= high[0] + radius and low[1] - radius <= y <= high[1] + radius:
                return False
        return True

    hub = cell(room_samples["Library / Wine Tasting Lounge"])
    if not walkable(*hub):
        return {name: False for name in room_samples}, {"error": "hub sample is blocked", "hub": hub}
    reached = {hub}
    queue = deque([hub])
    while queue:
        ix, iy = queue.popleft()
        for nxt in ((ix + 1, iy), (ix - 1, iy), (ix, iy + 1), (ix, iy - 1)):
            if nxt not in reached and walkable(*nxt):
                reached.add(nxt)
                queue.append(nxt)
    result = {name: cell(point) in reached for name, point in room_samples.items()}
    return result, {"grid_resolution_m": resolution, "uav_radius_m": radius, "reachable_cells": len(reached)}


def run():
    checks = []

    def check(name, condition, detail=None):
        checks.append({"name": name, "pass": bool(condition), "detail": detail})

    scene = bpy.context.scene
    meshes = [obj for obj in scene.objects if obj.type == "MESH" and obj.get("shell_geometry")]
    floors = [obj for obj in meshes if obj.get("element_type") in {"floor", "terrace"}]
    walls = [obj for obj in meshes if obj.get("element_type") == "wall"]
    columns = [obj for obj in meshes if obj.get("element_type") == "column"]
    glass = [obj for obj in meshes if obj.get("element_type") == "glass"]
    stairs = [obj for obj in meshes if obj.get("element_type") == "stair"]
    structure = walls + columns + glass

    check("Blender file opens with expected B1 scene", scene.get("floor_id") == "B1", scene.get("floor_id"))
    check("Scene uses meters at unit scale 1", scene.unit_settings.system == "METRIC" and abs(scene.unit_settings.scale_length - 1.0) < 1e-9)
    check("Architectural shell geometry exists", len(meshes) >= 35, len(meshes))
    required = ["B1_Floor_Main", "B1_Terrace_Courtyard", "B1_Opening_Stair_From1F",
                "B1_Connection_1F", "B1_Camera_Top_Orthographic"]
    missing = [name for name in required if bpy.data.objects.get(name) is None]
    check("Required floor, courtyard, stair interface, and camera exist", not missing, missing)
    check("Saved top validation camera is truly orthographic",
          (cam := bpy.data.objects.get("B1_Camera_Top_Orthographic")) is not None and cam.type == "CAMERA" and cam.data.type == "ORTHO",
          {"type": cam.data.type, "ortho_scale": cam.data.ortho_scale} if cam and cam.type == "CAMERA" else None)
    ref = bpy.data.objects.get("B1_Reference_Plan")
    packed = bool(ref and ref.data and ref.data.packed_file)
    check("Calibrated B1 reference image is packed", packed, list(ref.data.size) if ref and ref.data else None)
    check("No furniture, equipment, appliance, or decorative object names",
          not [obj.name for obj in scene.objects if any(word in obj.name.lower() for word in
              ("furniture", "sofa", "chair", "table", "gym_equipment", "projector", "book", "decor", "appliance"))])
    check("No physical stair is duplicated in B1", not stairs, [obj.name for obj in stairs])
    check("All architectural mesh transforms have unit scale",
          all(all(abs(value - 1.0) < 1e-7 for value in obj.scale) for obj in meshes),
          [obj.name for obj in meshes if any(abs(value - 1.0) >= 1e-7 for value in obj.scale)])

    if meshes:
        lows, highs = zip(*(bounds(obj) for obj in meshes))
        scene_bounds = [[min(v[i] for v in lows) for i in range(3)],
                        [max(v[i] for v in highs) for i in range(3)]]
    else:
        scene_bounds = [[0, 0, 0], [0, 0, 0]]
    dimensions = [scene_bounds[1][i] - scene_bounds[0][i] for i in range(3)]
    check("B1 XY bounds are realistic in the established villa frame",
          35.0 <= dimensions[0] <= 40.0 and 22.0 <= dimensions[1] <= 27.0,
          {"bounds_xyz_m": scene_bounds, "dimensions_xyz_m": dimensions})
    check("B1 shell Z bounds are exactly slab bottom to wall top",
          abs(scene_bounds[0][2] + .2) < 1e-5 and abs(scene_bounds[1][2] - 3.2) < 1e-5,
          [scene_bounds[0][2], scene_bounds[1][2]])

    floor = bpy.data.objects.get("B1_Floor_Main")
    floor_z = (bounds(floor)[0][2], bounds(floor)[1][2]) if floor else (999, 999)
    check("Main floor slab is Z -0.20..0.00 m", floor is not None and abs(floor_z[0] + .2) < 1e-5 and abs(floor_z[1]) < 1e-5, floor_z)
    wall_ranges = {obj.name: bounds(obj)[0][2:] + bounds(obj)[1][2:] for obj in walls}
    check("All walls span Z 0.00..3.20 m", bool(walls) and all(abs(v[0]) < 1e-5 and abs(v[1] - 3.2) < 1e-5 for v in wall_ranges.values()), wall_ranges)
    wall_classes = {key: [float(obj.get("nominal_thickness_m", 0)) for obj in walls if obj.get("wall_class") == key]
                    for key in ("exterior", "interior", "stairwell")}
    check("Exterior walls use nominal 0.28 m thickness", bool(wall_classes["exterior"]) and all(abs(v - .28) < 1e-7 for v in wall_classes["exterior"]), wall_classes["exterior"])
    check("Interior walls use nominal 0.18 m thickness", bool(wall_classes["interior"]) and all(abs(v - .18) < 1e-7 for v in wall_classes["interior"]), wall_classes["interior"])
    check("Stairwell walls use nominal 0.22 m thickness", bool(wall_classes["stairwell"]) and all(abs(v - .22) < 1e-7 for v in wall_classes["stairwell"]), wall_classes["stairwell"])
    glass_data = [(obj.name, float(obj.get("nominal_thickness_m", 0)), bounds(obj)[0][2], bounds(obj)[1][2]) for obj in glass]
    check("Glazing is separate 0.020 m floor-to-ceiling geometry", bool(glass_data) and all(abs(t - .02) < 1e-7 and abs(z0) < 1e-5 and abs(z1 - 3.2) < 1e-5 for _, t, z0, z1 in glass_data), glass_data)
    glass_mat = bpy.data.materials.get("Placeholder_Glass_Blue")
    glass_bsdf = glass_mat.node_tree.nodes.get("Principled BSDF") if glass_mat and glass_mat.use_nodes else None
    glass_style = ({"rgba": list(glass_mat.diffuse_color),
                    "roughness": glass_bsdf.inputs["Roughness"].default_value,
                    "transmission": glass_bsdf.inputs["Transmission Weight"].default_value,
                    "alpha": glass_bsdf.inputs["Alpha"].default_value} if glass_bsdf else {})
    check("Glass material matches the actual existing-floor rendering convention",
          bool(glass_style) and max(abs(a - b) for a, b in zip(glass_style["rgba"], (.13, .54, .70, .32))) < 1e-6
          and abs(glass_style["roughness"] - .35) < 1e-6
          and abs(glass_style["transmission"]) < 1e-7
          and abs(glass_style["alpha"] - .32) < 1e-6, glass_style)

    opening_schedule = json.loads(scene.get("opening_schedule_json", "[]"))
    counts = {kind: sum(item.get("classification") == kind for item in opening_schedule) for kind in
              ("doorway", "circulation_opening", "stair_opening", "glazing", "accidental_gap")}
    check("Every source wall interruption has an allowed classification",
          bool(opening_schedule) and sum(counts.values()) == len(opening_schedule), counts)
    check("Opening audit records zero accidental gaps", counts["accidental_gap"] == 0, counts)
    opening_blockers = {}
    for item in opening_schedule:
        if item["classification"] in {"doorway", "circulation_opening"} and item.get("sample_world_xy_m"):
            opening_blockers[item["name"]] = blocker_at(structure, *item["sample_world_xy_m"], radius=.05)
    check("Every intentional doorway and circulation opening is physically clear",
          bool(opening_blockers) and all(not value for value in opening_blockers.values()), opening_blockers)

    live = inspect_live_1f_stair()
    opening = bpy.data.objects.get("B1_Opening_Stair_From1F")
    if opening:
        ob = [opening.location.x - abs(opening.scale.x), opening.location.y - abs(opening.scale.y),
              opening.location.x + abs(opening.scale.x), opening.location.y + abs(opening.scale.y)]
    else:
        ob = []
    live_bounds = live.get("bounds_xyxy_m", [])
    alignment = json.loads(scene.get("stair_alignment_json", "{}"))
    recorded_stair = alignment.get("physical_stair_bounds_xyxy_m", [])
    stair_error = max((abs(a - b) for a, b in zip(recorded_stair, live_bounds)), default=999.0)
    expected_stair_error = max((abs(a - b) for a, b in zip(recorded_stair, EXPECTED_STAIR)), default=999.0)
    opening_error = max((abs(a - b) for a, b in zip(ob, EXPECTED_SLAB_OPENING)), default=999.0)
    live_section = live.get("slab_top_cross_section_xyxy_m", [])
    live_opening_error = max((abs(a - b) for a, b in zip(ob, live_section)), default=999.0)
    check("B1 records the exact live 1F physical stair XY bounds",
          len(recorded_stair) == 4 and stair_error < 1e-6 and expected_stair_error < 1e-6,
          {"B1_physical_stair_xyxy_m": recorded_stair, "live_1F_stair_xyxy_m": live_bounds,
           "maximum_xy_error_m": stair_error})
    check("B1 slab opening is limited to the 1F stair/slab collision footprint",
          len(ob) == 4 and len(live_section) == 4 and opening_error < 1e-6 and live_opening_error < 1e-6,
          {"B1_slab_opening_xyxy_m": ob, "expected_collision_footprint_xyxy_m": EXPECTED_SLAB_OPENING,
           "live_1F_mesh_cross_section_at_B1_slab_top_xyxy_m": live_section,
           "maximum_xy_error_m": max(opening_error, live_opening_error)})
    connection = bpy.data.objects.get("B1_Connection_1F")
    connection_local = list(connection.location) if connection else []
    connection_error = max((abs(a - b) for a, b in zip(connection_local, EXPECTED_CONNECTION)), default=999.0)
    connection_props = {k: connection.get(k) for k in ("upper_landing_end", "lower_landing_end", "travel_direction", "exit_direction")} if connection else {}
    check("B1 arrival threshold is centered on the exact south edge of the live 1F lower landing",
          connection_error < 1e-6 and abs(live.get("terminal_elevation_m", 999) + 3.2) < 1e-7,
          {"B1_local_xyz_m": connection_local, "expected_local_xyz_m": EXPECTED_CONNECTION,
           "maximum_error_m": connection_error, "assembly_z_offset_m": -3.2})
    check("B1 stair direction and landing ends match both floor-plan arrows",
          connection_props == {"upper_landing_end": EXPECTED_UPPER_LANDING_END,
                               "lower_landing_end": EXPECTED_LOWER_LANDING_END,
                               "travel_direction": EXPECTED_B1_TRAVEL,
                               "exit_direction": EXPECTED_B1_EXIT}
          and abs(live.get("north_end_top_z_m", -999)) < 1e-6
          and abs(live.get("south_end_top_z_m", 999) + 3.2) < 1e-6,
          {**connection_props, "live_north_top_z_m": live.get("north_end_top_z_m"),
           "live_south_top_z_m": live.get("south_end_top_z_m")})
    if len(ob) == 4:
        samples = [(ob[0] + (ob[2] - ob[0]) * u, ob[1] + (ob[3] - ob[1]) * v)
                   for u in (.15, .5, .85) for v in (.10, .35, .65, .9)]
        covered = [(obj.name, x, y) for obj in floors for x, y in samples if has_floor_at([obj], x, y)]
    else:
        samples, covered = [], [("missing opening", 0, 0)]
    check("No B1 slab covers the aligned stair aperture", not covered, covered)
    upper_flight_sample = ((EXPECTED_STAIR[0] + EXPECTED_STAIR[2]) / 2,
                           (EXPECTED_SLAB_OPENING[3] + EXPECTED_STAIR[3]) / 2)
    check("B1 slab remains beneath the non-colliding upper stair flight",
          has_floor_at(floors, *upper_flight_sample), upper_flight_sample)
    landing_clearance_samples = [(EXPECTED_CONNECTION[0], EXPECTED_CONNECTION[1] - dy) for dy in (.10, .35, .60)]
    landing_blockers = {str(dy): blocker_at(structure, x, y, radius=.08) for dy, (x, y) in zip((.10, .35, .60), landing_clearance_samples)}
    landing_floor = {str(dy): has_floor_at(floors, x, y) for dy, (x, y) in zip((.10, .35, .60), landing_clearance_samples)}
    check("B1 lower landing has clear supported initial -Y exit circulation",
          all(not value for value in landing_blockers.values()) and all(landing_floor.values()),
          {"blockers": landing_blockers, "floor_support": landing_floor, "samples_world_xy_m": landing_clearance_samples})
    east_wall = bpy.data.objects.get("B1_Wall_Stair_002_From1F_East")
    east_bounds = xyxy(east_wall) if east_wall else []
    check("Both B1 stair side walls enclose the full aligned flight",
          bool(east_wall) and abs(east_bounds[1] - EXPECTED_STAIR[1]) < 1e-6 and abs(east_bounds[3] - EXPECTED_STAIR[3]) < 1e-6,
          east_bounds)
    check("Obsolete south stair glazing from the incorrect 1F landing assumption is absent",
          bpy.data.objects.get("B1_Glass_011_StairSouth") is None)

    room_samples = json.loads(scene.get("room_samples_json", "{}"))
    room_samples = {name: tuple(point) for name, point in room_samples.items()}
    accessibility, access_detail = validate_accessibility(floors, structure, room_samples) if floors and room_samples else ({}, {"error": "missing floors or samples"})
    check("Every enclosed room reaches the main lounge with 0.40 m UAV clearance",
          bool(accessibility) and all(accessibility.values()), {"rooms": accessibility, **access_detail})

    junction_schedule = json.loads(scene.get("junction_schedule_json", "[]"))
    junction_gaps = {}
    missing_junctions = []
    for item in junction_schedule:
        a, b = bpy.data.objects.get(item["a"]), bpy.data.objects.get(item["b"])
        if not a or not b:
            missing_junctions.append(item)
        else:
            junction_gaps[item["name"]] = {"type": item["type"], "gap_m": bbox_gap_xy(a, b)}
    check("All audited wall-to-wall, wall-to-column, and wall-to-glass junction objects exist", not missing_junctions and bool(junction_schedule), missing_junctions)
    check("Audited junctions contain no tiny cracks",
          bool(junction_gaps) and max((item["gap_m"] for item in junction_gaps.values()), default=999) <= .002,
          junction_gaps)

    overlaps = []
    for index, a in enumerate(structure):
        for b in structure[index + 1:]:
            ov = positive_overlap_xyz(a, b)
            area = actual_positive_xy_overlap(a, b)
            if area > 1e-8 and ov[2] > 1e-6:
                overlaps.append({"objects": [a.name, b.name], "overlap_area_m2": area,
                                 "z_overlap_m": ov[2]})
    check("No overlapping structural or glazing volumes", not overlaps, overlaps)
    floor_overlaps = []
    for index, a in enumerate(floors):
        for b in floors[index + 1:]:
            area = actual_positive_xy_overlap(a, b)
            z_overlap = positive_overlap_xyz(a, b)[2]
            if area > 1e-8 and z_overlap > 1e-6:
                floor_overlaps.append({"objects": [a.name, b.name], "overlap_area_m2": area,
                                       "z_overlap_m": z_overlap})
    check("Main floor and courtyard slab have no coplanar overlap", not floor_overlaps, floor_overlaps)
    manifold = {obj.name: manifold_and_volume(obj) for obj in meshes}
    bad_manifold = {name: data for name, data in manifold.items() if data[0] or data[1] or data[2] <= 1e-8}
    check("All architectural meshes are closed with positive signed volume", not bad_manifold, bad_manifold)
    fragments = {obj.name: mesh_components(obj) for obj in walls if mesh_components(obj) != 1}
    check("No wall object contains disconnected fragments", not fragments, fragments)
    signatures = {}
    duplicates = []
    for obj in meshes:
        signature = tuple(sorted(tuple(round(value, 5) for value in (obj.matrix_world @ vertex.co)) for vertex in obj.data.vertices))
        if signature in signatures:
            duplicates.append([signatures[signature], obj.name])
        else:
            signatures[signature] = obj.name
    check("No duplicate complete architectural meshes", not duplicates, duplicates)
    floating = []
    for obj in structure:
        low, high = bounds(obj)
        center = ((low[0] + high[0]) / 2, (low[1] + high[1]) / 2)
        support = has_floor_at(floors, *center)
        if not support:
            # Long segments may bridge a stair/courtyard void; check four inset points too.
            candidates = [
                (low[0] * .9 + high[0] * .1, low[1] * .9 + high[1] * .1),
                (low[0] * .1 + high[0] * .9, low[1] * .9 + high[1] * .1),
                (low[0] * .9 + high[0] * .1, low[1] * .1 + high[1] * .9),
                (low[0] * .1 + high[0] * .9, low[1] * .1 + high[1] * .9),
            ]
            support = any(has_floor_at(floors, *point) for point in candidates)
        if not support:
            floating.append(obj.name)
    check("No wall, column, or glazing object is floating without slab support", not floating, floating)

    baseline = json.loads(scene.get("protected_floor_hashes_json", "{}"))
    current = {path.relative_to(ROOT).as_posix(): sha256(path) for path in OTHER_FLOORS if path.exists()}
    check("1F, 2F, and 3F shell blends remain byte-identical to pre-build hashes", bool(baseline) and baseline == current,
          {"baseline": baseline, "current": current})

    triangles = sum(len(loop_tri.vertices) for obj in [] for loop_tri in obj.data.loop_triangles)
    for obj in meshes:
        obj.data.calc_loop_triangles()
    triangle_count = sum(len(obj.data.loop_triangles) for obj in meshes)
    failed = [item for item in checks if not item["pass"]]
    report = {
        "summary": {"passed": len(checks) - len(failed), "failed": len(failed), "total": len(checks)},
        "checks": checks,
        "stats": {
            "object_count_total": len(scene.objects),
            "architectural_mesh_count": len(meshes),
            "mesh_datablock_count": len({obj.data.name for obj in meshes}),
            "triangle_count": triangle_count,
            "xy_bounds_m": [scene_bounds[0][0], scene_bounds[0][1], scene_bounds[1][0], scene_bounds[1][1]],
            "z_bounds_m": [scene_bounds[0][2], scene_bounds[1][2]],
            "intentional_openings": counts["doorway"] + counts["circulation_opening"] + counts["stair_opening"] + counts["glazing"],
            "opening_counts": counts,
            "accidental_gaps": counts["accidental_gap"],
        },
        "stair_alignment": {
            "B1_slab_opening_xyxy_m": ob,
            "live_1F_stair_xyxy_m": live_bounds,
            "maximum_xy_error_m": stair_error,
            "B1_arrival_local_xyz_m": connection_local,
            "upper_1F_landing": EXPECTED_UPPER_LANDING_END,
            "lower_B1_landing": EXPECTED_LOWER_LANDING_END,
            "B1_travel_direction": EXPECTED_B1_TRAVEL,
            "B1_exit_direction": EXPECTED_B1_EXIT,
            "assembly_result": "B1 local Z=0 meets 1F stair terminal Z=-3.2 when B1 is assembled at world Z=-3.2",
            "physical_stair_owner": "1F_shell.blend",
            "duplicate_B1_stair_count": len(stairs),
        },
        "source_ambiguities": json.loads(scene.get("source_ambiguities_json", "[]")),
    }
    REPORT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["summary"], sort_keys=True))
    for item in failed:
        print("FAIL:", item["name"], item["detail"])
    return report


if __name__ == "__main__":
    result = run()
    if result["summary"]["failed"]:
        raise SystemExit(1)
