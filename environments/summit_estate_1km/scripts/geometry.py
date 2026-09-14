"""Small deterministic scene graph with separate visual and collision export.

All geometry is metric, right handed, Z up. Static visuals are batched by
material; structural collisions remain named primitives or explicit triangle
meshes. The generator never downloads assets or writes outside its output root.
"""
from collections import defaultdict
import gzip
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np

COLORS = {
    'ivory': (.88,.87,.81,1), 'plaster':(.78,.77,.71,1),
    'charcoal':(.045,.054,.060,1), 'glass':(.36,.58,.63,.22),
    'stone':(.42,.43,.39,1), 'paving':(.53,.53,.49,1),
    'asphalt':(.12,.135,.145,1), 'grass':(.22,.30,.12,1),
    'grass_light':(.29,.37,.16,1), 'grass_dark':(.14,.22,.085,1),
    'rock':(.34,.355,.32,1), 'wood':(.30,.18,.095,1),
    'brass':(.68,.48,.22,1), 'metal':(.21,.23,.24,1),
    'water':(.075,.24,.30,1), 'pool_water':(.08,.56,.67,.87),
    'court':(.045,.105,.18,1), 'court_key':(.12,.22,.31,1),
    'white':(.93,.93,.89,1), 'sand':(.55,.48,.32,1),
    'fabric':(.70,.64,.52,1), 'dark_fabric':(.095,.12,.14,1),
    'rubber':(.035,.042,.045,1), 'screen':(.11,.28,.38,1),
    'emissive':(.94,.73,.36,1), 'fire':(1,.34,.025,1),
    'leaf0':(.072,.145,.065,1), 'leaf1':(.105,.195,.085,1),
    'leaf2':(.15,.235,.105,1), 'trunk':(.19,.12,.072,1),
}

def rotation_matrix(rotation):
    r,p,y=rotation
    cr,sr,cp,sp,cy,sy=math.cos(r),math.sin(r),math.cos(p),math.sin(p),math.cos(y),math.sin(y)
    return np.array([[cy*cp,cy*sp*sr-sy*cr,cy*sp*cr+sy*sr],
                     [sy*cp,sy*sp*sr+cy*cr,sy*sp*cr-cy*sr],[-sp,cp*sr,cp*cr]])


def triangulate(obj):
    """Return (world vertices, outward-wound triangles) for a scene object."""
    kind=obj['kind']
    if kind=='mesh': return np.asarray(obj['vertices'],float),np.asarray(obj['faces'],int)
    if kind=='box':
        v=np.array([[-1,-1,-1],[1,-1,-1],[1,1,-1],[-1,1,-1],
                    [-1,-1,1],[1,-1,1],[1,1,1],[-1,1,1]],float)*np.array(obj['size'])/2
        f=np.array([[0,2,1],[0,3,2],[4,5,6],[4,6,7],[0,1,5],[0,5,4],
                    [1,2,6],[1,6,5],[2,3,7],[2,7,6],[3,0,4],[3,4,7]])
    elif kind=='cylinder':
        n=obj.get('segments',20); a=np.arange(n)*2*np.pi/n; radius=obj['radius']; h=obj['length']/2
        ring=np.column_stack((radius*np.cos(a),radius*np.sin(a)))
        v=np.concatenate([np.column_stack((ring,np.full(n,-h))),np.column_stack((ring,np.full(n,h))),[[0,0,-h],[0,0,h]]])
        f=[]
        for i in range(n):
            j=(i+1)%n; f.extend([[i,j,n+j],[i,n+j,n+i],[2*n,j,i],[2*n+1,n+i,n+j]])
        f=np.asarray(f)
    elif kind=='sphere':
        n=obj.get('segments',12); rings=obj.get('rings',6)
        v=[[0,0,-1]]
        for j in range(1,rings):
            phi=-np.pi/2+np.pi*j/rings
            v.extend([[np.cos(phi)*np.cos(a*2*np.pi/n),np.cos(phi)*np.sin(a*2*np.pi/n),np.sin(phi)] for a in range(n)])
        v.append([0,0,1]); f=[]
        for i in range(n): f.append([0,1+(i+1)%n,1+i])
        for j in range(rings-2):
            k=1+j*n
            for i in range(n):
                a=k+i;b=k+(i+1)%n;c=b+n;d=a+n;f.extend([[a,b,c],[a,c,d]])
        k=1+(rings-2)*n
        for i in range(n): f.append([k+i,k+(i+1)%n,len(v)-1])
        v=np.asarray(v)*np.asarray(obj['radii']); f=np.asarray(f)
    else: raise ValueError(f'Unsupported primitive {kind}')
    return v@rotation_matrix(obj.get('rotation',[0,0,0])).T+np.asarray(obj['center']),f


class Model:
    def __init__(self,name): self.name=name; self.objects=[]
    def _add(self,name,kind,material,collision,**kw):
        if any(o['name']==name for o in self.objects): raise ValueError(f'Duplicate {self.name}/{name}')
        obj={'name':name,'kind':kind,'material':material,'collision':bool(collision),'rotation':[0.,0.,0.],**kw}
        self.objects.append(obj); return obj
    def box(self,name,center,size,material='ivory',collision=True,yaw=0.):
        if min(size)<=0: raise ValueError(f'Nonpositive box {name}: {size}')
        return self._add(name,'box',material,collision,center=list(center),size=list(size),rotation=[0,0,yaw])
    def cylinder(self,name,center,radius,length,material='stone',collision=True,segments=20):
        if radius<=0 or length<=0: raise ValueError(name)
        return self._add(name,'cylinder',material,collision,center=list(center),radius=radius,length=length,segments=segments)
    def sphere(self,name,center,radii=(1,1,1),material='stone',collision=True,segments=12,rings=6):
        return self._add(name,'sphere',material,collision,center=list(center),radii=list(radii),segments=segments,rings=rings)
    def mesh(self,name,vertices,faces,material,collision=False):
        return self._add(name,'mesh',material,collision,vertices=np.asarray(vertices,float),faces=np.asarray(faces,int))
    def beam(self,name,start,end,width,material,collision=True):
        a,b=np.asarray(start,float),np.asarray(end,float); d=b-a; length=float(np.linalg.norm(d))
        obj=self.box(name,(a+b)/2,(width,width,length),material,collision)
        obj['rotation']=[0,math.atan2(math.hypot(d[0],d[1]),d[2]),math.atan2(d[1],d[0])]; return obj
    def ring(self,name,center,inner_radius,outer_radius,height,material,collision=True,segments=64):
        if not 0<inner_radius<outer_radius: raise ValueError(name)
        v=[];f=[];cx,cy,cz=center
        for z in [-height/2,height/2]:
            for r in [inner_radius,outer_radius]:
                v.extend([[cx+r*math.cos(i*2*math.pi/segments),cy+r*math.sin(i*2*math.pi/segments),cz+z] for i in range(segments)])
        n=segments
        for i in range(n):
            j=(i+1)%n
            for a,b,c,d in [(i,n+i,n+j,j),(2*n+i,2*n+j,3*n+j,3*n+i),
                            (n+i,3*n+i,3*n+j,n+j),(i,j,2*n+j,2*n+i)]:
                f.extend([[a,b,c],[a,c,d]])
        return self.mesh(name,v,np.asarray(f)[:,::-1],material,collision)
    def text(self,name,text,origin,height,material='brass',yaw=0.):
        """Extrude the built-in Pillow bitmap font; no texture/font resource needed."""
        from PIL import Image,ImageDraw,ImageFont
        font=ImageFont.load_default(); box=font.getbbox(text)
        im=Image.new('1',(max(1,box[2]-box[0]),max(1,box[3]-box[1])),0)
        ImageDraw.Draw(im).text((-box[0],-box[1]),text,font=font,fill=1)
        a=np.asarray(im); scale=height/a.shape[0]; verts=[];faces=[]
        rot=rotation_matrix([0,0,yaw])
        for row in range(a.shape[0]):
            col=0
            while col<a.shape[1]:
                if not a[row,col]: col+=1;continue
                end=col+1
                while end<a.shape[1] and a[row,end]:end+=1
                x0,x1=col*scale,end*scale;z0,z1=(a.shape[0]-row-1)*scale,(a.shape[0]-row)*scale
                v=np.array([[x0,0,z0],[x1,0,z0],[x1,0,z1],[x0,0,z1]])@rot.T+np.array(origin)
                k=len(verts);verts.extend(v);faces.extend([[k,k+1,k+2],[k,k+2,k+3]]);col=end
        return self.mesh(name,verts,faces,material,False)


def write_dae(path,vertices,faces):
    """COLLADA 1.4.1 with explicit normals; portable across Gazebo and Blender."""
    v=np.asarray(vertices,float);f=np.asarray(faces,int)
    if not len(f): raise ValueError(f'Empty mesh {path}')
    if not np.isfinite(v).all() or f.min()<0 or f.max()>=len(v): raise ValueError(path)
    normals=np.cross(v[f[:,1]]-v[f[:,0]],v[f[:,2]]-v[f[:,0]])
    mag=np.linalg.norm(normals,axis=1)
    if np.any(mag<1e-10):
        good=mag>=1e-10;f=f[good];normals=normals[good];mag=mag[good]
    normals/=mag[:,None]
    indices=np.empty((len(f),3,2),int);indices[:,:,0]=f;indices[:,:,1]=np.arange(len(f))[:,None]
    path.parent.mkdir(parents=True,exist_ok=True)
    pos=' '.join(f'{x:.5f}' for x in v.ravel()); nor=' '.join(f'{x:.5f}' for x in normals.ravel()); idx=' '.join(map(str,indices.ravel()))
    path.write_text(f'''<?xml version="1.0" encoding="UTF-8"?>
<COLLADA xmlns="http://www.collada.org/2005/11/COLLADASchema" version="1.4.1">
<asset><contributor><authoring_tool>Summit Estate procedural mesh exporter</authoring_tool></contributor><created>2026-09-11T00:00:00Z</created><modified>2026-09-11T00:00:00Z</modified><unit name="meter" meter="1"/><up_axis>Z_UP</up_axis></asset>
<library_geometries><geometry id="geometry" name="geometry"><mesh>
<source id="positions"><float_array id="positions-array" count="{v.size}">{pos}</float_array><technique_common><accessor source="#positions-array" count="{len(v)}" stride="3"><param name="X" type="float"/><param name="Y" type="float"/><param name="Z" type="float"/></accessor></technique_common></source>
<source id="normals"><float_array id="normals-array" count="{normals.size}">{nor}</float_array><technique_common><accessor source="#normals-array" count="{len(normals)}" stride="3"><param name="X" type="float"/><param name="Y" type="float"/><param name="Z" type="float"/></accessor></technique_common></source>
<vertices id="vertices"><input semantic="POSITION" source="#positions"/></vertices><triangles count="{len(f)}"><input semantic="VERTEX" source="#vertices" offset="0"/><input semantic="NORMAL" source="#normals" offset="1"/><p>{idx}</p></triangles>
</mesh></geometry></library_geometries><library_visual_scenes><visual_scene id="Scene"><node id="mesh"><instance_geometry url="#geometry"/></node></visual_scene></library_visual_scenes><scene><instance_visual_scene url="#Scene"/></scene></COLLADA>''')
    return len(v),len(f)


def sub(parent,tag,text=None,**attrs):
    e=ET.SubElement(parent,tag,attrs)
    if text is not None:e.text=str(text)
    return e


def floats(seq):return ' '.join(f'{float(n):.6g}' for n in seq)


def write_xml(path,root):
    path.parent.mkdir(parents=True,exist_ok=True);ET.indent(root,space='  ')
    ET.ElementTree(root).write(path,encoding='utf-8',xml_declaration=True)


class Scene:
    def __init__(self):
        self.models={}
        self.materials={k:{'color':list(v),'roughness':.8,'metalness':0.0} for k,v in COLORS.items()}
        for k in ['metal','brass']:self.materials[k].update(roughness=.35,metalness=.65)
        for k in ['glass','water','pool_water']:self.materials[k].update(roughness=.16)
    def model(self,name):
        if name not in self.models:self.models[name]=Model(name)
        return self.models[name]
    def export(self,root):
        root=Path(root); manifest=[]
        for name,model in self.models.items():
            dest=root/'gazebo/models'/name
            sdf=ET.Element('sdf',version='1.9');me=sub(sdf,'model',name=name);sub(me,'static','true');link=sub(me,'link',name='structure')
            batches=defaultdict(lambda:[[],[],0]);collisions=[]
            for obj in model.objects:
                v,f=triangulate(obj)
                if obj.get('visual',True):
                    b=batches[obj['material']]; b[0].append(v);b[1].append(f+b[2]);b[2]+=len(v)
                if obj['collision']:collisions.append(obj)
            total_tri=0
            for mat,(vs,fs,_) in batches.items():
                if mat not in self.materials:raise ValueError(f'Unknown material {mat}')
                path=dest/'meshes/visual'/f'{mat}.dae';_,tri=write_dae(path,np.concatenate(vs),np.concatenate(fs));total_tri+=tri
                vis=sub(link,'visual',name=f'visual_{mat}');geo=sub(vis,'geometry');mesh=sub(geo,'mesh');sub(mesh,'uri',f'model://{name}/meshes/visual/{mat}.dae')
                material=sub(vis,'material'); spec=self.materials[mat];color=spec['color'];opaque=color[:3]+[1.]
                sub(material,'ambient',floats(opaque));sub(material,'diffuse',floats(opaque));sub(material,'specular','0.15 0.15 0.15 1')
                if color[3]<1:sub(vis,'transparency',1-color[3]);sub(vis,'cast_shadows','false')
                if mat in ['emissive','fire','screen']:sub(material,'emissive',floats([c*.55 for c in color[:3]]+[1]))
                pbr=sub(material,'pbr');metal=sub(pbr,'metal');sub(metal,'roughness',spec.get('roughness',.8));sub(metal,'metalness',spec.get('metalness',0))
            for obj in collisions:
                col=sub(link,'collision',name=obj['name']);geo=sub(col,'geometry');kind=obj['kind']
                if kind=='mesh':
                    path=dest/'meshes/collision'/f"{obj['name']}.dae";write_dae(path,obj['vertices'],obj['faces'])
                    sub(sub(geo,'mesh'),'uri',f"model://{name}/meshes/collision/{obj['name']}.dae")
                else:
                    sub(col,'pose',floats(obj['center']+obj.get('rotation',[0,0,0])))
                    if kind=='box':sub(sub(geo,'box'),'size',floats(obj['size']))
                    elif kind=='cylinder':
                        shape=sub(geo,'cylinder');sub(shape,'radius',obj['radius']);sub(shape,'length',obj['length'])
                    elif kind=='sphere':
                        # Ellipsoids are exported as exact low-poly collision meshes.
                        v,f=triangulate(obj); path=dest/'meshes/collision'/f"{obj['name']}.dae";write_dae(path,v,f)
                        col.remove(col.find('pose'));sub(sub(geo,'mesh'),'uri',f"model://{name}/meshes/collision/{obj['name']}.dae")
            write_xml(dest/'model.sdf',sdf)
            cfg=ET.Element('model');sub(cfg,'name',name);sub(cfg,'version','1.0');sub(cfg,'sdf','model.sdf',version='1.9');sub(cfg,'description','Locally generated Summit Estate asset, metres, Z up.')
            write_xml(dest/'model.config',cfg)
            manifest.append({'name':name,'objects':len(model.objects),'visual_batches':len(batches),'visual_triangles':total_tri,'collisions':len(collisions)})
        return manifest
    def save_geometry(self,path):
        def convert(o):
            if isinstance(o,np.ndarray):return o.tolist()
            if isinstance(o,np.generic):return o.item()
            raise TypeError(type(o))
        path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
        with gzip.open(path,'wt') as out:json.dump({'materials':self.materials,'models':{k:v.objects for k,v in self.models.items()}},out,default=convert,separators=(',',':'))
