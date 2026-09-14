#!/usr/bin/env python3
"""Move the running showcase's GUI camera and optionally save a real screenshot."""
import argparse
import json
import math
import os
from pathlib import Path
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]


def call(service,kind,request):
    env=os.environ.copy()
    env['GZ_PARTITION']=env.get('ALISHAN_SHOWCASE_PARTITION','alishan_showcase_1km')
    result=subprocess.run(['gz','service','-s',service,'--reqtype',kind,'--reptype','gz.msgs.Boolean','--timeout','5000','--req',request],env=env,capture_output=True,text=True,timeout=10)
    if result.returncode or 'data: true' not in result.stdout:
        raise RuntimeError(f'{service} failed; launch the showcase GUI first.\n{result.stdout}{result.stderr}')


def main():
    views=json.loads((ROOT/'configs/views.json').read_text())
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('view',choices=views,default='overview',nargs='?')
    parser.add_argument('--capture',action='store_true')
    args=parser.parse_args()
    x,y,z,pitch,yaw=views[args.view]
    sy,cy=math.sin(yaw/2),math.cos(yaw/2)
    sp,cp=math.sin(pitch/2),math.cos(pitch/2)
    pose=f'position: {{x: {x} y: {y} z: {z}}} orientation: {{x: {-sp*sy} y: {sp*cy} z: {cp*sy} w: {cp*cy}}}'
    call('/gui/move_to/pose','gz.msgs.GUICamera','pose: {'+pose+'}')
    if args.capture:
        time.sleep(2)
        directory=ROOT/'data/processed/previews'; directory.mkdir(parents=True,exist_ok=True)
        previous=set(directory.glob('*.png'))
        call('/gui/screenshot','gz.msgs.StringMsg','data: '+json.dumps(str(directory)))
        deadline=time.monotonic()+10
        while time.monotonic()<deadline:
            files=set(directory.glob('*.png'))-previous
            if files:
                source=max(files,key=lambda p:p.stat().st_mtime)
                # Wait for PNG writing to finish before moving its filename.
                time.sleep(.5)
                target=directory/(args.view+'.png'); source.replace(target)
                print(target); return
            time.sleep(.2)
        raise RuntimeError('Screenshot request succeeded but no image arrived.')
    print('Camera view:',args.view)


if __name__=='__main__':
    main()
