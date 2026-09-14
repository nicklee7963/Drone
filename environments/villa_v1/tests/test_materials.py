"""Blender-side contract checks for the Summit Estate material library."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "materials.py"
EXPECTED_KEYS = {
    "stone", "marble", "dark_marble", "walnut", "oak", "black",
    "bronze", "glass", "cream", "taupe", "charcoal", "leather",
    "rubber", "acoustic", "ceramic", "water", "foliage", "soil",
    "emission", "book_0", "book_1", "book_2", "book_3", "book_4",
    "book_5", "mirror", "plaster", "carpet", "stainless",
}


def load_module():
    spec = importlib.util.spec_from_file_location("summit_materials", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def group_for(material):
    groups = [n for n in material.node_tree.nodes if n.bl_idname == "ShaderNodeGroup"]
    assert len(groups) == 1, f"{material.name}: expected one editable surface group"
    return groups[0].node_tree


def group_inputs(group):
    return {
        item.name
        for item in group.interface.items_tree
        if item.item_type == "SOCKET" and item.in_out == "INPUT"
    }


def test_material_library_contract():
    materials = load_module().build_materials()
    assert set(materials) == EXPECTED_KEYS
    assert len({m.name for m in materials.values()}) == len(EXPECTED_KEYS)

    for key, material in materials.items():
        assert material.use_nodes, key
        output = next(n for n in material.node_tree.nodes if n.bl_idname == "ShaderNodeOutputMaterial")
        assert output.inputs["Surface"].is_linked, key
        assert material.get("summit_key") == key
        assert material.use_fake_user, f"{key}: zero-user library material could be purged"

    # A second call must reuse the same datablocks, not create .001 copies.
    again = load_module().build_materials()
    assert all(again[key] == materials[key] for key in EXPECTED_KEYS)


def test_signature_materials_have_editable_physical_controls():
    materials = load_module().build_materials()

    for key in ("stone", "marble", "dark_marble"):
        group = group_for(materials[key])
        assert "Feature Scale (m)" in group_inputs(group)
        texture_types = {node.bl_idname for node in group.nodes}
        assert "ShaderNodeTexNoise" in texture_types
        if key != "stone":
            assert "ShaderNodeTexWave" in texture_types
            assert "ShaderNodeTexVoronoi" in texture_types

    for key in ("walnut", "oak"):
        group = group_for(materials[key])
        inputs = group_inputs(group)
        assert {"Grain Width (m)", "Grain Rotation (rad)"} <= inputs
        texture_types = {node.bl_idname for node in group.nodes}
        assert {"ShaderNodeTexNoise", "ShaderNodeTexWave"} <= texture_types

    for key in ("cream", "taupe", "charcoal", "acoustic", "carpet"):
        group = group_for(materials[key])
        assert "Weave Scale (m)" in group_inputs(group)
        assert sum(n.bl_idname == "ShaderNodeTexWave" for n in group.nodes) >= 2


def test_physical_glass_and_warm_emission_metadata():
    materials = load_module().build_materials()
    assert materials["glass"]["summit_ior"] == 1.45
    assert materials["glass"]["summit_min_thickness_m"] == 0.006
    assert materials["water"]["summit_ior"] == 1.333

    emission_group = group_for(materials["emission"])
    blackbody = next(n for n in emission_group.nodes if n.bl_idname == "ShaderNodeBlackbody")
    assert blackbody.inputs["Temperature"].default_value == 3000.0


def render_cpu_smoke(materials, output_path):
    """Render signature swatches with Cycles CPU to compile real shaders."""
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 8
    scene.cycles.use_denoising = False
    scene.cycles.max_bounces = 4
    scene.render.resolution_x = 720
    scene.render.resolution_y = 360
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(output_path)
    scene.render.film_transparent = False
    scene.world.color = (0.025, 0.025, 0.025)

    swatches = ("marble", "dark_marble", "walnut", "bronze", "cream", "rubber", "glass")
    for index, key in enumerate(swatches):
        x = (index - 3) * 1.8
        if key == "glass":
            bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, location=(x, 0, 1.05))
        else:
            bpy.ops.mesh.primitive_cube_add(location=(x, 0, 1.0), scale=(0.72, 0.72, 0.72))
            obj = bpy.context.object
            bevel = obj.modifiers.new("Preview edge bevel", "BEVEL")
            bevel.width = 0.12
            bevel.segments = 4
        obj = bpy.context.object
        obj.name = f"Smoke_{key}"
        obj.data.materials.append(materials[key])

    bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 0, 0))
    bpy.context.object.data.materials.append(materials["stone"])

    bpy.ops.object.light_add(type="AREA", location=(-4, -4, 7))
    key_light = bpy.context.object
    key_light.data.energy = 1100
    key_light.data.shape = "DISK"
    key_light.data.size = 5.0
    bpy.ops.object.light_add(type="AREA", location=(5, 1, 5))
    fill_light = bpy.context.object
    fill_light.data.energy = 850
    fill_light.data.size = 4.0

    bpy.ops.object.camera_add(location=(0, -15.5, 5.0))
    camera = bpy.context.object
    direction = Vector((0, 0, 1.0)) - camera.location
    camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    camera.data.lens = 49
    scene.camera = camera
    bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    test_material_library_contract()
    test_signature_materials_have_editable_physical_controls()
    test_physical_glass_and_warm_emission_metadata()
    print("Summit material tests: PASS")
    materials = load_module().build_materials()
    if "--save-library" in sys.argv:
        output_arg = sys.argv[sys.argv.index("--save-library") + 1]
        output_path = (ROOT / output_arg).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete(use_global=False)
        bpy.ops.wm.save_as_mainfile(filepath=str(output_path), check_existing=False)
        print(f"Saved tested material library: {output_path}")
    if "--render-smoke" in sys.argv:
        render_arg = sys.argv[sys.argv.index("--render-smoke") + 1]
        render_path = (ROOT / render_arg).resolve()
        render_cpu_smoke(materials, render_path)
        print(f"Rendered CPU smoke image: {render_path}")
