"""Acceptance tests: missing resources, unsafe clearings, and displaced meshes."""
import json
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from asset_checks import read_mesh, sample_terrain, surface_gaps


class GeneratedEnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue((ROOT / 'data/processed/scene.json').is_file(),
                        'Generate the scenic world before validation')
        self.scene = json.loads((ROOT / 'data/processed/scene.json').read_text())
        self.terrain = np.load(ROOT / 'data/processed/terrain.npz')

    def test_full_kilometre_and_mountain_relief(self):
        for key in ['x', 'y']:
            axis = self.terrain[key]
            self.assertAlmostEqual(float(axis.min()), -500)
            self.assertAlmostEqual(float(axis.max()), 500)
        z = self.terrain['z']
        self.assertTrue(np.isfinite(z).all())
        self.assertGreater(float(np.ptp(z)), 200)
        self.assertLess(float(np.ptp(z)), 450)

    def test_roads_grounded_and_reasonable_grade(self):
        for road in self.scene['roads']:
            p = np.array(road['points'])
            length = np.linalg.norm(np.diff(p[:, :2], axis=0), axis=1)
            self.assertTrue((length > 0).all())
            self.assertLess(float(np.max(np.abs(np.diff(p[:, 2])) / length)), .23)
        self.assertGreater(self.scene['road_length_m'], 1800)
        _,vertices,groups=read_mesh(ROOT/'gazebo/models/showcase_roads/meshes/roads.dae')
        for material in ['asphalt','gravel']:
            gaps=surface_gaps(vertices,groups[material],self.terrain)
            self.assertGreater(gaps['min_m'],-.025)
            self.assertLess(gaps['max_m'],.26)

    def test_buildings_do_not_block_through_road(self):
        road=np.array(self.scene['roads'][0]['points'])
        for b in self.scene['buildings']:
            dx=np.maximum(np.abs(road[:,0]-b['x'])-b['width']/2-1,0)
            dy=np.maximum(np.abs(road[:,1]-b['y'])-b['depth']/2-1,0)
            self.assertGreater(float(np.hypot(dx,dy).min()),7,b['name'])

    def test_launch_sites_flat_clear_and_connected(self):
        launches = [p for p in self.scene['clearings'] if p['launch']]
        self.assertGreaterEqual(len(launches), 2)
        trees = np.array([[t['x'], t['y'], t['radius']] for t in self.scene['trees']])
        for pad in launches:
            self.assertGreaterEqual(pad['pad_size_m'], 24)
            self.assertLess(pad['pad_terrain_relief_m'], .15)
            distance = np.linalg.norm(trees[:, :2] - [pad['x'], pad['y']], axis=1)
            self.assertTrue((distance - trees[:, 2] > 22).all())
            self.assertLess(pad['road_connection_distance_m'], 2)

    def test_forest_and_buildings_grounded(self):
        self.assertGreater(len(self.scene['trees']), 4000)
        self.assertGreaterEqual(len(set(t['species'] for t in self.scene['trees'])), 3)
        self.assertGreaterEqual(len(self.scene['buildings']), 9)
        self.assertLessEqual(len(self.scene['buildings']), 20)
        trees=np.array([[t['x'],t['y'],t['z']] for t in self.scene['trees']])
        self.assertLess(float(np.max(np.abs(trees[:,2]-sample_terrain(self.terrain,trees[:,:2])))),.03)
        self.assertGreater(self.scene['min_tree_road_clearance_m'], 7)
        for b in self.scene['buildings']:
            self.assertLess(b['foundation_terrain_relief_m'], .15)

    def test_world_resolves_local_models_and_has_no_vehicle_systems(self):
        world = ET.parse(ROOT / 'gazebo/worlds/alishan_showcase.sdf')
        self.assertFalse(world.findall('.//sensor'))
        self.assertGreater(len(world.findall('.//include')), 4)
        for sdf in (ROOT / 'gazebo').rglob('*.sdf'):
            doc = ET.parse(sdf)
            for uri in doc.findall('.//uri'):
                self.assertTrue(uri.text.startswith('model://'), uri.text)
                asset = ROOT / 'gazebo/models' / uri.text.removeprefix('model://')
                self.assertTrue(asset.exists(), str(asset))
        self.assertLess(self.scene['render_triangle_count'], 1200000)


if __name__ == '__main__':
    unittest.main()
