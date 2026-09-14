import bpy,sys,json,math
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import equipment
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
col=bpy.data.collections.new('Equipment asset verification');bpy.context.scene.collection.children.link(col)
cases=[(k,{}) for k in equipment._BUILDERS]+[('car',{'style':'classic','color':(.025,.12,.07)}),('kitchen',{'island':True,'width':3.4})]
rows=[]
for i,(kind,kw) in enumerate(cases):
    root=equipment.build_asset(kind,f'{i:02}_{kind}',col,{},**kw)
    bpy.context.view_layer.update()
    pts=[o.matrix_world@Vector(v) for o in root.children if o.type in {'MESH','CURVE'} for v in o.bound_box]
    assert pts and all(o.parent==root for o in root.children)
    lo=[min(p[j] for p in pts) for j in range(3)];hi=[max(p[j] for p in pts) for j in range(3)]
    dims=[round(hi[j]-lo[j],4) for j in range(3)]
    assert all(math.isfinite(v) and v>0 for v in dims)
    assert lo[2]>=-.011,(kind,lo)
    rows.append({'kind':kind,'kwargs':kw,'objects':len(root.children),'dimensions':dims,'minimum':lo,'maximum':hi})
    root.location=((i%6)*10,(i//6)*7,0)
    cu=bpy.data.curves.new(kind+'_label','FONT');cu.body=kind+(' classic' if kw.get('style') else (' island' if kw.get('island') else ''));cu.size=.37;cu.align_x='CENTER'
    obj=bpy.data.objects.new(kind+'_label',cu);col.objects.link(obj);obj.location=root.location+Vector((0,-2.6,.01))
Path(ROOT/'renders/assets_equipment/smoke.json').write_text(json.dumps(rows,indent=2))
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=16
scene.render.resolution_x=1800;scene.render.resolution_y=1080;scene.render.resolution_percentage=100
scene.world.color=(.35,.35,.35)
bpy.ops.mesh.primitive_plane_add(size=200,location=(25,7,-.025));ground=bpy.context.object
m=equipment._fallback('Verification floor',(.32,.34,.35),0,.72);ground.data.materials.append(m)
for x in [0,20,40,60]:
    ld=bpy.data.lights.new('Softbox','AREA');ld.energy=3500;ld.shape='DISK';ld.size=12
    lo=bpy.data.objects.new('Softbox',ld);scene.collection.objects.link(lo);lo.location=(x,3,12)
camd=bpy.data.cameras.new('Asset contact sheet');cam=bpy.data.objects.new('Asset contact sheet',camd);scene.collection.objects.link(cam)
cam.location=(31,-35,41);target=Vector((25,7,0));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();camd.type='ORTHO';camd.ortho_scale=65;scene.camera=cam
scene.view_settings.view_transform='AgX'
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'renders/assets_equipment/equipment_smoke.blend'))
scene.render.filepath=str(ROOT/'renders/assets_equipment/contact.png');bpy.ops.render.render(write_still=True)
print('EQUIPMENT_SMOKE_OK',len(rows))
