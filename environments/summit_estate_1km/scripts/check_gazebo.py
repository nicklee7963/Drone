#!/usr/bin/python3
"""Launch an isolated Gazebo server, check loaded models and capture real images.

Uses Ubuntu Gazebo Python bindings (/usr/bin/python3). No PX4/ROS or GUI needed.
The process created here is always stopped on exit. Optional cameras/probes
exist only in this validation server and are never saved into the main world.
"""
import argparse
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import threading
import time
import xml.etree.ElementTree as ET
from gz.transport13 import Node
from gz.msgs10.boolean_pb2 import Boolean
from gz.msgs10.empty_pb2 import Empty
from gz.msgs10.entity_factory_pb2 import EntityFactory
from gz.msgs10.image_pb2 import Image as GzImage
from gz.msgs10.pose_pb2 import Pose
from gz.msgs10.pose_v_pb2 import Pose_V
from gz.msgs10.scene_pb2 import Scene
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]


def request(node,endpoint,message,response_type=Boolean,timeout=5000):
    ok,response=node.request('/world/summit_estate/'+endpoint,message,type(message),response_type,timeout)
    if not ok or (isinstance(response,Boolean) and not response.data):raise RuntimeError(f'Gazebo request failed: {endpoint}')
    return response


def pose_message(name,position,target):
    d=[target[i]-position[i] for i in range(3)];pitch=math.atan2(-d[2],math.hypot(d[0],d[1]));yaw=math.atan2(d[1],d[0])
    msg=Pose(name=name);msg.position.x,msg.position.y,msg.position.z=position
    msg.orientation.w=math.cos(pitch/2)*math.cos(yaw/2);msg.orientation.x=-math.sin(pitch/2)*math.sin(yaw/2);msg.orientation.y=math.sin(pitch/2)*math.cos(yaw/2);msg.orientation.z=math.cos(pitch/2)*math.sin(yaw/2)
    return msg


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--capture',action='store_true');parser.add_argument('--views',default='overview,villa,arrival,lake,amenities,gate');parser.add_argument('--timeout',type=int,default=150);parser.add_argument('--physics',action='store_true');args=parser.parse_args()
    processed=ROOT/'data/processed';logs=processed/'logs';logs.mkdir(exist_ok=True);preview=processed/'previews';preview.mkdir(exist_ok=True)
    partition=f'summit_check_{os.getpid()}';os.environ['GZ_PARTITION']=partition
    env=os.environ.copy();env['GZ_SIM_RESOURCE_PATH']=str(ROOT/'gazebo/models');env['GZ_PARTITION']=partition
    logpath=logs/'gazebo_validation.log';report={'partition':partition,'world':str(ROOT/'gazebo/worlds/summit_estate.sdf'),'captured_views':[],'physics_probes':[]}
    node=Node();process=None
    try:
        with logpath.open('w') as log:
            command=['gz','sim','-s','-r','--headless-rendering','-v','3',str(ROOT/'gazebo/worlds/summit_estate.sdf')]
            process=subprocess.Popen(command,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            deadline=time.monotonic()+args.timeout
            while True:
                if process.poll() is not None:raise RuntimeError(f'Gazebo exited {process.returncode}; see {logpath}')
                ok,scene=node.request('/world/summit_estate/scene/info',Empty(),Empty,Scene,1000)
                if ok:break
                if time.monotonic()>deadline:raise TimeoutError('World scene service did not become ready')
            expected={p.text.removeprefix('model://') for p in ET.parse(ROOT/'gazebo/worlds/summit_estate.sdf').findall('.//include/uri')};actual={m.name for m in scene.model}
            missing=sorted(expected-actual)
            if missing:raise RuntimeError(f'Missing loaded models: {missing}')
            report.update(world_loaded=True,expected_models=len(expected),loaded_models=sorted(actual));print(f'Loaded {len(expected)} expected models',flush=True)
            if args.physics:
                poses={};node.subscribe(Pose_V,'/world/summit_estate/pose/info',lambda msg:poses.update({p.name:p.position.z for p in msg.pose}))
                probes=[('lawn',125,8,80),('road',-88,-148,54.12),('basement',78,140,74.8),('main',78,124,80.2),('upper',78,125,85.8),('pool',167,149,77.65)]
                for name,x,y,surface in probes:
                    sdf=f'<sdf version="1.9"><model name="probe_{name}"><pose>{x} {y} {surface+2} 0 0 0</pose><link name="body"><inertial><mass>1</mass><inertia><ixx>.025</ixx><iyy>.025</iyy><izz>.025</izz></inertia></inertial><collision name="ball"><geometry><sphere><radius>.25</radius></sphere></geometry></collision></link></model></sdf>'
                    request(node,'create',EntityFactory(sdf=sdf))
                deadline=time.monotonic()+30
                while time.monotonic()<deadline:
                    time.sleep(.25)
                    if all('probe_'+n in poses and abs(poses['probe_'+n]-(z+.25))<.2 for n,_,_,z in probes):break
                for name,x,y,surface in probes:
                    measured=poses.get('probe_'+name);passed=measured is not None and abs(measured-(surface+.25))<.2
                    report['physics_probes'].append({'name':name,'expected_z':surface+.25,'measured_z':measured,'passed':passed})
                if not all(p['passed'] for p in report['physics_probes']):raise RuntimeError('A physics support probe failed; inspect runtime_validation.json')
                print(f'{len(probes)} physical drop probes passed',flush=True)
            if args.capture:
                frames=[];event=threading.Event()
                def frame(msg):
                    frames.append(msg)
                    if len(frames)>4:frames.pop(0)
                    event.set()
                node.subscribe(GzImage,'/summit_validation/image',frame)
                sdf='<sdf version="1.9"><model name="validation_camera"><static>true</static><pose>230 -470 345 0 .4 2  </pose><link name="camera_link"><sensor name="camera" type="camera"><always_on>true</always_on><update_rate>3</update_rate><topic>/summit_validation/image</topic><camera><horizontal_fov>1.12</horizontal_fov><image><width>1600</width><height>1000</height><format>R8G8B8</format></image><clip><near>.08</near><far>3000</far></clip></camera></sensor></link></model></sdf>'
                request(node,'create',EntityFactory(sdf=sdf))
                views=json.loads((ROOT/'configs/views.json').read_text())
                for name in args.views.split(','):
                    view=views[name];request(node,'set_pose',pose_message('validation_camera',view['position'],view['target']))
                    # Three distinct frames after pose update avoid saving a stale camera image.
                    for _ in range(3):
                        event.clear()
                        if not event.wait(args.timeout):raise TimeoutError(f'No rendered frame for {name}')
                    msg=frames[-1];im=Image.frombytes('RGB',(msg.width,msg.height),msg.data,'raw','RGB',msg.step)
                    im.save(preview/f'{name}.png');report['captured_views'].append({'name':name,'file':f'data/processed/previews/{name}.png','width':msg.width,'height':msg.height});print('Captured '+name,flush=True)
            report['passed']=True
    except Exception as exc:
        report['passed']=False;report['error']=str(exc);raise
    finally:
        if process and process.poll() is None:
            os.killpg(process.pid,signal.SIGINT)
            try:process.wait(timeout=10)
            except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGTERM);process.wait(timeout=5)
        logtext=logpath.read_text(errors='replace') if logpath.exists() else ''
        errors=[line for line in logtext.splitlines() if re.search(r'\[Err\]|Unable to (find|load)|Failed to (find|load)|Unable to resolve',line)]
        report['resource_or_runtime_errors']=errors;report['log']=str(logpath.relative_to(ROOT))
        if errors:report['passed']=False
        (processed/'runtime_validation.json').write_text(json.dumps(report,indent=2))
    if not report['passed']:raise SystemExit('Validation logged runtime/resource errors')
    print('Gazebo validation passed',flush=True)

if __name__=='__main__':main()
