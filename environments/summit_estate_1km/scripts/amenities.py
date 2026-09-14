"""Deterministic outdoor architecture for the reference-inspired Summit Estate.

All dimensions are metres. Decorative geometry is collected by material before
being handed to the shared Scene API; walkable structures retain real collision.
"""
from math import asin, cos, pi, sin, sqrt

import numpy as np


class _Details:
    """Collect fine visual geometry without multiplying SDF scene entities."""

    def __init__(self, model):
        self.model = model
        self.parts = {}

    def mesh(self, material, vertices, faces):
        verts, tris = self.parts.setdefault(material, ([], []))
        offset = len(verts)
        verts.extend([list(map(float, v)) for v in vertices])
        tris.extend([[int(a) + offset, int(b) + offset, int(c) + offset] for a, b, c in faces])

    def quad(self, material, points):
        self.mesh(material, points, [(0, 1, 2), (0, 2, 3)])

    def box(self, material, center, size, yaw=0):
        center, half = np.asarray(center), np.asarray(size) / 2
        verts = np.array([[-1,-1,-1], [1,-1,-1], [1,1,-1], [-1,1,-1],
                          [-1,-1,1], [1,-1,1], [1,1,1], [-1,1,1]], dtype=float) * half
        rot = np.array([[cos(yaw), -sin(yaw), 0], [sin(yaw), cos(yaw), 0], [0,0,1]])
        verts = verts @ rot.T + center
        faces = [(0,2,1),(0,3,2),(4,5,6),(4,6,7),(0,1,5),(0,5,4),
                 (1,2,6),(1,6,5),(2,3,7),(2,7,6),(3,0,4),(3,4,7)]
        self.mesh(material, verts, faces)

    def ellipsoid(self, material, center, radii, segments=10, rings=5):
        x, y, z = center
        rx, ry, rz = radii
        verts = [(x, y, z-rz)]
        for j in range(1, rings):
            phi = -pi/2 + pi*j/rings
            for i in range(segments):
                theta = 2*pi*i/segments
                verts.append((x+rx*cos(phi)*cos(theta), y+ry*cos(phi)*sin(theta), z+rz*sin(phi)))
        top = len(verts)
        verts.append((x, y, z+rz))
        faces = []
        for i in range(segments):
            nxt = (i+1) % segments
            faces.append((0, 1+nxt, 1+i))
            for j in range(rings-2):
                a, b = 1+j*segments+i, 1+j*segments+nxt
                faces.extend([(a,b,b+segments), (a,b+segments,a+segments)])
            a, b = 1+(rings-2)*segments+i, 1+(rings-2)*segments+nxt
            faces.append((a,b,top))
        self.mesh(material, verts, faces)

    def tube(self, material, points, radius, sides=6):
        points = np.asarray(points, dtype=float)
        verts, faces = [], []
        for i, point in enumerate(points):
            tangent = points[min(i+1, len(points)-1)] - points[max(i-1, 0)]
            tangent /= np.linalg.norm(tangent)
            reference = np.array([0.,0.,1.]) if abs(tangent[2]) < .9 else np.array([1.,0.,0.])
            u = np.cross(tangent, reference)
            u /= np.linalg.norm(u)
            v = np.cross(tangent, u)
            for j in range(sides):
                verts.append(point + radius*(cos(2*pi*j/sides)*u + sin(2*pi*j/sides)*v))
            if i:
                for j in range(sides):
                    a, b = (i-1)*sides+j, (i-1)*sides+(j+1)%sides
                    faces.extend([(a,b,b+sides), (a,b+sides,a+sides)])
        self.mesh(material, verts, faces)

    def arc(self, material, center, radius, start=0, end=2*pi, width=.05, segments=72):
        x, y, z = center
        verts, faces = [], []
        for i in range(segments+1):
            t = start + (end-start)*i/segments
            verts.extend([(x+(radius-width/2)*cos(t),y+(radius-width/2)*sin(t),z),
                          (x+(radius+width/2)*cos(t),y+(radius+width/2)*sin(t),z)])
            if i:
                a = 2*i-2
                faces.extend([(a,a+3,a+2),(a,a+1,a+3)])
        self.mesh(material, verts, faces)

    def line(self, material, start, end, width=.05):
        a, b = np.asarray(start), np.asarray(end)
        d = b-a
        normal = np.array([-d[1], d[0], 0.])
        normal *= width / (2*np.linalg.norm(normal))
        self.quad(material, [a-normal,b-normal,b+normal,a+normal])

    def disk(self, material, center, radius, segments=80):
        x,y,z = center
        verts = [center] + [(x+radius*cos(2*pi*i/segments),y+radius*sin(2*pi*i/segments),z) for i in range(segments)]
        self.mesh(material, verts, [(0,i+1,(i+1)%segments+1) for i in range(segments)])

    def flush(self):
        for material, (vertices, faces) in sorted(self.parts.items()):
            self.model.mesh(f"details_{material}", vertices, faces, material, collision=False)


def _feature(features, name, kind, bounds, **extra):
    features.append(dict(name=name, type=kind, bounds=list(bounds), **extra))


def _cypress(model, details, name, x, y, z, height=7):
    model.cylinder(name+"_trunk", (x,y,z+height*.25), .20, height*.5, "trunk", segments=8)
    details.ellipsoid("leaf1", (x,y,z+height*.59), (.90,.90,height*.43))
    details.ellipsoid("leaf0", (x+.12,y-.08,z+height*.77), (.65,.65,height*.25))


def _planter(model, details, name, x, y, z, radius=1.35):
    model.cylinder(name, (x,y,z+.36), radius, .72, "stone", segments=16)
    details.disk("grass_dark", (x,y,z+.725), radius-.13, segments=20)
    details.ellipsoid("leaf2", (x,y,z+1.1), (radius*.80,radius*.80,.63))
    for i in range(7):
        a=2*pi*i/7
        details.ellipsoid("white", (x+.75*radius*cos(a),y+.75*radius*sin(a),z+.98), (.18,.18,.12), segments=6,rings=3)


def _seat(model, details, name, center, yaw=0, width=2.8):
    x,y,z = center
    model.box(name+"_base", (x,y,z+.35), (width,1.3,.58), "wood", yaw=yaw)
    details.box("fabric", (x,y,z+.69), (width-.1,1.20,.20), yaw)
    back = np.array([x,y,z+1.04]) + np.array([-sin(yaw),cos(yaw),0])*.56
    model.box(name+"_back", back, (width,.19,1.0), "wood", yaw=yaw)
    details.box("fabric", back-np.array([-sin(yaw),cos(yaw),0])*.12, (width-.18,.24,.66), yaw)
    for side in [-1,1]:
        offset=np.array([cos(yaw),sin(yaw),0])*width*.37*side
        details.box("dark_fabric", np.array([x,y,z+.93])+offset, (.45,.65,.34), yaw)


def _gate(scene, config, features):
    model=scene.model("estate_entrance")
    details=_Details(model)
    x,y,z=config["gate"]["center"]
    half=config["gate"]["width"]/2
    for sign, label in [(-1,"west"),(1,"east")]:
        px=x+sign*(half+1.4)
        model.box(label+"_gate_pier", (px,y,z+2.7), (2.2,2.5,5.4), "stone")
        model.box(label+"_pier_base", (px,y,z+.25), (2.7,2.9,.5), "paving")
        model.box(label+"_pier_cap", (px,y,z+5.43), (2.65,2.95,.30), "ivory")
        model.box(label+"_pier_inset", (px,y-1.26,z+2.8), (1.55,.04,3.8), "ivory", collision=False)
        details.box("metal", (px,y,z+5.85), (.55,.55,.7))
        details.box("emissive", (px,y-.29,z+5.88), (.30,.02,.45))
        details.box("brass", (px,y,z+6.25), (.80,.80,.12))
        # At 90 degrees open, the wrought-iron leaves run beside the road.
        lx=x+sign*(half+1.20)
        for level in [.5,1.25,2.9]:
            model.box(label+"_leaf_rail_"+str(level), (lx,y+3.2,z+level), (.14,5.9,.12), "metal")
        for i in range(21):
            yy=y+.30+i*.29
            h=2.95+.40*sin(pi*i/20)
            model.box(f"{label}_picket_{i}", (lx,yy,z+h/2+.15), (.065,.065,h), "metal")
            details.ellipsoid("brass", (lx,yy,z+h+.20), (.085,.085,.15), segments=6,rings=3)
        wallx=x+sign*(half+10)
        model.box(label+"_entry_wing", (wallx,y,z+1.5), (13,1.3,3.0), "stone")
        model.box(label+"_wing_cap", (wallx,y,z+3.05), (13.4,1.5,.22), "ivory")
        if sign == 1:
            model.box("sign_inset", (wallx,y-.66,z+1.6), (10.5,.07,2.25), "ivory", collision=False)
            model.text("estate_name", "THE SUMMIT", (wallx-3.2,y-.71,z+1.7), .77, "charcoal")
            model.text("estate_subtitle", "ESTATE", (wallx-1.9,y-.72,z+.80), .74, "charcoal")
        for i in range(3):
            tx=x+sign*(half+4+5*i)
            _cypress(model,details,f"{label}_entry_cypress_{i}",tx,y+4.5,z+.35,6.2+i*.6)
        for i in range(4):
            _planter(model,details,f"{label}_approach_planter_{i}",x+sign*(half+3.5),y-5-i*5,z-.3-i*.32,1.05)
    details.flush()
    _feature(features,"entrance_gate","open_gate",[x-half-23,x+half+23,y-23,y+9,z-2,z+8],
             center=[x,y,z], clear_width=2*half+.10, leaves_open=True, sign="THE SUMMIT ESTATE")


def _arrival(scene, config, features):
    model=scene.model("estate_arrival")
    details=_Details(model)
    x,y,z=config["arrival"]["center"]
    inner,outer=config["arrival"]["inner_radius"],config["arrival"]["outer_radius"]
    model.ring("arrival_drive", (x,y,z+.055), inner,outer,.16,"asphalt",segments=120)
    model.ring("inner_drive_curb",(x,y,z+.14),inner-.3,inner+.12,.28,"stone",segments=120)
    details.arc("paving",(x,y,z+.15),outer-.15,width=.3,segments=120)
    details.arc("paving",(x,y,z+.15),inner+.8,width=.12,segments=120)
    details.disk("grass",(x,y,z+.04),inner-.35)
    model.ring("fountain_walk",(x,y,z+.10),12.0,16.0,.16,"paving",segments=96)
    model.cylinder("fountain_base",(x,y,z+.24),12,.48,"stone",segments=96)
    model.ring("fountain_basin",(x,y,z+.91),10.45,11.6,1.34,"ivory",segments=96)
    model.ring("fountain_coping",(x,y,z+1.64),10.2,11.85,.22,"stone",segments=96)
    details.disk("water",(x,y,z+1.35),10.44)
    model.cylinder("fountain_pedestal",(x,y,z+1.85),1.05,3.2,"stone",segments=32)
    model.ring("fountain_middle_bowl",(x,y,z+3.12),3.48,4.0,.48,"ivory",segments=64)
    model.cylinder("fountain_middle_floor",(x,y,z+2.89),3.95,.18,"ivory",segments=64)
    details.disk("water",(x,y,z+3.29),3.47)
    model.cylinder("fountain_upper_stem",(x,y,z+3.95),.56,2.0,"stone",segments=24)
    model.ring("fountain_upper_bowl",(x,y,z+5.0),1.9,2.32,.40,"ivory",segments=48)
    model.cylinder("fountain_upper_floor",(x,y,z+4.78),2.3,.18,"ivory",segments=48)
    details.disk("water",(x,y,z+5.13),1.89)
    details.ellipsoid("brass",(x,y,z+5.40),(.48,.48,.64),segments=16,rings=8)
    # Parabolic jets, tier spill streams and central plume are visual-only water.
    for i in range(20):
        a=2*pi*i/20
        points=[]
        for t in np.linspace(0,1,15):
            r=9.25-3.2*t
            points.append((x+r*cos(a),y+r*sin(a),z+1.4+10*t*(1-t)))
        details.tube("water",points,.065)
        details.ellipsoid("brass",(x+9.25*cos(a),y+9.25*sin(a),z+1.43),(.12,.12,.15),segments=6,rings=3)
    for radius,startz,count in [(3.75,3.28,16),(2.13,5.16,12)]:
        for i in range(count):
            a=2*pi*i/count
            points=[(x+(radius+.28*t)*cos(a),y+(radius+.28*t)*sin(a),z+startz-1.8*t*t) for t in np.linspace(0,1,10)]
            details.tube("water",points,.045)
    details.tube("water",[(x+.05*sin(t*4),y,z+5.8+2.4*t) for t in np.linspace(0,1,15)],.115)
    for i in range(30):
        a=2*pi*i/30
        for radius in [18.7,22.7]:
            details.ellipsoid("leaf"+str(i%3),(x+radius*cos(a),y+radius*sin(a),z+.63),(1.45,1.45,.65))
            if i%2==0:
                details.ellipsoid("white",(x+(radius-.4)*cos(a),y+(radius-.4)*sin(a),z+1.17),(.35,.35,.17),segments=6,rings=3)
    for i in range(10):
        a=2*pi*i/10
        # Preserve arrival road southwest and the main north entry axis.
        if (sin(a)>.7 and abs(cos(a))<.4) or (cos(a)<-.6 and sin(a)<0):
            continue
        _cypress(model,details,f"arrival_cypress_{i}",x+(outer+4)*cos(a),y+(outer+4)*sin(a),z,7)
    # Broad approach joins the northern loop and reaches the villa entry sill.
    endy=config["villa"]["bounds"][2]
    starty=y+outer-3
    mainz=config["villa"]["main_z"]
    model.box("villa_entry_walk",(x,(starty+endy)/2,mainz-.10),(12,endy-starty,.20),"paving")
    for side in [-1,1]:
        for i in range(3):
            yy=starty+4+i*6
            _planter(model,details,f"entry_walk_planter_{side}_{i}",x+side*8.6,yy,z,1.3)
    details.flush()
    _feature(features,"arrival_drive","annular_drive",[x-outer,x+outer,y-outer,y+outer,z-.025,z+.3],center=[x,y,z],radii=[inner,outer])
    _feature(features,"arrival_fountain","tiered_fountain",[x-12,x+12,y-12,y+12,z,z+8.3],center=[x,y,z],basin_count=3,jet_count=49)
    _feature(features,"villa_approach","pedestrian_approach",[x-6,x+6,starty,endy,z,mainz],clear_width=12,endpoint=[x,endy,mainz])


def _pool(scene, config, features, excavations):
    model=scene.model("estate_pool")
    details=_Details(model)
    x,y,z=config["pool"]["center"]
    sx,sy=config["pool"]["size"]
    x0,x1,y0,y1=x-sx/2,x+sx/2,y-sy/2,y+sy/2
    bed,water=z-2.3,z-.1
    model.box("pool_floor",(x,y,bed-.18),(sx+.8,sy+.8,.36),"ivory")
    for name,c,s in [("west",(x0-.2,y,z-1.12),(.4,sy+.8,2.6)),("east",(x1+.2,y,z-1.12),(.4,sy+.8,2.6)),
                     ("south",(x,y0-.2,z-1.12),(sx,.4,2.6)),("north",(x,y1+.2,z-1.12),(sx,.4,2.6))]:
        model.box("pool_"+name+"_wall",c,s,"ivory")
    details.quad("pool_water",[(x0,y0,water),(x1,y0,water),(x1,y1,water),(x0,y1,water)])
    for i in range(5):
        top=z-.12-.44*i
        model.box(f"pool_entry_step_{i}",(x,y1-.5-i, (bed+top)/2),(10,1,top-bed),"paving")
    for name,c,s in [("west",(x0-.4,y,z+.11),(.8,sy+1.6,.24)),("east",(x1+.4,y,z+.11),(.8,sy+1.6,.24)),
                     ("south",(x,y0-.4,z+.11),(sx,.8,.24)),("north",(x,y1+.4,z+.11),(sx,.8,.24))]:
        model.box("pool_"+name+"_coping",c,s,"stone")
    dx0,dx1,dy0,dy1=x0-17,x1+17,y0-11,y1+13
    for name,c,s in [("south",(x,(dy0+y0-.8)/2,z+.03),(dx1-dx0,y0-.8-dy0,.3)),
                     ("north",(x,(y1+.8+dy1)/2,z+.03),(dx1-dx0,dy1-y1-.8,.3)),
                     ("west",((dx0+x0-.8)/2,y,z+.03),(x0-.8-dx0,sy+1.6,.3)),
                     ("east",((x1+.8+dx1)/2,y,z+.03),(dx1-x1-.8,sy+1.6,.3))]:
        model.box("pool_deck_"+name,c,s,"paving")
    # Thin joints read as large stone slabs without fragmenting the deck collider.
    for xx in np.arange(dx0+2,dx1,2):
        details.line("stone",(xx,dy0,z+.185),(xx,y0-.8,z+.185),.018)
        details.line("stone",(xx,y1+.8,z+.185),(xx,dy1,z+.185),.018)
    for i in range(6):
        lx=x0-7+i*7.6
        ly=y1+6.3
        model.box(f"lounger_{i}_frame",(lx,ly,z+.45),(2.1,4.5,.44),"wood")
        details.box("fabric",(lx,ly-.4,z+.72),(1.96,3.4,.15))
        # Raised back with a gentle incline, expressed directly as a quad slab.
        details.quad("fabric",[(lx-.98,ly+.9,z+.8),(lx+.98,ly+.9,z+.8),
                                 (lx+.98,ly+2,z+1.4),(lx-.98,ly+2,z+1.4)])
        details.box("dark_fabric",(lx,ly+1.4,z+1.28),(1.7,.6,.18))
        if i<5:
            model.box(f"lounger_table_{i}",(lx+3.6,ly,z+.5),(1.1,1.1,.65),"stone")
    for i,cy in enumerate([y-7,y+7]):
        cx=x1+10
        model.box(f"cabana_{i}_platform",(cx,cy,z+.28),(9,10,.22),"wood")
        for ax in [-3.9,3.9]:
            for ay in [-4.4,4.4]:
                model.box(f"cabana_{i}_post_{ax}_{ay}",(cx+ax,cy+ay,z+1.96),(.2,.2,3.6),"metal")
        model.box(f"cabana_{i}_roof",(cx,cy,z+3.9),(9.6,10.5,.3),"ivory")
        for k in range(7):
            details.box("fabric",(cx+3.7,cy-3.9+k*.45,z+2.02),(.12,.35,3.4))
        _seat(model,details,f"cabana_{i}_sofa",(cx,cy+2.8,z+.4),width=6.4)
        model.box(f"cabana_{i}_table",(cx,cy,z+.82),(2.8,1.8,.6),"stone")
    for i, (px,py) in enumerate([(dx0+2,dy0+2),(dx0+2,dy1-2),(dx1-2,dy0+2),(dx1-2,dy1-2)]):
        _planter(model,details,f"pool_planter_{i}",px,py,z+.2,1.5)
    vx=config["villa"]["bounds"][1]
    if dx0 > vx:
        model.box("villa_pool_link",((vx+dx0)/2,y,z+.10),(dx0-vx,10,.20),"paving")
    details.flush()
    excavations.append({"bounds":[x0-.7,x1+.7,y0-.7,y1+.7],"z":bed-.4,"name":"swimming_pool"})
    _feature(features,"swimming_pool","recessed_pool",[x0-.8,x1+.8,y0-.8,y1+.8,bed-.36,z+.23],
             center=[x,y,z],water_z=water,floor_z=bed,water_collision=False,step_count=5)
    _feature(features,"pool_deck","furnished_terrace",[dx0,dx1,dy0,dy1,z-.12,z+4.1],loungers=6,cabanas=2)


def _court(scene, config, features):
    model=scene.model("estate_basketball")
    details=_Details(model)
    x,y,z=config["court"]["center"]
    sx,sy=config["court"]["size"]
    surface=z+.12
    model.box("court_surface",(x,y,surface-.1),(sx,sy,.2),"court")
    # Playing boundary is measured to the inside of the 5 cm painted lines.
    h,k=14,7.5
    paint=surface+.006
    details.line("white",(x-h-.025,y-k-.05,paint),(x-h-.025,y+k+.05,paint))
    details.line("white",(x+h+.025,y-k-.05,paint),(x+h+.025,y+k+.05,paint))
    details.line("white",(x-h,y-k-.025,paint),(x+h,y-k-.025,paint))
    details.line("white",(x-h,y+k+.025,paint),(x+h,y+k+.025,paint))
    details.line("white",(x,y-k-.15,paint),(x,y+k+.15,paint))
    details.arc("white",(x,y,paint),1.775,width=.05)
    hoops=[]
    for sign,label in [(-1,"west"),(1,"east")]:
        base=x+sign*h
        basket=x+sign*(h-1.575)
        ft=x+sign*(h-5.8)
        key_left,key_right=sorted([base,ft])
        details.quad("court_key",[(key_left,y-2.45,surface+.002),(key_right,y-2.45,surface+.002),
                                    (key_right,y+2.45,surface+.002),(key_left,y+2.45,surface+.002)])
        details.line("white",(base,y-2.425,paint),(ft,y-2.425,paint))
        details.line("white",(base,y+2.425,paint),(ft,y+2.425,paint))
        details.line("white",(ft+sign*.025,y-2.45,paint),(ft+sign*.025,y+2.45,paint))
        facing=0 if sign==-1 else pi
        details.arc("white",(ft,y,paint),1.775,facing-pi/2,facing+pi/2)
        # Dashed free-throw semicircle inside the key.
        for i in range(8):
            a=facing+pi/2+i*pi/8
            details.arc("white",(ft,y,paint),1.775,a,a+pi/16,segments=5)
        # Three-point line: 6.75 m outer radius, straight corners 0.90 m in.
        arc_radius=6.725
        side_offset=6.575
        alpha=asin(side_offset/arc_radius)
        joinx=basket-sign*sqrt(arc_radius**2-side_offset**2)
        for sygn in [-1,1]:
            details.line("white",(base,y+sygn*side_offset,paint),(joinx,y+sygn*side_offset,paint))
        details.arc("white",(basket,y,paint),arc_radius,facing-alpha,facing+alpha,segments=100)
        details.arc("white",(basket,y,paint),1.275,facing-pi/2,facing+pi/2,segments=32)
        for i,distance in enumerate([1.75,2.65,3.55,4.5]):
            px=base-sign*distance
            for s in [-1,1]:
                details.line("white",(px,y+s*2.45,paint),(px,y+s*2.6,paint),.10)
        # Support is in the runoff; the board and rim face inward.
        pole=x+sign*15.2
        model.box(label+"_hoop_base",(pole,y,surface+.25),(1.0,1.25,.5),"rubber")
        model.box(label+"_hoop_post",(pole,y,surface+2.0),(.22,.22,4.0),"metal")
        board=x+sign*(h-1.2)
        model.beam(label+"_hoop_arm",(pole,y,surface+3.7),(board,y,surface+3.7),.16,"metal")
        model.box(label+"_backboard",(board,y,surface+3.5),(.08,1.8,1.05),"glass")
        # White backboard boundary and target square on the face toward court.
        bx=board-sign*.046
        for yy in [y-.90,y+.90]:
            details.box("white",(bx,yy,surface+3.5),(.025,.045,1.05))
        for zz in [surface+2.975,surface+4.025]:
            details.box("white",(bx,y,zz),(.025,1.8,.045))
        for yy in [y-.295,y+.295]:
            details.box("white",(bx,yy,surface+3.28),(.025,.05,.45))
        for zz in [surface+3.055,surface+3.505]:
            details.box("white",(bx,y,zz),(.025,.59,.05))
        model.ring(label+"_rim",(basket,y,surface+3.035),.225,.243,.03,"brass",segments=32)
        for i in range(12):
            a=2*pi*i/12
            details.tube("white",[(basket+.225*cos(a),y+.225*sin(a),surface+3.035),
                                    (basket+.14*cos(a+.15),y+.14*sin(a+.15),surface+2.60)],.009,sides=4)
        hoops.append([basket,y,surface+3.05])
    for sign in [-1,1]:
        yy=y+sign*(sy/2+1)
        # End-adjacent mesh fence protects edges; south centre remains an entry.
        for i in range(9):
            xx=x-sx/2+i*sx/8
            if sign==-1 and abs(xx-x)<4:
                continue
            model.box(f"court_fence_post_{sign}_{i}",(xx,yy,z+1.1),(.08,.08,2.2),"metal")
        for zz in [.18,2.15]:
            if sign==1:
                model.box(f"court_fence_rail_{sign}_{zz}",(x,yy,z+zz),(sx,.065,.065),"metal")
            else:
                for side in [-1,1]:
                    model.box(f"court_fence_rail_{sign}_{zz}_{side}",(x+side*(sx/4+2),yy,z+zz),(sx/2-4,.065,.065),"metal")
        for i in range(81):
            xx=x-sx/2+i*sx/80
            if sign==-1 and abs(xx-x)<4:
                continue
            details.line("metal",(xx,yy-.02,z+.2),(xx+.02,yy+.02,z+2.1),.025)
    for i in [-1,1]:
        _seat(model,details,f"court_bench_{i}",(x+i*8,y-sy/2-4,z),yaw=pi,width=4.5)
    details.flush()
    _feature(features,"basketball_court","marked_sport_court",[x-sx/2-1,x+sx/2+1,y-sy/2-6,y+sy/2+1.1,z,z+4.2],
             center=[x,y,z],playing_size=[28,15],runoff_size=[sx,sy],surface_z=surface,
             line_width=.05,three_point_radius=6.75,hoops=hoops,
             rules_source="https://assets.fiba.basketball/image/upload/documents-corporate-fiba-official-rules-2024-v10a.pdf")


def _fire_lounge(scene, config, features):
    model=scene.model("estate_fire_lounge")
    details=_Details(model)
    x,y,z=config["fire_lounge"]["center"]
    radius=config["fire_lounge"]["radius"]
    model.cylinder("fire_lounge_terrace",(x,y,z+.05),radius,.22,"paving",segments=80)
    model.ring("lounge_border",(x,y,z+.11),radius-.4,radius,.18,"stone",segments=80)
    model.cylinder("fire_pit_plinth",(x,y,z+.32),3.4,.5,"stone",segments=48)
    model.ring("fire_pit_bowl",(x,y,z+.8),2.2,2.8,.65,"ivory",segments=48)
    model.cylinder("fire_pit_coals",(x,y,z+.61),2.2,.18,"charcoal",segments=48)
    for i in range(11):
        a=2*pi*i/11
        r=.7+1.0*(i%3)/2
        details.ellipsoid("rock",(x+r*cos(a),y+r*sin(a),z+.88),(.45,.30,.24),segments=8,rings=4)
        details.ellipsoid("fire",(x+r*cos(a),y+r*sin(a),z+1.35),(.28,.25,.72+(i%3)*.18),segments=7,rings=4)
    for i,a in enumerate([0,pi/3,2*pi/3,pi,4*pi/3,5*pi/3]):
        cx,cy=x+8*cos(a),y+8*sin(a)
        _seat(model,details,f"fireside_sofa_{i}",(cx,cy,z+.16),yaw=a-pi/2,width=4.2)
        tablea=a+pi/6
        model.cylinder(f"fireside_table_{i}",(x+8*cos(tablea),y+8*sin(tablea),z+.63),.85,.9,"stone",segments=12)
    for i,a in enumerate([.2,1.0,2.0,2.9,3.7,4.7,5.6]):
        _planter(model,details,f"lounge_planter_{i}",x+(radius+2)*cos(a),y+(radius+2)*sin(a),z,1.25)
    details.flush()
    _feature(features,"fire_pit_lounge","furnished_fire_lounge",[x-radius-4,x+radius+4,y-radius-4,y+radius+4,z-.1,z+3],
             center=[x,y,z],radius=radius,seats=18,fire_collision=False)


def _pavilion(scene, config, features):
    model=scene.model("estate_lake_pavilion")
    details=_Details(model)
    x,y=-75,100
    water=config["lake"]["water_z"]
    floor=water+.55
    model.box("dock_platform",(x,y,floor-.18),(12,10,.36),"wood")
    model.box("dock_walkway",(-57,y,floor-.15),(24,4.5,.30),"wood")
    for xx in [x-5,x+5,-57,-46]:
        for yy in [y-1.8,y+1.8]:
            model.cylinder(f"dock_pile_{xx}_{yy}",(xx,yy,water-.7),.25,3.2,"trunk",segments=12)
    for xx in np.arange(x-5.7,-45,.4):
        extent=4.85 if xx<x+6 else 2.15
        details.line("charcoal",(xx,y-extent,floor+.005),(xx,y+extent,floor+.005),.023)
    for ax in [-4.5,4.5]:
        for ay in [-3.6,3.6]:
            model.box(f"pavilion_post_{ax}_{ay}",(x+ax,y+ay,floor+1.9),(.28,.28,3.8),"wood")
    eave=floor+3.6
    model.box("pavilion_eave",(x,y,eave+.08),(11.5,9.6,.16),"wood")
    # Hipped canopy with a narrow ridge, four coherent roof planes.
    verts=[(x-6,y-5,eave+.2),(x+6,y-5,eave+.2),(x+6,y+5,eave+.2),(x-6,y+5,eave+.2),
           (x-2,y,eave+2),(x+2,y,eave+2)]
    model.mesh("pavilion_hipped_roof",verts,[(0,1,5),(0,5,4),(1,2,5),(2,3,4),(2,4,5),(3,0,4)],"charcoal",collision=True)
    for side in [-1,1]:
        _seat(model,details,f"pavilion_seat_{side}",(x,y+side*2.7,floor),yaw=0 if side==1 else pi,width=6)
    model.box("pavilion_table",(x,y,floor+.55),(3,1.2,.7),"wood")
    # Rails on outer three platform edges; the east approach remains open.
    for yy in [y-4.6,y+4.6]:
        model.box(f"dock_side_rail_{yy}",(x,yy,floor+1.05),(11.6,.1,.1),"wood")
        for xx in [x-5.6,x,x+5.6]:
            model.box(f"dock_rail_post_{xx}_{yy}",(xx,yy,floor+.5),(.1,.1,1),"wood")
    model.box("dock_west_rail",(x-5.6,y,floor+1.05),(.1,9.2,.1),"wood")
    details.box("emissive",(x,y,eave-.12),(1.8,.4,.10))
    details.flush()
    _feature(features,"lake_pavilion","covered_dock",[x-6,-45,y-5,y+5,water-2.3,eave+2],
             center=[x,y,floor],floor_z=floor,clear_headroom=3.6,shore_connection=[-45,y,floor])


def build_amenities(scene, config):
    """Build amenity models, returning terrain edits and navigable feature data."""
    features,excavations=[],[]
    _gate(scene,config,features)
    _arrival(scene,config,features)
    _pool(scene,config,features,excavations)
    _court(scene,config,features)
    _fire_lounge(scene,config,features)
    _pavilion(scene,config,features)
    gx,gy,gz=config["gate"]["center"]
    return {"features":features,"excavations":excavations,"flight_routes":[
        {"name":"open_estate_gate","clearance_radius":1.5,"waypoints":[[gx,gy-15,gz+3],[gx,gy+8,gz+3]]},
        {"name":"villa_main_approach","clearance_radius":1.2,"waypoints":[[78,96,82.4],[78,110,82.4],[78,115,82.4]]},
        {"name":"lake_dock_approach","clearance_radius":.8,"waypoints":[[-45,100,51.6],[-65,100,51.6]]}
    ]}
