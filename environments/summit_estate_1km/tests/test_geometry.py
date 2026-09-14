import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

class GeometryTests(unittest.TestCase):
    def test_geometry_module_exists(self):
        self.assertIsNotNone(importlib.util.find_spec('geometry'), 'missing scene/mesh export implementation')
    def test_ring_top_normals_face_up(self):
        from geometry import Scene,triangulate
        m=Scene().model('test')
        o=m.ring('r',(0,0,0),2,3,1,'stone')
        v,f=triangulate(o);tri=v[f]
        top=np.all(abs(tri[:,:,2]-.5)<1e-8,axis=1)
        normals=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0])
        self.assertTrue(np.all(normals[top,2]>0))

    def test_export_preserves_open_ring_and_primitive_collision(self):
        if importlib.util.find_spec('geometry') is None:
            self.skipTest('geometry not implemented yet')
        from geometry import Scene
        s=Scene(); m=s.model('summit_test')
        m.box('floor',(0,0,0),(6,6,.3),'stone')
        m.ring('basin',(0,0,1),2,3,.5,'ivory')
        m.box('water',(0,0,.3),(2,2,.1),'water',collision=False)
        with tempfile.TemporaryDirectory() as d:
            s.export(Path(d))
            tree=ET.parse(Path(d)/'gazebo/models/summit_test/model.sdf')
            self.assertEqual(len(tree.findall('.//collision')),2)
            self.assertEqual(len(tree.findall('.//visual')),3)
            for uri in tree.findall('.//uri'):
                self.assertTrue((Path(d)/'gazebo/models'/uri.text.removeprefix('model://')).exists())
        ring=next(o for o in m.objects if o['name']=='basin')
        v=np.asarray(ring['vertices']); self.assertGreaterEqual(np.linalg.norm(v[:,:2],axis=1).min(),1.99)

if __name__=='__main__': unittest.main()
