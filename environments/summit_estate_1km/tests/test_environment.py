"""Acceptance checks on delivered assets; run generate_environment.py first."""
import json
import unittest
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
ROOT=Path(__file__).resolve().parents[1]

class EnvironmentTests(unittest.TestCase):
    def test_launchable_local_world_exists(self):
        path=ROOT/'gazebo/worlds/summit_estate.sdf'
        self.assertTrue(path.exists(),'No launchable world generated')
        if not path.exists(): return
        world=ET.parse(path)
        self.assertEqual(world.find('world').get('name'),'summit_estate')
        for inc in world.findall('.//include/uri'):
            self.assertTrue((ROOT/'gazebo/models'/inc.text.removeprefix('model://')/'model.sdf').is_file())
        for model in (ROOT/'gazebo/models').glob('*/model.sdf'):
            for uri in ET.parse(model).findall('.//uri'):
                self.assertTrue(uri.text.startswith('model://'),uri.text)
                self.assertTrue((ROOT/'gazebo/models'/uri.text.removeprefix('model://')).is_file(),uri.text)
    def test_site_scale_road_and_required_content(self):
        path=ROOT/'data/processed/scene.json'
        self.assertTrue(path.exists(),'No semantic scene generated')
        if not path.exists(): return
        scene=json.loads(path.read_text()); self.assertEqual(scene['world_bounds'],[-500,500,-500,500])
        names={m['name'] for m in scene['models']}
        for name in ['summit_terrain','summit_road','summit_lake','summit_villa']:
            self.assertIn(name,names)
        road=np.array(scene['landscape']['road_centerline']); lengths=np.linalg.norm(np.diff(road[:,:2],axis=0),axis=1)
        self.assertTrue(np.all(lengths>0))
        self.assertLess(float(np.max(np.abs(np.diff(road[:,2]))/lengths)),.16)
        self.assertGreater(road[-1,2]-road[0,2],50)
        bedrooms=[r for r in scene['villa']['rooms'] if r['function']=='bedroom']
        self.assertEqual(len(bedrooms),4)
        functions={r['function'] for r in scene['villa']['rooms']}
        for f in ['kitchen','dining','living','bathroom','gym','boxing','cinema','study','storage']:
            self.assertIn(f,functions)

if __name__=='__main__': unittest.main()
