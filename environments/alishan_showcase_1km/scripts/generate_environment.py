#!/usr/bin/env python3
"""Generate the complete offline Alishan showcase from a fixed procedural seed."""
import json
import os
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
from PIL import Image
from geometry import Mesh
from landscape import Landscape, nearest

ROOT=Path(__file__).resolve().parents[1]
MODELS=ROOT/'gazebo/models'


def xml_write(root,path):
    path.parent.mkdir(parents=True,exist_ok=True)
    ET.indent(root,space='  ')
    ET.ElementTree(root).write(path,encoding='utf-8',xml_declaration=True)


def model(name,meshes,collision_mesh=False,boxes=()):
    directory=MODELS/name
    sdf=ET.Element('sdf',version='1.9'); node=ET.SubElement(sdf,'model',name=name)
    ET.SubElement(node,'static').text='true'; link=ET.SubElement(node,'link',name='landscape')
    for filename in meshes:
        visual=ET.SubElement(link,'visual',name=Path(filename).stem)
        ET.SubElement(visual,'cast_shadows').text='true'
        geometry=ET.SubElement(visual,'geometry')
        ET.SubElement(ET.SubElement(geometry,'mesh'),'uri').text=f'model://{name}/meshes/{filename}'
        if collision_mesh:
            col=ET.SubElement(link,'collision',name=Path(filename).stem+'_collision')
            ET.SubElement(ET.SubElement(ET.SubElement(col,'geometry'),'mesh'),'uri').text=f'model://{name}/meshes/{filename}'
    for i,(center,size) in enumerate(boxes):
        col=ET.SubElement(link,'collision',name=f'foundation_{i}')
        ET.SubElement(col,'pose').text=' '.join(map(str,(*center,0,0,0)))
        ET.SubElement(ET.SubElement(ET.SubElement(col,'geometry'),'box'),'size').text=' '.join(map(str,size))
    xml_write(sdf,directory/'model.sdf')
    config=ET.Element('model'); ET.SubElement(config,'name').text=name
    ET.SubElement(config,'version').text='1.0'
    ET.SubElement(config,'sdf',version='1.9').text='model.sdf'
    ET.SubElement(config,'description').text='Procedural Alishan showcase asset; metres, Z up.'
    xml_write(config,directory/'model.config')


def texture(land,rng):
    n=2048; axis=np.linspace(-500,500,n)
    x,y=np.meshgrid(axis,axis)
    # Broad moss/grass variation plus a fine stipple, with exposed steep slopes.
    z=land.sample(x,y)
    gy,gx=np.gradient(z,1000/(n-1)); slope=np.hypot(gx,gy)
    variation=.06*np.sin(x/53+y/79)+.035*np.sin(x/11-y/19)+rng.normal(0,.025,(n,n))
    color=np.stack([.38+variation,.46+variation,.235+variation*.55],axis=-1)
    rock=np.clip((slope-.64)*.95,0,.75)[...,None]
    color=color*(1-rock)+np.array([.47,.45,.37])*rock
    image=Image.fromarray(np.uint8(np.clip(color[::-1]*255,0,255)))
    out=MODELS/'showcase_terrain/materials/textures/ground.png'
    out.parent.mkdir(parents=True,exist_ok=True); image.save(out)


def ribbon(mesh,land,xy,width,material,lift=.12,offset=0):
    length=np.r_[0,np.cumsum(np.linalg.norm(np.diff(xy,axis=0),axis=1))]
    distance=np.linspace(0,length[-1],max(len(xy),int(length[-1]/.8)+1))
    xy=np.column_stack([np.interp(distance,length,xy[:,j]) for j in range(2)])
    tangent=np.gradient(xy,axis=0)
    tangent/=np.linalg.norm(tangent,axis=1)[:,None]
    normal=np.column_stack([-tangent[:,1],tangent[:,0]])
    across=np.linspace(-width/2,width/2,max(2,int(width/.8)+1))+offset
    coords=xy[:,None,:]+normal[:,None,:]*across[None,:,None]
    z=land.sample(coords[...,0],coords[...,1])+lift
    vertices=np.dstack([coords,z]).reshape(-1,3)
    n=len(across); faces=[]
    for i in range(len(xy)-1):
        for j in range(n-1):
            a=i*n+j
            # normal points left, so longitudinal cross lateral points up.
            faces.extend([(a,a+n,a+n+1),(a,a+n+1,a+1)])
    mesh.add(vertices,faces,material)


def make_roads(land):
    mesh=Mesh(); records=[]; length=0
    for route in land.routes:
        xy=route['xy']; main=route is land.routes[0]
        width=land.config['road_width_m'] if main else 6
        ribbon(mesh,land,xy,land.config['road_shoulder_width_m'] if main else 9,'gravel',.055)
        ribbon(mesh,land,xy,width,'asphalt',.13)
        if main:
            for side in [-1,1]:
                ribbon(mesh,land,xy,.19,'white',.155,side*(width/2-.42))
            for i in range(0,len(xy)-3,9):
                ribbon(mesh,land,xy[i:i+4],.20,'gold',.17)
            # Short roadside posts reinforce depth without thousands of entities.
            tangent=np.gradient(xy,axis=0)
            tangent/=np.linalg.norm(tangent,axis=1)[:,None]
            for i in range(0,len(xy),18):
                p=xy[i]+np.array([-tangent[i,1],tangent[i,0]])*(width/2+1.7)
                z=float(land.sample(*p))
                mesh.box([*p,z+.65],[.22,.22,1.3],'white')
                mesh.box([*p,z+1.1],[.24,.24,.19],'gold')
        z=land.sample(xy[:,0],xy[:,1])
        route_length=float(np.linalg.norm(np.diff(xy,axis=0),axis=1).sum()); length+=route_length
        records.append(dict(name=route['name'],points=np.column_stack([xy,z]).round(5).tolist(),length_m=route_length))
    mesh.write(MODELS/'showcase_roads/meshes/roads.dae')
    model('showcase_roads',['roads.dae'])
    return mesh.triangle_count,records,length


def make_clearings(land):
    mesh=Mesh(); boxes=[]
    for pad in land.clearings:
        x,y,z=pad['x'],pad['y'],pad['z']
        if pad['launch']:
            size=28
            mesh.box([x,y,z-.15],[size,size,.6],'concrete')
            boxes.append(([x,y,z-.15],[size,size,.6]))
            for dx in [-3.5,3.5]:
                mesh.box([x+dx,y,z+.162],[1.25,10,.024],'white')
            mesh.box([x,y,z+.162],[7,1.25,.024],'white')
            theta=np.linspace(0,2*np.pi,81)
            ring=np.column_stack([x+10.5*np.cos(theta),y+10.5*np.sin(theta)])
            ribbon(mesh,land,ring,.35,'gold',.18)
            for dx in [-12,12]:
                for dy in [-12,12]:
                    mesh.box([x+dx,y+dy,z+.17],[1.4,1.4,.04],'gold')
            pad['pad_size_m']=size
        else:
            mesh.box([x,y,z-.12],[26,19,.4],'gravel')
            boxes.append(([x,y,z-.12],[26,19,.4]))
            pad['pad_size_m']=0
        sample=np.linspace(-14,14,15); xx,yy=np.meshgrid(sample+x,sample+y)
        pad['pad_terrain_relief_m']=float(np.ptp(land.sample(xx,yy)))
        pad['road_connection_distance_m']=min(float(np.linalg.norm(r['xy'][-1]-[x,y])) for r in land.routes)
        # Benches on the southern edge, outside the flight square.
        for dx in [-23,23]:
            bx=x+dx; by=y-(20 if pad['launch'] else 6); bz=float(land.sample(bx,by))
            mesh.box([bx,by,bz+.65],[3,.65,.18],'wood')
            for leg in [-1,1]: mesh.box([bx+leg,by,bz+.3],[.18,.5,.6],'roof')
    mesh.write(MODELS/'showcase_clearings/meshes/clearings.dae')
    model('showcase_clearings',['clearings.dae'],boxes=boxes)
    return mesh.triangle_count


def make_buildings(land):
    mesh=Mesh(); boxes=[]
    for b in land.buildings:
        x,y,z,w,d,h=(b[k] for k in ['x','y','z','width','depth','height'])
        mesh.box([x,y,z+.2],[w+1.6,d+1.6,.8],'stone')
        mesh.box([x,y,z+h/2+.5],[w,d,h],'plaster')
        mesh.box([x,y,z+1.05],[w+.08,d+.08,1.3],'wood')
        boxes.append(([x,y,z+(h+2.5)/2],[w,d,h+2.5]))
        # Gabled roof, deep eaves, and a warm timber fascia.
        rx=w/2+1; ry=d/2+1; e=z+h+.35; peak=e+2.5
        vertices=[(x-rx,y-ry,e),(x+rx,y-ry,e),(x+rx,y+ry,e),(x-rx,y+ry,e),
                  (x-rx,y,peak),(x+rx,y,peak)]
        mesh.add(vertices,[(0,1,5),(0,5,4),(4,5,2),(4,2,3),(0,4,3),(1,2,5),(0,3,2),(0,2,1)],b['roof'])
        for dx in [-w*.29,w*.29]:
            mesh.box([x+dx,y-d/2-.06,z+2.6],[1.8,.14,1.55],'roof')
            mesh.box([x+dx,y-d/2-.14,z+2.6],[1.55,.08,1.3],'glass')
            mesh.box([x+dx,y-d/2-.2,z+2.6],[.09,.06,1.35],'white')
        mesh.box([x,y-d/2-.08,z+1.6],[1.25,.18,2.2],'wood')
        mesh.box([x,y-d/2-1,z+.35],[3,1.8,.35],'stone')
        for side in [-1,1]:
            mesh.box([x+side*(w/2+.04),y,z+2.5],[.12,2,1.6],'glass')
        xx,yy=np.meshgrid(np.linspace(x-w/2,x+w/2,5),np.linspace(y-d/2,y+d/2,5))
        b['foundation_terrain_relief_m']=float(np.ptp(land.sample(xx,yy)))
    mesh.write(MODELS/'showcase_village/meshes/cabins.dae')
    model('showcase_village',['cabins.dae'],boxes=boxes)
    return mesh.triangle_count


def tea_area(x,y):
    return ((x-185)/67)**2+((y-20)/47)**2<1


def make_tea(land):
    mesh=Mesh()
    for y in np.arange(-20,61,5):
        x=np.arange(120,252,2.)
        curve=np.column_stack([x,y+4*np.sin((x-120)/58)])
        curve=curve[tea_area(curve[:,0],curve[:,1])]
        if len(curve)<3: continue
        ribbon(mesh,land,curve,2.3,'tea',.9)
        for offset in [-1,1]:
            ribbon(mesh,land,curve,.4,'broadleaf_light',.65,offset)
    mesh.write(MODELS/'showcase_tea/meshes/tea_rows.dae')
    model('showcase_tea',['tea_rows.dae'])
    return mesh.triangle_count


def tree(mesh,x,y,z,height,radius,species,angle):
    mesh.cone((x,y,z-.15),.26 if species=='bamboo' else .45,height*.64,'bark',5,top=.6,angle=angle)
    if species=='cedar':
        for base,r,h,mat in [(.21,1,.47,'cedar'),(.44,.77,.39,'cedar_light'),(.65,.52,.35,'cedar')]:
            mesh.cone((x,y,z+height*base),radius*r,height*h,mat,7,angle=angle)
    elif species=='broadleaf':
        mesh.crown((x,y,z+height*.72),radius,height*.57,'broadleaf',angle)
        mesh.crown((x+radius*.33,y-radius*.24,z+height*.84),radius*.62,height*.36,'broadleaf_light',angle+.4)
    else:
        for dx,dy in [(-.7,0),(.6,.6),(0,-.7)]:
            mesh.cone((x+dx,y+dy,z),.09,height*.8,'bamboo',4,top=.75)
        mesh.crown((x,y,z+height*.76),radius,height*.52,'bamboo',angle)


def make_forest(land,rng):
    spacing=land.config['tree_spacing_m']
    x,y=np.meshgrid(np.arange(-488,490,spacing),np.arange(-488,490,spacing))
    xy=np.column_stack([x.ravel(),y.ravel()])+rng.uniform(-spacing*.38,spacing*.38,(x.size,2))
    d,_=nearest(xy,np.vstack([r['xy'] for r in land.routes]))
    # Clustered density and varying silhouettes, with lower sparse meadows.
    chance=land.config['tree_probability']+.10*np.sin(xy[:,0]/75)*np.cos(xy[:,1]/62)
    keep=(rng.random(len(xy))<chance)&(d>14)
    keep&=~tea_area(xy[:,0],xy[:,1])
    for pad in land.clearings:
        keep&=(np.abs(xy[:,0]-pad['x'])>pad['half_x']+10)|(np.abs(xy[:,1]-pad['y'])>pad['half_y']+11)
    xy=xy[keep]; d=d[keep]
    z=land.sample(xy[:,0],xy[:,1]); tiles={}; records=[]
    for i,((x,y),ground) in enumerate(zip(xy,z)):
        pick=rng.random()
        species='cedar' if pick<.65 else ('broadleaf' if pick<.91 else 'bamboo')
        height=float(rng.uniform(15,28) if species=='cedar' else rng.uniform(12,22))
        radius=float(rng.uniform(4.0,6.4) if species!='bamboo' else rng.uniform(2.3,3.4))
        key=(int((x+500)//125),int((y+500)//125))
        mesh=tiles.setdefault(key,Mesh())
        tree(mesh,float(x),float(y),float(ground),height,radius,species,float(rng.uniform(0,6.28)))
        records.append(dict(x=round(float(x),5),y=round(float(y),5),z=round(float(ground),5),height=round(height,3),radius=round(radius,3),species=species))
    names=[]; triangles=0
    for (ix,iy),mesh in sorted(tiles.items()):
        name=f'forest_{ix}_{iy}.dae'; names.append(name)
        mesh.write(MODELS/'showcase_forest/meshes'/name); triangles+=mesh.triangle_count
    model('showcase_forest',names)
    return triangles,records,float(np.min(d-np.array([t['radius'] for t in records])))


def world():
    sdf=ET.Element('sdf',version='1.9'); w=ET.SubElement(sdf,'world',name='alishan_showcase')
    ET.SubElement(w,'gravity').text='0 0 -9.81'
    physics=ET.SubElement(w,'physics',name='showcase',type='ignored')
    ET.SubElement(physics,'max_step_size').text='0.004'
    ET.SubElement(physics,'real_time_factor').text='1'
    for suffix,name in [('physics','Physics'),('user-commands','UserCommands'),('scene-broadcaster','SceneBroadcaster')]:
        ET.SubElement(w,'plugin',filename=f'gz-sim-{suffix}-system',name='gz::sim::systems::'+name)
    scene=ET.SubElement(w,'scene')
    ET.SubElement(scene,'ambient').text='0.64 0.67 0.68 1'
    ET.SubElement(scene,'background').text='0.72 0.82 0.88 1'
    ET.SubElement(scene,'shadows').text='true'
    light=ET.SubElement(w,'light',name='morning_sun',type='directional')
    ET.SubElement(light,'pose').text='0 0 1000 0 0 0'
    ET.SubElement(light,'cast_shadows').text='true'
    ET.SubElement(light,'diffuse').text='0.95 0.88 0.73 1'
    ET.SubElement(light,'specular').text='0.10 0.10 0.08 1'
    ET.SubElement(light,'direction').text='-0.45 0.35 -0.85'
    gui=ET.SubElement(w,'gui',fullscreen='false')
    plugin=ET.SubElement(gui,'plugin',filename='MinimalScene',name='3D View')
    props=ET.SubElement(plugin,'gz-gui')
    ET.SubElement(props,'title').text='Alishan Showcase 1km | V1'
    ET.SubElement(props,'property',type='bool',key='showTitleBar').text='false'
    ET.SubElement(props,'property',type='string',key='state').text='docked'
    ET.SubElement(plugin,'engine').text='ogre2'
    ET.SubElement(plugin,'scene').text='scene'
    ET.SubElement(plugin,'ambient_light').text='0.64 0.67 0.68'
    ET.SubElement(plugin,'background_color').text='0.72 0.82 0.88'
    vx,vy,vz,pitch,yaw=json.loads((ROOT/'configs/views.json').read_text())['overview']
    ET.SubElement(plugin,'camera_pose').text=f'{vx} {vy} {vz} 0 {pitch} {yaw}'
    clip=ET.SubElement(plugin,'camera_clip')
    ET.SubElement(clip,'near').text='0.5'; ET.SubElement(clip,'far').text='6000'
    for filename,name in [('GzSceneManager','Scene Manager'),('InteractiveViewControl','View control'),('CameraTracking','Camera tracking'),('WorldControl','World control'),('WorldStats','Statistics'),('Screenshot','Screenshot')]:
        p=ET.SubElement(gui,'plugin',filename=filename,name=name)
        g=ET.SubElement(p,'gz-gui')
        ET.SubElement(g,'property',key='state',type='string').text='floating'
        ET.SubElement(g,'property',key='showTitleBar',type='bool').text='false'
        if filename in ['GzSceneManager','InteractiveViewControl','CameraTracking']:
            ET.SubElement(g,'property',key='width',type='double').text='5'
            ET.SubElement(g,'property',key='height',type='double').text='5'
    for name in ['terrain','roads','clearings','village','tea','forest']:
        ET.SubElement(ET.SubElement(w,'include'),'uri').text='model://showcase_'+name
    xml_write(sdf,ROOT/'gazebo/worlds/alishan_showcase.sdf')


def preview(land,scene):
    os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'.runtime/matplotlib'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.colors import LightSource
    fig,ax=plt.subplots(figsize=(10,10),facecolor='#eff1e8')
    shade=LightSource(azdeg=315,altdeg=48).shade(land.z,cmap=plt.get_cmap('gist_earth'),vert_exag=.6,dx=4,dy=4)
    ax.imshow(shade,extent=(-500,500,-500,500),origin='lower')
    t=scene['trees']; ax.scatter([p['x'] for p in t],[p['y'] for p in t],s=2,c='#264b32',alpha=.5,linewidths=0)
    for r in land.routes:
        ax.plot(*r['xy'].T,color='#e2d5b4',linewidth=5)
        ax.plot(*r['xy'].T,color='#515854',linewidth=2.4)
    for b in land.buildings:
        ax.add_patch(plt.Rectangle((b['x']-b['width']/2,b['y']-b['depth']/2),b['width'],b['depth'],color='#903f30'))
    for p in land.clearings:
        ax.plot(p['x'],p['y'],'s',color='#f9d265',markersize=12)
        ax.annotate(p['name'],(p['x'],p['y']),xytext=(8,-21),textcoords='offset points',fontsize=10,fontweight='bold',bbox=dict(facecolor='white',alpha=.85,edgecolor='none',pad=3))
    ax.set(xlim=(-500,500),ylim=(-500,500),xlabel='X (metres)',ylabel='Y (metres)',title='ALISHAN SHOWCASE 1km\nV1 · Scenic mountain UAV park · Procedural site plan')
    fig.tight_layout(); fig.savefig(ROOT/'data/processed/site_plan.png',dpi=150); plt.close(fig)


def main():
    config=json.loads((ROOT/'configs/showcase.json').read_text())
    rng=np.random.default_rng(config['seed'])
    out=ROOT/'data/processed'; out.mkdir(parents=True,exist_ok=True)
    print('Sculpting terrain and grading connected roads...',flush=True)
    land=Landscape(config); terrain=land.terrain_mesh()
    texture(land,rng)
    terrain.write(MODELS/'showcase_terrain/meshes/terrain.dae','../materials/textures/ground.png')
    model('showcase_terrain',['terrain.dae'],collision_mesh=True)
    np.savez_compressed(out/'terrain.npz',x=land.axis,y=land.axis,z=land.z)
    print('Building roads, clearings, cabins and tea slopes...',flush=True)
    road_tri,roads,length=make_roads(land)
    triangles=terrain.triangle_count+road_tri+make_clearings(land)+make_buildings(land)+make_tea(land)
    print('Batching mixed forest into 125m tiles...',flush=True)
    forest_tri,trees,clearance=make_forest(land,rng); triangles+=forest_tri
    world()
    scene=dict(version=config['version'],seed=config['seed'],size_m=config['size_m'],
               elevation_min_m=float(land.z.min()),elevation_max_m=float(land.z.max()),
               render_triangle_count=triangles,road_length_m=length,roads=roads,
               clearings=land.clearings,buildings=land.buildings,trees=trees,
               max_tree_ground_error_m=float(max(abs(t['z']-land.sample(t['x'],t['y'])) for t in trees)),
               min_tree_road_clearance_m=clearance)
    (out/'scene.json').write_text(json.dumps(scene,indent=2)+'\n')
    preview(land,scene)
    print(f'Generated {len(trees)} trees, {len(land.buildings)} cabins, {length:.0f} m of roads, {triangles:,} triangles.',flush=True)
    print(f'Elevation: {land.z.min():.1f}–{land.z.max():.1f} m; relief {np.ptp(land.z):.1f} m.',flush=True)


if __name__=='__main__':
    main()
