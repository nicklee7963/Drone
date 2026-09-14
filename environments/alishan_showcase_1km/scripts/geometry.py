"""Small deterministic mesh builder and COLLADA exporter (metres, Z up)."""
from collections import defaultdict
from pathlib import Path
import math
import xml.etree.ElementTree as ET
import numpy as np

PALETTE = {
    'bark': (.26, .18, .105), 'cedar': (.12, .30, .19),
    'cedar_light': (.23, .40, .22), 'broadleaf': (.29, .44, .16),
    'broadleaf_light': (.38, .51, .21), 'bamboo': (.41, .52, .21),
    'asphalt': (.24, .28, .28), 'gravel': (.60, .57, .43),
    'white': (.92, .91, .78), 'gold': (.98, .69, .15),
    'concrete': (.53, .56, .51), 'wood': (.53, .31, .16),
    'plaster': (.87, .79, .62), 'roof': (.30, .18, .15),
    'roof_green': (.16, .29, .27), 'glass': (.23, .46, .51),
    'tea': (.37, .49, .17), 'stone': (.42, .43, .37),
}


class Mesh:
    def __init__(self):
        self.vertices = []
        self.uv = []
        self.faces = defaultdict(list)

    @property
    def triangle_count(self):
        return sum(len(f) for f in self.faces.values())

    def add(self, vertices, faces, material, uv=None):
        start = len(self.vertices)
        self.vertices.extend(vertices)
        self.uv.extend(uv if uv is not None else [(0, 0)] * len(vertices))
        self.faces[material].extend(tuple(start + i for i in f) for f in faces)

    def box(self, center, size, material, yaw=0):
        x, y, z = np.array(size) / 2
        v = np.array([[-x,-y,-z],[x,-y,-z],[x,y,-z],[-x,y,-z],
                      [-x,-y,z],[x,-y,z],[x,y,z],[-x,y,z]])
        c,s = math.cos(yaw),math.sin(yaw)
        v = v @ np.array([[c,s,0],[-s,c,0],[0,0,1]]) + center
        self.add(v, [(0,2,1),(0,3,2),(4,5,6),(4,6,7),
                     (0,1,5),(0,5,4),(1,2,6),(1,6,5),
                     (2,3,7),(2,7,6),(3,0,4),(3,4,7)], material)

    def cone(self, center, radius, height, material, sides=7, top=.03, angle=0):
        x,y,z = center
        a = np.arange(sides) * 2 * np.pi / sides + angle
        vertices = [(x+radius*np.cos(t),y+radius*np.sin(t),z) for t in a]
        vertices += [(x+radius*top*np.cos(t),y+radius*top*np.sin(t),z+height) for t in a]
        faces=[]
        for i in range(sides):
            j=(i+1)%sides
            faces.extend([(i,j,sides+j),(i,sides+j,sides+i)])
        vertices.append((x,y,z))
        for i in range(sides):
            faces.append((2*sides,(i+1)%sides,i))
        self.add(vertices,faces,material)

    def crown(self, center, radius, height, material, angle=0):
        x,y,z=center; sides=7
        vertices=[]
        for dz,r in [(-.5,.08),(-.25,.84),(.12,1),(.40,.60),(.5,.05)]:
            for i in range(sides):
                a=angle+i*2*np.pi/sides
                vertices.append((x+radius*r*np.cos(a),y+radius*r*np.sin(a),z+height*dz))
        faces=[]
        for k in range(4):
            for i in range(sides):
                a=k*sides+i; b=k*sides+(i+1)%sides
                faces.extend([(a,b,b+sides),(a,b+sides,a+sides)])
        self.add(vertices,faces,material)

    def write(self, path, texture=None):
        """Indexed normals and material groups keep batches compact."""
        path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
        v=np.asarray(self.vertices,dtype=float)
        normals=np.zeros_like(v)
        for faces in self.faces.values():
            f=np.asarray(faces,dtype=int)
            n=np.cross(v[f[:,1]]-v[f[:,0]],v[f[:,2]]-v[f[:,0]])
            for i in range(3):
                np.add.at(normals,f[:,i],n)
        normals/=np.maximum(np.linalg.norm(normals,axis=1,keepdims=True),1e-12)
        root=ET.Element('COLLADA',xmlns='http://www.collada.org/2005/11/COLLADASchema',version='1.4.1')
        asset=ET.SubElement(root,'asset')
        ET.SubElement(asset,'created').text='2026-09-11T00:00:00Z'
        ET.SubElement(asset,'modified').text='2026-09-11T00:00:00Z'
        ET.SubElement(asset,'unit',name='meter',meter='1')
        ET.SubElement(asset,'up_axis').text='Z_UP'
        if texture:
            img=ET.SubElement(ET.SubElement(root,'library_images'),'image',id='terrain_image')
            ET.SubElement(img,'init_from').text=texture
        effects=ET.SubElement(root,'library_effects'); materials=ET.SubElement(root,'library_materials')
        for name in self.faces:
            effect=ET.SubElement(effects,'effect',id=name+'_effect')
            profile=ET.SubElement(effect,'profile_COMMON')
            if name=='terrain' and texture:
                param=ET.SubElement(profile,'newparam',sid='surface')
                surface=ET.SubElement(param,'surface',type='2D')
                ET.SubElement(surface,'init_from').text='terrain_image'
                param=ET.SubElement(profile,'newparam',sid='sampler')
                ET.SubElement(ET.SubElement(param,'sampler2D'),'source').text='surface'
            phong=ET.SubElement(ET.SubElement(profile,'technique',sid='common'),'phong')
            color=PALETTE.get(name,(.48,.57,.34))
            ET.SubElement(ET.SubElement(phong,'ambient'),'color').text=' '.join(map(str,(*color,1)))
            diffuse=ET.SubElement(phong,'diffuse')
            if name=='terrain' and texture:
                ET.SubElement(diffuse,'texture',texture='sampler',texcoord='UVMap')
            else:
                ET.SubElement(diffuse,'color').text=' '.join(map(str,(*color,1)))
            ET.SubElement(ET.SubElement(phong,'specular'),'color').text='0.03 0.03 0.03 1'
            ET.SubElement(ET.SubElement(phong,'shininess'),'float').text='8'
            mat=ET.SubElement(materials,'material',id=name+'_material',name=name)
            ET.SubElement(mat,'instance_effect',url='#'+name+'_effect')
        geo=ET.SubElement(ET.SubElement(root,'library_geometries'),'geometry',id='mesh',name=path.stem)
        mesh=ET.SubElement(geo,'mesh')
        for name,data,axes in [('position',v,'XYZ'),('normal',normals,'XYZ'),('uv',np.asarray(self.uv),'ST')]:
            source=ET.SubElement(mesh,'source',id=name)
            ET.SubElement(source,'float_array',id=name+'_array',count=str(data.size)).text=' '.join(f'{n:.5f}' for n in data.flat)
            accessor=ET.SubElement(ET.SubElement(source,'technique_common'),'accessor',source='#'+name+'_array',count=str(len(data)),stride=str(len(axes)))
            for axis in axes:
                ET.SubElement(accessor,'param',name=axis,type='float')
        vertices=ET.SubElement(mesh,'vertices',id='vertices')
        ET.SubElement(vertices,'input',semantic='POSITION',source='#position')
        for name,faces in self.faces.items():
            tri=ET.SubElement(mesh,'triangles',count=str(len(faces)),material=name)
            # Gazebo's COLLADA loader advances by the number of inputs, even
            # when inputs share an offset. Use explicit interleaved tuples.
            for offset,(semantic,source) in enumerate([('VERTEX','vertices'),('NORMAL','normal'),('TEXCOORD','uv')]):
                attrs=dict(semantic=semantic,source='#'+source,offset=str(offset))
                if semantic=='TEXCOORD': attrs['set']='0'
                ET.SubElement(tri,'input',**attrs)
            ET.SubElement(tri,'p').text=' '.join(f'{i} {i} {i}' for f in faces for i in f)
        scene=ET.SubElement(ET.SubElement(root,'library_visual_scenes'),'visual_scene',id='Scene')
        node=ET.SubElement(scene,'node',id='Node',name=path.stem)
        inst=ET.SubElement(node,'instance_geometry',url='#mesh')
        common=ET.SubElement(ET.SubElement(inst,'bind_material'),'technique_common')
        for name in self.faces:
            mat=ET.SubElement(common,'instance_material',symbol=name,target='#'+name+'_material')
            ET.SubElement(mat,'bind_vertex_input',semantic='UVMap',input_semantic='TEXCOORD',input_set='0')
        ET.SubElement(ET.SubElement(root,'scene'),'instance_visual_scene',url='#Scene')
        ET.ElementTree(root).write(path,encoding='utf-8',xml_declaration=True)
