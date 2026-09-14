"""Terrain, graded roads and clearings; all placements sample exported triangles."""
import numpy as np


def smoothstep(x):
    x=np.clip(x,0,1)
    return x*x*(3-2*x)


def natural_height(x,y):
    z=55+.135*(y+500)+.025*x
    for cx,cy,sx,sy,h in [(-340,190,160,255,138),(285,240,200,210,174),
                          (-80,440,260,135,112),(80,-260,180,150,66),
                          (-390,-340,150,150,50),(460,-190,130,280,70)]:
        z=z+h*np.exp(-(((x-cx)/sx)**2+((y-cy)/sy)**2)/2)
    z=z-53*np.exp(-((x+40+75*np.sin(y/180))/100)**2/2)*np.exp(-(y/370)**2/2)
    return z+7*np.sin(x/57+y/95)+4*np.sin(x/28-y/69)+2*np.cos(x/15+y/27)


def spline(points,step=2):
    """Catmull-Rom spline resampled to approximately uniform arc distance."""
    p=np.asarray(points,dtype=float)
    q=np.vstack([2*p[0]-p[1],p,2*p[-1]-p[-2]])
    chunks=[]
    for i in range(1,len(q)-2):
        a,b,c,d=q[i-1:i+3]
        t=np.linspace(0,1,max(12,int(np.linalg.norm(c-b))),endpoint=False)[:,None]
        chunks.append(.5*((2*b)+(-a+c)*t+(2*a-5*b+4*c-d)*t*t+(-a+3*b-3*c+d)*t*t*t))
    curve=np.vstack([*chunks,p[-1:]])
    length=np.r_[0,np.cumsum(np.linalg.norm(np.diff(curve,axis=0),axis=1))]
    at=np.linspace(0,length[-1],int(length[-1]/step)+1)
    return np.column_stack([np.interp(at,length,curve[:,j]) for j in range(2)])


def nearest(points,curve):
    """Bounded-memory exact nearest sampled centerline point."""
    points=np.asarray(points).reshape(-1,2)
    dist=np.empty(len(points)); indexes=np.empty(len(points),dtype=int)
    for start in range(0,len(points),1536):
        d=((points[start:start+1536,None,:]-curve[None,:,:2])**2).sum(axis=2)
        i=np.argmin(d,axis=1)
        indexes[start:start+len(i)]=i
        dist[start:start+len(i)]=np.sqrt(d[np.arange(len(i)),i])
    return dist,indexes


class Landscape:
    def __init__(self,config):
        self.config=config
        n=config['grid_samples']; extent=config['size_m']/2
        self.axis=np.linspace(-extent,extent,n)
        self.x,self.y=np.meshgrid(self.axis,self.axis)
        self.z=natural_height(self.x,self.y)
        xy=np.column_stack([self.x.ravel(),self.y.ravel()])
        main=spline(config['road_control_points'])
        rz=natural_height(main[:,0],main[:,1])
        rz=np.convolve(np.pad(rz,40,mode='edge'),np.ones(81)/81,mode='valid')
        ds=np.linalg.norm(np.diff(main,axis=0),axis=1)
        arc=np.r_[0,np.cumsum(ds)]
        allowed_rise=.145*ds
        # Give each clearing a level approach before grading; flattening a
        # clearing afterwards must not introduce a step in the through road.
        for pad in config['clearings']:
            _,idx=nearest([[pad['x'],pad['y']]],main)
            i=int(idx[0]); distance=np.abs(arc-arc[i])
            blend=1-smoothstep((distance-(pad['half_x']+42))/85)
            rz=rz*(1-blend)+rz[i]*blend
            plateau=distance<(pad['half_x']+42)
            allowed_rise[plateau[:-1]&plateau[1:]]=0
        # Project grades to a 15% envelope, then soften grade transitions.
        for _ in range(6):
            for i in range(1,len(rz)):
                rz[i]=np.clip(rz[i],rz[i-1]-allowed_rise[i-1],rz[i-1]+allowed_rise[i-1])
            for i in range(len(rz)-2,-1,-1):
                rz[i]=np.clip(rz[i],rz[i+1]-allowed_rise[i],rz[i+1]+allowed_rise[i])
        rz=np.convolve(np.pad(rz,12,mode='edge'),np.ones(25)/25,mode='valid')
        self.routes=[dict(name='Mountain Scenic Road',xy=main,target=rz)]
        self.clearings=[]
        for item in config['clearings']:
            item=dict(item)
            _,idx=nearest([[item['x'],item['y']]],main)
            item['z']=float(rz[idx[0]])
            start=main[idx[0]]; end=np.array([item['x'],item['y']])
            t=np.linspace(0,1,max(3,int(np.linalg.norm(end-start)/2)+1))
            spur=start[None,:]*(1-t[:,None])+end[None,:]*t[:,None]
            self.routes.append(dict(name=item['name']+' access',xy=spur,target=np.full(len(spur),item['z'])))
            self.clearings.append(item)
        for route in self.routes:
            d,i=nearest(xy,route['xy'])
            # Project onto the adjoining line segments instead of assigning
            # the nearest vertex height, which produces stair steps in slopes.
            best=np.full(len(xy),np.inf); target=np.zeros(len(xy))
            for start in [np.maximum(i-1,0),np.minimum(i,len(route['xy'])-2)]:
                a=route['xy'][start]; delta=route['xy'][start+1]-a
                t=np.clip(np.sum((xy-a)*delta,axis=1)/np.sum(delta*delta,axis=1),0,1)
                distance=np.linalg.norm(xy-a-t[:,None]*delta,axis=1)
                nearer=distance<best
                target[nearer]=(route['target'][start]*(1-t)+route['target'][start+1]*t)[nearer]
                best=np.minimum(best,distance)
            d=best
            # Include one full terrain-cell diagonal beyond the 7m shoulder.
            # This prevents shoulder triangles crossing the steep cut edge.
            blend=1-smoothstep((d-14)/25)
            self.z=self.z*(1-blend.reshape(n,n))+target.reshape(n,n)*blend.reshape(n,n)
        for pad in self.clearings:
            self.flatten(pad['x'],pad['y'],pad['half_x'],pad['half_y'],pad['z'],18)
        self.buildings=[]
        for index,pad in enumerate(self.clearings):
            # Cabins occupy the outer edge; launch pad remains in the centre.
            for j,(dx,dy) in enumerate([(-28,22),(-8,22),(15,22),(32,17)]):
                if index==1:
                    dy=-dy
                x=pad['x']+dx; y=pad['y']+dy
                w=12 if j==1 else 9; depth=8
                self.flatten(x,y,w/2+2,depth/2+2,pad['z'],9)
                self.buildings.append(dict(name=f'cabin_{index}_{j}',x=x,y=y,z=pad['z'],width=w,depth=depth,height=5.5 if j==1 else 4.5,roof='roof_green' if index==2 else 'roof'))

    def flatten(self,x,y,hx,hy,z,margin):
        distance=np.maximum(np.abs(self.x-x)-hx,np.abs(self.y-y)-hy)
        blend=1-smoothstep(distance/margin)
        self.z=self.z*(1-blend)+z*blend

    def sample(self,x,y):
        """Piecewise linear interpolation matching the mesh diagonal exactly."""
        x,y=np.broadcast_arrays(np.asarray(x,dtype=float),np.asarray(y,dtype=float))
        step=self.axis[1]-self.axis[0]; n=len(self.axis)
        u=np.clip((x-self.axis[0])/step,0,n-1-1e-9)
        v=np.clip((y-self.axis[0])/step,0,n-1-1e-9)
        i=u.astype(int); j=v.astype(int); a=u-i; b=v-j
        z00=self.z[j,i]; z10=self.z[j,i+1]; z01=self.z[j+1,i]; z11=self.z[j+1,i+1]
        return np.where(a>=b,z00+(z10-z00)*a+(z11-z10)*b,z00+(z11-z01)*a+(z01-z00)*b)

    def terrain_mesh(self):
        from geometry import Mesh
        n=len(self.axis); m=Mesh()
        vertices=np.column_stack([self.x.ravel(),self.y.ravel(),self.z.ravel()])
        i,j=np.meshgrid(np.arange(n-1),np.arange(n-1)); a=(j*n+i).ravel()
        faces=np.vstack([np.column_stack([a,a+1,a+n+1]),np.column_stack([a,a+n+1,a+n])])
        uv=(vertices[:,:2]-self.axis[0])/(self.axis[-1]-self.axis[0])
        m.add(vertices,faces,'terrain',uv)
        return m
