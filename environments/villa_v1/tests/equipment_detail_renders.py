import bpy,sys
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1]
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'renders/assets_equipment/equipment_smoke.blend'))
s=bpy.context.scene;s.render.resolution_x=1000;s.render.resolution_y=760;s.cycles.samples=32
cam=s.camera;cam.data.type='PERSP';cam.data.lens=52
cases=[('07_car',(5,-7,3.1),(0,0,.65)),('16_car',(5,-7,3.1),(0,0,.7)),('00_piano',(3.5,-4.8,3.5),(0,0,.85)),('11_hot_tub',(4,-5,4),(0,-.15,.45)),('06_cinema_seat',(2.4,-3.4,2.2),(0,0,.65)),('15_shoe_display',(3.4,-7,3),(0,0,1.25))]
for name,offset,look in cases:
    root=bpy.data.objects[name];cam.location=root.location+Vector(offset)
    target=root.location+Vector(look);cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
    s.render.filepath=str(ROOT/'renders/assets_equipment'/f'detail_{name}.png');bpy.ops.render.render(write_still=True)
