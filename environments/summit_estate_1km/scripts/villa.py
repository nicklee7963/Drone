"""Detailed, drone-accessible contemporary estate villa.

All dimensions are metres in the shared world coordinate system. Glazing and
furniture collide; circulation is built with open doors and subtracted slabs.
"""
from __future__ import annotations

import math


def build_villa(scene, config):
    """Add the furnished villa and return semantic spaces and clear flight paths."""
    v = config["villa"]
    x0, x1, y0, y1 = v["bounds"]
    base, main, upper, roof = (v[k] for k in ("basement_z", "main_z", "upper_z", "roof_z"))
    m = scene.model("summit_villa")
    rooms, portals, routes = [], [], []
    scene.materials.update({
        "villa_rug": {"color": [.29, .32, .31, 1], "roughness": .97, "metalness": 0},
        "villa_cream": {"color": [.83, .79, .69, 1], "roughness": .91, "metalness": 0},
        "villa_book_red": {"color": [.28, .085, .065, 1], "roughness": .8, "metalness": 0},
        "villa_book_blue": {"color": [.08, .17, .23, 1], "roughness": .8, "metalness": 0},
        "villa_bronze": {"color": [.24, .16, .075, 1], "roughness": .32, "metalness": .75},
        "villa_cinema": {"color": [.045, .055, .067, 1], "roughness": .96, "metalness": 0},
    })

    def box(name, center, size, material="ivory", collision=True, yaw=0):
        m.box(name, center=center, size=size, material=material, collision=collision, yaw=yaw)

    def rect(name, bounds, z, thickness=.3, material="ivory", collision=True):
        a, b, c, d = bounds
        box(name, ((a+b)/2, (c+d)/2, z-thickness/2), (b-a, d-c, thickness), material, collision)

    def room(name, level, bounds, function, **extra):
        floor = {"basement": base, "main": main, "upper": upper}[level]
        ceiling = {"basement": main-.34, "main": upper-.34, "upper": roof-.34}[level]
        rooms.append(dict(name=name, level=level, bounds=[*bounds, floor, ceiling], function=function, **extra))

    def portal(name, center, width, height, normal):
        portals.append(dict(name=name, center=list(center), width=width, height=height, normal=list(normal)))

    def route(name, points):
        routes.append(dict(name=name, clearance_radius=.45, waypoints=[list(p) for p in points]))

    def slab_with_holes(name, z, holes, bounds=None, material="ivory"):
        # Disjoint rectangles tile the solid region. No hidden full-size collider.
        pieces = [bounds or [x0, x1, y0, y1]]
        for ha, hb, hc, hd in holes:
            next_pieces = []
            for a, b, c, d in pieces:
                ia, ib, ic, id_ = max(a, ha), min(b, hb), max(c, hc), min(d, hd)
                if ia >= ib or ic >= id_:
                    next_pieces.append([a, b, c, d])
                    continue
                if a < ia: next_pieces.append([a, ia, c, d])
                if ib < b: next_pieces.append([ib, b, c, d])
                if c < ic: next_pieces.append([ia, ib, c, ic])
                if id_ < d: next_pieces.append([ia, ib, id_, d])
            pieces = next_pieces
        for i, bounds_ in enumerate(pieces):
            rect(f"{name}_{i:02d}", bounds_, z, .34, material)

    def wall_y(name, y, a, b, floor, ceiling, doors=(), material="plaster", thick=.22):
        cursor = a
        for center, width, height in sorted(doors):
            lo, hi = center-width/2, center+width/2
            if lo > cursor:
                box(f"{name}_{cursor:g}", ((cursor+lo)/2, y, (floor+ceiling)/2),
                    (lo-cursor, thick, ceiling-floor), material)
            if floor+height < ceiling:
                box(f"{name}_lintel_{center:g}", (center, y, (floor+height+ceiling)/2),
                    (width, thick, ceiling-floor-height), material)
            cursor = hi
        if cursor < b:
            box(f"{name}_{cursor:g}", ((cursor+b)/2, y, (floor+ceiling)/2),
                (b-cursor, thick, ceiling-floor), material)

    def wall_x(name, x, a, b, floor, ceiling, doors=(), material="plaster", thick=.22):
        cursor = a
        for center, width, height in sorted(doors):
            lo, hi = center-width/2, center+width/2
            if lo > cursor:
                box(f"{name}_{cursor:g}", (x, (cursor+lo)/2, (floor+ceiling)/2),
                    (thick, lo-cursor, ceiling-floor), material)
            if floor+height < ceiling:
                box(f"{name}_lintel_{center:g}", (x, center, (floor+height+ceiling)/2),
                    (thick, width, ceiling-floor-height), material)
            cursor = hi
        if cursor < b:
            box(f"{name}_{cursor:g}", (x, (cursor+b)/2, (floor+ceiling)/2),
                (thick, b-cursor, ceiling-floor), material)

    def glazing_y(name, y, a, b, floor, ceiling):
        count = max(1, math.ceil((b-a)/6))
        pitch = (b-a)/count
        for i in range(count):
            x = a+(i+.5)*pitch
            box(f"{name}_pane_{i}", (x, y, (floor+ceiling)/2), (pitch-.11, .075, ceiling-floor), "glass")
        for i in range(count+1):
            box(f"{name}_mullion_{i}", (a+i*pitch, y, (floor+ceiling)/2), (.115, .19, ceiling-floor), "charcoal")
        for z in (floor, ceiling):
            box(f"{name}_transom_{z:g}", ((a+b)/2, y, z), (b-a, .2, .13), "charcoal")

    def glazing_x(name, x, a, b, floor, ceiling):
        count = max(1, math.ceil((b-a)/5))
        pitch = (b-a)/count
        for i in range(count):
            y = a+(i+.5)*pitch
            box(f"{name}_pane_{i}", (x, y, (floor+ceiling)/2), (.075, pitch-.11, ceiling-floor), "glass")
        for i in range(count+1):
            box(f"{name}_mullion_{i}", (x, a+i*pitch, (floor+ceiling)/2), (.19, .115, ceiling-floor), "charcoal")
        for z in (floor, ceiling):
            box(f"{name}_transom_{z:g}", (x, (a+b)/2, z), (.2, b-a, .13), "charcoal")

    def furniture_box(name, origin, offset, size, material, yaw=0, collision=True):
        co, si = math.cos(yaw), math.sin(yaw)
        dx, dy, dz = offset
        center = (origin[0]+dx*co-dy*si, origin[1]+dx*si+dy*co, origin[2]+dz)
        box(name, center, size, material, collision, yaw)

    def sofa(name, x, y, f, width=4.8, yaw=0, material="villa_cream"):
        p = (x, y, f)
        furniture_box(name+"_base", p, (0, 0, .36), (width, 1.65, .46), "wood", yaw)
        furniture_box(name+"_back", p, (0, .72, .96), (width, .32, 1.15), material, yaw)
        for i in range(3):
            furniture_box(name+f"_cushion_{i}", p, ((i-1)*(width-.5)/3, -.08, .67),
                          ((width-.65)/3, 1.35, .24), material, yaw)
        for dx in (-width/2+.15, width/2-.15):
            furniture_box(name+f"_arm_{dx:g}", p, (dx, 0, .75), (.3, 1.7, .8), material, yaw)
            for dy in (-.55, .55):
                furniture_box(name+f"_foot_{dx:g}_{dy:g}", p, (dx, dy, .10), (.12, .12, .2), "brass", yaw)

    def chair(name, x, y, f, yaw=0, material="villa_cream"):
        p = (x, y, f)
        furniture_box(name+"_seat", p, (0, 0, .53), (.76, .76, .18), material, yaw)
        furniture_box(name+"_back", p, (0, .34, 1.02), (.76, .15, .95), material, yaw)
        for dx in (-.27, .27):
            for dy in (-.27, .27):
                furniture_box(name+f"_leg_{dx:g}_{dy:g}", p, (dx, dy, .24), (.075, .075, .48), "wood", yaw)

    def table(name, x, y, f, size=(5, 2.4), height=.82, material="wood"):
        dx, dy = size
        box(name+"_top", (x, y, f+height-.08), (dx, dy, .16), material)
        for sx in (-1, 1):
            for sy in (-1, 1):
                box(name+f"_leg_{sx}_{sy}", (x+sx*(dx/2-.4), y+sy*(dy/2-.4), f+(height-.16)/2),
                    (.13, .13, height-.16), "villa_bronze")

    def planter(name, x, y, f, radius=.65, height=1.0):
        m.cylinder(name+"_pot", (x, y, f+height/2), radius, height, "charcoal", segments=12)
        m.cylinder(name+"_stem", (x, y, f+height+1), .1, 2, "trunk", segments=8)
        for i, (dx, dy, dz) in enumerate(((-.4, 0, 1.9), (.4, .15, 2.15), (0, -.3, 2.55))):
            m.sphere(name+f"_foliage_{i}", (x+dx, y+dy, f+dz), (.7, .7, .85), "leaf1", False)

    def bookshelf(name, x, y, f, width=6, depth=.7, height=3.8):
        box(name+"_back", (x, y+.25, f+height/2), (width, .12, height), "wood")
        for side in (-1, 1):
            box(name+f"_side_{side}", (x+side*(width/2-.08), y, f+height/2), (.16, depth, height), "wood")
        for tier in range(5):
            z = f+.18+tier*.84
            box(name+f"_shelf_{tier}", (x, y, z), (width, depth, .12), "wood")
            if tier == 4: continue
            for book in range(14):
                bx = x-width/2+.32+book*(width-.65)/14
                h = .40+.06*((book+tier)%4)
                mat = ("villa_book_red", "villa_book_blue", "villa_cream", "wood")[(book+2*tier)%4]
                box(name+f"_book_{tier}_{book}", (bx, y-.1, z+.08+h/2), (.20, .36, h), mat, False)

    # Floors and the connected stair/atrium voids.
    atrium = [72, 84, 133, 149]
    stairwell = [81, 85, 118, 133]
    rect("basement_slab", [x0, x1, y0, y1], base, .4, "stone")
    slab_with_holes("main_slab", main, [atrium, stairwell])
    slab_with_holes("upper_slab", upper, [atrium, stairwell])
    slab_with_holes("roof_slab", roof, [atrium])
    # Broad white overhangs articulate the three projecting front volumes.
    rect("west_lower_balcony", [27, 70, 111, 115], main, .32)
    rect("east_lower_balcony", [87, 130, 111, 115], main, .32)
    rect("main_entry_threshold", [70, 87, 107, 115], main, .28, "stone")
    rect("west_upper_balcony", [28, 69, 110, 115], upper, .38)
    rect("east_upper_balcony", [87, 129, 110, 115], upper, .38)
    rect("west_roof_overhang", [27, 70, 109, 115], roof, .42)
    rect("east_roof_overhang", [86, 130, 109, 115], roof, .42)
    rect("west_roof_side_overhang", [27, 30, 115, 164], roof, .42)
    rect("east_roof_side_overhang", [126, 130, 115, 165], roof, .42)
    rect("east_pool_veranda", [126, 140, 131, 161], main, .28, "wood")
    for i in range(5):
        step_top = main-(i+1)*.04
        rect(f"veranda_step_{i}", [140+i*.55, 140+(i+1)*.55, 133, 159], step_top, .15, "stone")

    # Front entrance is ten metres wide, with 4.2 m clear height.
    for level, f, c in (("main", main+.16, upper-.4), ("upper", upper+.16, roof-.4)):
        if level == "main":
            glazing_y(level+"_front_west", y0, x0, 73, f, c)
            glazing_y(level+"_front_east", y0, 83, x1, f, c)
            box("entry_header", (78, y0, (main+4.2+upper-.34)/2), (10, .6, upper-.34-main-4.2), "charcoal")
        else:
            glazing_y(level+"_front_west", y0, x0, 70, f, c)
            glazing_y(level+"_front_center", y0+4, 70, 87, f, c)
            glazing_y(level+"_front_east", y0, 87, x1, f, c)
        glazing_y(level+"_rear", y1, x0, x1, f, c)
        glazing_x(level+"_west", x0, y0, y1, f, c)
        if level == "main":
            glazing_x(level+"_east_south", x1, y0, 136, f, c)
            glazing_x(level+"_east_north", x1, 144, y1, f, c)
            box("pool_door_header", (x1, 140, (main+4.2+upper-.34)/2), (.5, 8, upper-.34-main-4.2), "charcoal")
        else:
            glazing_x(level+"_east", x1, y0, y1, f, c)
    portal("main_entry", (78, y0, main+2.1), 10, 4.2, (0, -1, 0))
    portal("main_pool_access", (x1, 140, main+2.1), 8, 4.2, (1, 0, 0))
    # Full-height dark piers and ivory blades give depth to the glass facade.
    for i, x in enumerate((30, 50, 70, 86, 107, 126)):
        box(f"facade_pier_{i}", (x, 114.7, (main+roof)/2), (.58, .7, roof-main), "charcoal")
    for i, x in enumerate((32, 68, 89, 124)):
        box(f"ivory_blade_{i}", (x, 118, roof+1.1), (1.2, 3, 2.2), "ivory")
        box(f"ivory_blade_cap_{i}", (x, 118, roof+2.26), (1.35, 3.2, .18), "charcoal")
    box("entry_canopy", (78, 111, main+4.7), (17, 8, .36), "charcoal")
    box("entry_canopy_recess", (78, 111, main+4.50), (15.8, 7, .045), "wood", False)
    m.text("villa_name", "SUMMIT ESTATE", (71.0, 106.93, main+4.53), .69, "brass")
    for x in (69, 88):
        planter(f"entry_planter_{x}", x, 109, main, .8, 1.1)
    # Upper balconies have transparent guarding with solid black cap rails.
    for label, a, b in (("west", 28, 69), ("east", 87, 129)):
        glazing_y(label+"_balcony_guard", 110, a, b, upper+.1, upper+1.15)
        sofa(label+"_balcony_sofa", (a+b)/2, 112.7, upper, width=6)
        table(label+"_balcony_table", (a+b)/2, 110.9, upper, (3, .9), .42, "stone")

    # West walkout and sunken garden. Other basement sides are retaining walls.
    wall_y("basement_south_retaining", y0, x0, x1, base, main-.34, material="stone", thick=.45)
    wall_y("basement_north_retaining", y1, x0, x1, base, main-.34, material="stone", thick=.45)
    wall_x("basement_east_retaining", x1, y0, y1, base, main-.34, material="stone", thick=.45)
    glazing_x("basement_west_south", x0, y0, 136, base+.2, main-.4)
    glazing_x("basement_west_north", x0, 144, y1, base+.2, main-.4)
    box("walkout_lintel", (x0, 140, (base+4.2+main-.34)/2), (.5, 8, main-.34-base-4.2), "charcoal")
    portal("basement_walkout", (x0, 140, base+2), 8, 4.2, (-1, 0, 0))
    rect("sunken_garden_floor", [8, 30, 125, 153], base, .32, "paving")
    for y in (125, 153):
        box(f"sunken_garden_retaining_{y}", (19, y, (74.4+80)/2), (22, .45, 5.6), "stone")
        box(f"sunken_garden_cap_{y}", (19, y, 80), (22, .65, .2), "ivory")
    sofa("sunken_garden_sofa", 23, 150, base, 5)
    table("sunken_garden_table", 23, 147.5, base, (3, 1.4), .45, "stone")
    planter("sunken_garden_tree_south", 25, 128, base, .75)

    # Stairs sit south of the east/west hall. Both stairs use the same real hole.
    for label, f, target in (("basement_to_main", base, main), ("main_to_upper", main, upper)):
        count = 28
        rise, run = (target-f)/count, 15/count
        for i in range(count):
            box(f"stair_{label}_tread_{i:02d}", (83, 118+(i+.5)*run, f+(i+1)*rise-.09),
                (3.3, run+.025, .18), "wood")
        for x in (81.5, 84.5):
            m.beam(f"stair_{label}_stringer_{x:g}", (x, 118, f-.1), (x, 133, target-.1), .22, "charcoal")
            m.beam(f"stair_{label}_rail_{x:g}", (x, 118, f+1.05), (x, 133, target+1.05), .065, "brass")
            for i in range(0, count, 4):
                box(f"stair_{label}_baluster_{x:g}_{i}", (x, 118+(i+.5)*run, f+(i+1)*rise+.48),
                    (.05, .05, 1), "metal")
    # Guarding is below the flight altitude and surrounds the physical slab void.
    for level, f in (("main", main), ("upper", upper)):
        for x in (72, 84):
            glazing_x(f"{level}_atrium_guard_{x}", x, 133, 149, f+.08, f+1.1)
        glazing_y(level+"_atrium_north_guard", 149, 72, 84, f+.08, f+1.1)
        glazing_y(level+"_atrium_south_guard", 133, 72, 81, f+.08, f+1.1)
    # Raised lantern keeps the central volume light and visually distinct.
    glazing_y("atrium_lantern_south", 133, 72, 84, roof, roof+2.5)
    glazing_y("atrium_lantern_north", 149, 72, 84, roof, roof+2.5)
    glazing_x("atrium_lantern_west", 72, 133, 149, roof, roof+2.5)
    glazing_x("atrium_lantern_east", 84, 133, 149, roof, roof+2.5)
    rect("atrium_skylight", [72, 84, 133, 149], roof+2.6, .12, "glass")
    for x in (72, 78, 84):
        box(f"skylight_rafter_{x}", (x, 141, roof+2.58), (.12, 16, .22), "charcoal")

    # Main level: spacious living / dining / kitchen flank a broad central hall.
    room("main_living", "main", [31, 69, 116, 135], "living")
    room("main_dining", "main", [89, 125, 116, 135], "dining")
    room("main_kitchen", "main", [89, 125, 145, 162], "kitchen")
    room("main_lake_lounge", "main", [31, 69, 145, 162], "lounge")
    room("main_entry_hall", "main", [70, 89, 115.2, 133], "circulation")
    room("main_gallery", "main", [31, 125, 135, 145], "circulation")
    room("central_atrium", "main", [72, 84, 133, 149], "atrium", open_to_basement=True, open_to_upper=True)
    rect("living_rug", [38, 59, 119, 133], main+.022, .025, "villa_rug", False)
    sofa("living_north_sofa", 48.5, 131, main, 8.5)
    sofa("living_west_sofa", 39.5, 125.7, main, 6, math.pi/2)
    sofa("living_east_sofa", 57.5, 125.7, main, 6, -math.pi/2)
    table("living_coffee", 48.5, 125.5, main, (5.8, 2.8), .43, "stone")
    box("living_fireplace_chimney", (63.5, 120.1, main+2.35), (3.2, 1.25, 4.7), "stone")
    box("living_fireplace_recess", (63.5, 119.42, main+.95), (2.6, .13, 1.25), "charcoal")
    box("living_fireplace_glow", (63.5, 119.33, main+.63), (2.3, .08, .18), "fire", False)
    for x, y in ((34, 118), (65, 131), (33, 159)):
        planter(f"main_tree_{x}_{y}", x, y, main)
    table("dining_table", 106, 125, main, (12, 3.2), .86)
    for i in range(6):
        for side in (-1, 1):
            chair(f"dining_chair_{i}_{side}", 101+i*2, 125+side*2.3, main,
                  0 if side == 1 else math.pi)
    chair("dining_head_west", 99, 125, main, -math.pi/2)
    chair("dining_head_east", 113, 125, main, math.pi/2)
    box("dining_sideboard", (119, 120, main+.62), (7, 1.05, 1.24), "wood")
    for x in (101, 106, 111):
        m.cylinder(f"dining_pendant_wire_{x}", (x, 125, upper-.85), .025, 1, "metal", False, 8)
        m.sphere(f"dining_pendant_{x}", (x, 125, upper-1.48), (.65, .65, .24), "brass", False)
        m.sphere(f"dining_pendant_glow_{x}", (x, 125, upper-1.57), (.55, .55, .13), "emissive", False)
    box("kitchen_back_cabinet", (107, 161, main+.65), (28, 1.3, 1.3), "wood")
    box("kitchen_back_counter", (107, 160.9, main+1.36), (28.2, 1.5, .16), "stone")
    box("kitchen_back_splash", (107, 161.55, main+2), (28, .12, 1.15), "stone")
    for i in range(14):
        box(f"kitchen_lower_door_{i}", (94+i*2, 160.3, main+.69), (1.93, .075, 1.12), "wood")
        box(f"kitchen_door_pull_{i}", (94+i*2, 160.22, main+1.12), (.75, .06, .06), "brass", False)
    box("kitchen_island_base", (107, 152.5, main+.65), (11, 3.1, 1.3), "wood")
    box("kitchen_island_counter", (107, 152.5, main+1.4), (11.6, 3.7, .22), "stone")
    box("kitchen_sink", (110, 152.5, main+1.53), (1.5, .95, .04), "metal", False)
    m.beam("kitchen_faucet", (110, 153, main+1.5), (110, 153, main+2), .08, "metal", False)
    m.beam("kitchen_faucet_spout", (110, 153, main+2), (110, 152.6, main+2), .08, "metal", False)
    box("kitchen_induction", (104, 152.5, main+1.53), (2.1, 1.2, .04), "charcoal", False)
    for x in (103.5, 104.5):
        for y in (152.2, 152.8):
            m.cylinder(f"kitchen_hob_{x}_{y}", (x, y, main+1.56), .22, .02, "metal", False, 16)
    for x in (92, 121):
        box(f"kitchen_tall_cabinet_{x}", (x, 160.5, main+1.8), (3.1, 1.8, 3.6), "wood")
        box(f"kitchen_appliance_{x}", (x, 159.54, main+1.9), (2.5, .12, 2.8), "metal")
        box(f"kitchen_appliance_panel_{x}", (x, 159.46, main+2.45), (2.2, .04, .3), "charcoal", False)
    for i in range(5):
        chair(f"kitchen_stool_{i}", 103+i*2, 149.6, main, math.pi)
    sofa("lake_lounge_sofa", 48, 158, main, 8)
    sofa("lake_lounge_side", 38, 154, main, 5.5, math.pi/2)
    table("lake_lounge_coffee", 48, 154, main, (5, 2.5), .45, "stone")
    bookshelf("main_display_bookshelf", 61, 161.7, main, 9, .8, 3.8)
    table("main_console", 67, 151.5, main, (2.6, 1.2), .92)

    # Four complete upper suites. Each has an open 3.2 m hall door and ensuite.
    upper_door_height = 3.8
    wall_y("upper_front_suite_partition", 134, x0, 70, upper, roof-.34,
           ((53, 3.2, upper_door_height),))
    wall_y("upper_front_east_partition", 134, 88, x1, upper, roof-.34,
           ((105, 3.2, upper_door_height),))
    wall_y("upper_rear_suite_partition", 148, x0, 70, upper, roof-.34,
           ((53, 3.2, upper_door_height),))
    wall_y("upper_rear_east_partition", 148, 88, x1, upper, roof-.34,
           ((105, 3.2, upper_door_height),))
    for name, bounds, door_x, door_y, north in (
            ("bedroom_1", [30.3, 69.8, 115.3, 133.8], 53, 134, False),
            ("bedroom_2", [88.2, 125.7, 115.3, 133.8], 105, 134, False),
            ("bedroom_3", [30.3, 69.8, 148.2, 162.7], 53, 148, True),
            ("bedroom_4", [88.2, 125.7, 148.2, 162.7], 105, 148, True)):
        a, b, c, d = bounds
        room(name, "upper", bounds, "bedroom", ensuite=name+"_bathroom", door_width=3.2)
        portal(name+"_door", (door_x, door_y, upper+1.9), 3.2, 3.8, (0, -1 if north else 1, 0))
        bath_a, bath_b = b-9.4, b
        bath_c, bath_d = (d-8.8, d) if north else (c, c+9.0)
        room(name+"_bathroom", "upper", [bath_a, bath_b, bath_c, bath_d], "bathroom")
        bath_entry_y = (bath_c+bath_d)/2
        wall_x(name+"_bath_wall", bath_a, bath_c, bath_d, upper, roof-.34,
               ((bath_entry_y, 2.4, 3.3),))
        wall_y(name+"_bath_inner", bath_c if north else bath_d, bath_a, bath_b, upper, roof-.34)
        portal(name+"_ensuite", (bath_a, bath_entry_y, upper+1.7), 2.4, 3.3, (-1, 0, 0))
        bx, by = a+12, (c+d)/2
        rect(name+"_rug", [bx-5.5, bx+5.5, by-4.5, by+4.5], upper+.024, .025, "villa_rug", False)
        box(name+"_bed_frame", (bx, by, upper+.33), (3.1, 3.7, .5), "wood")
        box(name+"_bed_mattress", (bx, by-.05, upper+.7), (3, 3.5, .36), "villa_cream")
        box(name+"_bed_duvet", (bx, by-.55, upper+.91), (3.08, 2.35, .15), "white")
        box(name+"_bed_throw", (bx, by-1.35, upper+1), (3.08, .72, .06), "villa_rug", False)
        box(name+"_bed_headboard", (bx, by+1.9, upper+1.08), (6.2, .25, 2.16), "wood")
        for side in (-1, 1):
            box(name+f"_bed_pillow_{side}", (bx+side*.78, by+1.05, upper+.98), (1.15, .65, .22), "white")
            box(name+f"_nightstand_{side}", (bx+side*2.2, by+1.25, upper+.39), (1, 1, .78), "wood")
            m.cylinder(name+f"_lamp_stem_{side}", (bx+side*2.2, by+1.25, upper+1.1), .045, .7, "brass", False, 8)
            m.cylinder(name+f"_lamp_shade_{side}", (bx+side*2.2, by+1.25, upper+1.52), .3, .35, "villa_cream", False)
        sofa(name+"_lounge", a+23.5, by+1, upper, 4, -math.pi/2)
        table(name+"_lounge_table", a+21.1, by+1, upper, (1.6, 1.8), .45, "stone")
        # Wardrobes stay against outer side walls, away from the suite doorway.
        box(name+"_wardrobe", (a+1.1, by, upper+1.8), (1.5, 7, 3.6), "wood")
        for i in range(5):
            box(name+f"_wardrobe_panel_{i}", (a+1.88, by-2.8+i*1.4, upper+1.8), (.07, 1.33, 3.45), "wood")
        # Freestanding bathtub, glazed shower, double vanity and toilet.
        tx, ty = bath_b-3.2, bath_d-2.2
        box(name+"_bath_tub_base", (tx, ty, upper+.3), (3.5, 1.8, .6), "white")
        box(name+"_bath_tub_inset", (tx, ty, upper+.64), (2.9, 1.28, .08), "charcoal", False)
        for sy in (-1, 1):
            box(name+f"_bath_tub_rim_{sy}", (tx, ty+sy*.83, upper+.72), (3.55, .22, .24), "white")
        box(name+"_bath_vanity", (bath_b-1.1, bath_c+2.2, upper+.54), (1.3, 3.8, 1.08), "wood")
        box(name+"_bath_counter", (bath_b-1.1, bath_c+2.2, upper+1.12), (1.5, 4, .12), "stone")
        for i in range(2):
            m.cylinder(name+f"_basin_{i}", (bath_b-1.1, bath_c+1.2+i*1.9, upper+1.24), .44, .16, "white")
        box(name+"_bath_mirror", (bath_b-.34, bath_c+2.2, upper+2.2), (.04, 3.8, 1.55), "metal", False)
        rect(name+"_shower_pan", [bath_a+.4, bath_a+3.2, bath_c+.4, bath_c+3.2], upper+.1, .1, "stone")
        box(name+"_shower_glass", (bath_a+3.2, bath_c+1.8, upper+1.4), (.075, 2.8, 2.8), "glass")
        box(name+"_toilet_base", (bath_a+2, bath_d-1.5, upper+.3), (.75, 1.05, .6), "white")
        box(name+"_toilet_cistern", (bath_a+2, bath_d-1.05, upper+.65), (.8, .28, .95), "white")
    room("upper_gallery", "upper", [31, 125, 134.2, 147.8], "circulation")

    # Basement rooms flank a continuous, twelve-metre-wide center hall.
    wall_y("basement_front_west", 134, x0, 70, base, main-.34, ((52, 4, 3.8),))
    wall_y("basement_front_east", 134, 88, x1, base, main-.34, ((104, 4, 3.8),), "villa_cinema")
    wall_y("basement_rear_west", 146, x0, 70, base, main-.34, ((52, 4, 3.8),))
    wall_y("basement_rear_east", 146, 88, x1, base, main-.34, ((101, 3.6, 3.8), (119, 3, 3.8)))
    wall_x("basement_study_storage", 111, 146, y1, base, main-.34)
    room("basement_gym", "basement", [30.3, 69.8, 115.3, 133.8], "gym")
    room("basement_boxing", "basement", [30.3, 69.8, 146.2, 162.7], "boxing")
    room("basement_cinema", "basement", [88.2, 125.7, 115.3, 133.8], "cinema")
    room("basement_library", "basement", [88.2, 110.8, 146.2, 162.7], "study")
    room("basement_storage", "basement", [111.2, 125.7, 146.2, 162.7], "storage")
    room("basement_utility", "basement", [70.2, 87.8, 151, 162.7], "utility")
    room("basement_gallery", "basement", [30.3, 125.7, 134.2, 145.8], "circulation")
    for name, x, y, width in (("gym", 52, 134, 4), ("cinema", 104, 134, 4),
                              ("boxing", 52, 146, 4), ("study", 101, 146, 3.6), ("storage", 119, 146, 3)):
        portal(name+"_door", (x, y, base+1.9), width, 3.8, (0, 1 if y == 134 else -1, 0))
        m.text(name+"_sign", name.upper(), (x+width/2+.6, y-.15, base+2.4), .33, "brass")

    # Gym: four treadmills, bikes, rower, racks, bench presses and free weights.
    rect("gym_rubber_floor", [31, 69, 116, 133], base+.025, .03, "rubber", False)
    box("gym_mirror", (53, 115.48, base+2.25), (30, .045, 3.4), "metal", False)
    for i in range(4):
        x, y = 36+i*4.1, 120.2
        box(f"treadmill_{i}_base", (x, y, base+.22), (1.45, 3.3, .36), "charcoal")
        box(f"treadmill_{i}_belt", (x, y, base+.43), (1.03, 2.8, .05), "rubber", False)
        for sx in (-.64, .64):
            m.beam(f"treadmill_{i}_upright_{sx}", (x+sx, y+1.25, base+.25), (x+sx, y+.9, base+1.75), .11, "metal")
            m.beam(f"treadmill_{i}_rail_{sx}", (x+sx, y+.9, base+1.55), (x+sx, y-.15, base+1.55), .09, "charcoal")
        box(f"treadmill_{i}_console", (x, y+.85, base+1.83), (1.28, .45, .28), "charcoal")
        box(f"treadmill_{i}_screen", (x, y+.6, base+1.85), (.55, .025, .24), "screen", False)
    for i in range(3):
        x, y = 35.5+i*4.3, 129
        box(f"exercise_bike_{i}_base", (x, y, base+.1), (1.1, 2, .18), "charcoal")
        m.beam(f"exercise_bike_{i}_frame", (x, y-.5, base+.25), (x, y+.35, base+1.1), .19, "metal")
        box(f"exercise_bike_{i}_wheel", (x, y+.5, base+.6), (.38, .78, .78), "charcoal")
        m.beam(f"exercise_bike_{i}_seatpost", (x, y-.4, base+.3), (x, y-.4, base+1.25), .08, "metal")
        box(f"exercise_bike_{i}_seat", (x, y-.4, base+1.3), (.45, .55, .12), "rubber")
        m.beam(f"exercise_bike_{i}_handlepost", (x, y+.55, base+.7), (x, y+.8, base+1.5), .08, "metal")
        m.beam(f"exercise_bike_{i}_handlebar", (x-.45, y+.8, base+1.5), (x+.45, y+.8, base+1.5), .09, "charcoal")
    box("rowing_machine_rail", (58, 127, base+.3), (.26, 4.4, .23), "metal")
    box("rowing_machine_seat", (58, 126.5, base+.54), (.85, .7, .22), "rubber")
    box("rowing_machine_flywheel", (58, 128.65, base+.7), (.6, .9, 1.1), "charcoal")
    m.beam("rowing_machine_handle", (57.55, 128.05, base+1.05), (58.45, 128.05, base+1.05), .1, "metal")
    for i in range(2):
        x, y = 59+i*6.8, 120.2
        for sx in (-1.05, 1.05):
            box(f"weight_rack_{i}_upright_{sx}", (x+sx, y+.7, base+1.7), (.18, .18, 3.4), "metal")
            box(f"weight_rack_{i}_foot_{sx}", (x+sx, y, base+.1), (.45, 2.8, .2), "charcoal")
        m.beam(f"weight_rack_{i}_top", (x-1.05, y+.7, base+3.35), (x+1.05, y+.7, base+3.35), .15, "metal")
        box(f"bench_press_{i}_cushion", (x, y-.6, base+.75), (.75, 2.5, .23), "rubber")
        box(f"bench_press_{i}_support", (x, y-.6, base+.34), (.23, 2.2, .68), "metal")
        m.beam(f"bench_press_{i}_barbell", (x-1.7, y+.55, base+1.7), (x+1.7, y+.55, base+1.7), .065, "metal")
        for sx in (-1.4, 1.4):
            box(f"bench_press_{i}_plate_{sx}", (x+sx, y+.55, base+1.7), (.26, .8, .8), "rubber")
    for tier in range(2):
        box(f"dumbbell_rack_{tier}", (65, 130, base+.65+tier*.55), (6, .75, .12), "metal")
        for i in range(6):
            x = 62.6+i*.95
            m.beam(f"dumbbell_{tier}_{i}_grip", (x-.25, 130, base+.85+tier*.55), (x+.25, 130, base+.85+tier*.55), .07, "metal")
            for sx in (-.25, .25):
                box(f"dumbbell_{tier}_{i}_end_{sx}", (x+sx, 130, base+.85+tier*.55), (.17, .36, .36), "rubber")

    # Boxing ring has corner posts, four ropes, steps, and independent bags.
    box("boxing_ring_platform", (42, 155.2, base+.4), (11, 10.5, .8), "charcoal")
    box("boxing_ring_canvas", (42, 155.2, base+.83), (10.65, 10.15, .075), "villa_rug")
    corners = [(36.8, 150.2), (47.2, 150.2), (47.2, 160.2), (36.8, 160.2)]
    for i, (x, y) in enumerate(corners):
        box(f"boxing_ring_post_{i}", (x, y, base+1.58), (.3, .3, 2.2), "villa_book_red" if i%2 else "charcoal")
    for tier in range(4):
        for i, a in enumerate(corners):
            b = corners[(i+1)%4]
            m.beam(f"boxing_ring_rope_{tier}_{i}", (a[0], a[1], base+1.15+tier*.4),
                   (b[0], b[1], base+1.15+tier*.4), .07, "white" if tier%2 else "villa_book_red")
    for i in range(4):
        box(f"boxing_ring_step_{i}", (49.6-i*.55, 154, base+.1*(i+1)), (.55, 2.2, .2*(i+1)), "metal")
    for i in range(3):
        x, y = 57+i*4.5, 158
        m.cylinder(f"punch_bag_{i}", (x, y, base+2.15), .46, 2.35, "charcoal")
        box(f"punch_bag_{i}_stripe", (x, y-.47, base+2.1), (.32, .02, .65), "villa_book_red", False)
        m.beam(f"punch_bag_{i}_chain", (x, y, base+3.34), (x, y, main-.4), .05, "metal")
    sofa("boxing_bench", 62, 150.2, base, 6, math.pi, "dark_fabric")

    # Cinema has an actual front screen, tiered floor platforms, and 15 seats.
    rect("cinema_carpet", [88.5, 125.5, 115.5, 133.5], base+.03, .03, "villa_cinema", False)
    box("cinema_screen_frame", (106, 115.9, base+2.7), (14.8, .3, 4.05), "charcoal")
    box("cinema_screen", (106, 116.08, base+2.7), (14.2, .04, 3.65), "screen", False)
    # A subtle mountain silhouette is geometric visual artwork, not a blank panel.
    verts = [(99, 116.105, base+1), (113, 116.105, base+1), (113, 116.105, base+1.6),
             (109.6, 116.105, base+3.6), (106.8, 116.105, base+2.5),
             (104.5, 116.105, base+3.9), (101.6, 116.105, base+2.3), (99, 116.105, base+2.8)]
    m.mesh("cinema_screen_mountains", verts, [(0, i, i+1) for i in range(1, 7)], "villa_book_blue", False)
    for row_index in range(3):
        y = 120.5+row_index*3.6
        riser = row_index*.25
        if riser:
            rect(f"cinema_riser_{row_index}", [92, 122, y-1.3, y+1.4], base+riser, riser, "villa_cinema")
        for seat in range(5):
            x = 94+seat*5.7
            sofa(f"cinema_seat_{row_index}_{seat}", x, y, base+riser, 1.8, 0, "dark_fabric")
    for x in (91, 121):
        box(f"cinema_speaker_{x}", (x, 117.5, base+1.45), (.7, .65, 2.9), "charcoal")
    box("cinema_projector", (106, 130, main-.95), (1.25, .9, .42), "charcoal")

    # Study/library and storage: shelves contain visible books and equipment.
    rect("library_rug", [93, 108, 149, 159], base+.024, .025, "villa_rug", False)
    for x in (92, 99, 106):
        bookshelf(f"library_bookshelf_{x}", x, 162.1, base, 6.5)
    table("library_desk", 100, 155.5, base, (6.7, 2.6), .9)
    chair("library_desk_chair", 100, 157.5, base)
    chair("library_visitor_chair_1", 98.2, 153.4, base, math.pi)
    chair("library_visitor_chair_2", 102, 153.4, base, math.pi)
    box("library_laptop_base", (100.8, 155.5, base+.94), (.9, .65, .05), "metal", False)
    box("library_laptop_screen", (100.8, 155.77, base+1.27), (.9, .065, .62), "charcoal", False)
    m.cylinder("library_desk_lamp_base", (98, 155.8, base+.99), .23, .12, "brass", False)
    m.beam("library_desk_lamp_arm", (98, 155.8, base+1), (98, 155.8, base+1.8), .055, "brass", False)
    m.sphere("library_desk_lamp_shade", (98, 155.8, base+1.8), (.4, .23, .13), "brass", False)
    for x in (113, 123.6):
        for y in (151, 158.8):
            for tier in range(4):
                box(f"storage_shelf_{x}_{y}_{tier}", (x, y, base+.25+tier*.92), (2, 5.4, .12), "metal")
                for bidx in range(3):
                    box(f"storage_crate_{x}_{y}_{tier}_{bidx}", (x, y-1.6+bidx*1.6, base+.58+tier*.92),
                        (1.7, 1.25, .54), "wood" if tier%2 else "charcoal")
            for sy in (-2.65, 2.65):
                box(f"storage_shelf_post_{x}_{y}_{sy}", (x, y+sy, base+1.85), (.1, .1, 3.7), "metal")
    box("utility_air_handler", (75, 159.5, base+1.25), (3, 3, 2.5), "metal")
    for i in range(3):
        m.cylinder(f"utility_water_tank_{i}", (80+i*2.1, 160.2, base+1.6), .72, 3.2, "metal")
    box("utility_electrical_panel", (72, 161.7, base+1.7), (2.3, .5, 2.4), "charcoal")
    box("utility_workbench", (85, 153.5, base+.65), (4, 1.5, 1.3), "wood")

    # Rooftop lounge with light pergola and a marked eastern helipad.
    rect("rooftop_west_deck", [33, 65, 126, 157], roof+.045, .045, "wood")
    for x in (36, 62):
        for y in (132, 151):
            box(f"roof_pergola_post_{x}_{y}", (x, y, roof+1.8), (.25, .25, 3.6), "charcoal")
    for i in range(12):
        box(f"roof_pergola_louver_{i}", (36+i*26/11, 141.5, roof+3.7), (.55, 20.5, .2), "wood")
    for y, yaw in ((134.5, math.pi), (149, 0)):
        sofa(f"rooftop_lounge_{y}", 49, y, roof+.045, 9, yaw)
    table("rooftop_lounge_table", 49, 141.5, roof+.045, (7.5, 3.7), .48, "stone")
    for x, y in ((35, 129), (64, 155), (92, 160), (121, 160)):
        planter(f"roof_tree_{x}_{y}", x, y, roof, .7)
    # Flat painted pad is visual-only on the actual load-bearing roof slab.
    m.cylinder("helipad_surface", (108, 139, roof+.032), 12.0, .055, "charcoal", False, 64)
    for i in range(64):
        a, b = i*math.tau/64, (i+1)*math.tau/64
        m.beam(f"helipad_circle_{i}", (108+10.8*math.cos(a), 139+10.8*math.sin(a), roof+.075),
               (108+10.8*math.cos(b), 139+10.8*math.sin(b), roof+.075), .2, "white", False)
    for x in (105.5, 110.5):
        box(f"helipad_H_upright_{x}", (x, 139, roof+.09), (.65, 7, .025), "white", False)
    box("helipad_H_crossbar", (108, 139, roof+.09), (5, .65, .025), "white", False)
    for i in range(8):
        a = i*math.tau/8
        m.cylinder(f"helipad_edge_light_{i}", (108+11.75*math.cos(a), 139+11.75*math.sin(a), roof+.14),
                   .13, .16, "emissive", False, 8)

    # Warm ceiling strips emphasize the deep, habitable interior in dusk views.
    for label, f, ceiling in (("main", main, upper-.34), ("basement", base, main-.34), ("upper", upper, roof-.34)):
        for x in (35, 65, 91, 121):
            box(f"{label}_ceiling_light_{x}", (x, 140, ceiling-.04), (.13, 39, .055), "emissive", False)

    entry = (78, 109, main+2)
    main_hall = (76, 140, main+2)
    base_hall = (76, 140, base+2)
    upper_hall = (76, 140, upper+2)
    entry_path = [entry, (78, 121, main+2), (76, 131, main+2), main_hall]
    route("arrival_to_main_atrium", entry_path)
    route("main_to_pool", [main_hall, (110, 140, main+2), (134, 140, main+2)])
    route("main_to_basement", [main_hall, base_hall])
    route("main_to_upper", [main_hall, upper_hall])
    route("basement_west_walkout", [(18, 140, base+2), (31, 140, base+2), base_hall])
    for name, x, y, target_y in (("gym", 52, 134, 131), ("cinema", 104, 134, 132),
                                ("boxing", 52, 146, 150), ("library", 101, 146, 150),
                                ("storage", 119, 146, 150)):
        route("basement_to_"+name, [base_hall, (x, 140, base+2), (x, y, base+2), (x, target_y, base+2)])
    for i, x, y, target_y in ((1, 53, 134, 130), (2, 105, 134, 130),
                              (3, 53, 148, 151), (4, 105, 148, 151)):
        route(f"upper_to_bedroom_{i}", [upper_hall, (x, 140, upper+2), (x, y, upper+2), (x, target_y, upper+2)])
    return {
        "rooms": rooms,
        "portals": portals,
        "flight_routes": routes,
        "floor_levels": {"basement": base, "main": main, "upper": upper, "roof": roof},
        "excavations": [{"bounds": [x0, x1, y0, y1], "z": base-.4},
                        {"bounds": [8, 30, 125, 153], "z": 74.4}],
        "slab_openings": [{"name": "central_atrium", "bounds": atrium, "levels": ["main", "upper", "roof"]},
                          {"name": "stairwell", "bounds": stairwell, "levels": ["main", "upper"]}],
        "helipad": {"center": [108, 139, roof+.1], "radius": 12},
        "views": {
            "interior_living": {"position": [66, 133, main+3.4], "target": [46, 124, main+1.5]},
            "interior_dining": {"position": [90, 133, main+3.3], "target": [108, 125, main+1.1]},
            "interior_kitchen": {"position": [93, 143, main+3.1], "target": [109, 155, main+1.4]},
            "interior_bedroom": {"position": [59, 132, upper+3.3], "target": [43, 124.5, upper+1.1]},
            "interior_bathroom": {"position": [61.3, 123.2, upper+2.5], "target": [66.2, 119.2, upper+1]},
            "interior_gym": {"position": [67, 132, base+3.8], "target": [44, 122, base+1.3]},
            "interior_boxing": {"position": [66, 148.5, base+3.5], "target": [43, 155, base+1.5]},
            "interior_cinema": {"position": [106, 132.5, base+4], "target": [106, 117, base+2.2]},
            "interior_library": {"position": [108, 148, base+3.2], "target": [99, 158, base+1.8]},
            "interior_atrium": {"position": [76, 131, upper+2.8], "target": [78, 144, main+1]},
            "basement_walkout": {"position": [14, 142, base+3.2], "target": [44, 140, base+1.5]},
            "roof_terrace": {"position": [18, 100, roof+20], "target": [76, 141, roof+1]},
        },
        "design": "Three-storey glazed villa, four ensuite bedrooms, walkout wellness basement and roof terrace",
    }
