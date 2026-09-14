import bpy,sys,os,json,math
from mathutils import Vector
base='/home/nicklee/Phenix_Project/Drone/environments/villa_v1'
sys.path.insert(0,base+'/scripts')
import furniture
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
materials={}
colors={'stone':(.55,.52,.46,1),'marble':(.65,.63,.56,1),'dark_marble':(.055,.048,.044,1),'walnut':(.12,.052,.022,1),'oak':(.28,.16,.07,1),'cream':(.72,.65,.53,1),'taupe':(.31,.25,.18,1),'black':(.018,.019,.018,1),'charcoal':(.05,.048,.042,1),'leather':(.25,.095,.035,1),'foliage':(.055,.14,.018,1),'bronze':(.29,.16,.06,1),'ceramic':(.30,.28,.22,1),'soil':(.022,.01,.003,1),'glass':(.6,.6,.6,1),'emission':(1,.58,.25,1)}
for i in range(6): colors['book_'+str(i)]=[(.05,.08,.09,1),(.22,.07,.035,1),(.38,.31,.20,1),(.055,.055,.045,1),(.62,.56,.4,1),(.18,.15,.11,1)][i]
for key,color in colors.items():
    m=bpy.data.materials.new(key);m.diffuse_color=color;m.use_nodes=True
    p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=color;p.inputs['Roughness'].default_value=.5
    if key=='bronze':p.inputs['Metallic'].default_value=.8;p.inputs['Roughness'].default_value=.25
    if key=='emission':p.inputs['Emission Color'].default_value=color;p.inputs['Emission Strength'].default_value=3
    if key=='glass':p.inputs['Transmission Weight'].default_value=1;p.inputs['Roughness'].default_value=.1
    materials[key]=m
coll=bpy.data.collections.new('Furniture_Test');bpy.context.scene.collection.children.link(coll)
roots=[]
layout=[('bookshelf',(-5,3,0),{}),('closet',(0,3,0),{}),('bed',(4.6,1.3,0),{}),('sofa',(-4,-.8,0),{}),('table',(-4,-2.2,0),{'round':True,'width':1.2,'height':.4}),('armchair',(-1.3,-.7,0),{}),('chair',(1,-.7,0),{}),('stool',(2.5,-.7,0),{}),('hanging_chair',(-7,-.7,0),{}),('plant',(7.2,2.6,0),{}),('cabinet',(1,-4.0,0),{'width':1.6,'height':.8}),('decor',(1,-4,.82),{}),('rug',(4.6,1.3,0),{'width':3.3,'depth':4}),('lamp',(-2.3,1,0),{})]
for kind,loc,kw in layout:
    root=furniture.build_asset(kind,kind,coll,materials,**kw);root.location=loc;roots.append(root)
bpy.context.view_layer.update();dg=bpy.context.evaluated_depsgraph_get();report=[]
for root in roots:
    coords=[]
    for child in root.children:
        assert child.parent==root
        assert child.data.materials,child.name
        ob=child.evaluated_get(dg)
        mesh=ob.to_mesh()
        coords.extend([root.matrix_world.inverted()@ob.matrix_world@v.co for v in mesh.vertices])
        ob.to_mesh_clear()
    low=[min(c[i] for c in coords) for i in range(3)];high=[max(c[i] for c in coords) for i in range(3)]
    assert low[2]>-.015,(root.name,'below floor',low)
    assert min(low)>-10 and max(high)<10,(root.name,low,high)
    report.append({'kind':root['asset_kind'],'components':len(root.children),'bounds_min':low,'bounds_max':high,'dimensions':[high[i]-low[i] for i in range(3)]})
with open(base+'/renders/assets_furniture/smoke_report.json','w') as f:json.dump(report,f,indent=2)
# Fallback and unknown-kind smoke paths.
fallback=furniture.build_asset('chair','Fallback_check',coll,{})
for ob in list(fallback.children):bpy.data.objects.remove(ob,do_unlink=True)
bpy.data.objects.remove(fallback,do_unlink=True)
try:furniture.build_asset('bad','bad',coll,materials)
except ValueError:pass
else:raise AssertionError('unknown kind must raise')
# Neutral stage and camera for a single overview.
bpy.ops.mesh.primitive_plane_add(size=200);floor=bpy.context.object;floor.name='Preview_floor';floor.data.materials.append(materials['stone'])
scene=bpy.context.scene;scene.unit_settings.system='METRIC'
world=scene.world or bpy.data.worlds.new('Preview_world');scene.world=world;world.use_nodes=True;world.node_tree.nodes['Background'].inputs[0].default_value=(.3,.35,.4,1);world.node_tree.nodes['Background'].inputs[1].default_value=.45
for name,loc,energy,size in [('Key',(0,-4,10),2400,8),('Fill',(-7,4,7),1600,6),('Rim',(6,5,8),2100,5)]:
    light=bpy.data.lights.new(name,'AREA');light.energy=energy;light.shape='DISK';light.size=size
    ob=bpy.data.objects.new(name,light);scene.collection.objects.link(ob);ob.location=loc;ob.rotation_euler=(Vector((0,0,0))-ob.location).to_track_quat('-Z','Y').to_euler()
camera=bpy.data.cameras.new('Furniture_preview');ob=bpy.data.objects.new('Furniture_preview',camera);scene.collection.objects.link(ob);ob.location=(11,-16,11);ob.rotation_euler=(Vector((0,0,1))-ob.location).to_track_quat('-Z','Y').to_euler();scene.camera=ob;camera.type='ORTHO';camera.ortho_scale=18
scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=24;scene.cycles.use_denoising=True
scene.render.resolution_x=1600;scene.render.resolution_y=1000;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.render.filepath=base+'/renders/assets_furniture/furniture_preview.png'
bpy.ops.wm.save_as_mainfile(filepath=base+'/renders/assets_furniture/furniture_preview.blend')
print('FURNITURE_SMOKE_OK',len(report),'types',sum(x['components'] for x in report),'components')
if '--render' in sys.argv:bpy.ops.render.render(write_still=True)
