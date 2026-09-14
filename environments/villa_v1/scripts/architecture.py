"""Thick, modular architectural shell; dimensions are metres."""
import bpy,math
import scene_utils as U
Z={'B1':-4.2,'1F':0.0,'2F':5.8,'3F':10.0,'ROOF':14.2}
HEIGHT={'B1':4.2,'1F':5.8,'2F':4.2,'3F':4.2}
ROOMS={
'B1':{'gym':(-25,-13,-16,-4),'cinema':(-8,5,-16,-5),'acoustic_lobby':(-8,5,-5,-1.8),'library':(-25,-8,1,18),'wine':(-7,0,7,15),'lounge':(1,14,2,17),'laundry':(20,27,-16,-6),'mechanical':(28,38,-16,-5),'gym_shower':(17,21,2,8),'bathroom':(21,25,2,8),'linen':(17,25,9,17)},
'1F':{'foyer':(-8,8,-16,10),'piano':(-8,8,10,18),'living':(-23,-11,6,18),'daily_lounge':(-23,-11,-4.8,4.8),'dining':(11,21,8,17),'kitchen':(13,24,-4,6),'prep':(27,38,-5,5),'pantry':(40,47,-5,5),'shoe_gallery':(-34,-26,-16,-6),'flex':(-23,-14,-18,-9),'powder':(-12,-8,-18,-11),'garage':(-54,-34,-18,6),'service':(28,54,-18,-8)},
'2F':{'family_lounge':(-9,9,10,18),'gaming':(14,25,-3,7.5),'guest_A':(-25,-17,9.5,17),'guest_B':(17,25,9.5,17),'art_gallery':(-24,5,-16,-10),'gallery_west':(-25,-12,-8,7.5)},
'3F':{'bedroom':(-7,7,-3,13),'closets':(-24,-8,-14,13),'bath':(8,24,-2,13),'private_entry':(7,20,-18,-3),'terrace':(-26,26,14,30)}}


def slab(name,rect,z,holes=(),floor='1F',thickness=.30,mat='stone',role='slab'):
    U.context(floor,'structure','STRUCTURE')
    x0,x1,y0,y1=rect
    xs=sorted(set([x0,x1]+[v for h in holes for v in h[:2] if x0<v<x1]))
    ys=sorted(set([y0,y1]+[v for h in holes for v in h[2:] if y0<v<y1]))
    count=0
    for ya,yb in zip(ys,ys[1:]):
        runs=[];start=None
        for xa,xb in zip(xs,xs[1:]):
            empty=any(a<(xa+xb)/2<b and c<(ya+yb)/2<d for a,b,c,d in holes)
            if not empty and start is None:start=xa
            if empty and start is not None:runs.append((start,xa));start=None
        if start is not None:runs.append((start,x1))
        for xa,xb in runs:
            o=U.box(name+f'.{count:02}',((xa+xb)/2,(ya+yb)/2,z-thickness/2),(xb-xa,yb-ya,thickness),mat,.005)
            o['role']=role;o['thickness_m']=thickness;count+=1


def finish_floor(floor,name,rect,mat):
    x0,x1,y0,y1=rect;z=Z[floor]
    U.context(floor,name)
    o=U.box(f'{floor}.{name}.floor_finish',((x0+x1)/2,(y0+y1)/2,z+.014),(x1-x0,y1-y0,.028),mat,.002);o['role']='floor_finish'


def panels(floor,name,a,b,z,height,mat='walnut',spacing=1.2):
    U.context(floor,name)
    axis=0 if a[0]!=b[0] else 1;lo,hi=sorted((a[axis],b[axis]));const=a[1-axis];n=math.ceil((hi-lo)/spacing)
    for i in range(n):
        p=[0,0,z+height/2];p[axis]=lo+(i+.5)*(hi-lo)/n;p[1-axis]=const
        d=[.04,.04,height];d[axis]=(hi-lo)/n-.012
        U.box(f'{floor}.{name}.panel.{i}',p,d,mat,.004)


def stairs(floor,z0,z1):
    U.context(floor,'main_stair','STAIRS')
    n=math.ceil((z1-z0)/.185);n+=n%2;half=n//2;r=(z1-z0)/n;run=.32;width=2.6;x0=8.;y0=-14.;landing=2.6;length=half*run
    for flight in range(2):
        x=x0+width/2+flight*(width+.25)
        for i in range(half):
            yy=y0+(i+.5)*run if flight==0 else y0+(half-i-.5)*run
            zz=z0+(i+1)*r if flight==0 else z0+(half+i+1)*r
            o=U.box(f'{floor}.stair.flight{flight}.tread{i:02}',(x,yy,zz-.075),(width,run+.012,.15),'oak',.015)
            o['role']='stair_tread';o['riser_m']=r;o['going_m']=run;o['flight_width_m']=width
            U.box(f'{floor}.stair.riser',(x,yy-run/2 if flight==0 else yy+run/2,zz-r/2),(width,.06,r),'dark_marble',.005)
            U.strip(f'{floor}.step_LED',(x-width/2+.12,yy-run/2-.008,zz-.04),(x+width/2-.12,yy-run/2-.008,zz-.04),.018)
        ya=y0;yb=y0+length
        za=z0 if flight==0 else z1;zb=z0+half*r
        for xx in [x-width/2+.08,x+width/2-.08]:
            U.rod(f'{floor}.stair.stringer',(xx,ya,za-.17),(xx,yb,zb-.17),.095,'black')
            U.rod(f'{floor}.stair.handrail',(xx,ya,za+1.05),(xx,yb,zb+1.05),.035,'black')
            # continuous true glazing follows stair pitch; mesh has solidify thickness.
            me=U.mesh(f'{floor}.stair.glass',[(xx,ya,za+.12),(xx,yb,zb+.12),(xx,yb,zb+1.0),(xx,ya,za+1.0)],[(0,1,2,3)],'glass')
            mod=me.modifiers.new('Laminated glass thickness','SOLIDIFY');mod.thickness=.02
    o=U.box(f'{floor}.stair.half_landing',(x0+width+.125,y0+length+landing/2,z0+half*r-.15),(width*2+.25,landing,.30),'marble');o['role']='stair_landing'
    U.guard(f'{floor}.landing.guard',(x0,y0+length+landing),(x0+width*2+.25,y0+length+landing),z0+half*r)
    U.area(f'{floor}.stair.landing_light',(10.8,y0+length+1,z0+half*r+2.4),160,2)


def elevator(name,rect,stop_floors,service=False):
    x0,x1,y0,y1=rect
    for f in stop_floors:
        z=Z[f];h=HEIGHT[f]-.30;U.context(f,name,'ELEVATORS')
        U.wall(name+'.back',(x0,y1),(x1,y1),z,h,.24,mat='stone')
        for x in [x0,x1]:U.wall(name+'.side',(x,y0),(x,y1),z,h,.24)
        mid=(x0+x1)/2;w=1.4 if service else 1.6
        U.wall(name+'.front',(x0,y0),(x1,y0),z,h,.24,[(mid-w/2,mid+w/2,2.5)])
        for dx in [-w/4,w/4]:
            o=U.box(name+f'.{f}.sliding_door',(mid+dx,y0-.025,z+1.25),(w/2-.009,.06,2.48),'bronze');o['role']='elevator_door'
        U.box(name+'.call_panel',(mid+w/2+.2,y0-.15,z+1.25),(.12,.05,.26),'black')
        U.text3d(name+'.floor_label',f,(mid,y0-.16,z+2.68),.18)
        U.box(name+'.cabin_floor',(mid,(y0+y1)/2,z+.015),(x1-x0-.5,y1-y0-.5,.03),'marble')
        # Guide rails real; cabin represented at B1 only; landings closed elsewhere.
    U.context('B1',name,'ELEVATORS')
    for xx in [x0+.3,x1-.3]:U.rod(name+'.guide_rail',(xx,y1-.3,-4.1),(xx,y1-.3,13.6),.035,'stainless')


def shell():
    s=bpy.context.scene;s.unit_settings.system='METRIC';s.unit_settings.scale_length=1.;s.unit_settings.length_unit='METERS'
    for n in ['ARCH','STRUCTURE','B1','1F','2F','3F','ROOF','STAIRS','ELEVATORS','DOORS','WINDOWS','GLASS','FURNITURE','LIGHTING','MATERIALS','GARAGE','TERRACE','SUNken_COURTYARD','CAMERAS','PRESENTATION']:U.collection(n)
    core=(8,13.45,-14.2,-5.4);lift=(15.3,19,-16,-12)
    slab('B1.foundation',(-26,26,-18.5,18.5),-4.2,floor='B1',thickness=.40)
    slab('B1.service_foundation',(26,54,-18.5,0),-4.2,floor='B1',thickness=.40)
    slab('1F.main_slab',(-26,26,-18.5,18.5),0,[core,lift],floor='1F')
    slab('2F.slab_atrium_open',(-26,26,-18.5,18.5),5.8,[(-8,8,-6,10),core,lift],floor='2F')
    slab('3F.COMPLETE_slab',(-26,26,-18.5,18.5),10,[core,lift],floor='3F')
    slab('3F.outdoor_terrace',(-26,26,14,30),9.97,floor='3F',mat='stone')
    slab('ROOF.master',(-27,27,-19,14.8),14.2,floor='ROOF',thickness=.35,role='roof')
    slab('1F.service_slab',(26,54,-18.5,6),0,[(49,53,-5,-1)],floor='1F')
    slab('1F.service_roof',(25.7,54.5,-19,6.5),5.35,floor='1F',role='roof')
    slab('GARAGE.floor',(-54,-34,-18.5,6),-1.2,floor='1F',thickness=.35,mat='dark_marble')
    slab('GARAGE.roof',(-54.5,-25.7,-19,6.5),3.7,floor='1F',role='roof')
    slab('1F.mudroom_slab',(-34,-26,-18.5,6),0,[(-34,-29,-13,-9)],floor='1F')
    slab('1F.view_terrace',(-34,34,18.5,30),-.03,floor='1F')
    slab('1F.arrival_portico',(-8,8,-28,-18.5),-.02,floor='1F')
    # B1 retaining enclosure; courtyard is open beside west wall.
    U.context('B1','enclosure')
    U.wall('B1.front',(-26,-18.5),(54,-18.5),-4.2,4.2,.35)
    U.wall('B1.rear',(-26,18.5),(26,18.5),-4.2,4.2,.35)
    U.wall('B1.east',(54,-18.5),(54,0),-4.2,4.2,.35)
    U.wall('B1.west_retaining',(-26,-18.5),(-26,18.5),-4.2,4.2,.35,[(1,17.8,3.7)])
    U.glazing('B1.library.courtyard',(-26,1),(-26,17.8),-4.17,3.72,7,sliding=True,open_bay=3)
    # Basement partitions with actual door gaps.
    for x in [-13,-8,5,19.5,27.5]:U.wall('B1.room.side',(x,-18),(x,-1.8),-4.2,3.9,.22, [(-3.7,-2.1,2.5)] if x in [5,19.5,27.5] else [])
    U.wall('B1.gym.front',(-26,-4),(-13,-4),-4.2,3.9,.22,[(-16,-14.4,2.6)])
    U.wall('B1.cinema.acoustic',(-8,-5),(5,-5),-4.2,3.9,.28,[(2,3.4,2.5)],'acoustic')
    U.wall('B1.vestibule',(-8,-1.8),(5,-1.8),-4.2,3.9,.24,[(-5,-3.6,2.5)])
    U.door('B1.cinema.inner',(2.7,-5),-4.2,1.4,2.5,angle=.5)
    U.door('B1.cinema.outer',(-4.3,-1.8),-4.2,1.4,2.5,angle=-.35)
    U.door('B1.gym.door',(-15.2,-4),-4.2,1.6,2.6,angle=-.9)
    U.wall('B1.laundry.front',(19.5,-6),(27.5,-6),-4.2,3.9,.22,[(22,23.4,2.5)])
    U.door('B1.laundry.door',(22.7,-6),-4.2,1.4,2.5)
    U.wall('B1.service_east',(26,-4.5),(26,18.5),-4.2,3.9,.3)
    U.wall('B1.service_top',(26,0),(54,0),-4.2,3.9,.3,[(30,31.5,2.5)])
    for yy in [2,8,9,17.8]:U.wall('B1.wet_storage',(16.5,yy),(26,yy),-4.2,3.9,.2,[(17.5,19,2.5)] if yy in [2,9] else [])
    for xx in [16.5,21]:U.wall('B1.wet.divide',(xx,2),(xx,17.8),-4.2,3.9,.18,[(4,5.4,2.5)] if xx==16.5 else [(4,5.4,2.5),(10,11.4,2.5)])
    U.door('B1.shower.entry',(18.25,2),-4.2,1.5,2.5)
    U.door('B1.bath.entry',(21,10.7),-4.2,1.4,2.5,axis='Y')
    # Main facades: stone piers with true full-height glazed fields.
    for f in ['1F','2F','3F']:
        z=Z[f];h=HEIGHT[f]-.30;rear=14 if f=='3F' else 18.5
        U.context(f,'facade')
        openings=[(-23,-14,h-.12),(-7,7,h-.12),(14,23,h-.12)] if f!='3F' else [(-22,-9,h-.12),(-5,5,h-.12)]
        if f=='1F':openings=[(-23,-14,3.8),(-4,4,4.3),(1e2,1e2+1,3)] # east front stair/elevator stone
        openings=[q for q in openings if q[0]<26]
        U.wall(f+'.front',(-26,-18.5),(26,-18.5),z,h,.32,openings)
        for a,b,hh in openings:
            if f=='1F' and a==-4:
                U.door('1F.entrance.left',(-2,-18.5),0,3.8,4.3,angle=-.25)
                U.door('1F.entrance.right',(2,-18.5),0,3.8,4.3,angle=.25)
            else:U.glazing(f+'.front.glazing',(a,-18.5),(b,-18.5),z+.04,hh,4)
        U.glazing(f+'.REAR.glazing',(-26,rear),(26,rear),z+.04,h-.08,20,sliding=True,open_bay=10 if f=='3F' else 9)
        for x in [-26,26]:
            U.wall(f+'.side',(x,-18.5),(x,rear),z,h,.32,[(-4,rear-.3,h-.10),(-15,-9,2.8)])
            U.glazing(f+'.side.view',(x,-4),(x,rear-.3),z+.04,h-.14,7)
            U.glazing(f+'.side.front',(x,-15),(x,-9),z+.04,2.76,3,sliding=(f=='1F'),open_bay=1 if f=='1F' else None)
        # Piers are aligned down the building to support slabs and cantilevers.
        for xx in [-26,-11,11,26]:
            for yy in [-18.5,18.5 if f!='3F' else 13.9]:
                U.box(f+'.structural.pier',(xx,yy,z+h/2),(.46,.46,h),'stone')
        for y in [-18.7,rear+.16]:
            U.box(f+'.horizontal.black_fascia',(0,y,z+h-.04),(53,.28,.26),'black')
            U.strip(f+'.facade.linear',(-25.7,y-.1,z+h-.21),(25.7,y-.1,z+h-.21),.03)
        for x in [-26.18,26.18]:U.box(f+'.side.fascia',(x,(rear-18.5)/2,z+h-.04),(.27,rear+18.5,.26),'black')
    # 1F partitions define rooms while central lounge edges remain open portals.
    U.context('1F','partitions')
    U.wall('1F.left_suite_front',(-26,-8),(-8,-8),0,5.5,.22,[(-20,-18.6,2.7),(-11,-9.6,2.7)])
    U.wall('1F.flex_powder_divide',(-13,-18.5),(-13,-8),0,5.5,.2)
    U.wall('1F.powder_side',(-8,-18.5),(-8,-10),0,5.5,.2,[(-15.8,-14.5,2.6)])
    U.door('1F.flex.entry',(-19.3,-8),0,1.4,2.7,angle=-.7)
    U.door('1F.powder.entry',(-8,-15.15),0,1.3,2.6,axis='Y')
    U.wall('1F.living.TV_support',(-24,5.2),(-12,5.2),0,5.5,.24,[(-14,-11.8,3.6)])
    U.wall('1F.kitchen.side',(25.7,-5),(25.7,8),0,5.0,.24,[(0,3,3.2)])
    # Upper suites: 8 x 7.5 m, both bathrooms and closet within 60 square metres.
    U.context('2F','partitions')
    for side in [-1,1]:
        x0,x1=(-25,-17) if side==-1 else (17,25)
        for xx in [x0,x1]:U.wall('2F.suite.side',(xx,8.7),(xx,18.2),5.8,3.9,.18,[(10,11.4,2.6)] if xx==(x1 if side==-1 else x0) else [])
        U.wall('2F.suite.front',(x0,9.3),(x1,9.3),5.8,3.9,.18,[(x0+5.7,x0+7.1,2.6)])
        U.wall('2F.suite.bath_front',(x0,13.4),(x0+5,13.4),5.8,3.9,.18,[(x0+1.9,x0+3.1,2.5),(x0+3.8,x0+5,2.5)])
        U.wall('2F.suite.bath_closet',(x0+3.5,9.3),(x0+3.5,13.4),5.8,3.9,.18)
        U.door('2F.suite.entry.'+str(side),(x0+6.4,9.3),5.8,1.4,2.6)
    U.wall('2F.gaming.wall',(13.5,-3.3),(25.5,-3.3),5.8,3.9,.22)
    # Guard around the ONLY atrium; gallery continuous 3.2 m minimum.
    U.context('2F','atrium_gallery')
    for a,b in [((-8,-6),(8,-6)),((-8,-6),(-8,10)),((8,-6),(8,10)),((-8,10),(8,10))]:U.guard('2F.atrium.guard',a,b,5.8)
    # Roof soffit directly above foyer at 9.7m (3F slab underside).
    U.context('2F','foyer_ceiling')
    U.box('ATRIUM.CLOSED_CEILING_UNDER_3F',(0,2,9.675),(16,16,.05),'plaster')['role']='ceiling'
    # Third-floor privacy vestibule encloses both stair and main elevator arrival.
    U.context('3F','private_entry')
    for xx in [7,20]:U.wall('3F.secure_core.side',(xx,-18.5),(xx,-3),10,3.9,.24)
    U.wall('3F.PRIVACY_BOUNDARY',(7,-3),(20,-3),10,3.9,.26,[(14,17,3.3)],'dark_marble')
    U.door('3F.PRIVACY_DOOR',(15.5,-3),10,3,3.3,secure=True)
    U.text3d('3F.entry.inscription','MASTER RESIDENCE',(18.1,-3.15,12.7),.18)
    # Only WC enclosed within the master bathroom, secondary to open-plan zones.
    U.context('3F','bath')
    for xx in [20,25.5]:U.wall('3F.WC.nook.side',(xx,-9),(xx,-3),10,3.9,.18)
    U.wall('3F.WC.nook.front',(20,-9),(25.5,-9),10,3.9,.18,[(21,22.2,2.5)])
    U.wall('3F.WC.nook.back',(20,-3),(25.5,-3),10,3.9,.18)
    U.door('3F.WC.door',(21.6,-9),10,1.2,2.5)
    for f in ['B1','1F','2F']:stairs(f,Z[f],Z[['1F','2F','3F'][['B1','1F','2F'].index(f)]])
    elevator('Main_elevator',(15.3,19,-16,-12),['B1','1F','2F','3F'])
    elevator('Service_elevator',(49,53,-5,-1),['B1','1F'],True)
    # Garage: semi-underground floor, ramp to arrival and two independent interior connections.
    U.context('1F','garage','GARAGE')
    U.wall('Garage.front',(-54,-18.5),(-34,-18.5),-1.2,4.6,.32,[(-50,-39,3.5)])
    U.wall('Garage.west',(-54,-18.5),(-54,6),-1.2,4.6,.32)
    U.wall('Garage.rear',(-54,6),(-26,6),-1.2,4.6,.32)
    U.wall('Garage.east',(-34,-18.5),(-34,6),-1.2,4.6,.26,[(-13,-9,3.1),(-17.5,-15,2.8)])
    U.glazing('Garage.arrival_door',(-50,-18.5),(-39,-18.5),-1.16,3.45,5,sliding=True,open_bay=2)
    # 10m-long ramp, gentle 10% grade; kept clear of arrival pedestrian steps.
    U.mesh('Garage.vehicle_ramp',[(-51,-28,-.2),(-38,-28,-.2),(-38,-18.5,-1.2),(-51,-18.5,-1.2),(-51,-28,-.4),(-38,-28,-.4),(-38,-18.5,-1.4),(-51,-18.5,-1.4)],[(0,1,2,3),(4,7,6,5),(0,4,5,1),(1,5,6,2),(2,6,7,3),(3,7,4,0)],'stone')
    U.context('1F','shoe_gallery')
    for i in range(8):
        o=U.box('Garage.mudroom.step'+str(i),(-33.85+(i+.5)*.32,-11,-1.2+(i+1)*.15-.075),(.32,3.0,.15),'marble');o['role']='stair_tread';o['riser_m']=.15;o['going_m']=.32;o['flight_width_m']=3.
        U.strip('Garage.mudroom.step_LED',(-33.85+i*.32,-12.4,-1.2+(i+1)*.15-.025),(-33.85+i*.32,-9.6,-1.2+(i+1)*.15-.025),.018)
    # Service-side route along front wing connects through foyer/service landing.
    U.wall('1F.mudroom.front',(-34,-18.5),(-26,-18.5),0,3.4,.24,[(-31.5,-29,2.7)])
    U.wall('1F.mudroom.side',(-26,-18.5),(-26,-6),0,3.4,.24,[(-13,-9,3.1),(-17.5,-15,2.8)])
    U.context('1F','service')
    U.wall('Service.front',(26,-18.5),(54,-18.5),0,5.0,.3,[ (29,33,3.2),(40,44,3.2)])
    for a,b in [( (54,-18.5),(54,6)),((26,6),(54,6))]:U.wall('Service.enclosure',a,b,0,5.0,.3)
    U.wall('Service.circulation',(26,-7.7),(54,-7.7),0,5.0,.2,[(28,30,2.8),(41,43,2.8),(49,51,2.8)])
    for x in [39,48]:U.wall('Service.prep_pantry',(x,-7.7),(x,6),0,5.0,.2,[(-4,-1.4,2.8)])
    # Courtyard is daylight open from B1 to sky, with retaining walls and exterior stair.
    U.context('B1','courtyard','SUNken_COURTYARD')
    U.box('Courtyard.stone_floor',(-33,9,-4.36),(14,18,.32),'stone')
    for a,b in [((-40,0),(-40,18.5)),((-40,18.5),(-26,18.5)),((-40,0),(-26,0))]:U.wall('Courtyard.retaining',a,b,-4.2,4.2,.4)
    for i in range(24):U.box('Courtyard.exit.step'+str(i),(-38.3,1+(i+.5)*.30,-4.2+(i+1)*.175-.0875),(2.5,.30,.175),'stone')
    U.guard('Courtyard.edge',(-40.3,0),(-40.3,18.5),0)
    U.context('3F','terrace','TERRACE')
    for a,b in [((-26,14),(-26,30)),((-26,30),(26,30)),((26,30),(26,14))]:U.guard('3F.OUTDOOR.glass_guard',a,b,10)
    U.context('1F','terrace','TERRACE')
    for a,b in [((-34,30),(34,30)),((-34,18.5),(-34,30)),((34,18.5),(34,30))]:U.guard('1F.rear_terrace.guard',a,b,0)
    # Entry portal and exterior stair from gently lower arrival court.
    U.context('1F','arrival')
    for x in [-6,6]:U.box('Entrance.portal.pier',(x,-20,4.8),(.65,1.0,9.6),'stone')
    U.box('Entrance.portal.crown',(0,-20,9.45),(12.65,1.0,.5),'stone')
    U.box('Entrance.wood_canopy',(0,-22,4.65),(14,7,.22),'walnut')
    for i in range(6):U.box('Entrance.arrival.step'+str(i),(0,-27.5+i*.50,-1.05+(i+1)*.175-.0875),(12,.50,.175),'stone')
    U.context('ROOF','roof','ROOF')
    for a,b in [((-27,-19),(27,-19)),((-27,-19),(-27,14.8)),((27,-19),(27,14.8))]:U.wall('Roof.parapet',a,b,14.2,.32,.20,mat='stone')
    U.box('Roof.future_UAV_small_pad',(-21,-12,14.235),(2.4,2.4,.07),'charcoal')['future_only']=True
    # Room schedule metadata guides selection and QA; no visible plan labels in rooms.
    for f,rooms in ROOMS.items():
        for name,rect in rooms.items():
            U.context(f,name);ob=bpy.data.objects.new(f+'.'+name+'.ZONE',None);U.link(ob);ob.empty_display_type='CUBE';ob.empty_display_size=.1;ob.hide_render=True
            ob['room_bounds_m']=list(rect);ob['area_m2']=(rect[1]-rect[0])*(rect[3]-rect[2]);ob['level_m']=Z[f];ob['role']='room_zone'
    s['building_orientation']='FRONT -Y; REAR +Y; X right when viewed from front';s['envelope_width_m']=108.;s['envelope_depth_m']=58.;s['atrium_levels']='1F + 2F only';s['3F_complete_slab']=True
