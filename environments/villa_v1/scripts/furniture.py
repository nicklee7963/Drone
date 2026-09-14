"""Detailed editable furniture for Summit Estate. Metres, floor-centred, front -Y.

build_asset(kind, name, collection, materials, **kwargs) returns an Empty root.
Never clears the scene or changes render/light settings. All geometry is parented
in asset-local coordinates. Random detail is stable for a given asset name.
"""
import bpy
import math
import random
import hashlib
from mathutils import Vector
from math import sin, cos, pi


def _material(materials, key):
    if key in materials:
        return materials[key]
    fallback = {'marble':'stone','dark_marble':'black','oak':'walnut','taupe':'cream',
                'leather':'taupe','rubber':'black','acoustic':'charcoal','soil':'walnut',
                'foliage':'taupe','bronze':'walnut','ceramic':'cream','emission':'cream'}
    if fallback.get(key) in materials:
        return materials[fallback[key]]
    name = 'FurnitureFallback_' + key
    mat = bpy.data.materials.get(name)
    if mat:
        return mat
    mat = bpy.data.materials.new(name)
    colors = {'stone':(.55,.52,.46,1),'walnut':(.12,.052,.022,1),'cream':(.72,.65,.53,1),
              'black':(.018,.019,.018,1),'charcoal':(.06,.06,.055,1),
              'foliage':(.08,.16,.03,1),'bronze':(.29,.16,.06,1)}
    mat.diffuse_color = colors.get(key, (.35,.29,.22,1))
    mat.use_nodes = True
    mat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value = mat.diffuse_color
    return mat


class Builder:
    def __init__(self, name, collection, materials):
        self.root = bpy.data.objects.new(name, None)
        collection.objects.link(self.root)
        self.root.empty_display_type = 'PLAIN_AXES'
        self.root.empty_display_size = .25
        self.collection, self.materials = collection, materials
        self.rng = random.Random(int(hashlib.sha256(name.encode()).hexdigest()[:12],16))
        self.prefix = name

    def attach(self, obj, label, mat=None):
        obj.name = self.prefix + '__' + label
        for col in list(obj.users_collection):
            col.objects.unlink(obj)
        self.collection.objects.link(obj)
        obj.parent = self.root
        if mat:
            obj.data.materials.append(_material(self.materials, mat))
        return obj

    def mesh(self, label, vertices, faces, mat, smooth=False):
        data = bpy.data.meshes.new(self.prefix+'__'+label+'_mesh')
        data.from_pydata(vertices, [], faces)
        data.update()
        obj = bpy.data.objects.new(label, data)
        self.attach(obj, label, mat)
        if smooth:
            for poly in data.polygons:
                poly.use_smooth = True
        return obj

    def box(self, label, loc, size, mat, bevel=.02):
        x,y,z = (v/2 for v in size)
        verts = [(-x,-y,-z),(-x,-y,z),(-x,y,-z),(-x,y,z),(x,-y,-z),(x,-y,z),(x,y,-z),(x,y,z)]
        faces = [(0,4,6,2),(1,3,7,5),(0,1,5,4),(2,6,7,3),(0,2,3,1),(4,5,7,6)]
        obj=self.mesh(label,verts,faces,mat)
        obj.location=loc
        if bevel:
            mod=obj.modifiers.new('Soft manufactured edges','BEVEL')
            mod.width=min(bevel,min(size)*.45)
            mod.segments=3
            mod=obj.modifiers.new('Weighted normals','WEIGHTED_NORMAL')
        return obj

    def cylinder(self, label, loc, radius, depth, mat, vertices=40, radius_top=None):
        r2=radius if radius_top is None else radius_top
        verts=[(radius*cos(i*2*pi/vertices),radius*sin(i*2*pi/vertices),-depth/2) for i in range(vertices)]
        verts += [(r2*cos(i*2*pi/vertices),r2*sin(i*2*pi/vertices),depth/2) for i in range(vertices)]
        faces=[tuple(reversed(range(vertices))),tuple(range(vertices,2*vertices))]
        faces += [(i,(i+1)%vertices,(i+1)%vertices+vertices,i+vertices) for i in range(vertices)]
        obj=self.mesh(label,verts,faces,mat,True)
        obj.location=loc
        bevel=obj.modifiers.new('Edge radius','BEVEL'); bevel.width=min(.008,depth*.1,radius*.1); bevel.segments=2
        return obj

    def tube(self, label, paths, radius, mat, cyclic=False):
        if not paths: return
        if isinstance(paths[0][0], (int,float)):
            paths=[paths]
        curve=bpy.data.curves.new(self.prefix+'__'+label,'CURVE')
        curve.dimensions='3D'; curve.resolution_u=2
        curve.bevel_depth=radius; curve.bevel_resolution=2; curve.use_fill_caps=True
        for points in paths:
            spl=curve.splines.new('POLY'); spl.points.add(len(points)-1)
            for point, xyz in zip(spl.points,points): point.co=(*xyz,1)
            spl.use_cyclic_u=cyclic
        obj=bpy.data.objects.new(label,curve)
        return self.attach(obj,label,mat)

    def ellipsoid(self,label,loc,size,mat):
        verts=[]; faces=[]; rows=12; cols=24
        for j in range(rows+1):
            t=pi*j/rows
            for i in range(cols):
                p=2*pi*i/cols
                verts.append((size[0]*.5*sin(t)*cos(p),size[1]*.5*sin(t)*sin(p),size[2]*.5*cos(t)))
        for j in range(rows):
            for i in range(cols):
                a=j*cols+i; b=j*cols+(i+1)%cols
                faces.append((a,b,b+cols,a+cols))
        obj=self.mesh(label,verts,faces,mat,True); obj.location=loc
        return obj

    def pillow(self,label,loc,size,mat='cream',rotation=(0,0,0), seam=True):
        # Soft superellipsoid with low-amplitude uneven puckering at welt edge.
        verts=[]; faces=[]; rows=20; cols=40
        def signed_power(v,p): return math.copysign(abs(v)**p,v)
        for j in range(rows+1):
            t=-pi/2+pi*j/rows
            for i in range(cols):
                p=2*pi*i/cols
                edge=1+.012*sin(11*p+1.2)*cos(t)**8
                verts.append((size[0]/2*signed_power(cos(t),.48)*signed_power(cos(p),.38)*edge,
                              size[1]/2*signed_power(cos(t),.48)*signed_power(sin(p),.38)*edge,
                              size[2]/2*signed_power(sin(t),.55)*(1+.026*sin(4*p+cos(t)*8))))
        for j in range(rows):
            for i in range(cols):
                a=j*cols+i; b=j*cols+(i+1)%cols; faces.append((a,b,b+cols,a+cols))
        obj=self.mesh(label,verts,faces,mat,True); obj.location=loc; obj.rotation_euler=rotation
        if seam:
            pts=[]
            for i in range(81):
                p=i*2*pi/80
                pts.append((size[0]/2*signed_power(cos(p),.38)*1.003,size[1]/2*signed_power(sin(p),.38)*1.003,0))
            seamobj=self.tube(label+'_welt',pts,.0035,mat,True)
            seamobj.location=loc; seamobj.rotation_euler=rotation
        return obj

    def cloth(self,label,loc,width,depth,mat='taupe',drop=.25):
        # Top panel drapes down lateral edges and front end. Analytic wrinkles,
        # retained as editable mesh, rather than simulated cloth dependency.
        nx,ny=36,32; verts=[]; faces=[]
        for j in range(ny+1):
            v=j/ny; y=(v-.5)*depth
            for i in range(nx+1):
                u=i/nx; x=(u-.5)*width
                edgex=max(0,(abs(u-.5)-.37)/.13)
                edgey=max(0,(.12-v)/.12)
                z=-drop*max(edgex,edgey)+.011*sin(u*61+v*9)+.007*sin(v*83+u*14)
                verts.append((x,y,z))
        for j in range(ny):
            for i in range(nx):
                a=j*(nx+1)+i; faces.append((a,a+1,a+nx+2,a+nx+1))
        obj=self.mesh(label,verts,faces,mat,True); obj.location=loc
        sol=obj.modifiers.new('Textile thickness','SOLIDIFY'); sol.thickness=.009
        return obj

    def lathe(self,label,loc,profile,mat):
        n=36; verts=[]; faces=[]
        for r,z in profile:
            verts += [(r*cos(i*2*pi/n),r*sin(i*2*pi/n),z) for i in range(n)]
        for j in range(len(profile)-1):
            for i in range(n):
                a=j*n+i; b=j*n+(i+1)%n; faces.append((a,b,b+n,a+n))
        obj=self.mesh(label,verts,faces,mat,True); obj.location=loc
        return obj

    def feet(self,width,depth,height=.16,mat='bronze',inset=.12):
        for x in (-width/2+inset,width/2-inset):
            for y in (-depth/2+inset,depth/2-inset):
                self.cylinder('Tapered_foot',(x,y,height/2),.032,height,mat,24,.021)

    def chair_shell(self,width=.8,depth=.8,base=.42,height=.45,mat='cream'):
        # Swept curved bucket shell, open toward -Y; padded actual surface.
        verts=[]; faces=[]; n=48
        for i in range(n+1):
            t=-.22*pi+1.44*pi*i/n
            x=width*.5*cos(t); y=depth*.46*sin(t)
            h=height*(.74+.26*sin(t))
            for j in range(7):
                f=j/6
                verts.append((x*(.94+.06*f),y*(.94+.06*f),base+f*h))
        for i in range(n):
            for j in range(6):
                a=i*7+j; faces.append((a,a+7,a+8,a+1))
        obj=self.mesh('Curved_upholstered_shell',verts,faces,mat,True)
        sol=obj.modifiers.new('Padded shell thickness','SOLIDIFY'); sol.thickness=.09
        bev=obj.modifiers.new('Soft rim','BEVEL'); bev.width=.03; bev.segments=3
        rim=[]
        for i in range(n+1):
            t=-.22*pi+1.44*pi*i/n
            rim.append((width*.5*cos(t),depth*.46*sin(t),base+height*(.74+.26*sin(t))))
        self.tube('Shell_top_welt',rim,.004,mat)

    def seat(self,kind,kw):
        mat=kw.get('material','leather' if kind=='armchair' else 'cream')
        if kind=='sofa':
            width=kw.get('width',3.6); seats=max(1,int(kw.get('seats',3))); depth=kw.get('depth',1.05)
            self.feet(width,depth,.14,'black')
            self.box('Walnut_underframe',(0,0,.20),(width-.09,depth-.09,.18),'walnut',.05)
            self.pillow('Upholstered_base',(0,0,.33),(width,depth,.3),mat)
            self.pillow('Back_frame',(0,.38,.69),(width-.12,.27,.73),mat)
            for side in [-1,1]:
                self.pillow('Rounded_arm',(side*(width/2-.13),-.01,.62),(.28,depth,.48),mat)
            usable=width-.58
            for i in range(seats):
                x=-usable/2+(i+.5)*usable/seats
                self.pillow('Separate_seat_'+str(i),(x,-.11,.53),(usable/seats-.024,.76,.22),mat)
                self.pillow('Loose_back_'+str(i),(x,.28,.83),(usable/seats-.018,.23,.55),mat,(-.13,0,0))
            for i,x in enumerate([-width*.33,width*.32]):
                self.pillow('Scatter_pillow_'+str(i),(x,-.01,.85),(.5,.16,.5),'taupe' if i else 'cream',(-.24,.12*(-1)**i,.12*(-1)**i))
            if kw.get('throw',True):
                self.cloth('Draped_arm_throw',(-width*.32,-.08,.67),.64,1.05,'taupe',.3)
        elif kind in ('chair','armchair'):
            width=kw.get('width',.68 if kind=='chair' else .95)
            depth=.64 if kind=='chair' else .86
            self.feet(width,depth,.43 if kind=='chair' else .39,'walnut',.11)
            self.pillow('Seat_cushion',(0,-.05,.46),(width*.9,depth*.95,.17),mat)
            self.chair_shell(width,depth,.4,.47 if kind=='chair' else .48,mat)
            if kind=='armchair':
                self.pillow('Lumbar_cushion',(0,.22,.66),(.5,.14,.35),'taupe',(-.14,0,0))
        elif kind=='stool':
            height=kw.get('height',.78); width=kw.get('width',.48)
            self.feet(width,width,height-.12,'black',.07)
            self.pillow('Bar_seat',(0,0,height-.05),(width,width,.14),mat)
            self.tube('Foot_ring',[(.24*cos(i*2*pi/48),.24*sin(i*2*pi/48),.3) for i in range(48)],.013,'bronze',True)
            self.chair_shell(width,.45,height-.1,.23,mat)

    def table(self,kw):
        width=kw.get('width',2.4); depth=kw.get('depth',1.0); height=kw.get('height',.75)
        top=kw.get('material','dark_marble' if kw.get('round',False) else 'walnut')
        if kw.get('round',False):
            self.cylinder('Round_slab',(0,0,height-.045),width/2,.09,top,96)
            self.cylinder('Recessed_pedestal',(0,0,(height-.09)/2),width*.32,height-.09,'bronze',64)
            self.cylinder('Recessed_plinth',(0,0,.035),width*.29,.07,'black',64)
        else:
            self.box('Solid_tabletop',(0,0,height-.05),(width,depth,.10),top,.055)
            for x in [-width*.31,width*.31]:
                self.box('Pedestal',(x,0,(height-.12)/2),(.22,depth*.65,height-.12),'walnut',.045)
                self.box('Bronze_foot',(x,0,.025),(.30,depth*.72,.05),'bronze',.018)
            self.box('Inset_bronze_underside',(0,0,height-.105),(width-.10,depth-.10,.035),'bronze',.015)

    def bed(self,kw):
        w=kw.get('width',2.2); d=kw.get('depth',2.35)
        self.box('Recessed_plinth',(0,0,.10),(w-.12,d-.12,.20),'black',.045)
        self.pillow('Upholstered_bed_frame',(0,0,.28),(w+.12,d+.08,.42),'taupe')
        self.pillow('Mattress',(0,-.05,.53),(w,d,.28),'cream')
        self.pillow('Low_padded_headboard',(0,d/2-.05,.86),(w+.32,.20,1.34),'taupe')
        for i in range(1,10):
            x=-(w+.2)/2+i*(w+.2)/10
            self.tube('Headboard_channel',[(x,d/2-.154,.32),(x,d/2-.156,1.46)],.003,'cream')
        self.cloth('White_duvet',(0,-.15,.715),w+.26,d+.02,'cream',.29)
        for y,z,wide in [(.72,.88,.85),(.48,.91,.69)]:
            for x in [-w*.245,w*.245]:
                self.pillow('Layered_sleep_pillow',(x,y,z),(wide,.20,.47),'cream',(-.35,0,0))
        self.pillow('Accent_lumbar',(0,.25,.91),(.95,.19,.30),'charcoal',(-.2,0,0))
        self.cloth('Foot_of_bed_throw',(0,-.76,.755),w+.35,.79,'taupe',.38)
        fringes=[]
        for i in range(68):
            x=-w*.49+i*w*.98/67
            fringes.append([(x,-1.145,.73),(x+.006,-1.185,.66),(x+.003,-1.18,.60)])
        self.tube('Throw_fringe',fringes,.002,'taupe')

    def cabinet(self,kw):
        w=kw.get('width',3.0); h=kw.get('height',2.8); d=kw.get('depth',.6)
        self.box('Recessed_toe',(0,.04,.06),(w-.1,d-.1,.12),'black',.009)
        self.box('Carcass',(0,0,h/2+.06),(w,d,h-.12),'walnut',.02)
        bays=max(2,int(w/.65))
        for i in range(bays):
            x=-w/2+(i+.5)*w/bays
            self.box('Inlay_door_'+str(i),(x,-d/2-.011,h/2+.07),(w/bays-.018,.042,h-.18),'walnut',.007)
            self.box('Slim_pull_'+str(i),(x+w/bays*.32,-d/2-.045,h*.55),(.014,.022,.28),'bronze',.005)
        self.box('Counter_cap',(0,0,h),(w+.025,d+.035,.045),'marble',.012)

    def book_cluster(self, x0, y, z, width, height):
        # All simple book solids become one multi-material mesh per cluster.
        verts=[]; faces=[]; indices=[]
        keys=['book_'+str(i) for i in range(6)]+['cream','bronze']
        def cube(loc,size,mi):
            start=len(verts); x,y0,z0=loc; a,b,c=(v/2 for v in size)
            verts.extend([(x+dx*a,y0+dy*b,z0+dz*c) for dx,dy,dz in [(-1,-1,-1),(-1,-1,1),(-1,1,-1),(-1,1,1),(1,-1,-1),(1,-1,1),(1,1,-1),(1,1,1)]])
            faces.extend([tuple(start+i for i in f) for f in [(0,4,6,2),(1,3,7,5),(0,1,5,4),(2,6,7,3),(0,2,3,1),(4,5,7,6)]])
            indices.extend([mi]*6)
        x=x0
        while x<x0+width-.055:
            bw=self.rng.uniform(.035,.069); bh=self.rng.uniform(height*.65,height); bd=self.rng.uniform(.19,.26)
            color=self.rng.randrange(6)
            cube((x+bw/2,y,z+bh/2),(bw-.008,bd-.012,bh-.015),6)
            for dx in [-bw/2+.003,bw/2-.003]: cube((x+bw/2+dx,y,z+bh/2),(.006,bd,bh),color)
            cube((x+bw/2,y-bd/2,z+bh/2),(bw,.009,bh),color)
            for tz in [.10,.83]: cube((x+bw/2,y-bd/2-.006,z+bh*tz),(bw*.73,.003,.005),7)
            x+=bw+.006
        obj=self.mesh('Varied_books',verts,faces,keys[0])
        for key in keys[1:]: obj.data.materials.append(_material(self.materials,key))
        for face,idx in zip(obj.data.polygons,indices): face.material_index=idx

    def shelving(self,kind,kw):
        w=kw.get('width',4.0); h=kw.get('height',3.4 if kind=='bookshelf' else 3.2)
        d=kw.get('depth',.38 if kind=='bookshelf' else .66)
        bays=max(2,round(w/1.0)); bw=w/bays
        self.box('Timber_back',(0,d/2-.02,h/2),(w,.04,h),'walnut',.006)
        self.box('Recessed_plinth',(0,0,.065),(w-.08,d-.04,.13),'black',.01)
        for i in range(bays+1): self.box('Vertical_partition_'+str(i),(-w/2+i*bw,0,h/2),(.045,d,h),'walnut',.006)
        for z in [.15,h-.025]: self.box('Continuous_shelf',(0,0,z),(w,d,.045),'walnut',.006)
        for i in range(bays):
            x=-w/2+(i+.5)*bw
            if kind=='bookshelf':
                levels=max(4,round(h/.52)); pitch=(h-.2)/levels
                for j in range(levels):
                    z=.17+j*pitch
                    if j: self.box('Shelf',(x,0,z),(bw-.045,d,.04),'walnut',.006)
                    self.box('LED_diffuser',(x,-d*.32,z+pitch-.035),(bw-.09,.014,.012),'emission',.003)
                    if (i+j)%4!=2:
                        self.book_cluster(x-bw*.43,-.01,z+.025,bw*.57,min(.34,pitch-.10))
                    if (i+j)%3==0:
                        self.vase((x+bw*.3,-.015,z+.025),.12,.24)
                    elif (i+j)%4==2:
                        self.book_cluster(x-bw*.43,0,z+.025,bw*.32,min(.33,pitch-.08))
                        self.box('Display_plinth',(x+bw*.2,-.02,z+.055),(.25,.23,.045),'stone',.009)
                        self.tube('Bronze_loop',[(x+bw*.2+.075*cos(k*2*pi/48),-.02,z+.18+.10*sin(k*2*pi/48)) for k in range(48)],.011,'bronze',True)
            else:
                for z in [.52,h-.52]:
                    self.box('Closet_shelf',(x,0,z),(bw-.045,d,.038),'walnut',.008)
                    self.box('Closet_LED',(x,-d*.40,z-.035),(bw-.08,.015,.013),'emission',.003)
                for z in [.245,.415]:
                    self.box('Drawer_front',(x,-d/2+.03,z),(bw-.07,.045,.15),'walnut',.008)
                    self.box('Drawer_pull',(x,-d/2-.003,z+.038),(.25,.016,.012),'bronze',.004)
                if i%3!=2:
                    railz=h-.67
                    self.tube('Garment_rail',[(x-bw*.43,0,railz),(x+bw*.43,0,railz)],.016,'bronze')
                    count=max(5,int(bw/.14))
                    for k in range(count):
                        gx=x-bw*.35+k*bw*.70/(count-1)
                        self.garment((gx,0,railz-.07),k)
                else:
                    for j,z in enumerate([.9,1.3,1.7,2.1]):
                        if z>h-.65: break
                        self.box('Accessories_shelf',(x,0,z),(bw-.045,d,.034),'walnut',.005)
                        self.box('Accessories_LED',(x,-d*.39,z-.03),(bw-.10,.014,.012),'emission',.003)
                        if j%2: self.bag((x,-.06,z+.025),.33)
                        else:
                            for dx in [-.2,.03]:
                                self.shoe((x+dx,-.12,z+.025),'leather')
                                self.shoe((x+dx+.095,-.12,z+.025),'leather')
                if i%3!=2:
                    for fold in range(3):
                        self.pillow('Folded_textiles',(x,-.07,.58+fold*.065),(bw*.48,.35,.066),'cream' if fold%2 else 'taupe',seam=False)
                if i%2: self.bag((x,-.03,h-.49),.32)
                else:
                    for k in range(2): self.box('Lidded_storage_box',(x,-.015,h-.41+k*.15),(bw*.61,d*.72,.13),'taupe',.009)

    def garment(self,loc,index):
        # Garment panels lie in the YZ plane: clothes packed along hanging rail X.
        x,y,z=loc
        paths=[[(x,y-.22,z-.17),(x,y,z-.04),(x,y+.22,z-.17),(x,y-.22,z-.17)],
               [(x,y,z-.04),(x,y,z+.015),(x,y+.023,z+.05),(x,y+.045,z+.027)]]
        self.tube('Individual_hanger',paths,.007,'bronze')
        length=.88+(index%3)*.11
        outline=[(-.065,-.10),(-.21,-.16),(-.32,-.37),(-.26,-.48),(-.17,-.34),(-.17,-length),(.17,-length),(.17,-.34),(.26,-.48),(.32,-.37),(.21,-.16),(.065,-.10),(.05,-.20),(-.05,-.20)]
        verts=[]
        for side in [-1,1]:
            for yy,zz in outline:
                verts.append((x+side*.03+.008*sin(yy*41+zz*7),y+yy,z+zz))
        n=len(outline); faces=[tuple(reversed(range(n))),tuple(range(n,2*n))]
        faces += [(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
        mat=['cream','taupe','charcoal','cream','leather'][index%5]
        obj=self.mesh('Hanging_jacket_'+str(index),verts,faces,mat,True)
        b=obj.modifiers.new('Garment_softness','BEVEL'); b.width=.025;b.segments=3
        # Front lapels make the garment legible beyond the silhouette.
        self.tube('Garment_lapel',[[(x+.036,y-.055,z-.15),(x+.038,y-.085,z-.33),(x+.038,y,z-.47)],[(x+.036,y+.055,z-.15),(x+.038,y+.085,z-.33),(x+.038,y,z-.47)]],.005,mat)

    def shoe(self,loc,mat):
        x,y,z=loc
        self.ellipsoid('Shoe_sole',(x,y,z+.02),(.082,.23,.035),'black')
        self.ellipsoid('Shoe_upper',(x,y-.025,z+.065),(.078,.18,.087),mat)
        self.ellipsoid('Shoe_opening',(x,y+.052,z+.096),(.047,.062,.013),'black')

    def bag(self,loc,width):
        x,y,z=loc
        self.box('Handbag_body',(x,y,z+width*.35),(width,.16,width*.62),'leather',.045)
        self.box('Bag_flap',(x,y-.088,z+width*.46),(width*.94,.015,width*.30),'leather',.025)
        self.box('Bag_clasp',(x,y-.102,z+width*.37),(.034,.016,.023),'bronze',.005)
        handles=[]
        for yy in [-.06,.06]:
            handles.append([(x+width*.29*cos(i*pi/24),y+yy,z+width*.61+width*.35*sin(i*pi/24)) for i in range(25)])
        self.tube('Bag_handles',handles,.011,'leather')

    def vase(self,loc,r=.14,h=.35):
        self.lathe('Ceramic_vase',loc,[(0,0),(r*.75,0),(r,.06*h),(r,.53*h),(r*.58,.84*h),(r*.47,h),(r*.39,h),(r*.40,.89*h)],'ceramic')

    def plant(self,kw):
        h=kw.get('height',2.0); pot=min(.64,h*.30); radius=pot*.43
        self.lathe('Planter',(0,0,0),[(0,0),(radius*.70,0),(radius,pot*.91),(radius,pot),(radius*.89,pot),(radius*.86,pot*.16)],kw.get('pot_material','ceramic'))
        self.cylinder('Potting_soil',(0,0,pot-.04),radius*.86,.035,'soil',40)
        trunk=[(0,0,pot-.02),(.025,0,h*.55),(-.02,.015,h*.80),(0,0,h)]
        self.tube('Tree_trunk',trunk,max(.011,h*.012),'walnut')
        verts=[]; faces=[]; midribs=[]
        for j in range(20):
            angle=j*2.399; bz=pot+(h-pot)*(.20+.67*j/20)
            reach=h*(.27-.12*j/20)
            end=Vector((cos(angle)*reach,sin(angle)*reach,bz+h*.12))
            start=Vector((.0,.0,bz))
            self.tube('Fine_branch',[tuple(start),tuple(start.lerp(end,.55)+Vector((0,0,.035))),tuple(end)],max(.003,h*.0035),'walnut')
            for k in range(13):
                u=.13+.87*k/12; p=start.lerp(end,u)
                ang=angle+(-1 if k%2 else 1)*self.rng.uniform(.35,1.05)
                length=h*self.rng.uniform(.085,.14); wide=length*.42
                direction=Vector((cos(ang),sin(ang),self.rng.uniform(.12,.45))).normalized()
                side=Vector((-sin(ang),cos(ang),0))
                a=len(verts); segments=7
                for t in range(segments+1):
                    f=t/segments; center=p+direction*length*f+Vector((0,0,sin(pi*f)*length*.18))
                    leafwidth=wide*sin(pi*f)**.85
                    verts.extend([tuple(center-side*leafwidth/2-Vector((0,0,leafwidth*.15))),tuple(center+Vector((0,0,leafwidth*.06))),tuple(center+side*leafwidth/2-Vector((0,0,leafwidth*.15)))])
                for t in range(segments):
                    b=a+t*3; faces.extend([(b,b+3,b+4,b+1),(b+1,b+4,b+5,b+2)])
                midribs.append([tuple(p),tuple(p+direction*length*.5+Vector((0,0,length*.18))),tuple(p+direction*length)])
        self.mesh('Individual_curved_leaves',verts,faces,'foliage',True)
        self.tube('Leaf_midribs',midribs,.0008,'foliage')

    def hanging_chair(self,kw):
        # Open egg shell: rear and sides have latitude/meridian strands; front open.
        self.tube('Weighted_stand_base',[(.63*cos(i*2*pi/64),.46*sin(i*2*pi/64),.045) for i in range(64)],.043,'black',True)
        self.tube('Curved_hanging_stand',[(0,.38,.06),(0,.57,.65),(0,.60,1.4),(0,.48,2.05),(0,.20,2.39),(0,-.03,2.40)],.045,'black')
        self.tube('Suspension_link',[(0,-.03,2.4),(0,-.03,2.22)],.014,'bronze')
        strands=[]
        # Parameterized body: sphere from bottom to top, open 120-degree front sector.
        for j in range(1,27):
            t=.09+(pi-.18)*j/27
            strands.append([(.64*sin(t)*cos(a),.53*sin(t)*sin(a),1.35+.91*cos(t)) for a in [-pi/6+4*pi/3*i/76 for i in range(77)]])
        for i in range(51):
            a=-pi/6+4*pi/3*i/50
            strands.append([(.64*sin(t)*cos(a),.53*sin(t)*sin(a),1.35+.91*cos(t)) for t in [.06+(pi-.12)*j/60 for j in range(61)]])
        self.tube('Woven_rattan_shell',strands,.009,'oak')
        rims=[]
        for a in [-pi/6,7*pi/6]: rims.append([(.64*sin(t)*cos(a),.53*sin(t)*sin(a),1.35+.91*cos(t)) for t in [pi*j/64 for j in range(65)]])
        self.tube('Bound_opening_rim',rims,.025,'walnut')
        self.pillow('Egg_seat',(0,-.08,.62),(1.01,.8,.22),'cream')
        self.pillow('Egg_back_pillow',(0,.23,.99),(.68,.18,.59),'cream',(-.2,0,0))
        self.pillow('Egg_scatter_pillow',(.18,-.01,.85),(.39,.15,.38),'taupe',(-.14,0,.2))
        self.cloth('Egg_throw',(-.19,-.11,.74),.46,.84,'taupe',.24)

    def decor(self,kw):
        self.cylinder('Tray',(0,0,.019),.27,.038,'bronze',64)
        self.cylinder('Tray_inner',(0,0,.041),.25,.012,'black',64)
        for i,(x,y) in enumerate([(-.12,-.05),(.10,.08)]):
            h=.1+i*.055
            self.cylinder('Glass_candle_vessel',(x,y,.055+h/2),.056,h,'glass',32)
            self.cylinder('Wax',(x,y,.051+h/2),.046,h-.018,'cream',32)
            self.ellipsoid('Warm_candle_flame',(x,y,h+.065),(.012,.012,.030),'emission')
        self.vase((.035,-.075,.053),.055,.22)
        self.tube('Sprigs',[[ (.035,-.075,.19),(.06,-.05,.38),(.12,-.07,.45)],[(.04,-.075,.2),(-.01,-.08,.37)]],.003,'walnut')
        for x,y,z in [( .07,-.05,.36),(.11,-.07,.41),(-.01,-.08,.34)]:
            leaf=self.ellipsoid('Sprig_leaf',(x,y,z),(.07,.028,.01),'foliage');leaf.rotation_euler=(.2,.5,.4)

    def rug(self,kw):
        w=kw.get('width',4.0);d=kw.get('depth',3.0)
        self.box('Bound_textile',(0,0,.014),(w,d,.028),'taupe',.012)
        self.box('Inset_woven_field',(0,0,.029),(w-.12,d-.12,.012),'cream',.015)
        paths=[]
        for side in [-1,1]:
            for i in range(max(20,int(w/.033))):
                x=-w/2+.03+i*.033
                paths.append([(x,side*d/2,.015),(x+.003,side*(d/2+.045),.012)])
        self.tube('Rug_end_fringe',paths,.0015,'taupe')
        self.tube('Binding_border',[(-w/2+.035,-d/2+.035,.032),(w/2-.035,-d/2+.035,.032),(w/2-.035,d/2-.035,.032),(-w/2+.035,d/2-.035,.032)],.006,'taupe',True)

    def lamp(self,kw):
        h=kw.get('height',1.5);r=.24 if h>1 else .17
        self.cylinder('Weighted_lamp_base',(0,0,.035),r*.73,.07,'bronze',48)
        self.cylinder('Lamp_stem',(0,0,h*.43),.015,h*.82,'bronze',24)
        self.lathe('Linen_lampshade',(0,0,0),[(r,h*.71),(r*.91,h*.95),(r*.60,h),(r*.57,h),(r*.85,h*.94),(r*.95,h*.72)],'cream')
        self.cylinder('Light_diffuser',(0,0,h*.735),r*.93,.018,'emission',48)
        self.tube('Shade_lower_binding',[(r*cos(i*2*pi/64),r*sin(i*2*pi/64),h*.71) for i in range(64)],.006,'bronze',True)


def build_asset(kind, name, collection, materials, **kwargs):
    """Create a furniture root, suitable for location/rotation placement.

    Optional material=palette_key on seats/tables, pot_material=palette_key on
    plants; sofa throw=False disables draped throw. No scene lights are added.
    """
    supported={'sofa','armchair','chair','stool','table','bed','cabinet','bookshelf',
               'closet','hanging_chair','plant','decor','rug','lamp'}
    if kind not in supported:
        raise ValueError('Unknown furniture kind: '+str(kind))
    b=Builder(name,collection,materials)
    b.root['asset_kind']=kind; b.root['units']='metres';b.root['front_axis']='-Y'
    if kind in {'sofa','armchair','chair','stool'}: b.seat(kind,kwargs)
    elif kind in {'bookshelf','closet'}: b.shelving(kind,kwargs)
    else: getattr(b,kind)(kwargs)
    b.root['component_count']=len(b.root.children)
    return b.root
