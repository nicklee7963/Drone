#!/usr/bin/env python3
"""Check exported geometry and optionally run a bounded Gazebo server smoke test."""
import argparse
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
from asset_checks import inspect_assets, read_mesh

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server',action='store_true',help='also run 125 Gazebo physics iterations')
    parser.add_argument('--native',action='store_true',help='check every mesh using the native Gazebo importer (requires C++ development headers)')
    args=parser.parse_args()
    tests=subprocess.run([sys.executable,'-m','unittest','discover','-s',str(ROOT/'tests'),'-v'])
    if tests.returncode: return tests.returncode
    report=inspect_assets(ROOT)
    if args.native:
        output=ROOT/'.runtime'; output.mkdir(parents=True,exist_ok=True)
        flags=subprocess.check_output(['pkg-config','--cflags','--libs','gz-common5-graphics'],text=True)
        binary=output/'check_gazebo_mesh'
        subprocess.run(['c++',str(ROOT/'tests/check_gazebo_mesh.cc'),'-o',str(binary),*shlex.split(flags)],check=True)
        count=0
        for path in sorted((ROOT/'gazebo/models').rglob('*.dae')):
            _,_,groups=read_mesh(path)
            result=subprocess.run([str(binary),str(path),str(sum(len(f) for f in groups.values()))],capture_output=True,text=True,timeout=30)
            if result.returncode:
                print(result.stdout+result.stderr,file=sys.stderr); return 1
            count+=1
        report['native_meshes_passed']=count
    env=os.environ.copy(); env['SDF_PATH']=str(ROOT/'gazebo/models')
    schema=subprocess.run(['gz','sdf','-k',str(ROOT/'gazebo/worlds/alishan_showcase.sdf')],env=env,capture_output=True,text=True,timeout=45)
    report['sdf_valid']=schema.returncode==0
    if schema.returncode:
        print(schema.stdout+schema.stderr,file=sys.stderr); return 1
    if args.server:
        output=ROOT/'data/processed/validation_runtime'; output.mkdir(parents=True,exist_ok=True)
        env['ALISHAN_SHOWCASE_PARTITION']='showcase_validation_'+str(os.getpid())
        try:
            result=subprocess.run([str(ROOT/'scripts/launch.sh'),'-s','--iterations','125','-v','3'],env=env,capture_output=True,text=True,timeout=60)
        except subprocess.TimeoutExpired as error:
            print('Gazebo did not complete the smoke test within 60 seconds.',file=sys.stderr)
            return 1
        log=re.sub(r'\x1b\[[0-9;]*m','',result.stdout+result.stderr)
        (output/'server.log').write_text(log)
        report['gazebo_server_exit_code']=result.returncode
        report['gazebo_world_initialized']='initialized with' in log
        errors=[line for line in log.splitlines() if re.search(r'\[Err\]|Error Code|Unable to find uri|Failed to load',line)]
        report['gazebo_errors']=errors
        if result.returncode or errors or not report['gazebo_world_initialized']:
            print(log,file=sys.stderr); return 1
    (ROOT/'data/processed/validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
