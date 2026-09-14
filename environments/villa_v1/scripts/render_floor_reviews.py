import bpy
from pathlib import Path

# Project root: .../villa_v1
blend_path = Path(bpy.data.filepath).resolve()
project_root = blend_path.parents[2]
out_dir = project_root / "renders" / "floor_review"
out_dir.mkdir(parents=True, exist_ok=True)

scene = bpy.context.scene
scene.render.image_settings.file_format = "PNG"
scene.render.resolution_x = 2200
scene.render.resolution_y = 1400

# 你要驗收的樓層與對應 overview camera
FLOORS = [
    ("B1", "B1_overview"),
    ("1F", "1F_overview"),
    ("2F", "2F_overview"),
    ("3F", "3F_overview"),
]

def belongs_to_floor(obj, floor_prefix):
    # 只要物件屬於該樓層 collection 或子 collection，就保留
    for coll in obj.users_collection:
        n = coll.name
        if n == floor_prefix or n.startswith(floor_prefix + "."):
            return True
    return False

def keep_for_render(obj, floor_prefix):
    # 相機和燈保留
    if obj.type in {"CAMERA", "LIGHT"}:
        return True
    # 只保留該樓層
    return belongs_to_floor(obj, floor_prefix)

for floor_prefix, camera_name in FLOORS:
    # 隱藏非本樓層所有物件
    for obj in bpy.data.objects:
        keep = keep_for_render(obj, floor_prefix)
        obj.hide_render = not keep
        obj.hide_viewport = not keep

    cam = bpy.data.objects.get(camera_name)
    if cam is None:
        print(f"[WARN] camera not found: {camera_name}")
        continue

    scene.camera = cam
    scene.render.filepath = str(out_dir / f"{floor_prefix}_overview.png")
    bpy.ops.render.render(write_still=True)
    print(f"[OK] rendered {floor_prefix} -> {scene.render.filepath}")

# 結束前恢復可見性
for obj in bpy.data.objects:
    obj.hide_render = False
    obj.hide_viewport = False

print(f"[DONE] floor review renders saved to: {out_dir}")
