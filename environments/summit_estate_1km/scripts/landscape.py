"""Sculpted 1 km hillside, graded road, natural lake and batched forest."""
import math
import numpy as np
from geometry import triangulate


def smooth(t):
    t=np.clip(t,0,1);return t*t*(3-2*t)


def road_curve(control):
    control=np.array(control,float);padded=np.vstack((2*control[0]-control[1],control,2*control[-1]-control[-2]));points=[]
    for i in range(1,len(padded)-2):
        p0,p1,p2,p3=padded[i-1:i+3];n=max(12,int(np.linalg.norm(p2[:2]-p1[:2])/1.5))
        for t in np.linspace(0,1,n,endpoint=False):
            xy=.5*((2*p1)+(p2-p0)*t+(2*p0-5*p1+4*p2-p3)*t*t+(-p0+3*p1-3*p2+p3)*t*t*t)
            xy[2]=p1[2]+t*(p2[2]-p1[2]);points.append(xy)
    return np.vstack((points,control[-1]))


class Landscape:
    def __init__(self,config,excavations=()):
        self.config=config;self.road=road_curve(config['road']['control_points']);self.excavations=list(excavations)
    def nearest_road(self,x,y):
        shape=np.shape(x);pts=np.column_stack((np.ravel(x),np.ravel(y)));a=self.road[:-1,:2];d=np.diff(self.road[:,:2],axis=0);l2=(d*d).sum(axis=1)
        distances=[];zs=[]
        for start in range(0,len(pts),768):
            delta=pts[start:start+768,None,:]-a[None,:,:]
            t=np.clip((delta*d).sum(axis=2)/l2,0,1)
            delta-=t[:,:,None]*d;dist=(delta*delta).sum(axis=2);idx=dist.argmin(axis=1);row=np.arange(len(idx))
            distances.extend(np.sqrt(dist[row,idx]));zs.extend(self.road[idx,2]+t[row,idx]*np.diff(self.road[:,2])[idx])
        return np.array(distances).reshape(shape),np.array(zs).reshape(shape)
    def lake_radius(self,x,y):
        lake=self.config['lake'];cx,cy=lake['center'];rx,ry=lake['radii']
        xx=(x-cx)/rx;yy=(y-cy)/ry;a=np.arctan2(yy,xx)
        return np.hypot(xx,yy)/(1+.065*np.sin(3*a+.4)+.035*np.sin(7*a-1))
    def height(self,x,y):
        x,y=np.asarray(x,dtype=float),np.asarray(y,dtype=float)
        z=34+.065*(y+300)+10*np.sin(x/105)*np.cos(y/110)+4*np.sin(x/27+y/33)
        # Forested mountain walls, inside the physical kilometre boundary.
        for cx,cy,h,sx,sy in [(-370,320,120,145,125),(-50,435,115,110,85),(260,420,135,120,105),(430,130,85,95,185),(-430,-80,68,95,135)]:
            z+=h*np.exp(-((x-cx)/sx)**2-((y-cy)/sy)**2)
        dx=np.maximum(np.maximum(-48-x,x-235),0);dy=np.maximum(np.maximum(-34-y,y-214),0)
        w=1-smooth(np.hypot(dx,dy)/65);z=z*(1-w)+80*w
        q=self.lake_radius(x,y);basin=49+np.maximum(q-1,-.27)*31
        lw=1-smooth((q-1.07)/.21);z=z*(1-lw)+basin*lw
        distance,road_z=self.nearest_road(x,y);rw=1-smooth((distance-6.7)/14)
        z=z*(1-rw)+road_z*rw
        # Formal gate wings need their own graded clearing outside the road strip.
        gx,gy,gz=self.config['gate']['center']
        gate_distance=np.hypot(np.maximum(abs(x-gx)-31,0),np.maximum(abs(y-gy)-13,0))
        gw=(1-smooth(gate_distance/17))*smooth((distance-6.7)/5)
        gate_grade=gz+(y-gy)*.068
        z=z*(1-gw)+gate_grade*gw
        # A small lakefront shelf connects the pavilion to dry shore.
        ds=np.hypot(np.maximum(abs(x+42)-7,0),np.maximum(abs(y-100)-6,0))
        sw=1-smooth(ds/6);z=z*(1-sw)+49.35*sw
        for cut in self.excavations:
            x0,x1,y0,y1=cut['bounds'];inside=(x>=x0)&(x<=x1)&(y>=y0)&(y<=y1)
            z=np.where(inside,cut['z'],z)
        # West sunken garden access slope; actual basement exterior door remains open.
        ramp=(x>=-30)&(x<8)&(y>=132)&(y<=148)
        z=np.where(ramp,80-(x+30)/38*5.6,z)
        return z


def ribbon(model,name,line,left,right,material,collision=False,zoffset=0):
    pts=np.asarray(line);t=np.gradient(pts[:,:2],axis=0);t/=np.linalg.norm(t,axis=1)[:,None];normal=np.column_stack((-t[:,1],t[:,0]));v=[]
    for off in [left,right]:v.append(np.column_stack((pts[:,:2]+normal*off,pts[:,2]+zoffset)))
    v=np.concatenate(v);n=len(pts);f=[]
    for i in range(n-1):f.extend([[i,n+i,i+1],[i+1,n+i,n+i+1]])
    return model.mesh(name,v,np.asarray(f)[:,::-1],material,collision)


def cone_mesh(center,radius,height,n,phase=0):
    x,y,z=center;angles=np.arange(n)*2*np.pi/n+phase
    v=np.vstack((np.column_stack((x+radius*np.cos(angles),y+radius*np.sin(angles),np.full(n,z))),[x,y,z+height],[x,y,z]))
    f=[]
    for i in range(n):j=(i+1)%n;f.extend([[i,j,n],[n+1,j,i]])
    return v,np.asarray(f)


def build_landscape(scene,config,excavations):
    land=Landscape(config,excavations)
    # Local 2m sampling; cut edges receive explicit neighbouring grid coordinates.
    xs=list(np.arange(-500,501,5))+list(np.arange(0,212,2))
    ys=list(np.arange(-500,501,5))+list(np.arange(-40,212,2))
    for cut in excavations:
        x0,x1,y0,y1=cut['bounds'];xs.extend([x0-.15,x0,x1,x1+.15]);ys.extend([y0-.15,y0,y1,y1+.15])
    xs=np.unique(xs);ys=np.unique(ys);xx,yy=np.meshgrid(xs,ys);zz=land.height(xx,yy)
    vertices=np.column_stack((xx.ravel(),yy.ravel(),zz.ravel()));nx=len(xs);indices=np.arange(len(vertices)).reshape(len(ys),nx)
    a=indices[:-1,:-1].ravel();b=a+1;c=a+nx;d=c+1;faces=np.vstack((np.column_stack((a,b,d)),np.column_stack((a,d,c))))
    terrain=scene.model('summit_terrain')
    # Ground colors follow slope plus broad mottling to read at aerial scale.
    normals=np.cross(vertices[faces[:,1]]-vertices[faces[:,0]],vertices[faces[:,2]]-vertices[faces[:,0]])
    slope=np.hypot(normals[:,0],normals[:,1])/np.maximum(normals[:,2],1e-6)
    centers=vertices[faces].mean(axis=1);pattern=np.sin(centers[:,0]/28)*np.sin(centers[:,1]/38)+.45*np.sin((centers[:,0]+centers[:,1])/11)
    classes=np.where(slope>.8,3,np.where(pattern>.5,1,np.where(pattern<-.45,2,0)))
    for cls,mat in enumerate(['grass','grass_light','grass_dark','rock']):
        terrain.mesh('surface_'+mat,vertices,faces[classes==cls],mat,False)
    o=terrain.mesh('ground_collision',vertices,faces,'grass',True);o['visual']=False
    road=scene.model('summit_road');w=config['road']['width']
    ribbon(road,'asphalt_surface',land.road,-w/2,w/2,'asphalt',True,.12)
    for off in [-w/2,w/2]:
        ribbon(road,'curb_'+str(off).replace('-','minus'),land.road,off-.3,off+.3,'stone',True,.18)
        ribbon(road,'edge_mark_'+str(off).replace('-','minus'),land.road,off-.055,off+.055,'white',False,.195)
    # Centerline dashes, road furniture and an occasional scenic overlook.
    for i in range(0,len(land.road)-4,12):ribbon(road,f'dash_{i}',land.road[i:i+5],-.06,.06,'sand',False,.135)
    for i in range(12,len(land.road)-16,25):
        p=land.road[i];t=land.road[i+1,:2]-land.road[i-1,:2];t/=np.linalg.norm(t);n=np.array([-t[1],t[0]])
        for side in [-1,1]:
            xy=p[:2]+n*side*6.6;z=float(land.height(*xy))
            road.box(f'bollard_{i}_{side}',[*xy,z+.5],[.22,.22,1.0],'charcoal',True)
            road.box(f'lamp_{i}_{side}',[*xy,z+.88],[.25,.25,.1],'emissive',False)
    lake=scene.model('summit_lake');cx,cy=config['lake']['center'];rx,ry=config['lake']['radii'];wz=config['lake']['water_z'];angles=np.arange(160)*2*np.pi/160
    radial=1+.065*np.sin(3*angles+.4)+.035*np.sin(7*angles-1)
    boundary=np.column_stack((cx+rx*radial*np.cos(angles),cy+ry*radial*np.sin(angles),np.full(160,wz)))
    v=np.vstack(([cx,cy,wz],boundary));f=[[0,i+1,(i+1)%160+1] for i in range(160)]
    lake.mesh('water_surface',v,f,'water',False)
    # Subtle flat ripple rings provide water cues without particles/dynamics.
    scene.materials['water_ripple']={'color':[.11,.31,.35,1],'roughness':.18}
    for i,(x,y,r) in enumerate([(-220,100,20),(-145,150,30),(-245,175,24),(-95,105,8)]):
        lake.ring(f'ripple_{i}',(x,y,wz+.008),r,r+.07,.008,'water_ripple',False,96)
    rng=np.random.default_rng(config['seed']);shore=scene.model('summit_shore')
    for i,a in enumerate(np.linspace(0,2*np.pi,95,endpoint=False)):
        q=1.025+rng.uniform(0,.06);r=1+.065*np.sin(3*a+.4)+.035*np.sin(7*a-1);x=cx+rx*r*q*np.cos(a);y=cy+ry*r*q*np.sin(a)
        if abs(y-100)<12 and x>-85:continue
        z=float(land.height(x,y));shore.sphere(f'shore_rock_{i}',(x,y,z+.45),(rng.uniform(1.1,2.7),rng.uniform(.8,2),rng.uniform(.7,1.8)),'rock',True,8,4)
    # Dense forest is batched into geographic sectors, with low-poly trunk/canopy collisions.
    candidates=rng.uniform(-490,490,(7300,2));dist,_=land.nearest_road(candidates[:,0],candidates[:,1]);q=land.lake_radius(candidates[:,0],candidates[:,1]);x,y=candidates.T
    keep=(dist>17)&(q>1.14)&~((x>-55)&(x<249)&(y>-42)&(y<225))&~((x>-219)&(x<-150)&(y>-424)&(y<-362))&~((x>-105)&(x<-20)&(y>83)&(y<118))
    points=candidates[keep];heights=land.height(points[:,0],points[:,1]);batches={};tree_records=[]
    for i,((x,y),ground) in enumerate(zip(points,heights)):
        key=(int((x+500)//250),int((y+500)//250));m=scene.model(f'summit_forest_{key[0]}_{key[1]}')
        height=rng.uniform(10,22);radius=rng.uniform(2.4,4.9);phase=rng.uniform(0,2*np.pi)
        m.cylinder(f'trunk_{i}',(x,y,ground+height*.34),.26,height*.68,'trunk',False,6)
        for j,(fheight,fradius,fbase) in enumerate([(0.55,1.,.20),(.48,.80,.40),(.43,.55,.59)]):
            v,f=cone_mesh((x,y,ground+height*fbase),radius*fradius,height*fheight,9,phase+j*.27)
            # Ring vertices get a slight irregularity instead of identical perfect cones.
            v[:9,:2]+=(rng.random((9,2))-.5)*.45
            m.mesh(f'crown_{i}_{j}',v,f,f'leaf{(i+j)%3}',False)
        if key not in batches:batches[key]=[[],[],0]
        bucket=batches[key];cv,cf=cone_mesh((x,y,ground+height*.20),radius,height*.83,6,phase)
        tr={'kind':'cylinder','center':[x,y,ground+height*.19],'radius':.3,'length':height*.38,'segments':6}
        tv,tf=triangulate(tr);cv=np.vstack((cv,tv));cf=np.vstack((cf,tf+len(cv)-len(tv)))
        bucket[0].append(cv);bucket[1].append(cf+bucket[2]);bucket[2]+=len(cv)
        tree_records.append([round(float(x),3),round(float(y),3),round(float(ground),3),round(float(height),2),round(float(radius),2)])
    for key,(vs,fs,_) in batches.items():
        obj=scene.models[f'summit_forest_{key[0]}_{key[1]}'].mesh('forest_collision',np.concatenate(vs),np.concatenate(fs),'trunk',True);obj['visual']=False
    # Exposed mountain boulders accent the terrain, keeping the central flight lawn clear.
    rocks=scene.model('summit_boulders')
    for i in range(150):
        x,y=rng.uniform(-480,480,2)
        if -95<x<260 and -70<y<255:continue
        if land.lake_radius(x,y)<1.1 or land.nearest_road(x,y)[0]<13:continue
        z=float(land.height(x,y));r=rng.uniform(2,6)
        rocks.sphere(f'outcrop_{i}',(x,y,z+.4),(r,r*.75,r*.62),'rock',True,8,4)
    return land,{'road_centerline':land.road.tolist(),'road_width':w,'road_length_m':float(np.linalg.norm(np.diff(land.road[:,:2],axis=0),axis=1).sum()),'road_max_grade':float(np.max(abs(np.diff(land.road[:,2]))/np.linalg.norm(np.diff(land.road[:,:2],axis=0),axis=1))),'terrain_grid_shape':list(xx.shape),'terrain_elevation_range':[float(zz.min()),float(zz.max())],'tree_count':len(points),'trees':tree_records,'lake_boundary':boundary.tolist(),'excavations':excavations},(xs,ys,zz)
