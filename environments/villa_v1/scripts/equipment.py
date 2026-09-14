"""Summit Estate technical furnishings. Metres; floor origin; front is -Y.

Public entry: build_asset(kind, name, collection, materials, **kwargs).
Import is side-effect free. Geometry is parented locally to one returned Empty.
"""
import math
import bpy
from mathutils import Vector

PI = math.pi


def _fallback(key, color, metal=0, rough=.35):
    name = 'Equipment_' + key
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name); m.use_nodes = True
        bs = m.node_tree.nodes.get('Principled BSDF')
        bs.inputs['Base Color'].default_value = (*color[:3], 1)
        bs.inputs['Metallic'].default_value = metal
        bs.inputs['Roughness'].default_value = rough
    return m


class Builder:
    def __init__(self, name, collection, materials):
        self.name, self.col, self.mats = name, collection, dict(materials)
        self.root = bpy.data.objects.new(name, None); collection.objects.link(self.root)
        self.root.empty_display_size = .3
        for key, col, metal, rough in [
            ('black',(.018,.019,.021),.35,.24),('bronze',(.34,.22,.09),.8,.23),
            ('chrome',(.48,.51,.54),.95,.18),('cream',(.79,.75,.65),0,.6),
            ('ceramic',(.84,.85,.81),0,.19),('walnut',(.16,.065,.025),0,.38),
            ('rubber',(.016,.017,.019),0,.7),('leather',(.07,.05,.038),0,.42),
            ('marble',(.7,.7,.67),0,.2),('glass',(.08,.14,.17),.6,.12),
            ('water',(.035,.23,.26),.3,.12),('emission',(1,.65,.3),0,.3)]:
            if key not in self.mats: self.mats[key] = _fallback(key,col,metal,rough)
        self.mats.setdefault('charcoal',self.mats['rubber'])
        self.mats.setdefault('stone',self.mats['marble'])
        self.mats.setdefault('dark_marble',self.mats['black'])

    def finish(self,o,label,mat):
        o.name = self.name + '_' + label
        for c in list(o.users_collection): c.objects.unlink(o)
        self.col.objects.link(o); o.parent = self.root
        if mat: o.data.materials.append(self.mats.get(mat,mat) if isinstance(mat,str) else mat)
        return o

    def mesh(self,label,verts,faces,mat,smooth=False,bevel=0):
        me=bpy.data.meshes.new(self.name+'_'+label+'_Mesh'); me.from_pydata(verts,[],faces); me.update()
        o=bpy.data.objects.new(label,me); self.finish(o,label,mat)
        if smooth:
            for p in me.polygons:p.use_smooth=True
        if bevel:self.bevel(o,bevel)
        return o

    def bevel(self,o,r,segments=3):
        b=o.modifiers.new('Machined soft edges','BEVEL'); b.width=r;b.segments=segments
        b=o.modifiers.new('Weighted normals','WEIGHTED_NORMAL'); b.keep_sharp=True
        return o

    def box(self,label,loc,size,mat='black',r=.02,rot=None):
        x,y,z=[a/2 for a in size]
        vs=[(-x,-y,-z),(x,-y,-z),(x,y,-z),(-x,y,-z),(-x,-y,z),(x,-y,z),(x,y,z),(-x,y,z)]
        fs=[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]
        o=self.mesh(label,vs,fs,mat,bevel=min(r,min(size)*.45) if r else 0);o.location=loc
        if rot:o.rotation_euler=rot
        return o

    def uv(self,label,loc,size,mat='black',segments=32,rings=16):
        vs=[(0,0,size[2])]
        for j in range(1,rings):
            a=PI*j/rings
            for i in range(segments):
                t=2*PI*i/segments
                vs.append((size[0]*math.sin(a)*math.cos(t),size[1]*math.sin(a)*math.sin(t),size[2]*math.cos(a)))
        vs.append((0,0,-size[2]));last=len(vs)-1
        fs=[(0,1+i,1+(i+1)%segments) for i in range(segments)]
        for j in range(rings-2):
            for i in range(segments):
                a=1+j*segments+i;bb=1+j*segments+(i+1)%segments
                fs.append((a,a+segments,bb+segments,bb))
        fs.extend((last,1+(rings-2)*segments+(i+1)%segments,1+(rings-2)*segments+i) for i in range(segments))
        o=self.mesh(label,vs,fs,mat,True);o.location=loc;return o

    def cyl(self,label,a,b,r,mat='chrome',vertices=24):
        a,b=Vector(a),Vector(b);d=b-a;n=vertices
        vs=[(r*math.cos(i*2*PI/n),r*math.sin(i*2*PI/n),z) for z in [-d.length/2,d.length/2] for i in range(n)]
        fs=[tuple(reversed(range(n))),tuple(n+i for i in range(n))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
        o=self.mesh(label,vs,fs,mat);o.location=(a+b)/2
        o.rotation_euler=d.to_track_quat('Z','Y').to_euler()
        self.bevel(o,min(r*.18,.008),2)
        for p in o.data.polygons:p.use_smooth=len(p.vertices)==4
        return o

    def tube(self,label,pts,r,mat='chrome',closed=False):
        cu=bpy.data.curves.new(self.name+'_'+label,'CURVE');cu.dimensions='3D';cu.resolution_u=16
        cu.bevel_depth=r;cu.bevel_resolution=3
        s=cu.splines.new('POLY');s.points.add(len(pts)-1)
        for p,co in zip(s.points,pts):p.co=(*co,1)
        s.use_cyclic_u=closed
        return self.finish(bpy.data.objects.new(label,cu),label,mat)

    def ring(self,label,loc,major,minor,mat='chrome',axis='Z',scale=None):
        pts=[]
        for i in range(64):
            a=2*PI*i/64;u,v=major*math.cos(a),major*math.sin(a)
            if scale:u*=scale[0];v*=scale[1]
            p=(u,v,0) if axis=='Z' else ((0,u,v) if axis=='X' else (u,0,v))
            pts.append(tuple(p[j]+loc[j] for j in range(3)))
        return self.tube(label,pts,minor,mat,True)

    def bowl(self,label,center,radii,height,mat='ceramic',power=2,wall=.05):
        # One continuous hollow shell, joined across the lip. Rounded superellipse profile.
        cx,cy,cz=center;rx,ry=radii;n=64
        profiles=[(.68,0),(.84,.04),(1,height*.75),(1,height),(.96,height+.018),
                  (1-wall/min(rx,ry),height),(.83,height*.30),(.64,.08)]
        vs=[]
        for sc,z in profiles:
            for i in range(n):
                a=2*PI*i/n;co,si=math.cos(a),math.sin(a)
                vs.append((cx+rx*sc*math.copysign(abs(co)**(2/power),co),cy+ry*sc*math.copysign(abs(si)**(2/power),si),cz+z))
        fs=[]
        for j in range(len(profiles)-1):
            for i in range(n):a=j*n+i;b=j*n+(i+1)%n;fs.append((a,b,b+n,a+n))
        fs += [tuple(reversed(range(n))),tuple((len(profiles)-1)*n+i for i in range(n))]
        return self.mesh(label,vs,fs,mat,True)

    def faucet(self,x,y,z,tall=.36):
        self.cyl('Tap base',(x,y,z),(x,y,z+.018),.045,'bronze')
        pts=[(x,y,z),(x,y,z+tall-.06)]
        for i in range(9):
            t=i/8*PI/2;pts.append((x,y-.08+.08*math.cos(t),z+tall-.08+.08*math.sin(t)))
        pts.extend([(x,y-.22,z+tall),(x,y-.25,z+tall-.06)])
        self.tube('Swan neck mixer',pts,.017,'bronze')
        self.cyl('Mixer lever',(x+.04,y,z+.12),(x+.11,y,z+.12),.011,'bronze')


def _bench(b,**kw):
    for y in [-.53,.53]:
        b.box('Rubber foot',(0,y,.04),(.68,.12,.08),'rubber')
        b.cyl('Angled support',(0,y,.08),(0,y*.65,.35),.045,'black')
    b.box('Main spine',(0,0,.23),(.10,1.3,.10))
    b.box('Seat cushion',(0,-.42,.43),(.37,.43,.12),'leather',.055)
    b.box('Backrest cushion',(0,.17,.46),(.39,.74,.12),'leather',.055,(-.08,0,0))
    b.cyl('Adjustment pivot',(-.24,-.14,.33),(.24,-.14,.33),.045)
    b.cyl('Selector handle',(.2,-.14,.33),(.31,-.14,.33),.014,'bronze')
    for y in [-.15,0,.15,.3]:b.cyl('Adjustment detent',(.065,y,.23),(.071,y,.23),.015)


def _treadmill(b,**kw):
    b.box('Deck chassis',(0,0,.18),(1.02,2.12,.25),'black',.09)
    b.box('Running belt',(0,-.03,.324),(.69,1.73,.027),'rubber',.006)
    for x in [-.44,.44]:
        b.box('Side foot rail',(x,0,.345),(.14,1.9,.055),'chrome')
        b.cyl('Inclined console post',(x,-.68,.3),(x,-.90,1.23),.052,'black')
        b.tube('Hand rail',[(x,-.88,1.2),(x,-.40,1.04),(x,-.12,1.02)],.038,'black')
    for i in range(38):b.box('Belt tread',(0,-.85+i*.046,.34),(.67,.006,.002),'charcoal',0)
    b.box('Motor cowl',(0,-.86,.43),(.74,.37,.21),'black',.06)
    b.box('Console',(0,-.91,1.32),(.8,.32,.14),'black',.04,(.5,0,0))
    b.box('Console display',(0,-.975,1.391),(.43,.18,.012),'glass',.008,(.5,0,0))
    for i in range(5):b.box('Display metric',(-.15+i*.075,-1.01,1.413),(.045,.006,.005),'emission',.001)
    for x in [-.3,.3]:b.ring('Bottle cup',(x,-.85,1.40),.052,.009,'black')
    b.box('Emergency stop',(0,-.75,1.34),(.035,.035,.017),'bronze')
    for x in [-.36,.36]:
        for y in [-.72,.73]:b.box('Isolated foot',(x,y,.055),(.14,.15,.11),'rubber')


def _dumbbell(b,x,y,z,r=.09,index=0):
    b.cyl('Knurled handle',(x-.12,y,z),(x+.12,y,z),.023,'chrome')
    for side in [-1,1]:
        b.cyl('Hex weight',(x+side*.11,y,z),(x+side*.21,y,z),r,'rubber',6)
        b.cyl('Weight end cap',(x+side*.21,y,z),(x+side*.215,y,z),r*.55,'black',24)


def _dumbbell_rack(b,width=3.4,**kw):
    for x in [-width/2+.15,width/2-.15]:
        b.box('Rack foot',(x,0,.06),(.15,.9,.12))
        b.cyl('Rack upright',(x,-.26,.1),(x,.18,1.10),.046,'black')
    count=max(4,int(width/.49))
    for tier in range(3):
        y=-.24+tier*.19;z=.34+tier*.31
        b.box('Weight shelf',(0,y,z),(width,.27,.05),'black',.012)
        for side in [-1,1]:b.box('Shelf lip',(0,y+side*.12,z+.03),(width,.025,.055))
        for i in range(count):
            r=.065+.025*i/(count-1)+.012*(2-tier)
            _dumbbell(b,-width/2+.26+i*(width-.52)/(count-1),y,z+r+.028,r,i)


def _power_rack(b,**kw):
    for x in [-.68,.68]:
        b.box('Rack ground rail',(x,0,.06),(.13,1.7,.12))
        for y in [-.53,.53]:
            b.box('Perforated steel upright',(x,y,1.18),(.09,.09,2.24))
            for z in [.3+i*.095 for i in range(20)]:
                b.cyl('Adjustment aperture',(x,y-.047,z),(x,y-.05,z),.012,'chrome',12)
            b.box('Top cross member',(0,y,2.27),(1.45,.10,.1))
        b.box('Safety spotter rail',(x,0,.87),(.065,1.1,.07),'chrome')
        b.box('Barbell J hook',(x,-.57,1.40),(.12,.16,.08),'chrome')
        for z in [.45,.8,1.15]:
            b.cyl('Plate storage peg',(x,.56,z),(x,.93,z),.024)
            b.cyl('Stored plate',(x,.68,z),(x,.77,z),.20,'rubber',48)
    b.cyl('Pull up bar',(-.72,-.53,2.28),(.72,-.53,2.28),.018)
    b.cyl('Olympic bar',(-1.12,-.62,1.48),(1.12,-.62,1.48),.014)
    for s in [-1,1]:
        for i,r in enumerate([.22,.20,.16]):
            a=s*(.77+i*.065);b.cyl('Loaded bumper plate',(a,-.62,1.48),(a+s*.055,-.62,1.48),r,'rubber',48)
            b.cyl('Plate steel hub',(a,-.62,1.48),(a+s*.058,-.62,1.48),.055,'chrome')


def _cable_machine(b,**kw):
    for x in [-.78,.78]:
        b.box('Cable station foot',(x,0,.06),(.52,1.04,.12))
        b.box('Rear upright',(x,.28,1.22),(.12,.1,2.35))
        for xx in [x-.13,x+.13]:b.cyl('Weight guide',(xx,.15,.14),(xx,.15,2.25),.014)
        for i in range(17):b.box('Selectable weight plate',(x,.15,.20+i*.037),(.39,.29,.031),'black',.01)
        b.cyl('Selector pin',(x,-.02,.47),(x,-.13,.47),.015,'bronze')
        b.cyl('Front chrome guide',(x,-.33,.18),(x,-.33,2.2),.022)
        b.box('Sliding pulley carrier',(x,-.33,1.45),(.11,.15,.21))
        for z in [.20,1.45,2.2]:
            b.cyl('Pulley wheel',(x-.035,-.35,z),(x+.035,-.35,z),.072,'rubber',32)
            b.cyl('Pulley axle',(x-.043,-.35,z),(x+.043,-.35,z),.018)
        b.tube('Continuous tension cable',[(x,.15,.87),(x,.15,2.22),(x,-.36,2.22),(x,-.36,1.45),(x,-.65,1.22)],.006,'black')
        b.tube('D handle',[(x,-.65,1.22),(x-.12,-.65,1.07),(x+.12,-.65,1.07)],.013,'chrome',True)
        b.cyl('Grip',(x-.10,-.65,1.07),(x+.1,-.65,1.07),.023,'rubber')
    b.box('Upper bridge',(0,.28,2.36),(1.7,.13,.12))
    b.tube('Wide grip pullup',[(-.72,-.18,2.30),(-.45,-.10,2.42),(.45,-.10,2.42),(.72,-.18,2.30)],.019,'chrome')


def _cinema_seat(b,**kw):
    b.box('Plinth',(0,.03,.12),(.88,.91,.22),'black',.06)
    b.box('Recline seat',(0,-.10,.47),(.69,.72,.24),'leather',.105)
    b.box('Angled back cushion',(0,.32,.88),(.71,.25,.84),'leather',.105,(-.17,0,0))
    b.box('Lumbar cushion',(0,.155,.70),(.57,.17,.24),'leather',.08,(-.17,0,0))
    b.box('Headrest',(0,.33,1.20),(.63,.24,.22),'leather',.085,(-.17,0,0))
    b.box('Extended footrest',(0,-.59,.31),(.69,.42,.16),'leather',.065,(-.24,0,0))
    for x in [-.47,.47]:
        b.box('Upholstered arm',(x,-.04,.43),(.23,.93,.71),'leather',.075)
        b.box('Soft arm pad',(x,-.08,.80),(.245,.83,.10),'leather',.045)
        b.cyl('Cupholder dark well',(x,-.29,.835),(x,-.29,.852),.058,'black')
        b.ring('Cupholder rim',(x,-.29,.853),.060,.008,'chrome')
        b.box('Recline controls',(x,-.41,.80),(.075,.06,.012),'bronze',.008)
    for x in [-.28,.28]:
        b.tube('Seat piping',[(x,-.4,.575),(x,.11,.575),(x,.24,.82),(x,.37,1.25)],.003,'black')
    for x in [-.16,.16]:b.tube('Back stitched channel',[(x,.182,.78),(x,.285,1.18)],.002,'black')


def _piano(b,**kw):
    # Bezier-sampled grand perimeter: straight bass edge and curved treble cheek.
    control=[(-.75,-.65),(-.76,.45),(-.72,1.02),(-.48,1.31),(-.08,1.40),(.28,1.23),(.34,.80),(.52,.30),(.74,.05),(.75,-.65)]
    pts=[]
    for i in range(len(control)):
        p0=Vector(control[(i-1)%len(control)]);p1=Vector(control[i]);p2=Vector(control[(i+1)%len(control)]);p3=Vector(control[(i+2)%len(control)])
        for j in range(8):
            t=j/8;v=.5*((2*p1)+(-p0+p2)*t+(2*p0-5*p1+4*p2-p3)*t*t+(-p0+3*p1-3*p2+p3)*t**3);pts.append(tuple(v))
    n=len(pts);vs=[(x,y,z) for z in [.76,1.00] for x,y in pts]
    fs=[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]+[tuple(reversed(range(n)))]
    b.mesh('Curved grand piano rim',vs,fs,'black',True)
    b.mesh('Golden soundboard',[(x*.94,y*.96,.83) for x,y in pts],[tuple(range(n))],'bronze')
    for i in range(40):
        x=-.65+i*.031;length=1.45-.62*(x+.65)
        b.cyl('Piano string',(x,-.42,.858),(x,-.42+length,.858),.0015,'chrome',8)
    for x in [-.55,-.2,.17]:b.cyl('Cast iron harp strut',(x,-.4,.87),(x,1.05-.6*(x+.55),.87),.018,'bronze')
    # Lid opens along left-side hinge; top edge rises toward treble side.
    lidvs=[(x,y,1.015+(x+.75)*.63+dz) for dz in [0,.035] for x,y in pts]
    lidfs=[tuple(reversed(range(n))),tuple(n+i for i in range(n))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    b.mesh('Raised sculpted lid',lidvs,lidfs,'black',bevel=.012)
    b.cyl('Lid prop',(.53,.16,.92),(.53,.16,1.83),.018,'black')
    b.box('Keyboard bed',(0,-.82,.755),(1.55,.43,.12),'black',.025)
    for i in range(52):
        x=-.712+i*.0279;b.box('Ivory key',(x,-.835,.838),(.0267,.31,.023),'ceramic',.002)
        if i%7 in [0,1,3,4,5] and i<51:b.box('Ebony key',(x+.014,-.752,.866),(.016,.17,.035),'black',.002)
    b.box('Fallboard',(0,-.625,.965),(1.43,.055,.19),'black',.018)
    b.box('Music desk',(0,-.35,1.18),(.72,.045,.34),'black',.015,(-.18,0,0))
    b.box('Music desk ledge',(0,-.40,1.03),(.73,.13,.035),'black')
    for x,y in [(-.64,-.59),(.64,-.59),(-.24,1.08)]:
        b.cyl('Tapered leg',(x,y,.11),(x,y,.78),.058,'black')
        b.cyl('Brass caster stem',(x,y,.05),(x,y,.15),.024,'bronze')
        b.cyl('Caster wheel',(x-.025,y,.048),(x+.025,y,.048),.048,'bronze')
    for x in [-.13,.13]:b.cyl('Pedal lyre upright',(x,-.52,.18),(x,-.52,.74),.021,'black')
    b.box('Pedal lyre foot',(0,-.52,.16),(.37,.15,.06),'black')
    for x in [-.11,0,.11]:b.uv('Brass pedal',(x,-.66,.125),(.035,.13,.018),'bronze')
    b.box('Pianist bench',(0,-1.38,.49),(.91,.39,.12),'leather',.055)
    for x in [-.37,.37]:
        for y in [-1.5,-1.26]:b.box('Bench leg',(x,y,.24),(.045,.045,.46),'black')


def _car(b,style='sport',color=(.045,.055,.06),**kw):
    classic=style=='classic';L=4.65 if classic else 4.55;W=1.79 if classic else 1.96
    paint=_fallback('Paint_'+b.name,tuple(color),.67,.20)
    bs=paint.node_tree.nodes.get('Principled BSDF');bs.inputs['Coat Weight'].default_value=.65
    b.mats['paint']=paint
    glass=_fallback('Automotive smoked glazing',(.034,.063,.073),.65,.12);b.mats['car_glass']=glass
    wheel_y=[-1.38,1.36];wr=.34 if classic else .365
    # Upper body loft, interpolated rounded fenders and genuinely open wheel cutouts.
    ys=[-L/2+i*L/64 for i in range(65)];verts=[];nx=20
    widths=[];tops=[]
    for y in ys:
        end=abs(y)/(L/2);width=W/2*(1-.20*end**6);widths.append(width)
        top=(.82 if classic else .76)+.085*math.exp(-((y+1.38)/.63)**2)+.10*math.exp(-((y-1.36)/.61)**2)
        tops.append(top)
        for j in range(nx+1):
            u=-1+2*j/nx;x=u*width
            z=top+.10*(1-u*u)+.09*math.exp(-((abs(u)-.82)/.22)**2)
            verts.append((x,y,z))
    faces=[]
    for i in range(64):
        for j in range(nx):a=i*(nx+1)+j;faces.append((a,a+1,a+nx+2,a+nx+1))
    b.mesh('Continuous sculpted hood fenders rear deck',verts,faces,'paint',True)
    for s in [-1,1]:
        vs=[]
        for i,y in enumerate(ys):
            arch=.24
            for wy in wheel_y:
                d=abs(y-wy)
                if d<wr+.055:arch=max(arch,wr+.018+math.sqrt((wr+.055)**2-d*d))
            edge=tops[i]+.09*math.exp(-((1-.82)/.22)**2)
            # Open arch rim has a high fender crown; avoids a flat box over the tire.
            top=max(edge,arch+.07)
            vs.extend([(s*widths[i],y,edge),(s*(widths[i]+.013),y,(top+arch)/2),(s*(widths[i]-.027),y,arch)])
        fs=[]
        for i in range(64):
            for j in range(2):a=i*3+j;fs.append((a,a+3,a+4,a+1))
        b.mesh('Sculpted side with open wheel arches',vs,fs,'paint',True)
        for wy in wheel_y:
            pts=[(s*(W/2+.002),wy+(wr+.065)*math.cos(a),wr+.018+(wr+.065)*math.sin(a)) for a in [PI*i/48 for i in range(49)]]
            b.tube('Wheel arch rolled lip',pts,.014,'chrome' if classic else 'paint')
        b.box('Rocker sill',(s*(W/2-.045),0,.24),(.09,1.80,.1),'chrome' if classic else 'black',.04)
    # Front and rear sculpted fascia cap lofts.
    for idx,y in [(0,-L/2),(64,L/2)]:
        w=widths[idx];z=tops[idx]
        vs=[(-w,y,.27),(-w,y,z),(0,y,z+.10),(w,y,z),(w,y,.27),(0,y-.025 if idx==0 else y+.025,.23)]
        b.mesh('Curved end fascia',vs,[tuple(range(6))],'paint',bevel=.025)
    # Glazed cabin, broad sloping windscreen, formed roof and pillar frames.
    yf=-.80 if classic else -.88;yr=1.00 if classic else .94;roof_z=1.37 if classic else 1.28
    stations=[(yf,.75,.91),(-.26,.64,roof_z),(.52,.64,roof_z+.025),(yr,.76,.93)]
    for si in range(3):
        vs=[]
        for y,hw,z in stations[si:si+2]:
            for j in range(17):u=-1+j/8;vs.append((u*hw,y,z+.035*(1-u*u)))
        fs=[(j,j+1,j+18,j+17) for j in range(16)]
        b.mesh('Formed roof' if si==1 else ('Windscreen' if si==0 else 'Rear window'),vs,fs,'paint' if si==1 else 'car_glass',True)
    for s in [-1,1]:
        line=[(s*hw,y,z) for y,hw,z in stations]
        b.mesh('Side window glazing',[line[0],line[1],line[2],line[3]],[(0,1,2,3)],'car_glass')
        b.tube('Window perimeter',line+[line[0]],.016,'chrome' if classic else 'black')
        b.cyl('B pillar',(s*.73,.33,.925),(s*.64,.33,roof_z+.02),.025,'paint')
        b.tube('Door shut line',[(s*(W/2+.012),-.77,.82),(s*(W/2+.012),-.62,.34),(s*(W/2+.012),.77,.34),(s*(W/2+.012),.92,.83)],.004,'black')
        b.box('Door handle',(s*(W/2+.024),.54,.77),(.025,.17,.025),'chrome',.012)
        b.cyl('Mirror stalk',(s*.76,-.70,.99),(s*1.01,-.72,1.01),.018,'chrome' if classic else 'black')
        b.uv('Sculpted door mirror',(s*1.035,-.73,1.04),(.13,.10,.065),'paint')
        b.uv('Mirror glass',(s*1.035,-.658,1.044),(.10,.012,.045),'chrome')
        for wy in wheel_y:
            x=s*(W/2-.02)
            b.ring('Rounded tire',(x,wy,wr),wr-.066,.075,'rubber','X')
            b.cyl('Tire barrel',(x-.105,wy,wr),(x+.105,wy,wr),wr-.045,'rubber',48)
            xx=s*(W/2+.061)
            b.ring('Polished rim',(xx,wy,wr),wr-.097,.020,'chrome','X')
            b.cyl('Brake disc',(xx-s*.022,wy,wr),(xx-s*.031,wy,wr),wr-.12,'chrome',48)
            b.cyl('Wheel hub',(xx,wy,wr),(xx+s*.021,wy,wr),.065,'chrome')
            spokes=28 if classic else 10
            for i in range(spokes):
                a=2*PI*i/spokes
                b.cyl('Wire spoke' if classic else 'Forged spoke',(xx+s*.012,wy+.049*math.cos(a),wr+.049*math.sin(a)),(xx,wy+(wr-.106)*math.cos(a+.15),wr+(wr-.106)*math.sin(a+.15)),.006 if classic else .013,'chrome',8)
            b.box('Brake caliper',(xx-s*.046,wy+.17,wr),(.06,.08,.18),'bronze',.02)
            for i in range(5):
                a=i*2*PI/5;b.cyl('Lug bolt',(xx+s*.015,wy+.043*math.cos(a),wr+.043*math.sin(a)),(xx+s*.028,wy+.043*math.cos(a),wr+.043*math.sin(a)),.009,'black',6)
    front=-L/2-.018
    if classic:
        b.uv('Oval chrome grille surround',(0,front,.47),(.55,.045,.205),'chrome')
        b.uv('Recessed grille',(0,front-.035,.47),(.51,.028,.17),'black')
        for i in range(13):b.cyl('Grille vertical slat',(-.43+i*.071,front-.059,.36),(-.43+i*.071,front-.059,.57),.006,'chrome',8)
        for x in [-.66,.66]:
            b.cyl('Round headlamp bezel',(x,front+.015,.76),(x,front-.046,.76),.125,'chrome',48)
            b.cyl('Fluted headlamp lens',(x,front-.045,.76),(x,front-.053,.76),.106,'ceramic',48)
            b.cyl('Amber marker',(x,front-.01,.52),(x,front-.04,.52),.035,'bronze')
        b.tube('Wraparound chrome bumper',[(-.80,front+.11,.30),(-.72,front-.055,.30),(0,front-.07,.30),(.72,front-.055,.30),(.80,front+.11,.30)],.028,'chrome')
    else:
        for x in [-.58,0,.58]:
            b.box('Front air intake',(x,front-.004,.42),(.44,.055,.25),'black',.052)
            for j in range(5):b.box('Intake grille slat',(x,front-.036,.33+j*.04),(.38,.012,.009),'chrome',.003)
        for x in [-.68,.68]:
            b.box('LED headlamp housing',(x,front+.025,.77),(.33,.10,.095),'black',.035)
            for z in [.745,.778]:b.box('LED blade',(x,front-.030,z),(.28,.01,.009),'ceramic',.004)
        b.box('Front carbon splitter',(0,front-.025,.24),(1.67,.20,.045),'black',.018)
        for x in [-.60,.60]:
            for j in range(4):b.box('Hood extractor',(x,-1.18+j*.075,.963),(.19,.028,.012),'black',.007)
        for x in [-.58,.58]:b.box('Rear wing stanchion',(x,1.88,.99),(.06,.16,.27),'black')
        b.box('Rear aerofoil',(0,1.9,1.135),(1.65,.25,.055),'paint',.024)
    for x in [-.63,.63]:
        b.box('Rear taillight',(x,L/2+.01,.74),(.34,.04,.07),'bronze',.018)
        b.cyl('Exhaust tip',(x,L/2-.05,.30),(x,L/2+.13,.30),.045,'chrome')
        b.cyl('Exhaust opening',(x,L/2+.132,.30),(x,L/2+.135,.30),.033,'black')
    b.box('License plaque',(0,front-.047,.57),(.29,.018,.075),'black',.005)
    # Dark interior pieces readable through reflective glazing edges.
    for x in [-.36,.36]:
        b.box('Seat cushion',(x,.05,.65),(.45,.47,.12),'leather',.07)
        b.box('Bucket back',(x,.33,.94),(.44,.14,.51),'leather',.09,(-.13,0,0))
    b.ring('Steering wheel',(-.36,-.40,1.03),.145,.016,'black','Y')


def _kitchen(b,width=8,island=False,**kw):
    if island:
        depth=1.15
        b.box('Island walnut carcass',(0,0,.47),(width-.10,depth-.08,.86),'walnut',.016)
        b.box('Waterfall stone top',(0,0,.94),(width,depth,.075),'marble',.012)
        for x in [-width/2+.035,width/2-.035]:b.box('Waterfall stone end',(x,0,.48),(.07,depth,.92),'marble',.009)
        count=max(3,int(width/.65));step=(width-.16)/count
        for i in range(count):
            x=-width/2+.08+step*(i+.5)
            for y in [-depth/2+.025,depth/2-.025]:
                b.box('Island drawer front',(x,y,.52),(step-.018,.028,.71),'walnut',.006)
                b.box('Recessed pull',(x,y*1.04,.80),(step-.08,.025,.015),'black',.003)
        b.box('Cutting board',(width*.25,0,1.002),(.45,.32,.028),'walnut',.035)
        b.bowl('Fruit bowl',(width*.25,0,1.018),(.17,.17),.07,'ceramic')
        for i in range(5):b.uv('Bowl fruit',(width*.25+.07*math.cos(i*1.5),.06*math.sin(i*1.5),1.10),(.042,.04,.041),'bronze')
        return
    depth=.68;tall=min(1.45,width*.25);cw=width-tall;left=-width/2;right=width/2
    b.box('Cabinet plinth',(0,.03,.075),(width-.08,.51,.15),'black')
    b.box('Base cabinetry',(-tall/2,0,.49),(cw,.62,.81),'walnut')
    # Top is segmented around actual sink opening.
    sx=left+cw*.32;sw=.68;sy=-.04;sd=.43;z=.94
    for xa,xb in [(left,sx-sw/2),(sx+sw/2,left+cw)]:
        if xb>xa:b.box('Stone worktop',((xa+xb)/2,0,z),(xb-xa,depth,.055),'marble',.008)
    for ya,yb in [(-depth/2,sy-sd/2),(sy+sd/2,depth/2)]:b.box('Sink top bridge',(sx,(ya+yb)/2,z),(sw,yb-ya,.055),'marble',.008)
    b.bowl('Undermount sink',(sx,sy,.70),(sw/2,sd/2),.237,'chrome',power=6,wall=.015)
    b.faucet(sx,.23,.965,.35)
    b.cyl('Sink drain',(sx,sy,.775),(sx,sy,.779),.03,'chrome')
    count=max(3,int(cw/.65));step=cw/count
    for i in range(count):
        x=left+step*(i+.5)
        for j in range(3):
            b.box('Drawer front',(x,-.323,.29+j*.255),(step-.02,.035,.24),'walnut',.005)
            b.box('Handle recess',(x,-.349,.38+j*.255),(step-.09,.018,.016),'black',.002)
    cookx=left+cw*.77
    b.box('Induction cooktop',(cookx,0,.977),(.79,.49,.018),'black',.018)
    for dx in [-.21,.21]:
        for dy in [-.13,.13]:
            b.ring('Induction zone',(cookx+dx,dy,.989),.083,.002,'chrome')
            b.ring('Induction inner zone',(cookx+dx,dy,.989),.06,.001,'chrome')
    b.box('Oven glazing',(cookx,-.348,.50),(.58,.026,.49),'glass',.016)
    b.box('Oven stainless fascia',(cookx,-.354,.79),(.59,.03,.09),'chrome',.006)
    b.cyl('Oven pull',(cookx-.23,-.40,.715),(cookx+.23,-.40,.715),.014)
    for x in [cookx-.20,cookx+.20]:b.cyl('Oven control',(x,-.377,.79),(x,-.395,.79),.024)
    b.box('Stone backsplash',(-tall/2,.336,1.28),(cw,.035,.62),'marble',.004)
    b.box('Upper cabinet body',(-tall/2,.15,2.08),(cw,.40,.89),'walnut')
    for i in range(count):
        x=left+step*(i+.5);b.box('Upper door',(x,-.066,2.08),(step-.018,.029,.865),'walnut',.005)
    b.box('Under cabinet task diffuser',(-tall/2,-.025,1.62),(cw-.06,.026,.014),'emission',.003)
    fx=right-tall/2;b.box('Integrated refrigerator body',(fx,.02,1.29),(tall,.66,2.49),'black')
    for side in [-1,1]:
        x=fx+side*tall*.25;b.box('Brushed refrigerator door',(x,-.332,1.33),(tall/2-.014,.065,2.36),'chrome',.018)
        b.cyl('Refrigerator pull',(fx+side*.055,-.397,.89),(fx+side*.055,-.397,1.64),.014,'chrome')
    b.box('Refrigerator screen',(fx+tall*.23,-.369,1.58),(.16,.012,.23),'glass',.008)
    # Espresso station on spare counter.
    ex=left+.36;b.box('Espresso machine',(ex,0,1.14),(.36,.34,.32),'chrome',.035)
    b.box('Espresso black face',(ex,-.18,1.14),(.31,.015,.24),'black',.008)
    b.box('Drip tray',(ex,-.23,1.00),(.31,.17,.025),'chrome',.007)
    for dx in [-.09,.09]:
        b.cyl('Coffee spout',(ex+dx,-.21,1.16),(ex+dx,-.21,1.09),.01)
        b.bowl('Coffee cup',(ex+dx,-.23,1.013),(.035,.035),.06,'ceramic',wall=.007)


def _laundry(b,width=3.6,**kw):
    count=4;step=width/count
    b.box('Continuous stone folding counter',(0,0,.97),(width,.76,.07),'marble',.012)
    for i in range(count):
        x=-width/2+step*(i+.5)
        b.box('Front loading appliance',(x,0,.46),(step-.045,.69,.9),'ceramic',.045)
        b.box('Appliance fascia',(x,-.353,.79),(step-.09,.019,.14),'chrome',.008)
        b.cyl('Program dial',(x-step*.28,-.371,.80),(x-step*.28,-.39,.80),.034,'chrome')
        b.box('Cycle display',(x+step*.12,-.369,.8),(.16,.015,.05),'glass',.004)
        b.cyl('Door dark drum',(x,-.356,.43),(x,-.38,.43),.253,'black',48)
        b.ring('Door steel ring',(x,-.387,.43),.25,.030,'chrome','Y')
        b.uv('Convex smoked door glass',(x,-.395,.43),(.216,.039,.216),'glass')
        b.tube('Door grab',[(x+.19,-.423,.34),(x+.21,-.423,.43),(x+.19,-.423,.52)],.014,'chrome')
        b.box('Upper cabinet',(x,.12,1.98),(step-.02,.49,.94),'walnut')
        b.box('Upper front',(x,-.14,1.98),(step-.045,.03,.91),'walnut',.005)
        b.cyl('Upper pull',(x+step*.3,-.18,1.66),(x+step*.3,-.18,1.86),.010,'bronze')
        for j in range(3):b.box('Folded linen',(x,.03,1.035+j*.045),(.42,.31,.041),'cream',.018)
    b.box('Task light',(0,-.06,1.496),(width-.1,.03,.015),'emission',.003)


def _tub(b,**kw):
    b.bowl('Freestanding oval bath',(0,0,0),(1.00,.47),.64,'ceramic',power=2.6,wall=.07)
    b.cyl('Waste drain',(.48,0,.08),(.48,0,.085),.026,'chrome')
    b.faucet(-.86,.49,0,.91)
    b.cyl('Floor mixer pedestal',(-.86,.49,0),(-.86,.49,.61),.027,'bronze')
    b.cyl('Overflow insert',(.93,0,.49),(.942,0,.49),.025,'chrome')


def _hot_tub(b,width=2.7,**kw):
    r=width/2
    b.box('Spa insulated base',(0,0,.06),(width-.1,width-.1,.12),'walnut',.05)
    for side in [-1,1]:
        b.box('Spa side casing',(side*(r-.10),0,.39),(.13,width-.1,.66),'walnut',.045)
        b.box('Spa end casing',(0,side*(r-.10),.39),(width-.1,.13,.66),'walnut',.045)
    for side in [-1,1]:
        for i in range(19):
            x=-r+.15+i*(width-.3)/18
            b.box('Spa vertical cabinet slat',(x,side*(r-.045),.40),(.07,.035,.69),'walnut',.009)
            b.box('Spa vertical cabinet slat',(side*(r-.045),x,.40),(.035,.07,.69),'walnut',.009)
    # The shell includes a true depressed floor and seating ledge profile.
    n=96;profiles=[(.92,.12),(.99,.72),(1,.85),(.97,.91),(.84,.89),(.79,.72),(.77,.43),(.60,.40),(.51,.17)]
    vs=[]
    for sc,z in profiles:
        for i in range(n):
            a=i*2*PI/n;c,s=math.cos(a),math.sin(a)
            vs.append((r*sc*math.copysign(abs(c)**.4,c),r*sc*math.copysign(abs(s)**.4,s),z))
    fs=[]
    for j in range(len(profiles)-1):
        for i in range(n):a=j*n+i;bb=j*n+(i+1)%n;fs.append((a,bb,bb+n,a+n))
    fs.append(tuple((len(profiles)-1)*n+i for i in range(n)))
    b.mesh('Contoured spa shell basin and seat bench',vs,fs,'ceramic',True)
    # Water surface uses a fine analytic ripple mesh clipped to rounded square.
    N=36;vs=[]
    for j in range(N+1):
        v=-1+2*j/N
        for i in range(N+1):
            u=-1+2*i/N;x=u*r*.805*math.sqrt(1-.15*v**8);y=v*r*.805*math.sqrt(1-.15*u**8)
            z=.73+.004*math.sin(x*25+y*14)+.003*math.sin(x*13-y*23);vs.append((x,y,z))
    fs=[(j*(N+1)+i,j*(N+1)+i+1,(j+1)*(N+1)+i+1,(j+1)*(N+1)+i) for j in range(N) for i in range(N)]
    b.mesh('Rippled spa water',vs,fs,'water',True)
    for side in [-1,1]:
        for x in [-r*.46,r*.46]:
            b.box('Spa headrest',(x,side*r*.85,.865),(.37,.20,.09),'charcoal',.044)
            for dx in [-.09,.09]:
                b.cyl('Hydrotherapy jet',(x+dx,side*r*.79,.62),(x+dx,side*r*.775,.62),.030,'chrome')
                b.cyl('Jet nozzle',(x+dx,side*r*.774,.62),(x+dx,side*r*.770,.62),.013,'black')
        b.ring('Spa cup holder',(side*r*.72,-r*.89,.899),.057,.007,'chrome')
        b.cyl('Spa cup well',(side*r*.72,-r*.89,.885),(side*r*.72,-r*.89,.895),.052,'black')
    b.box('Spa control panel',(0,-r*.92,.904),(.23,.105,.018),'black',.009)
    b.box('Spa control display',(0,-r*.935,.914),(.10,.038,.005),'glass',.003)
    for i in [-1,1]:b.cyl('Spa control button',(i*.078,-r*.92,.91),(i*.078,-r*.92,.921),.013,'chrome')
    for z,y in [(.12,-r-.31),(.30,-r-.16)]:b.box('Spa access step',(0,y,z),(1.2,.40,z*2),'walnut',.035)


def _vanity(b,width=3,**kw):
    b.box('Floating vanity cabinet',(0,0,.57),(width,.61,.47),'walnut',.013)
    b.box('Stone vanity top',(0,0,.845),(width+.035,.66,.065),'marble',.009)
    count=max(2,int(width/.55));step=width/count
    for i in range(count):
        x=-width/2+step*(i+.5);b.box('Handleless vanity door',(x,-.321,.57),(step-.016,.025,.435),'walnut',.006)
    b.box('Open towel shelf',(0,0,.20),(width-.05,.57,.035),'walnut')
    for x in [-width*.33,0,width*.33]:
        for z in [.25,.30]:b.box('Folded hand towel',(x,-.03,z),(.38,.30,.045),'cream',.018)
    b.box('Concealed vanity light',(0,-.21,.325),(width-.1,.02,.012),'emission',.003)
    basins=2 if width>=2 else 1
    for i in range(basins):
        x=(i-(basins-1)/2)*width*.48
        b.bowl('Vessel washbasin',(x,-.015,.881),(.32,.215),.15,'ceramic',power=2.4,wall=.025)
        b.cyl('Basin drain',(x,-.015,.962),(x,-.015,.965),.018,'chrome')
        b.faucet(x,.24,.88,.31)
        b.box('Backlit mirror glow',(x,.349,1.66),(min(width/basins-.11,1.22),.02,1.38),'emission',.08)
        b.box('Mirror bronze frame',(x,.329,1.66),(min(width/basins-.13,1.20),.025,1.36),'bronze',.08)
        b.box('Mirror face',(x,.312,1.66),(min(width/basins-.16,1.17),.008,1.33),'chrome',.075)
        b.cyl('Soap bottle',(x+.40,.15,.88),(x+.40,.15,1.05),.032,'black')
        b.cyl('Soap pump',(x+.40,.15,1.05),(x+.40,.15,1.10),.008,'bronze')


def _shower(b,width=1.7,depth=1.4,**kw):
    b.box('Shower tray',(0,0,.035),(width,depth,.07),'stone',.013)
    b.box('Linear shower drain',(0,depth/2-.12,.074),(width-.23,.055,.012),'black',.005)
    for i in range(24):b.box('Drain grille',(-width/2+.15+i*(width-.3)/23,depth/2-.12,.082),(.011,.048,.006),'chrome',.001)
    for x in [-width/2,width/2]:
        b.box('Fixed clear glass',(x,0,1.19),(.012,depth,2.3),'glass',.002)
        for y in [-depth/2+.06,depth/2-.06]:
            for z in [.23,2.02]:b.box('Glass bronze clamp',(x,y,z),(.05,.042,.06),'bronze',.006)
        b.cyl('Top screen stabilizer',(x,-depth/2,2.30),(x,depth/2,2.30),.012,'black')
    b.cyl('Rain head riser',(0,depth/2-.08,1.0),(0,depth/2-.08,2.35),.018,'bronze')
    b.cyl('Rain head arm',(0,depth/2-.08,2.35),(0,.05,2.35),.018,'bronze')
    b.box('Rain shower head',(0,.05,2.32),(.42,.42,.045),'bronze',.012)
    for i in range(8):
        for j in range(8):b.cyl('Rain nozzle',(-.17+i*.048,-.12+j*.048,2.295),(-.17+i*.048,-.12+j*.048,2.285),.003,'black',8)
    for x in [-.18,.18]:b.cyl('Thermostatic control',(x,depth/2-.04,1.10),(x,depth/2-.11,1.10),.037,'bronze')
    b.tube('Hand shower hose',[(.3,depth/2-.10,1.02),(.4,depth/2-.16,.5),(.55,depth/2-.16,.53),(.50,depth/2-.12,1.36)],.008,'bronze')
    b.cyl('Hand shower wand',(.50,depth/2-.12,1.29),(.50,depth/2-.12,1.53),.020,'bronze')


def _toilet(b,**kw):
    b.uv('Ceramic pedestal',(0,.04,.22),(.205,.25,.22),'ceramic')
    b.bowl('WC bowl',(0,-.08,.20),(.235,.33),.23,'ceramic',power=2.3,wall=.045)
    b.ring('Seat ring',(0,-.08,.445),1,.025,'ceramic',scale=(.215,.30))
    b.uv('Closed soft close lid',(0,-.065,.465),(.223,.313,.022),'ceramic')
    b.box('Concealed cistern casing',(0,.285,.47),(.42,.18,.89),'ceramic',.055)
    b.box('Dual flush plate',(0,.187,.77),(.18,.012,.105),'chrome',.012)
    for x in [-.045,.045]:b.cyl('Flush button',(x,.178,.77),(x,.17,.77),.028,'chrome')


def _shoe(b,x,y,z,side=1,style=0):
    # Plan-shaped sole outline and lofted upper; toe faces -Y, heel +Y.
    outline=[(-.045,.135),(-.056,.09),(-.063,-.035),(-.065,-.12),(-.035,-.165),(.025,-.172),(.061,-.135),(.06,-.02),(.045,.13)]
    n=len(outline);vs=[]
    for zz,sc in [(0,.95),(.015,1),(.035,.97)]:
        for xx,yy in outline:vs.append((x+xx*sc,y+yy,z+zz))
    fs=[tuple(reversed(range(n))),tuple(2*n+i for i in range(n))]
    fs += [(k*n+i,k*n+(i+1)%n,(k+1)*n+(i+1)%n,(k+1)*n+i) for k in range(2) for i in range(n)]
    b.mesh('Shaped sneaker sole',vs,fs,'ceramic',True,bevel=.006)
    stations=[(-.156,.021,.046),(-.125,.052,.060),(-.05,.057,.083),(.025,.050,.12),(.09,.044,.14),(.126,.037,.115)]
    vs=[]
    for yy,hw,hh in stations:
        for j in range(13):
            a=j*PI/12;vs.append((x+hw*math.cos(a),y+yy,z+.034+hh*math.sin(a)))
    fs=[(i*13+j,i*13+j+1,(i+1)*13+j+1,(i+1)*13+j) for i in range(len(stations)-1) for j in range(12)]
    fs.extend([tuple(reversed(range(13))),tuple((len(stations)-1)*13+j for j in range(13))])
    b.mesh('Sculpted sneaker upper',vs,fs,'cream' if style%2 else 'leather',True)
    b.ring('Padded ankle collar',(x,y+.068,z+.139),.039,.01,'black',scale=(1,.9))
    b.uv('Dark ankle opening',(x,y+.068,z+.139),(.029,.027,.008),'black')
    for j in range(5):
        yy=y-.054+j*.021;zz=z+.107+j*.009
        b.tube('Crossed lace',[(x-.032,yy,zz),(x+.031,yy+.015,zz+.005)],.0025,'ceramic')
        b.tube('Crossed lace',[(x+.032,yy,zz),(x-.031,yy+.015,zz+.005)],.0025,'ceramic')
    for s in [-1,1]:b.tube('Upper stitched panel',[(x+s*.051,y-.115,z+.061),(x+s*.057,y-.05,z+.058),(x+s*.042,y+.10,z+.090)],.0015,'bronze')


def _shoe_display(b,width=5,**kw):
    height=2.55;cols=max(3,int(width/.85));step=width/cols
    b.box('Boutique walnut back',(0,.24,height/2),(width,.055,height),'walnut')
    for i in range(cols+1):b.box('Gallery vertical divider',(-width/2+i*step,0,height/2),(.045,.52,height),'walnut')
    for row in range(6):
        z=.10+row*.475;b.box('Display shelf',(0,0,z),(width,.52,.038),'walnut',.007)
        if row<5:
            b.box('Warm shelf light',(0,-.19,z+.028),(width-.07,.018,.011),'emission',.002)
            for i in range(cols):
                x=-width/2+step*(i+.5)
                for side in [-1,1]:_shoe(b,x+side*.10,-.02,z+.023,side,row+i)
    b.box('Display top',(0,0,height),(width,.52,.045),'walnut')


_BUILDERS={'piano':_piano,'treadmill':_treadmill,'dumbbell_rack':_dumbbell_rack,
           'power_rack':_power_rack,'cable_machine':_cable_machine,'gym_bench':_bench,
           'cinema_seat':_cinema_seat,'car':_car,'kitchen':_kitchen,'laundry':_laundry,
           'tub':_tub,'hot_tub':_hot_tub,'vanity':_vanity,'shower':_shower,
           'toilet':_toilet,'shoe_display':_shoe_display}


def build_asset(kind,name,collection,materials,**kwargs):
    """Create a detailed editable asset; returned Empty controls all local children.

    Optional: width for rack/kitchen/laundry/vanity/shower/shoe_display/hot_tub;
    depth for shower; island=True for waterfall kitchen island;
    style='classic' or 'sport', color=(r,g,b) for original unbranded vehicles.
    """
    if kind not in _BUILDERS:raise ValueError('Unknown equipment kind: '+str(kind))
    b=Builder(name,collection,materials);b.root['asset_kind']=kind
    b.root['front_axis']='-Y';b.root['units']='metres'
    _BUILDERS[kind](b,**kwargs)
    return b.root
