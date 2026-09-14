import importlib.util
import json
import sys
import unittest
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
class LandscapeTests(unittest.TestCase):
    def test_landscape_implementation_exists(self):self.assertIsNotNone(importlib.util.find_spec('landscape'),'terrain pipeline missing')
    def test_road_faces_upward(self):
        from geometry import Scene,triangulate
        from landscape import ribbon
        obj=ribbon(Scene().model('test'),'road',np.array([[0,0,0],[0,10,1]]),-4.5,4.5,'asphalt')
        v,f=triangulate(obj);n=np.cross(v[f[:,1]]-v[f[:,0]],v[f[:,2]]-v[f[:,0]])
        self.assertTrue(np.all(n[:,2]>0))
    def test_gate_wings_stand_on_graded_land(self):
        from landscape import Landscape
        cfg=json.loads((ROOT/'configs/estate.json').read_text());land=Landscape(cfg)
        for x in [-213,-201,-169,-157]:
            self.assertLess(abs(float(land.height(x,-390))-26.4),.2)
    def test_road_grade_and_basin_ground(self):
        if importlib.util.find_spec('landscape') is None:self.skipTest('terrain not implemented')
        from landscape import Landscape
        cfg=json.loads((ROOT/'configs/estate.json').read_text());land=Landscape(cfg,[{'bounds':[26,130,111,167],'z':74.4}])
        r=land.road;self.assertLess(np.max(np.abs(np.diff(r[:,2]))/np.linalg.norm(np.diff(r[:,:2],axis=0),axis=1)),.16)
        self.assertLess(abs(float(land.height(np.array([78]),np.array([140]))[0])-74.4),.001)
        self.assertLess(float(land.height(np.array([-190]),np.array([135]))[0]),49)
        # Removing road grading would fail this continuous surface alignment check.
        h=land.height(r[:,0],r[:,1]);self.assertLess(float(np.max(abs(h-r[:,2]))),.08)
if __name__=='__main__':unittest.main()
