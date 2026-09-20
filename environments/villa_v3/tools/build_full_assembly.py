"""Build and optionally render the complete Villa V3 inspection assembly."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector


FLOOR_Z = {"B1": -3.2, "1F": 0.0, "2F": 3.2, "3F": 6.4, "Roof": 9.6}


def arguments():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--render", type=Path)
    parser.add_argument("--skip-render", action="store_true")
    return parser.parse_args(argv)


def point_camera(camera, target):
    camera.rotation_euler = (Vector(target) - camera.location).to_track_quat("-Z", "Y").to_euler()


def neutral_material(name, color, metallic=0.0, roughness=0.65):
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    shader = material.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = (*color, 1.0)
    shader.inputs["Metallic"].default_value = metallic
    shader.inputs["Roughness"].default_value = roughness
    return material


def inspection_materials():
    return {
        "structure": neutral_material("VillaV3_NeutralStructure", (0.72, 0.69, 0.64)),
        "slab": neutral_material("VillaV3_NeutralSlab", (0.30, 0.32, 0.34)),
        "glass": neutral_material("VillaV3_NeutralGlass", (0.12, 0.42, 0.62), metallic=0.18, roughness=0.28),
        "roof": neutral_material("VillaV3_NeutralRoof", (0.50, 0.52, 0.54)),
        "rail": neutral_material("VillaV3_NeutralRail", (0.12, 0.14, 0.16), metallic=0.4, roughness=0.3),
    }


def assign_inspection_material(obj, materials):
    element = str(obj.get("element_type", "")).lower()
    if "roof" in element or obj.name.startswith("Roof_"):
        selected = materials["roof"]
    elif element in {"floor", "bridge_floor", "terrace", "porch", "slab"} or "floor" in element:
        selected = materials["slab"]
    elif "glass" in element or "glass" in obj.name.lower():
        selected = materials["glass"]
    elif "rail" in element or "railing" in obj.name.lower():
        selected = materials["rail"]
    else:
        selected = materials["structure"]
    obj.data.materials.clear()
    obj.data.materials.append(selected)


def add_lighting_and_camera(scene):
    camera_data = bpy.data.cameras.new("VillaV3_InspectionCamera")
    camera = bpy.data.objects.new("VillaV3_InspectionCamera", camera_data)
    scene.collection.objects.link(camera)
    camera.location = (48.0, -58.0, 23.0)
    camera_data.lens = 55.0
    point_camera(camera, (0.0, 0.0, 3.6))
    scene.camera = camera

    sun_data = bpy.data.lights.new("VillaV3_Sun", "SUN")
    sun_data.energy = 2.0
    sun_data.angle = math.radians(20)
    sun = bpy.data.objects.new("VillaV3_Sun", sun_data)
    scene.collection.objects.link(sun)
    sun.rotation_euler = (math.radians(28), math.radians(-18), math.radians(-35))

    area_data = bpy.data.lights.new("VillaV3_Fill", "AREA")
    area_data.energy = 5000
    area_data.shape = "DISK"
    area_data.size = 24
    area = bpy.data.objects.new("VillaV3_Fill", area_data)
    scene.collection.objects.link(area)
    area.location = (32.0, -34.0, 26.0)
    point_camera(area, (0.0, 0.0, 4.0))

    rim_data = bpy.data.lights.new("VillaV3_Rim", "AREA")
    rim_data.energy = 3000
    rim_data.shape = "DISK"
    rim_data.size = 20
    rim = bpy.data.objects.new("VillaV3_Rim", rim_data)
    scene.collection.objects.link(rim)
    rim.location = (-26.0, 18.0, 24.0)
    point_camera(rim, (0.0, 0.0, 5.0))

    ground_material = bpy.data.materials.new("VillaV3_GroundNeutral")
    ground_material.diffuse_color = (0.12, 0.13, 0.15, 1.0)
    bpy.ops.mesh.primitive_plane_add(size=100, location=(0, 0, -3.42))
    ground = bpy.context.object
    ground.name = "VillaV3_InspectionGround"
    ground.data.materials.append(ground_material)


def main():
    args = arguments()
    root = args.root.resolve()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.name = "VillaV3_FullAssembly"
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.length_unit = "METERS"
    scene.unit_settings.scale_length = 1.0

    sources = {}
    counts = {}
    materials = inspection_materials()
    for floor, elevation in FLOOR_Z.items():
        source = root / "01_shell" / floor / f"{floor}_shell.blend"
        if not source.is_file():
            raise FileNotFoundError(source)
        collection = bpy.data.collections.new(f"FLOOR_{floor}")
        collection["floor_id"] = floor
        collection["floor_elevation_m"] = elevation
        scene.collection.children.link(collection)
        with bpy.data.libraries.load(str(source), link=False) as (available, loaded):
            loaded.objects = list(available.objects)
        kept = []
        for obj in (item for item in loaded.objects if item):
            if obj.type != "MESH" or not obj.get("shell_geometry"):
                bpy.data.objects.remove(obj, do_unlink=True)
                continue
            local_z = obj.matrix_world.translation.z
            obj.matrix_world.translation.z = local_z + elevation
            obj["assembly_floor"] = floor
            obj["assembly_floor_elevation_m"] = elevation
            obj["assembly_source_local_origin_z_m"] = local_z
            assign_inspection_material(obj, materials)
            collection.objects.link(obj)
            kept.append(obj)
        if not kept:
            raise RuntimeError(f"no shell geometry loaded for {floor}")
        sources[floor] = str(source)
        counts[floor] = len(kept)

    scene["villa_version"] = "villa_v3"
    scene["floor_elevations_json"] = json.dumps(FLOOR_Z)
    scene["assembly_sources_json"] = json.dumps(sources)
    scene["assembly_object_counts_json"] = json.dumps(counts)
    add_lighting_and_camera(scene)
    scene.render.engine = "BLENDER_EEVEE_NEXT" if args.skip_render else "CYCLES"
    if not args.skip_render:
        scene.cycles.device = "CPU"
        scene.cycles.samples = 16
        scene.cycles.use_denoising = True
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    if scene.world is None:
        scene.world = bpy.data.worlds.new("VillaV3_InspectionWorld")
    scene.world.color = (0.035, 0.045, 0.06)
    scene.world.use_nodes = True
    background = scene.world.node_tree.nodes.get("Background")
    background.inputs["Color"].default_value = (0.055, 0.07, 0.09, 1.0)
    background.inputs["Strength"].default_value = 0.7

    args.output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output.resolve()))
    if not args.skip_render:
        if not args.render:
            raise ValueError("--render is required unless --skip-render is used")
        args.render.parent.mkdir(parents=True, exist_ok=True)
        scene.render.filepath = str(args.render.resolve())
        bpy.ops.render.render(write_still=True)
        if not args.render.is_file() or args.render.stat().st_size == 0:
            raise RuntimeError("render did not produce a PNG")
    print(f"VILLA_ASSEMBLY objects={sum(counts.values())} floors={len(counts)}")


if __name__ == "__main__":
    main()
