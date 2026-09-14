"""Metric geometry and scene utilities for the Summit Estate master."""
import bpy, math, random
from mathutils import Vector
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
M={}
CURRENT={'floor':'1F','room':'general','discipline':'ARCH'}

def collection(path):
    parent=bpy.context.scene.collection
    for part in path.split('/'):
        found=next((c for c in parent.children if c.name==part),None)
        if not found:
            found=bpy.data.collections.new(part); parent.children.link(found)
        parent=found
    return parent

def context(floor,room='general',discipline='ARCH'):
    CURRENT.update(floor=floor,room=room,discipline=discipline)
    return collection(f'{discipline}/{floor}.{room}')

def link(obj,col=None):
    for c in list(obj.users_collection):c.objects.unlink(obj)
    (col or context(**CURRENT)).objects.link(obj)
    for k,v in CURRENT.items():obj[k]=v
    return obj

def material(obj,mat):
    if mat: obj.data.materials.append(M.get(mat,mat) if isinstance(mat,str) else mat)
    return obj

def box(name,loc,dims,mat='stone',bevel=.012,col=None):
    x,y,z=(d/2 for d in dims)
    verts=[(-x,-y,-z),(-x,-y,z),(-x,y,-z),(-x,y,z),(x,-y,-z),(x,-y,z),(x,y,-z),(x,y,z)]
    faces=[(0,4,6,2),(1,3,7,5),(0,1,5,4),(2,6,7,3),(0,2,3,1),(4,5,7,6)]
    mesh=bpy.data.meshes.new(name+'.mesh');mesh.from_pydata(verts,[],faces);mesh.update()
    obj=bpy.data.objects.new(name,mesh);obj.location=loc;link(obj,col);material(obj,mat)
    if bevel:
        mod=obj.modifiers.new('Edge highlights','BEVEL');mod.width=min(bevel,min(dims)*.3);mod.segments=3
        mod=obj.modifiers.new('Weighted corner normals','WEIGHTED_NORMAL')
    return obj

def mesh(name,verts,faces,mat='stone',col=None):
    me=bpy.data.meshes.new(name+'.mesh');me.from_pydata(verts,[],faces);me.update()
    o=bpy.data.objects.new(name,me);link(o,col);material(o,mat);return o

def rod(name,a,b,r=.03,mat='black',vertices=16,col=None):
    a,b=Vector(a),Vector(b); d=b-a
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices,radius=r,depth=d.length,location=(a+b)/2)
    o=bpy.context.object;o.name=name;o.rotation_mode='QUATERNION';o.rotation_quaternion=d.to_track_quat('Z','Y');link(o,col);material(o,mat)
    for p in o.data.polygons:p.use_smooth=True
    return o

def curve(name,points,r=.03,mat='bronze',closed=False,col=None):
    cu=bpy.data.curves.new(name+'.curve','CURVE');cu.dimensions='3D';cu.resolution_u=16;cu.bevel_depth=r;cu.bevel_resolution=3
    sp=cu.splines.new('POLY');sp.points.add(len(points)-1)
    for p,co in zip(sp.points,points):p.co=(*co,1)
    sp.use_cyclic_u=closed
    o=bpy.data.objects.new(name,cu);link(o,col);material(o,mat);return o

def ring(name,loc,radius,r=.025,mat='bronze',tilt=(0,0,0)):
    o=curve(name,[(radius*math.cos(i*math.tau/128),radius*math.sin(i*math.tau/128),0) for i in range(128)],r,mat,True)
    o.location=loc;o.rotation_euler=tilt;return o

def text3d(name,body,loc,size=.18,mat='bronze',rot=(math.pi/2,0,0)):
    cu=bpy.data.curves.new(name,'FONT');cu.body=body;cu.size=size;cu.align_x='CENTER';cu.extrude=.001;cu.space_character=1.15
    o=bpy.data.objects.new(name,cu);link(o);material(o,mat);o.location=loc;o.rotation_euler=rot;return o

def area(name,loc,power=100,size=2,target=None,temperature=3000,size_y=None):
    d=bpy.data.lights.new(name,'AREA');d.energy=power;d.shape='RECTANGLE';d.size=size;d.size_y=size_y or size
    d.use_temperature=True;d.temperature=temperature
    o=bpy.data.objects.new(name,d);link(o);o.location=loc;o['lighting_layer']='ambient';o['cct_K']=temperature
    if target:o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler()
    return o

def spot(name,loc,target,power=120,angle=.9,temperature=3000):
    d=bpy.data.lights.new(name,'SPOT');d.energy=power;d.spot_size=angle;d.spot_blend=.65;d.shadow_soft_size=.08;d.use_temperature=True;d.temperature=temperature
    o=bpy.data.objects.new(name,d);link(o);o.location=loc;o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler();o['lighting_layer']='accent';o['cct_K']=temperature;return o

def strip(name,a,b,width=.028,power=0):
    o=rod(name,a,b,width/2,'emission',12)
    o['lighting_layer']='linear LED';o['cct_K']=3000
    if power:
        a,b=Vector(a),Vector(b);area(name+'.bounce',(a+b)/2,power,max((b-a).length,.1),size_y=.15)
    return o

def camera(name,loc,target,lens=28,floor='ALL',overview=False,ortho=None):
    d=bpy.data.cameras.new(name);d.lens=lens;d.clip_end=8000;d.clip_start=.05
    o=bpy.data.objects.new(name,d);collection('CAMERAS').objects.link(o);o.location=loc;o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler()
    if ortho:d.type='ORTHO';d.ortho_scale=ortho
    o['view_floor']=floor;o['overview']=overview
    return o

def asset(module,kind,name,loc,rotation=0,floor=None,room=None,**kw):
    floor=floor or CURRENT['floor'];room=room or CURRENT['room']
    col=collection(f'FURNITURE/{floor}.{room}.furniture')
    before=set(col.objects)
    o=module.build_asset(kind,name,col,M,**kw);o.location=loc;o.rotation_euler.z=rotation
    for child in set(col.objects)-before:
        child['floor']=floor;child['room']=room;child['discipline']='FURNITURE';child['asset']=name
    return o

def wall(name,a,b,z,height,thickness=.24,openings=(),mat='stone'):
    """Axis-aligned wall with explicit gaps: openings = (start,end,height)."""
    axis=0 if abs(a[0]-b[0])>abs(a[1]-b[1]) else 1
    lo,hi=sorted((a[axis],b[axis])); const=a[1-axis]
    cuts=sorted([(max(lo,s),min(hi,e),h) for s,e,h in openings])
    end=lo
    def segment(s,e,zz,hh,suffix):
        if e-s<=.001 or hh<=.001:return
        loc=[0,0,zz+hh/2];loc[axis]=(s+e)/2;loc[1-axis]=const
        dim=[thickness,thickness,hh];dim[axis]=e-s
        o=box(name+suffix,loc,dim,mat);o['role']='wall';o['thickness_m']=thickness
    for s,e,h in cuts:
        segment(end,s,z,height,'.pier');segment(s,e,z+h,height-h,'.lintel');end=e
    segment(end,hi,z,height,'.pier')

def glazing(name,a,b,z,height,bays=4,sliding=False,open_bay=None):
    axis=0 if abs(a[0]-b[0])>abs(a[1]-b[1]) else 1
    lo,hi=sorted((a[axis],b[axis]));constant=a[1-axis];w=(hi-lo)/bays
    for i in range(bays+1):
        pos=[0,0,z+height/2];pos[axis]=lo+i*w;pos[1-axis]=constant
        dim=[.07,.07,height];dim[1-axis]=.12
        box(name+f'.mullion.{i}',pos,dim,'black',.007)['role']='frame'
    for zz in [z+.035,z+height-.035]:
        pos=[0,0,zz];pos[axis]=(lo+hi)/2;pos[1-axis]=constant
        dim=[.12,.12,.07];dim[axis]=hi-lo
        box(name+'.rail',pos,dim,'black',.007)['role']='frame'
    for i in range(bays):
        if i==open_bay:continue
        pos=[0,0,z+height/2];pos[axis]=lo+(i+.5)*w;pos[1-axis]=constant+(.06 if sliding and i%2 else 0)
        dim=[.025,.025,height-.10];dim[axis]=w-.075
        o=box(name+f'.glass.{i}',pos,dim,'glass',.002);o['role']='glass';o['thickness_m']=.025;o['sliding']=sliding
        if sliding:
            side=pos.copy();side[axis]-=w*.38
            rod(name+'.pull',(side[0],side[1]-.07,z+1),(side[0],side[1]-.07,z+1.45),.016,'black')
    if open_bay is not None:
        pos=[0,0,z+height/2];pos[axis]=lo+(max(0,open_bay-1)+.5)*w;pos[1-axis]=constant+.12
        dim=[.025,.025,height-.10];dim[axis]=w-.075
        box(name+'.sliding_leaf_open',pos,dim,'glass',.002)['role']='glass'

def door(name,xy,z,width=1.2,height=2.6,axis='X',angle=0,secure=False):
    # y-facing leaf; outer assembly rotates around centre for side-facing openings.
    root=bpy.data.objects.new(name+'.hinge',None);link(root);root.location=(*xy,z);root.rotation_euler.z=math.pi/2 if axis=='Y' else 0
    for dx in [-width/2-.045,width/2+.045]:
        o=box(name+'.jamb',(dx,0,height/2),(.09,.18,height+.09),'black');o.parent=root
    o=box(name+'.head',(0,0,height+.045),(width+.18,.18,.09),'black');o.parent=root
    pivot=bpy.data.objects.new(name+'.leaf_pivot',None);link(pivot);pivot.parent=root;pivot.location=(-width/2,0,.012);pivot.rotation_euler.z=angle
    leaf=box(name+'.leaf',(width/2,0,height/2),(width-.025,.065,height-.025),'walnut',.007);leaf.parent=pivot;leaf['role']='door';leaf['clear_width_m']=width;leaf['secure']=secure
    for sx in [-1,1]:
        o=rod(name+'.pull',(width-.14,sx*.07,1),(width-.14,sx*.07,1.65),.018,'bronze');o.parent=pivot
    if secure:
        o=box(name+'.access_reader',(width/2+.22,-.11,1.35),(.13,.055,.23),'black');o.parent=root
        o=box(name+'.reader_display',(width/2+.22,-.145,1.40),(.08,.006,.055),'emission');o.parent=root
    return root

def guard(name,a,b,z,height=1.1):
    axis=0 if abs(a[0]-b[0])>abs(a[1]-b[1]) else 1
    lo,hi=sorted((a[axis],b[axis]));con=a[1-axis];n=max(1,math.ceil((hi-lo)/1.6))
    for i in range(n):
        po=[0,0,z+height/2];po[axis]=lo+(i+.5)*(hi-lo)/n;po[1-axis]=con
        di=[.02,.02,height-.10];di[axis]=(hi-lo)/n-.02
        box(name+'.laminated_panel',po,di,'glass',.003)['role']='guard'
    for i in range(n+1):
        po=[0,0,z];po[axis]=lo+i*(hi-lo)/n;po[1-axis]=con
        rod(name+'.post',po,(po[0],po[1],z+height),.018,'black')
    rod(name+'.handrail',(*a,z+height),(*b,z+height),.027,'black')
