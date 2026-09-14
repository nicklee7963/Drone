"""Run inside Blender: --python scripts/build_estate.py -- --phase shell|B1|1F|2F|3F|final."""
import bpy,sys,math,json,random,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import scene_utils as U, architecture as A, materials

def configure():
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    for c in list(bpy.data.collections):
        if c.name!='Collection':bpy.data.collections.remove(c)
    U.M.update(materials.build_materials())
    s=bpy.context.scene;s.render.engine='CYCLES';s.cycles.samples=64;s.cycles.use_denoising=True;s.cycles.use_adaptive_sampling=True;s.cycles.adaptive_threshold=.025
    s.cycles.max_bounces=10;s.cycles.transmission_bounces=8;s.cycles.transparent_max_bounces=12
    try:
        pref=bpy.context.preferences.addons['cycles'].preferences;pref.compute_device_type='CUDA';pref.get_devices()
        for d in pref.devices:d.use=d.type=='CUDA'
        s.cycles.device='GPU'
    except Exception as e:print('GPU fallback:',e);s.cycles.device='CPU'
    s.render.resolution_x=1600;s.render.resolution_y=1000;s.render.resolution_percentage=100
    s.render.image_settings.file_format='PNG';s.render.image_settings.color_mode='RGB';s.render.image_settings.color_depth='8'
    s.view_settings.view_transform='AgX';s.view_settings.look='AgX - Medium High Contrast';s.view_settings.exposure=.5
    s.world=bpy.data.worlds.new('Summit dusk / editable sky');s.world.use_nodes=True
    n=s.world.node_tree.nodes;n.clear();out=n.new('ShaderNodeOutputWorld');bg=n.new('ShaderNodeBackground');bg.inputs['Color'].default_value=(.29,.38,.53,1);bg.inputs['Strength'].default_value=.30;s.world.node_tree.links.new(bg.outputs[0],out.inputs[0])
    s.render.film_transparent=False
    # Subtle optical glare from actual architectural luminaires.
    s.use_nodes=True;nt=s.node_tree;nt.nodes.clear();rl=nt.nodes.new('CompositorNodeRLayers');gl=nt.nodes.new('CompositorNodeGlare');gl.glare_type='FOG_GLOW';gl.quality='HIGH';gl.threshold=3.;gl.mix=-.92;out=nt.nodes.new('CompositorNodeComposite');nt.links.new(rl.outputs['Image'],gl.inputs['Image']);nt.links.new(gl.outputs['Image'],out.inputs[0])

def cameras():
    U.camera('exterior_front',(94,-126,53),(0,0,5),35)
    U.camera('exterior_rear',(-83,117,47),(0,4,6),38)
    for f,z in [('B1',-4.2),('1F',0),('2F',5.8),('3F',10)]:
        U.camera(f+'_overview',(57,-77,z+88),(-2,1,z),38,f,True,ortho=100 if f=='1F' else 78)
    U.camera('foyer',(-2,-15,2.2),(0,9,4.2),23,'1F')
    U.camera('living_room',(-12.4,16.3,1.65),(-20,8,1.3),22,'1F')
    U.camera('kitchen',(13,-2.8,1.8),(21,3,1.45),22,'1F')
    U.camera('dining',(12,9,1.7),(18,15,1.2),26,'1F')
    U.camera('garage',(-51,-7,1),(-39,2,0),24,'1F')
    U.camera('shoe_gallery',(-27,-7,1.65),(-30,-15,1.3),23,'1F')
    U.camera('gym',(-14.4,-5.2,-2.5),(-21.8,-13,-2.7),21,'B1')
    U.camera('cinema',(3.8,-6,-2.2),(-2,-13.8,-2.55),22,'B1')
    U.camera('library',(-10.3,2.5,-2.5),(-21,13.8,-2.7),21,'B1')
    U.camera('wine',(3.2,2,-2.5),(-4,10,-2.7),29,'B1')
    U.camera('basement_lounge',(12.8,3.2,-2.6),(5,12,-2.9),23,'B1')
    U.camera('laundry',(26,-6.9,-2.5),(22,-13,-2.9),23,'B1')
    U.camera('courtyard',(-27,2,-2.5),(-33,13,-2.7),24,'B1')
    U.camera('family_lounge',(-7,11,7.5),(2,17,7.1),23,'2F')
    U.camera('gaming_lounge',(15,6.7,7.5),(21,-2,7),23,'2F')
    U.camera('guest_suite',(-17.9,14,7.35),(-23.2,16,7),23,'2F')
    U.camera('guest_suite_B',(24,15,7.4),(19.5,12.5,7),23,'2F')
    U.camera('art_gallery',(-23,-13,7.45),(2,-13,7.15),27,'2F')
    U.camera('atrium_bridge',(-9.8,-8.9,7.5),(1,9,4.5),22,'2F')
    U.camera('master_bedroom',(-6,-1,11.65),(2,11,11.2),24,'3F')
    U.camera('master_bath',(9,1,11.65),(18,12,11.2),24,'3F')
    U.camera('master_closet',(-8,-7,11.65),(-19,8,11.3),23,'3F')
    U.camera('outdoor_terrace',(-12,15.8,11.65),(2,24,10.8),24,'3F')
    U.camera('private_entry',(15.5,-10.7,11.65),(15.5,-3,11.55),27,'3F')
    bpy.context.scene.camera=bpy.data.objects['exterior_front']

def basic_lighting():
    U.context('CONTEXT','sky','PRESENTATION')
    d=bpy.data.lights.new('Dusk sun','SUN');d.energy=1.2;d.angle=.065;d.color=(1.,.73,.49)
    o=bpy.data.objects.new('Dusk sun',d);U.link(o);o.rotation_euler=(math.radians(78),math.radians(-20),math.radians(140));o['day_energy']=2.0
    for f in ['B1','1F','2F','3F']:
        z=A.Z[f];h=A.HEIGHT[f]-.4
        U.context(f,'ambient','LIGHTING')
        for x in [-20,-8,4,19]:
            for y in [-13,-1,13]:
                if f=='2F' and -8<=x<=8 and -6<=y<=10:continue
                if f=='3F' and x>7 and y<-3:continue
                o=U.area(f+'.ambient.grid',(x,y,z+h-.06),450 if f!='1F' else 800,5,size_y=4);o['lighting_layer']='ambient'
        if f=='1F':
            for x in [-47,-38,33,44]:
                for y in [-12,0]:U.area('Wing.ambient',(x,y,2.9 if x<0 else 4.7),650,4)
    # Foyer capped by 3F; overhead lighting belongs 1F though located at 2F level.
    U.context('1F','foyer','LIGHTING');U.area('Foyer.double_height.ambient',(0,3,9.35),2600,9,size_y=10)

def main():
    args=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    p=argparse.ArgumentParser();p.add_argument('--phase',default='shell');p.add_argument('--input');ns=p.parse_args(args)
    if ns.input:
        bpy.ops.wm.open_mainfile(filepath=str(ROOT/ns.input));U.M.update({k:bpy.data.materials.get(v.name,v) for k,v in materials.build_materials().items()})
    else:
        configure();A.shell();cameras();basic_lighting()
    phases=['B1','1F','2F','3F']
    if ns.phase in phases:
        import importlib
        m=importlib.import_module('detail_'+ns.phase.lower());m.build()
    if ns.phase=='final':
        import finishing;finishing.build()
    bpy.context.scene['completed_phase']=ns.phase
    out=ROOT/'blender'/('summit_estate_master.blend' if ns.phase=='final' else 'checkpoints/'+{'shell':'02_shell','B1':'04_B1','1F':'05_1F','2F':'06_2F','3F':'07_3F'}[ns.phase]+'.blend')
    bpy.ops.wm.save_as_mainfile(filepath=str(out),compress=True)
    print('SUMMIT_SAVED',out,'OBJECTS',len(bpy.data.objects),flush=True)

if __name__=='__main__':main()
