"""Read generated assets independently of their generator for acceptance checks."""
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np

NS={'c':'http://www.collada.org/2005/11/COLLADASchema'}


def read_mesh(path):
    root=ET.parse(path)
    array=root.find('.//c:source[@id="position"]/c:float_array',NS)
    vertices=np.fromstring(array.text,sep=' ').reshape(-1,3)
    faces={}
    for group in root.findall('.//c:triangles',NS):
        inputs=group.findall('c:input',NS)
        stride=max(int(item.attrib['offset']) for item in inputs)+1
        vertex_offset=int(next(item for item in inputs if item.attrib['semantic']=='VERTEX').attrib['offset'])
        tuples=np.fromstring(group.find('c:p',NS).text,sep=' ',dtype=int).reshape(-1,stride)
        indices=tuples[:,vertex_offset].reshape(-1,3)
        if len(indices)!=int(group.attrib['count']):
            raise ValueError(f'Triangle count mismatch in {path}')
        faces[group.attrib['material']]=indices
    return root,vertices,faces


def sample_terrain(terrain,xy):
    axis=terrain['x']; n=len(axis)
    grid=(np.asarray(xy)-axis[0])/(axis[1]-axis[0])
    grid=np.clip(grid,0,n-1-1e-9)
    cells=np.floor(grid).astype(int); fraction=grid-cells
    i,j=cells[...,0],cells[...,1]; a,b=fraction[...,0],fraction[...,1]
    z=terrain['z']
    lower=z[j,i]*(1-a)+z[j,i+1]*(a-b)+z[j+1,i+1]*b
    upper=z[j,i]*(1-b)+z[j+1,i]*(b-a)+z[j+1,i+1]*a
    return np.where(a>=b,lower,upper)


def surface_gaps(vertices,faces,terrain,subdivisions=4):
    triangles=vertices[faces]; low=float('inf'); high=-low
    for i in range(subdivisions+1):
        for j in range(subdivisions+1-i):
            weights=np.array([i,j,subdivisions-i-j])/subdivisions
            samples=np.einsum('ijk,j->ik',triangles,weights)
            gap=samples[:,2]-sample_terrain(terrain,samples[:,:2])
            low=min(low,float(gap.min())); high=max(high,float(gap.max()))
    return dict(min_m=low,max_m=high)


def inspect_assets(root):
    root=Path(root); models=root/'gazebo/models'; triangles=0; files=0
    terrain=np.load(root/'data/processed/terrain.npz')
    road_gaps={}
    for path in sorted(models.rglob('*.dae')):
        doc,v,groups=read_mesh(path); files+=1
        if not np.isfinite(v).all(): raise ValueError(f'Nonfinite vertex in {path}')
        for name,f in groups.items():
            if f.min()<0 or f.max()>=len(v): raise ValueError(f'Bad indices in {path}')
            area=np.linalg.norm(np.cross(v[f[:,1]]-v[f[:,0]],v[f[:,2]]-v[f[:,0]]),axis=1)
            if np.any(area<1e-9): raise ValueError(f'Degenerate triangles in {path}')
            triangles+=len(f)
            if path.name=='roads.dae' and name in ['asphalt','gravel']:
                road_gaps[name]=surface_gaps(v,f,terrain)
        for image in doc.findall('.//c:library_images/c:image/c:init_from',NS):
            if not (path.parent/image.text).is_file():
                raise ValueError(f'Missing texture {image.text} in {path}')
    for path in sorted((root/'gazebo').rglob('*.sdf')):
        for uri in ET.parse(path).findall('.//uri'):
            if not uri.text.startswith('model://') or not (models/uri.text[8:]).exists():
                raise ValueError(f'Unresolved resource {uri.text} in {path}')
    return dict(mesh_files=files,triangles=triangles,road_surface_gaps=road_gaps)
