"""Procedural PBR material library for Summit Estate.

The scene uses metres. Procedural coordinates come from the shader Object
coordinate, so object scale should be applied before final look development.
Feature-size controls are expressed in metres and wood/fabric rotation is in
radians around local Z. Glass and water require closed, physically thick mesh.

Public API:
    build_materials() -> dict[str, bpy.types.Material]
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import bpy


LIBRARY_VERSION = 1
MATERIAL_PREFIX = "SUMMIT :: "

DISPLAY_NAMES = {
    "stone": "Limestone",
    "marble": "Calacatta Breccia",
    "dark_marble": "Dark Emperador Marble",
    "walnut": "Warm Walnut",
    "oak": "Natural Oak",
    "black": "Satin Architectural Black",
    "bronze": "Satin Bronze",
    "glass": "Low Iron Architectural Glass",
    "cream": "Cream Woven Upholstery",
    "taupe": "Taupe Woven Upholstery",
    "charcoal": "Charcoal Woven Upholstery",
    "leather": "Cognac Leather",
    "rubber": "Gym Rubber Fleck",
    "acoustic": "Charcoal Acoustic Fabric",
    "ceramic": "Warm White Ceramic",
    "water": "Clear Water",
    "foliage": "Living Foliage",
    "soil": "Potting Soil",
    "emission": "Warm 3000K Diffuser",
    "book_0": "Book Cloth Oxblood",
    "book_1": "Book Cloth Ochre",
    "book_2": "Book Cloth Forest",
    "book_3": "Book Cloth Slate",
    "book_4": "Book Cloth Parchment",
    "book_5": "Book Cloth Umber",
    "mirror": "Silvered Mirror",
    "plaster": "Warm Fine Plaster",
    "carpet": "Dense Taupe Carpet",
    "stainless": "Brushed Stainless Steel",
}


def _socket(node, name):
    socket = node.inputs.get(name)
    if socket is None:
        raise KeyError(f"{node.bl_idname} has no input named {name!r}")
    return socket


def _set(tree, target, value):
    """Link an output socket or assign a literal to an input socket."""
    if hasattr(value, "is_output") and value.is_output:
        tree.links.new(value, target)
    else:
        target.default_value = value


def _node(tree, node_type, name, location=(0, 0)):
    node = tree.nodes.new(node_type)
    node.name = name
    node.label = name
    node.location = location
    return node


def _interface_socket(
    group,
    name,
    socket_type,
    default=None,
    minimum=None,
    maximum=None,
    description="",
):
    socket = group.interface.new_socket(
        name=name, in_out="INPUT", socket_type=socket_type
    )
    if default is not None:
        socket.default_value = default
    if minimum is not None:
        socket.min_value = minimum
    if maximum is not None:
        socket.max_value = maximum
    socket.description = description
    return socket


def _new_group(key, controls, *, volume_output=False):
    name = f"SUMMIT_{key}_Surface"
    old = bpy.data.node_groups.get(name)
    if old is not None and old.users == 0:
        bpy.data.node_groups.remove(old)
    group = bpy.data.node_groups.new(name, "ShaderNodeTree")
    for control in controls:
        _interface_socket(group, *control)
    group.interface.new_socket(
        name="Surface", in_out="OUTPUT", socket_type="NodeSocketShader"
    )
    if volume_output:
        group.interface.new_socket(
            name="Volume", in_out="OUTPUT", socket_type="NodeSocketShader"
        )
    group_input = _node(group, "NodeGroupInput", "Editable Controls", (-1100, 0))
    group_output = _node(group, "NodeGroupOutput", "Material Output", (900, 0))
    return group, group_input, group_output


def _material_shell(key, group, preview_color):
    material_name = MATERIAL_PREFIX + DISPLAY_NAMES[key]
    material = bpy.data.materials.get(material_name)
    if material is None:
        material = bpy.data.materials.new(material_name)
    material.use_nodes = True
    material.use_fake_user = True
    material.node_tree.nodes.clear()
    material.diffuse_color = preview_color
    material["summit_key"] = key
    material["summit_library_version"] = LIBRARY_VERSION
    material["summit_units"] = "metres; apply object scale"

    group_node = _node(material.node_tree, "ShaderNodeGroup", "Surface Controls", (-120, 0))
    group_node.node_tree = group
    output = _node(material.node_tree, "ShaderNodeOutputMaterial", "Material Output", (220, 0))
    material.node_tree.links.new(group_node.outputs["Surface"], output.inputs["Surface"])
    if group_node.outputs.get("Volume") is not None:
        material.node_tree.links.new(group_node.outputs["Volume"], output.inputs["Volume"])
    return material


def _principled(group, group_output, *, color, roughness, metallic=0.0,
                normal=None, ior=1.5, transmission=0.0, anisotropic=0.0,
                coat=0.0, coat_roughness=0.03, subsurface=0.0,
                sheen=0.0, emission_color=None, emission_strength=0.0):
    bsdf = _node(group, "ShaderNodeBsdfPrincipled", "PBR Surface", (560, 80))
    _set(group, _socket(bsdf, "Base Color"), color)
    _set(group, _socket(bsdf, "Roughness"), roughness)
    _set(group, _socket(bsdf, "Metallic"), metallic)
    _set(group, _socket(bsdf, "IOR"), ior)
    _set(group, _socket(bsdf, "Transmission Weight"), transmission)
    _set(group, _socket(bsdf, "Anisotropic"), anisotropic)
    _set(group, _socket(bsdf, "Coat Weight"), coat)
    _set(group, _socket(bsdf, "Coat Roughness"), coat_roughness)
    _set(group, _socket(bsdf, "Subsurface Weight"), subsurface)
    _set(group, _socket(bsdf, "Sheen Weight"), sheen)
    if normal is not None:
        _set(group, _socket(bsdf, "Normal"), normal)
    if emission_color is not None:
        _set(group, _socket(bsdf, "Emission Color"), emission_color)
        _set(group, _socket(bsdf, "Emission Strength"), emission_strength)
    group.links.new(bsdf.outputs["BSDF"], group_output.inputs["Surface"])
    return bsdf


def _math(group, operation, a, b=None, name="Math", location=(0, 0)):
    node = _node(group, "ShaderNodeMath", name, location)
    node.operation = operation
    _set(group, node.inputs[0], a)
    if b is not None:
        _set(group, node.inputs[1], b)
    return node.outputs[0]


def _mix(group, fac, color_a, color_b, name="Color Mix", location=(0, 0), blend="MIX"):
    node = _node(group, "ShaderNodeMixRGB", name, location)
    node.blend_type = blend
    node.inputs[0].default_value = 0.5
    _set(group, node.inputs[0], fac)
    _set(group, node.inputs[1], color_a)
    _set(group, node.inputs[2], color_b)
    return node.outputs[0]


def _physical_coordinates(group, group_input, scale_name, rotation_name=None):
    texcoord = _node(group, "ShaderNodeTexCoord", "Object Coordinates", (-1080, 330))
    vector = texcoord.outputs["Object"]
    if rotation_name:
        rotate = _node(group, "ShaderNodeVectorRotate", "Local Z Rotation", (-880, 330))
        rotate.rotation_type = "AXIS_ANGLE"
        rotate.inputs["Axis"].default_value = (0.0, 0.0, 1.0)
        group.links.new(vector, rotate.inputs["Vector"])
        group.links.new(group_input.outputs[rotation_name], rotate.inputs["Angle"])
        vector = rotate.outputs["Vector"]
    inverse = _math(
        group, "DIVIDE", 1.0, group_input.outputs[scale_name],
        "Metres to Texture Scale", (-850, 160)
    )
    scale = _node(group, "ShaderNodeVectorMath", "Physical Feature Scale", (-650, 330))
    scale.operation = "SCALE"
    group.links.new(vector, scale.inputs[0])
    group.links.new(inverse, scale.inputs[3])
    return scale.outputs["Vector"]


def _bump(group, height, *, strength=0.18, distance=0.002, location=(330, -190)):
    bump = _node(group, "ShaderNodeBump", "Micro Surface Relief", location)
    bump.inputs["Strength"].default_value = strength
    bump.inputs["Distance"].default_value = distance
    group.links.new(height, bump.inputs["Height"])
    return bump.outputs["Normal"]


def _build_stone(key="stone"):
    controls = [
        ("Feature Scale (m)", "NodeSocketFloat", 0.32, 0.02, 5.0,
         "Largest mottling size in metres; apply object scale."),
        ("Pattern Rotation (rad)", "NodeSocketFloat", 0.0, -6.283, 6.283,
         "Rotation around local Z."),
        ("Base Color", "NodeSocketColor", (0.43, 0.39, 0.32, 1), None, None, "Warm limestone body."),
        ("Mineral Color", "NodeSocketColor", (0.22, 0.19, 0.15, 1), None, None, "Darker mineral variation."),
        ("Roughness", "NodeSocketFloat", 0.46, 0.0, 1.0, "Average polished stone roughness."),
    ]
    group, gin, gout = _new_group(key, controls)
    co = _physical_coordinates(group, gin, "Feature Scale (m)", "Pattern Rotation (rad)")
    macro = _node(group, "ShaderNodeTexNoise", "Sedimentary Mottle", (-430, 360))
    macro.noise_dimensions = "3D"
    macro.inputs["Scale"].default_value = 1.35
    macro.inputs["Detail"].default_value = 5.0
    macro.inputs["Roughness"].default_value = 0.68
    macro.inputs["Distortion"].default_value = 0.28
    group.links.new(co, macro.inputs["Vector"])
    micro = _node(group, "ShaderNodeTexNoise", "Fine Pores", (-420, 10))
    micro.noise_dimensions = "3D"
    micro.inputs["Scale"].default_value = 34.0
    micro.inputs["Detail"].default_value = 3.0
    micro.inputs["Roughness"].default_value = 0.58
    group.links.new(co, micro.inputs["Vector"])
    color = _mix(group, macro.outputs["Fac"], gin.outputs["Mineral Color"], gin.outputs["Base Color"], "Mineral Color Variation", (40, 320))
    rough_delta = _math(group, "MULTIPLY", micro.outputs["Fac"], 0.13, "Pore Roughness", (70, -25))
    roughness = _math(group, "ADD", gin.outputs["Roughness"], rough_delta, "Variable Roughness", (280, 10))
    normal = _bump(group, micro.outputs["Fac"], strength=0.13, distance=0.0015)
    _principled(group, gout, color=color, roughness=roughness, normal=normal, coat=0.08, coat_roughness=0.25)
    material = _material_shell(key, group, (0.43, 0.39, 0.32, 1))
    material["summit_feature_scale_m"] = 0.32
    return material


def _build_marble(key, base, vein, accent, roughness, feature_scale, vein_width):
    controls = [
        ("Feature Scale (m)", "NodeSocketFloat", feature_scale, 0.05, 5.0,
         "Major vein wavelength in metres; apply object scale."),
        ("Pattern Rotation (rad)", "NodeSocketFloat", 0.18, -6.283, 6.283,
         "Slab pattern rotation around local Z."),
        ("Base Color", "NodeSocketColor", base, None, None, "Stone body."),
        ("Vein Color", "NodeSocketColor", vein, None, None, "Major and hairline veins."),
        ("Accent Color", "NodeSocketColor", accent, None, None, "Broad mineral cloud."),
        ("Vein Width", "NodeSocketFloat", vein_width, 0.015, 0.30, "Normalized vein width."),
        ("Roughness", "NodeSocketFloat", roughness, 0.02, 0.8, "Polish roughness."),
    ]
    group, gin, gout = _new_group(key, controls)
    co = _physical_coordinates(group, gin, "Feature Scale (m)", "Pattern Rotation (rad)")

    macro = _node(group, "ShaderNodeTexNoise", "Broad Mineral Cloud", (-470, 520))
    macro.noise_dimensions = "3D"
    macro.inputs["Scale"].default_value = 0.72
    macro.inputs["Detail"].default_value = 5.0
    macro.inputs["Roughness"].default_value = 0.72
    macro.inputs["Distortion"].default_value = 0.32
    group.links.new(co, macro.inputs["Vector"])

    warp_scale = _node(group, "ShaderNodeVectorMath", "Vein Warp Amount", (-250, 370))
    warp_scale.operation = "SCALE"
    group.links.new(macro.outputs["Color"], warp_scale.inputs[0])
    warp_scale.inputs[3].default_value = 0.38
    warped = _node(group, "ShaderNodeVectorMath", "Warped Stone Coordinates", (-60, 390))
    warped.operation = "ADD"
    group.links.new(co, warped.inputs[0])
    group.links.new(warp_scale.outputs["Vector"], warped.inputs[1])

    major = _node(group, "ShaderNodeTexWave", "Major Flowing Veins", (130, 430))
    major.wave_type = "BANDS"
    major.bands_direction = "X"
    major.inputs["Scale"].default_value = 1.9
    major.inputs["Distortion"].default_value = 7.5
    major.inputs["Detail"].default_value = 7.0
    major.inputs["Detail Scale"].default_value = 2.0
    major.inputs["Detail Roughness"].default_value = 0.78
    group.links.new(warped.outputs["Vector"], major.inputs["Vector"])

    secondary_rotate = _node(group, "ShaderNodeVectorRotate", "Secondary Vein Angle", (110, 190))
    secondary_rotate.rotation_type = "AXIS_ANGLE"
    secondary_rotate.inputs["Axis"].default_value = (0.0, 0.0, 1.0)
    secondary_rotate.inputs["Angle"].default_value = 0.68
    group.links.new(warped.outputs["Vector"], secondary_rotate.inputs["Vector"])
    secondary = _node(group, "ShaderNodeTexWave", "Secondary Fracture Veins", (310, 190))
    secondary.wave_type = "BANDS"
    secondary.bands_direction = "X"
    secondary.inputs["Scale"].default_value = 4.8
    secondary.inputs["Distortion"].default_value = 11.0
    secondary.inputs["Detail"].default_value = 5.0
    secondary.inputs["Detail Scale"].default_value = 1.3
    group.links.new(secondary_rotate.outputs["Vector"], secondary.inputs["Vector"])

    cells = _node(group, "ShaderNodeTexVoronoi", "Hairline Mineral Boundaries", (100, -90))
    cells.distance = "EUCLIDEAN"
    cells.feature = "DISTANCE_TO_EDGE"
    cells.inputs["Scale"].default_value = 3.5
    group.links.new(warped.outputs["Vector"], cells.inputs["Vector"])

    major_mask = _math(group, "LESS_THAN", major.outputs["Fac"], gin.outputs["Vein Width"], "Major Vein Mask", (360, 460))
    thin_width = _math(group, "MULTIPLY", gin.outputs["Vein Width"], 0.33, "Thin Vein Width", (360, -30))
    secondary_mask = _math(group, "LESS_THAN", secondary.outputs["Fac"], thin_width, "Secondary Vein Mask", (530, 190))
    hair_width = _math(group, "MULTIPLY", gin.outputs["Vein Width"], 0.22, "Hairline Width", (350, -130))
    hair_mask = _math(group, "LESS_THAN", cells.outputs["Distance"], hair_width, "Hairline Mask", (530, -100))
    fractures = _math(group, "MAXIMUM", secondary_mask, hair_mask, "Fine Vein Network", (680, 100))
    vein_mask = _math(group, "MAXIMUM", major_mask, fractures, "Multiscale Vein Mask", (680, 360))

    cloud = _mix(group, macro.outputs["Fac"], gin.outputs["Base Color"], gin.outputs["Accent Color"], "Mineral Cloud Color", (50, 660))
    color = _mix(group, vein_mask, cloud, gin.outputs["Vein Color"], "Veined Stone Color", (700, 600))
    rough_variation = _math(group, "MULTIPLY", macro.outputs["Fac"], 0.055, "Mineral Roughness Variation", (410, -310))
    final_roughness = _math(group, "ADD", gin.outputs["Roughness"], rough_variation, "Variable Polish", (610, -300))
    normal = _bump(group, vein_mask, strength=0.095, distance=0.001, location=(690, -160))
    _principled(group, gout, color=color, roughness=final_roughness, normal=normal, coat=0.14, coat_roughness=0.12)
    material = _material_shell(key, group, base)
    material["summit_feature_scale_m"] = feature_scale
    material["summit_pattern"] = "three-scale flowing wave + fracture network"
    return material


def _build_wood(key, light, dark, roughness, grain_width):
    controls = [
        ("Grain Width (m)", "NodeSocketFloat", grain_width, 0.001, 0.05,
         "Fine grain spacing in metres; grain runs along local Y."),
        ("Grain Rotation (rad)", "NodeSocketFloat", 0.0, -6.283, 6.283,
         "Rotate grain around local Z for boards and panels."),
        ("Light Tone", "NodeSocketColor", light, None, None, "Earlywood tone."),
        ("Dark Tone", "NodeSocketColor", dark, None, None, "Latewood tone."),
        ("Roughness", "NodeSocketFloat", roughness, 0.08, 0.9, "Finished timber roughness."),
    ]
    group, gin, gout = _new_group(key, controls)
    co = _physical_coordinates(group, gin, "Grain Width (m)", "Grain Rotation (rad)")
    elongate = _node(group, "ShaderNodeVectorMath", "Lengthwise Grain", (-430, 360))
    elongate.operation = "MULTIPLY"
    elongate.inputs[1].default_value = (1.0, 0.035, 0.28)
    group.links.new(co, elongate.inputs[0])
    warp = _node(group, "ShaderNodeTexNoise", "Natural Grain Drift", (-230, 480))
    warp.noise_dimensions = "3D"
    warp.inputs["Scale"].default_value = 0.8
    warp.inputs["Detail"].default_value = 5.0
    warp.inputs["Roughness"].default_value = 0.65
    warp.inputs["Distortion"].default_value = 0.25
    group.links.new(elongate.outputs["Vector"], warp.inputs["Vector"])
    grain = _node(group, "ShaderNodeTexWave", "Fine Lengthwise Grain", (0, 390))
    grain.wave_type = "BANDS"
    grain.bands_direction = "X"
    grain.inputs["Scale"].default_value = 2.4
    grain.inputs["Distortion"].default_value = 6.0
    grain.inputs["Detail"].default_value = 7.0
    grain.inputs["Detail Scale"].default_value = 2.1
    grain.inputs["Detail Roughness"].default_value = 0.72
    group.links.new(elongate.outputs["Vector"], grain.inputs["Vector"])
    pores = _node(group, "ShaderNodeTexNoise", "Fine Timber Pores", (-20, 80))
    pores.noise_dimensions = "3D"
    pores.inputs["Scale"].default_value = 11.0
    pores.inputs["Detail"].default_value = 3.0
    pores.inputs["Roughness"].default_value = 0.62
    group.links.new(elongate.outputs["Vector"], pores.inputs["Vector"])
    tone = _mix(group, grain.outputs["Fac"], gin.outputs["Dark Tone"], gin.outputs["Light Tone"], "Growth Ring Tone", (240, 390))
    broad_tone = _mix(group, warp.outputs["Fac"], dark, tone, "Board Tonal Drift", (440, 480))
    rough_delta = _math(group, "MULTIPLY", pores.outputs["Fac"], 0.10, "Pore Roughness", (240, 30))
    variable_roughness = _math(group, "ADD", gin.outputs["Roughness"], rough_delta, "Variable Finish", (430, 40))
    height = _math(group, "MULTIPLY", grain.outputs["Fac"], pores.outputs["Fac"], "Grain Relief", (250, -100))
    normal = _bump(group, height, strength=0.15, distance=0.0008, location=(460, -170))
    _principled(group, gout, color=broad_tone, roughness=variable_roughness, normal=normal, coat=0.10, coat_roughness=0.2)
    material = _material_shell(key, group, light)
    material["summit_grain_direction"] = "local +Y; rotation control about local Z"
    material["summit_grain_width_m"] = grain_width
    return material


def _build_woven(key, color_a, color_b, roughness, weave_scale, bump_strength=0.2):
    controls = [
        ("Weave Scale (m)", "NodeSocketFloat", weave_scale, 0.0004, 0.03,
         "Thread repeat in metres; apply object scale."),
        ("Weave Rotation (rad)", "NodeSocketFloat", 0.0, -6.283, 6.283,
         "Rotate warp/weft around local Z."),
        ("Warp Color", "NodeSocketColor", color_a, None, None, "Primary textile tone."),
        ("Weft Color", "NodeSocketColor", color_b, None, None, "Cross-thread tone."),
        ("Roughness", "NodeSocketFloat", roughness, 0.2, 1.0, "Textile surface roughness."),
    ]
    group, gin, gout = _new_group(key, controls)
    co = _physical_coordinates(group, gin, "Weave Scale (m)", "Weave Rotation (rad)")
    warp = _node(group, "ShaderNodeTexWave", "Warp Threads", (-380, 380))
    warp.wave_type = "BANDS"
    warp.bands_direction = "X"
    warp.inputs["Scale"].default_value = 1.35
    warp.inputs["Distortion"].default_value = 0.16
    warp.inputs["Detail"].default_value = 2.0
    group.links.new(co, warp.inputs["Vector"])
    weft = _node(group, "ShaderNodeTexWave", "Weft Threads", (-380, 100))
    weft.wave_type = "BANDS"
    weft.bands_direction = "Y"
    weft.inputs["Scale"].default_value = 1.35
    weft.inputs["Distortion"].default_value = 0.16
    weft.inputs["Detail"].default_value = 2.0
    group.links.new(co, weft.inputs["Vector"])
    weave = _math(group, "MULTIPLY", warp.outputs["Fac"], weft.outputs["Fac"], "Over Under Weave", (-80, 250))
    color = _mix(group, weave, gin.outputs["Warp Color"], gin.outputs["Weft Color"], "Thread Color", (150, 330))
    normal = _bump(group, weave, strength=bump_strength, distance=weave_scale * 0.3, location=(260, 0))
    _principled(
        group, gout, color=color, roughness=gin.outputs["Roughness"],
        normal=normal, sheen=0.22,
    )
    material = _material_shell(key, group, color_a)
    material["summit_weave_scale_m"] = weave_scale
    return material


def _build_simple(key, color, roughness, *, metallic=0.0, coat=0.0,
                  subsurface=0.0, noise_scale=None, bump_strength=0.0):
    controls = [
        ("Base Color", "NodeSocketColor", color, None, None, "Editable material tint."),
        ("Roughness", "NodeSocketFloat", roughness, 0.0, 1.0, "Surface roughness."),
    ]
    if noise_scale:
        controls.insert(0, ("Feature Scale (m)", "NodeSocketFloat", noise_scale, 0.0005, 1.0, "Procedural relief scale in metres."))
    group, gin, gout = _new_group(key, controls)
    normal = None
    variable_roughness = gin.outputs["Roughness"]
    surface_color = gin.outputs["Base Color"]
    if noise_scale:
        co = _physical_coordinates(group, gin, "Feature Scale (m)")
        noise = _node(group, "ShaderNodeTexNoise", "Surface Microstructure", (-300, 260))
        noise.noise_dimensions = "3D"
        noise.inputs["Scale"].default_value = 1.0
        noise.inputs["Detail"].default_value = 4.0
        noise.inputs["Roughness"].default_value = 0.65
        group.links.new(co, noise.inputs["Vector"])
        shadow = tuple(max(0.0, component * 0.72) for component in color[:3]) + (1.0,)
        surface_color = _mix(group, noise.outputs["Fac"], shadow, gin.outputs["Base Color"], "Micro Color", (50, 300))
        delta = _math(group, "MULTIPLY", noise.outputs["Fac"], 0.09, "Micro Roughness", (50, 20))
        variable_roughness = _math(group, "ADD", gin.outputs["Roughness"], delta, "Variable Roughness", (250, 20))
        if bump_strength:
            normal = _bump(group, noise.outputs["Fac"], strength=bump_strength, distance=noise_scale * 0.12)
    _principled(group, gout, color=surface_color, roughness=variable_roughness, metallic=metallic, normal=normal, coat=coat, subsurface=subsurface)
    return _material_shell(key, group, color)


def _build_leather():
    key = "leather"
    controls = [
        ("Grain Scale (m)", "NodeSocketFloat", 0.004, 0.0005, 0.03, "Leather grain size in metres."),
        ("Base Color", "NodeSocketColor", (0.28, 0.075, 0.025, 1), None, None, "Cognac dye."),
        ("Roughness", "NodeSocketFloat", 0.34, 0.1, 0.9, "Leather finish roughness."),
    ]
    group, gin, gout = _new_group(key, controls)
    co = _physical_coordinates(group, gin, "Grain Scale (m)")
    grain = _node(group, "ShaderNodeTexNoise", "Leather Grain", (-330, 260))
    grain.noise_dimensions = "3D"
    grain.inputs["Scale"].default_value = 1.25
    grain.inputs["Detail"].default_value = 9.0
    grain.inputs["Roughness"].default_value = 0.76
    grain.inputs["Distortion"].default_value = 0.35
    group.links.new(co, grain.inputs["Vector"])
    pores = _node(group, "ShaderNodeTexVoronoi", "Leather Pores", (-330, -20))
    pores.feature = "DISTANCE_TO_EDGE"
    pores.inputs["Scale"].default_value = 3.2
    group.links.new(co, pores.inputs["Vector"])
    dark = (0.11, 0.018, 0.006, 1)
    color = _mix(group, grain.outputs["Fac"], dark, gin.outputs["Base Color"], "Dyed Grain", (60, 270))
    relief = _math(group, "MULTIPLY", grain.outputs["Fac"], pores.outputs["Distance"], "Leather Relief", (80, -40))
    normal = _bump(group, relief, strength=0.22, distance=0.00065, location=(310, -80))
    _principled(group, gout, color=color, roughness=gin.outputs["Roughness"], normal=normal, coat=0.12, coat_roughness=0.22)
    material = _material_shell(key, group, (0.28, 0.075, 0.025, 1))
    material["summit_grain_scale_m"] = 0.004
    return material


def _build_rubber():
    key = "rubber"
    controls = [
        ("Fleck Scale (m)", "NodeSocketFloat", 0.007, 0.001, 0.03, "Rubber aggregate size in metres."),
        ("Fleck Amount", "NodeSocketFloat", 0.78, 0.55, 0.95, "Threshold controlling visible flecks."),
        ("Roughness", "NodeSocketFloat", 0.72, 0.3, 1.0, "Rubber roughness."),
    ]
    group, gin, gout = _new_group(key, controls)
    co = _physical_coordinates(group, gin, "Fleck Scale (m)")
    flecks = _node(group, "ShaderNodeTexNoise", "Embedded EPDM Flecks", (-350, 280))
    flecks.noise_dimensions = "3D"
    flecks.inputs["Scale"].default_value = 2.8
    flecks.inputs["Detail"].default_value = 2.0
    flecks.inputs["Roughness"].default_value = 0.55
    group.links.new(co, flecks.inputs["Vector"])
    mask = _math(group, "GREATER_THAN", flecks.outputs["Fac"], gin.outputs["Fleck Amount"], "Sparse Fleck Mask", (-80, 260))
    color = _mix(group, mask, (0.012, 0.014, 0.014, 1), (0.13, 0.14, 0.13, 1), "Rubber Aggregate", (150, 280))
    normal = _bump(group, flecks.outputs["Fac"], strength=0.32, distance=0.0012, location=(220, -20))
    _principled(group, gout, color=color, roughness=gin.outputs["Roughness"], normal=normal)
    material = _material_shell(key, group, (0.02, 0.022, 0.021, 1))
    material["summit_fleck_scale_m"] = 0.007
    return material


def _build_metal(key, color, roughness, brushing_scale):
    controls = [
        ("Brushing Scale (m)", "NodeSocketFloat", brushing_scale, 0.0001, 0.02, "Brushed finish spacing in metres."),
        ("Brushing Rotation (rad)", "NodeSocketFloat", 0.0, -6.283, 6.283, "Brushing direction around local Z."),
        ("Metal Tint", "NodeSocketColor", color, None, None, "Metal tint."),
        ("Roughness", "NodeSocketFloat", roughness, 0.04, 0.8, "Satin finish roughness."),
        ("Anisotropy", "NodeSocketFloat", 0.36, 0.0, 1.0, "Directional satin highlight."),
    ]
    group, gin, gout = _new_group(key, controls)
    co = _physical_coordinates(group, gin, "Brushing Scale (m)", "Brushing Rotation (rad)")
    stretch = _node(group, "ShaderNodeVectorMath", "Directional Brushing", (-390, 300))
    stretch.operation = "MULTIPLY"
    stretch.inputs[1].default_value = (1.0, 0.025, 0.12)
    group.links.new(co, stretch.inputs[0])
    noise = _node(group, "ShaderNodeTexNoise", "Satin Brushing", (-180, 300))
    noise.noise_dimensions = "3D"
    noise.inputs["Scale"].default_value = 1.4
    noise.inputs["Detail"].default_value = 3.0
    noise.inputs["Roughness"].default_value = 0.62
    group.links.new(stretch.outputs["Vector"], noise.inputs["Vector"])
    rough_delta = _math(group, "MULTIPLY", noise.outputs["Fac"], 0.08, "Brushing Roughness", (80, 40))
    variable_roughness = _math(group, "ADD", gin.outputs["Roughness"], rough_delta, "Variable Satin Roughness", (290, 50))
    normal = _bump(group, noise.outputs["Fac"], strength=0.10, distance=brushing_scale * 0.16, location=(250, -130))
    _principled(group, gout, color=gin.outputs["Metal Tint"], roughness=variable_roughness, metallic=1.0, normal=normal, anisotropic=gin.outputs["Anisotropy"])
    material = _material_shell(key, group, color)
    material["summit_brushing_scale_m"] = brushing_scale
    return material


def _build_glass(key, tint, roughness, ior, density, min_thickness):
    controls = [
        ("Glass Tint", "NodeSocketColor", tint, None, None, "Subtle glass transmission tint."),
        ("Roughness", "NodeSocketFloat", roughness, 0.0, 0.5, "Surface polish."),
        ("IOR", "NodeSocketFloat", ior, 1.0, 2.0, "Physical index of refraction."),
        ("Absorption Density", "NodeSocketFloat", density, 0.0, 20.0, "Volume absorption per metre."),
    ]
    group, gin, gout = _new_group(key, controls, volume_output=True)
    _principled(group, gout, color=gin.outputs["Glass Tint"], roughness=gin.outputs["Roughness"], ior=gin.outputs["IOR"], transmission=1.0)
    absorption = _node(group, "ShaderNodeVolumeAbsorption", "Thickness Absorption", (560, -230))
    group.links.new(gin.outputs["Glass Tint"], absorption.inputs["Color"])
    group.links.new(gin.outputs["Absorption Density"], absorption.inputs["Density"])
    group.links.new(absorption.outputs["Volume"], gout.inputs["Volume"])
    material = _material_shell(key, group, tint)
    material["summit_ior"] = ior
    material["summit_min_thickness_m"] = min_thickness
    material["summit_geometry_note"] = "Use a closed solid mesh; never a zero-thickness plane."
    return material


def _build_water():
    key = "water"
    controls = [
        ("Ripple Scale (m)", "NodeSocketFloat", 0.055, 0.005, 1.0, "Small surface ripple size in metres."),
        ("Roughness", "NodeSocketFloat", 0.045, 0.0, 0.35, "Water surface roughness."),
        ("Ripple Strength", "NodeSocketFloat", 0.075, 0.0, 0.5, "Micro ripple normal strength."),
    ]
    group, gin, gout = _new_group(key, controls, volume_output=True)
    co = _physical_coordinates(group, gin, "Ripple Scale (m)")
    noise = _node(group, "ShaderNodeTexNoise", "Water Ripples", (-300, 250))
    noise.noise_dimensions = "3D"
    noise.inputs["Scale"].default_value = 1.2
    noise.inputs["Detail"].default_value = 4.0
    noise.inputs["Roughness"].default_value = 0.62
    noise.inputs["Distortion"].default_value = 0.18
    group.links.new(co, noise.inputs["Vector"])
    bump = _node(group, "ShaderNodeBump", "Ripple Normal", (250, -80))
    group.links.new(gin.outputs["Ripple Strength"], bump.inputs["Strength"])
    bump.inputs["Distance"].default_value = 0.006
    group.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    _principled(group, gout, color=(0.72, 0.90, 0.93, 1), roughness=gin.outputs["Roughness"], ior=1.333, transmission=1.0, normal=bump.outputs["Normal"])
    absorption = _node(group, "ShaderNodeVolumeAbsorption", "Water Depth Absorption", (550, -240))
    absorption.inputs["Color"].default_value = (0.13, 0.52, 0.62, 1)
    absorption.inputs["Density"].default_value = 0.16
    group.links.new(absorption.outputs["Volume"], gout.inputs["Volume"])
    material = _material_shell(key, group, (0.35, 0.66, 0.72, 1))
    material["summit_ior"] = 1.333
    material["summit_geometry_note"] = "Use a closed water volume with the surface at the modeled waterline."
    return material


def _build_emission():
    key = "emission"
    controls = [
        ("Temperature (K)", "NodeSocketFloat", 3000.0, 1000.0, 12000.0, "Architectural light color temperature."),
        ("Strength", "NodeSocketFloat", 7.5, 0.0, 1000.0, "Visible diffuser emission strength; pair with a real light."),
        ("Diffuser Roughness", "NodeSocketFloat", 0.32, 0.0, 1.0, "Diffuser surface roughness."),
    ]
    group, gin, gout = _new_group(key, controls)
    blackbody = _node(group, "ShaderNodeBlackbody", "3000K Blackbody", (-240, 180))
    blackbody.inputs["Temperature"].default_value = 3000.0
    group.links.new(gin.outputs["Temperature (K)"], blackbody.inputs["Temperature"])
    _principled(group, gout, color=(0.75, 0.60, 0.38, 1), roughness=gin.outputs["Diffuser Roughness"], emission_color=blackbody.outputs["Color"], emission_strength=gin.outputs["Strength"])
    material = _material_shell(key, group, (1.0, 0.68, 0.36, 1))
    material["summit_temperature_k"] = 3000
    material["summit_lighting_note"] = "Visible diffuser only; pair with an Area/Point light for illumination."
    return material


def _build_mirror():
    key = "mirror"
    controls = [
        ("Silver Tint", "NodeSocketColor", (0.93, 0.95, 0.97, 1), None, None, "Mirror reflection tint."),
        ("Roughness", "NodeSocketFloat", 0.012, 0.0, 0.25, "Mirror polish."),
    ]
    group, gin, gout = _new_group(key, controls)
    _principled(group, gout, color=gin.outputs["Silver Tint"], roughness=gin.outputs["Roughness"], metallic=1.0)
    material = _material_shell(key, group, (0.85, 0.88, 0.9, 1))
    material["summit_geometry_note"] = "Place on a flat backing plane; reflection is front-face visible."
    return material


def build_materials() -> dict[str, bpy.types.Material]:
    """Create or reuse the stable Summit Estate material palette.

    Existing materials from this library version are returned untouched, so
    repeated calls preserve downstream overrides and never create `.001`
    duplicates. Delete a material (or bump ``LIBRARY_VERSION``) to rebuild it.
    """
    existing = {}
    for key in DISPLAY_NAMES:
        material = bpy.data.materials.get(MATERIAL_PREFIX + DISPLAY_NAMES[key])
        if material is not None and material.get("summit_library_version") == LIBRARY_VERSION:
            existing[key] = material
    if len(existing) == len(DISPLAY_NAMES):
        return existing

    built = dict(existing)
    builders = {
        "stone": lambda: _build_stone("stone"),
        "marble": lambda: _build_marble(
            "marble", (0.78, 0.73, 0.64, 1), (0.025, 0.022, 0.020, 1),
            (0.48, 0.43, 0.36, 1), 0.17, 0.72, 0.075,
        ),
        "dark_marble": lambda: _build_marble(
            "dark_marble", (0.014, 0.008, 0.005, 1), (0.32, 0.15, 0.05, 1),
            (0.060, 0.028, 0.012, 1), 0.20, 0.58, 0.034,
        ),
        "walnut": lambda: _build_wood(
            "walnut", (0.27, 0.105, 0.035, 1), (0.055, 0.016, 0.006, 1), 0.30, 0.006,
        ),
        "oak": lambda: _build_wood(
            "oak", (0.50, 0.30, 0.13, 1), (0.19, 0.075, 0.020, 1), 0.34, 0.0075,
        ),
        "black": lambda: _build_simple("black", (0.009, 0.010, 0.011, 1), 0.27, noise_scale=0.012, bump_strength=0.035),
        "bronze": lambda: _build_metal("bronze", (0.42, 0.20, 0.065, 1), 0.25, 0.0012),
        "glass": lambda: _build_glass("glass", (0.82, 0.96, 0.94, 1), 0.025, 1.45, 0.045, 0.006),
        "cream": lambda: _build_woven("cream", (0.66, 0.58, 0.47, 1), (0.43, 0.36, 0.29, 1), 0.62, 0.0022),
        "taupe": lambda: _build_woven("taupe", (0.34, 0.28, 0.22, 1), (0.20, 0.16, 0.13, 1), 0.65, 0.0020),
        "charcoal": lambda: _build_woven("charcoal", (0.075, 0.068, 0.061, 1), (0.025, 0.023, 0.022, 1), 0.69, 0.0024),
        "leather": _build_leather,
        "rubber": _build_rubber,
        "acoustic": lambda: _build_woven("acoustic", (0.035, 0.038, 0.040, 1), (0.012, 0.014, 0.016, 1), 0.83, 0.0032, 0.28),
        "ceramic": lambda: _build_simple("ceramic", (0.82, 0.78, 0.69, 1), 0.14, coat=0.18, noise_scale=0.018, bump_strength=0.018),
        "water": _build_water,
        "foliage": lambda: _build_simple("foliage", (0.055, 0.19, 0.045, 1), 0.52, subsurface=0.075, noise_scale=0.045, bump_strength=0.10),
        "soil": lambda: _build_simple("soil", (0.055, 0.025, 0.010, 1), 0.88, noise_scale=0.022, bump_strength=0.34),
        "emission": _build_emission,
        "mirror": _build_mirror,
        "plaster": lambda: _build_simple("plaster", (0.72, 0.67, 0.58, 1), 0.68, noise_scale=0.018, bump_strength=0.07),
        "carpet": lambda: _build_woven("carpet", (0.25, 0.21, 0.18, 1), (0.12, 0.10, 0.085, 1), 0.82, 0.0055, 0.42),
        "stainless": lambda: _build_metal("stainless", (0.56, 0.58, 0.60, 1), 0.28, 0.0008),
    }
    book_specs = [
        ((0.25, 0.025, 0.018, 1), 0.58),
        ((0.42, 0.18, 0.025, 1), 0.62),
        ((0.025, 0.16, 0.075, 1), 0.60),
        ((0.060, 0.085, 0.12, 1), 0.57),
        ((0.55, 0.44, 0.27, 1), 0.64),
        ((0.20, 0.095, 0.035, 1), 0.59),
    ]
    for index, (color, roughness) in enumerate(book_specs):
        key = f"book_{index}"
        builders[key] = lambda key=key, color=color, roughness=roughness: _build_simple(
            key, color, roughness, noise_scale=0.0018, bump_strength=0.09
        )
    for key in DISPLAY_NAMES:
        if key not in built:
            built[key] = builders[key]()
    return built


def _parse_args(argv):
    parser = argparse.ArgumentParser(description="Build the Summit material library.")
    parser.add_argument("--save-library", type=Path, help="Save a standalone .blend material library.")
    return parser.parse_args(argv)


def _main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    args = _parse_args(argv)
    materials = build_materials()
    print(f"Built {len(materials)} Summit Estate materials")
    if args.save_library:
        destination = args.save_library.expanduser().resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(destination), check_existing=False)
        print(f"Saved material library: {destination}")


if __name__ == "__main__":
    _main()
