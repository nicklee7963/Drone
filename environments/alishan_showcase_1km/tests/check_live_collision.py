#!/usr/bin/python3
"""Drop two temporary spheres in a running showcase, check contact, remove them.

Run with the system Python that provides Gazebo's transport bindings.
Neither sphere is written into the delivered world.
"""
import json
import os
from pathlib import Path
import time
import subprocess
os.environ['GZ_PARTITION']=os.environ.get('ALISHAN_SHOWCASE_PARTITION','alishan_showcase_1km')
from gz.transport13 import Node
from gz.msgs10.pose_v_pb2 import Pose_V

ROOT=Path(__file__).resolve().parents[1]


def command(action,kind,request):
    reply=subprocess.run(['gz','service','-s','/world/alishan_showcase/'+action,
                          '--reqtype','gz.msgs.'+kind,'--reptype','gz.msgs.Boolean',
                          '--timeout','5000','--req',request],capture_output=True,text=True,timeout=10)
    if reply.returncode or 'data: true' not in reply.stdout:
        raise RuntimeError(f'{action} failed: {reply.stdout}{reply.stderr}')


def main():
    scene=json.loads((ROOT/'data/processed/scene.json').read_text())
    pad=scene['clearings'][0]
    cases=[('terrain',pad['x']-21,pad['y']-6,pad['z']),
           ('launch_pad',pad['x']+6,pad['y']+6,pad['z']+.15)]
    node=Node(); names=[]; result={}; live_poses={}
    def receive_poses(message):
        for pose in message.pose:
            if pose.name.startswith('_showcase_collision_probe_'):
                live_poses[pose.name]=pose.position.z
    node.subscribe(Pose_V,'/world/alishan_showcase/pose/info',receive_poses)
    try:
        command('control','WorldControl','pause: false')
        for label,x,y,z in cases:
            name='_showcase_collision_probe_'+label+'_'+str(os.getpid()); names.append(name)
            sdf=f'''<sdf version="1.9"><model name="{name}">
              <pose>{x} {y} {z+3} 0 0 0</pose><link name="ball">
              <inertial><mass>1</mass><inertia><ixx>.064</ixx><iyy>.064</iyy><izz>.064</izz></inertia></inertial>
              <collision name="contact"><geometry><sphere><radius>.4</radius></sphere></geometry></collision>
              </link></model></sdf>'''
            command('create','EntityFactory','sdf: '+json.dumps(sdf))
        time.sleep(3)
        for label,x,y,z in cases:
            name='_showcase_collision_probe_'+label+'_'+str(os.getpid())
            # scene/info is the construction snapshot; pose/info carries live
            # physics updates and must be used to check settled contacts.
            if name not in live_poses: raise RuntimeError('No live pose for '+name)
            measured=live_poses[name]
            expected=z+.4
            result[label]={'expected_center_z_m':expected,'measured_center_z_m':measured,
                           'contact_error_m':abs(measured-expected)}
            if abs(measured-expected)>.08:
                raise AssertionError(f'{label}: sphere did not settle on the surface: {result[label]}')
        print(json.dumps(result,indent=2))
        (ROOT/'data/processed/collision_validation.json').write_text(json.dumps(result,indent=2)+'\n')
    finally:
        for name in names:
            command('remove','Entity','name: '+json.dumps(name)+' type: MODEL')


if __name__=='__main__':
    main()
