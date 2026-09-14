#!/usr/bin/env python3
"""Regenerate the self-contained estate assets and Gazebo world."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
from geometry import Scene,sub,write_xml,floats
from landscape import build_landscape
from villa import build_villa
from amenities import build_amenities

ROOT=Path(__file__).resolve().parents[1]


def camera_pose(position,target):
    d=np.asarray(target)-np.asarray(position)
    return list(position)+[0,math.atan2(-d[2],math.hypot(d[0],d[1])),math.atan2(d[1],d[0])]


def write_world(root,models):
    sdf=ET.Element('sdf',version='1.9');world=sub(sdf,'world',name='summit_estate')
    physics=sub(world,'physics',name='default',type='ignored');sub(physics,'max_step_size',.004);sub(physics,'real_time_factor',1.)
    sub(world,'gravity','0 0 -9.81');sub(world,'magnetic_field','2.15e-5 0 4.27e-5')
    for filename,name in [('physics','Physics'),('user-commands','UserCommands'),('scene-broadcaster','SceneBroadcaster'),('sensors','Sensors')]:
        p=sub(world,'plugin',filename=f'gz-sim-{filename}-system',name=f'gz::sim::systems::{name}')
        if name=='Sensors':sub(p,'render_engine','ogre2')
    scene=sub(world,'scene');sub(scene,'ambient','.56 .58 .61 1');sub(scene,'background','.59 .70 .78 1');sub(scene,'shadows','true')
    light=sub(world,'light',type='directional',name='late_afternoon_sun');sub(light,'pose','0 0 400 0 0 0');sub(light,'cast_shadows','true')
    sub(light,'diffuse','1 .88 .70 1');sub(light,'specular','.35 .32 .26 1');sub(light,'direction','-.35 .45 -.83')
    attenuation=sub(light,'attenuation');sub(attenuation,'range',2000);sub(attenuation,'constant',1);sub(attenuation,'linear',0);sub(attenuation,'quadratic',0)
    gui=sub(world,'gui',fullscreen='false')
    p=sub(gui,'plugin',filename='MinimalScene',name='Summit Estate 1km');g=sub(p,'gz-gui');sub(g,'title','Summit Estate 1km');sub(g,'property','false',type='bool',key='showTitleBar');sub(g,'property','docked',type='string',key='state')
    sub(p,'engine','ogre2');sub(p,'scene','scene');sub(p,'camera_pose',floats(camera_pose([230,-470,345],[-45,20,65])));sub(p,'camera_clip','')
    clip=p.find('camera_clip');sub(clip,'near',.1);sub(clip,'far',3000)
    for filename in ['GzSceneManager','InteractiveViewControl','CameraTracking','EntityContextMenuPlugin']:
        p=sub(gui,'plugin',filename=filename,name=filename);g=sub(p,'gz-gui');sub(g,'property','floating',type='string',key='state');sub(g,'property','false',type='bool',key='showTitleBar');sub(g,'property','5',type='double',key='width');sub(g,'property','5',type='double',key='height')
    p=sub(gui,'plugin',filename='WorldControl',name='World control');sub(p,'play_pause','true');sub(p,'step','true');sub(p,'start_paused','false')
    for model in models:sub(sub(world,'include'),'uri','model://'+model['name'])
    # A named collision-free frame is a future spawn reference, not a vehicle.
    frame=sub(world,'frame',name='uav_lawn_spawn');sub(frame,'pose','125 8 80.5 0 0 0')
    write_xml(root/'gazebo/worlds/summit_estate.sdf',sdf)


def make_plans(root,config,manifest,grid):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.colors import LightSource
    from matplotlib.patches import Rectangle,Ellipse
    xs,ys,z=grid;fig,ax=plt.subplots(figsize=(12,12),facecolor='#111d20');ax.set_facecolor('#182727')
    ax.pcolormesh(xs,ys,z,cmap='gist_earth',shading='auto',rasterized=True,vmin=10,vmax=225)
    lake=np.array(manifest['landscape']['lake_boundary']);ax.fill(lake[:,0],lake[:,1],color='#285b68')
    road=np.array(manifest['landscape']['road_centerline']);ax.plot(road[:,0],road[:,1],color='#d3c8af',lw=5);ax.plot(road[:,0],road[:,1],color='#394144',lw=3)
    for room in manifest['villa']['rooms']:
        if room['level']!='main':continue
        x0,x1,y0,y1,*_=room['bounds'];ax.add_patch(Rectangle((x0,y0),x1-x0,y1-y0,facecolor='#ddd9ce',edgecolor='#172021',lw=.5))
    x0,x1,y0,y1=config['villa']['bounds'];ax.add_patch(Rectangle((x0,y0),x1-x0,y1-y0,fill=False,edgecolor='white',lw=2))
    ax.add_patch(Ellipse((78,58),74,74,facecolor='#616461',edgecolor='#d5cdb9'));ax.add_patch(Ellipse((78,58),52,52,facecolor='#536132',edgecolor='#c4bea8'));ax.add_patch(Ellipse((78,58),24,24,facecolor='#7fa4a6',edgecolor='white'))
    ax.add_patch(Rectangle((149,139),36,20,facecolor='#3daec0',edgecolor='white'));ax.add_patch(Rectangle((159,73.5),32,19,facecolor='#173a55',edgecolor='white'))
    labels=[('MAIN GATE',(-185,-390),(-325,-400)),('WINDING PRIVATE ROAD',(-88,-148),(-295,-205)),('PRIVATE LAKE',(-190,135),(-300,285)),('MAIN VILLA',(78,140),(150,290)),('FOUNTAIN COURT',(78,58),(-70,-45)),('POOL + LOUNGE',(167,149),(280,190)),('BASKETBALL',(175,83),(280,100)),('FIRE LOUNGE',(166,12),(275,-10))]
    for label,xy,xytext in labels:ax.annotate(label,xy,xytext,color='white',fontsize=9,arrowprops={'arrowstyle':'-','color':'#eee5cc','lw':.8},bbox={'facecolor':'#162324','alpha':.75,'edgecolor':'none','pad':4})
    ax.set(xlim=(-500,500),ylim=(-500,500),aspect='equal',xlabel='East / x (m)',ylabel='North / y (m)');ax.tick_params(colors='#d6dacd');ax.xaxis.label.set_color('#d6dacd');ax.yaxis.label.set_color('#d6dacd');ax.set_title('THE SUMMIT ESTATE  |  1 KM × 1 KM\nReference-inspired simulation site plan',color='#e8d3a7',pad=18,fontsize=16)
    fig.savefig(root/'data/processed/site_plan.png',dpi=160,bbox_inches='tight');plt.close(fig)
    levels=sorted({r['level'] for r in manifest['villa']['rooms']});fig,axes=plt.subplots(len(levels),1,figsize=(15,5*len(levels)),facecolor='#f3f1e8');axes=np.atleast_1d(axes)
    for ax,level in zip(axes,levels):
        ax.set_facecolor('#faf9f5')
        for i,room in enumerate(r for r in manifest['villa']['rooms'] if r['level']==level):
            x0,x1,y0,y1,z0,z1=room['bounds'];ax.add_patch(Rectangle((x0,y0),x1-x0,y1-y0,facecolor=plt.cm.Set3(i%12),edgecolor='#445050',alpha=.8));ax.text((x0+x1)/2,(y0+y1)/2,room['name'].replace('_','\n'),ha='center',va='center',fontsize=8)
        ax.set(xlim=(24,132),ylim=(108,170),aspect='equal',title=f'{level.upper()} — semantic room layout (metres)',xlabel='x / east',ylabel='y / north');ax.grid(alpha=.15)
    fig.tight_layout();fig.savefig(root/'data/processed/floor_plans.png',dpi=150);plt.close(fig)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=ROOT);parser.add_argument('--config',type=Path,default=ROOT/'configs/estate.json');args=parser.parse_args();root=args.output.resolve();config=json.loads(args.config.read_text())
    scene=Scene();print('Building villa and amenities...',flush=True);villa=build_villa(scene,config);amenities=build_amenities(scene,config)
    print('Sculpting terrain and forest...',flush=True);land,land_meta,grid=build_landscape(scene,config,villa.get('excavations',[])+amenities.get('excavations',[]))
    print('Exporting visual and collision assets...',flush=True);models=scene.export(root);write_world(root,models)
    manifest={'schema_version':1,'name':config['name'],'seed':config['seed'],'coordinate_system':'metres, x east, y north, z up','world_bounds':[-500,500,-500,500],'models':models,'villa':villa,'amenities':amenities,'landscape':land_meta,'spawn':{'name':'uav_lawn_spawn','position':[125,8,80.5]},'reference':'references/summit_estate_reference.png'}
    processed=root/'data/processed';processed.mkdir(parents=True,exist_ok=True)
    (processed/'scene.json').write_text(json.dumps(manifest,indent=2));np.savez_compressed(processed/'terrain.npz',x=grid[0],y=grid[1],z=grid[2]);scene.save_geometry(processed/'geometry.json.gz')
    views={'overview':{'position':[230,-470,345],'target':[-45,20,65]},'villa':{'position':[220,-66,147],'target':[84,135,85]},'arrival':{'position':[86,-28,101],'target':[78,136,85]},'lake':{'position':[-35,-110,142],'target':[-180,140,49]},'amenities':{'position':[240,15,133],'target':[156,116,80]},'gate':{'position':[-157,-449,39],'target':[-185,-381,29]}}
    views.update(villa.get('views',{}));(root/'configs').mkdir(exist_ok=True);(root/'configs/views.json').write_text(json.dumps(views,indent=2));make_plans(root,config,manifest,grid)
    inventory=[]
    for path in sorted((root/'gazebo').rglob('*')):
        if path.is_file():inventory.append({'path':str(path.relative_to(root)),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    (processed/'asset_manifest.json').write_text(json.dumps(inventory,indent=2))
    print(json.dumps({'models':len(models),'visual_triangles':sum(m['visual_triangles'] for m in models),'collision_shapes':sum(m['collisions'] for m in models),'trees':land_meta['tree_count'],'road_length_m':round(land_meta['road_length_m'],1),'max_grade_percent':round(100*land_meta['road_max_grade'],1)},indent=2))

if __name__=='__main__':main()
