"""Run from Blender's Scripting workspace, or blender --background --python this_file.

Uses the shared geometry archive, so no COLLADA add-on or external Python
modules beyond Blender's bundled NumPy are required. It does not alter assets.
"""
import gzip
import json
from pathlib import Path
import sys
import bpy
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from geometry import triangulate
with gzip.open(ROOT/'data/processed/geometry.json.gz','rt') as handle:scene=json.load(handle)
collection=bpy.data.collections.new('Summit Estate 1km');bpy.context.scene.collection.children.link(collection)
materials={}
for name,spec in scene['materials'].items():
    mat=bpy.data.materials.new(name);mat.diffuse_color=spec['color'];mat.use_nodes=True
    bsdf=mat.node_tree.nodes.get('Principled BSDF');bsdf.inputs['Base Color'].default_value=spec['color'];bsdf.inputs['Roughness'].default_value=spec.get('roughness',.8);bsdf.inputs['Metallic'].default_value=spec.get('metalness',0)
    materials[name]=mat
for model,objects in scene['models'].items():
    # Match Gazebo batching: one mesh per material per model.
    batches={}
    for obj in objects:
        if not obj.get('visual',True):continue
        v,f=triangulate(obj);verts,faces=batches.setdefault(obj['material'],([],[]));offset=len(verts);verts.extend(v.tolist());faces.extend((f+offset).tolist())
    for mat,(verts,faces) in batches.items():
        mesh=bpy.data.meshes.new(model+'_'+mat);mesh.from_pydata(verts,[],faces);mesh.materials.append(materials[mat]);obj=bpy.data.objects.new(mesh.name,mesh);collection.objects.link(obj)
scene=bpy.context.scene;scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=1
scene.render.engine='CYCLES';scene.world.color=(.35,.42,.50)
print('Imported Summit Estate visual assets. Save As a .blend inside blender/ if desired.')
