# Summit Estate material report

## Scope and reference response

`scripts/materials.py` builds 29 Blender 4.5 materials through the stable
`build_materials() -> dict[str, Material]` API. The palette is authored for
Cycles/Eevee PBR shading and retains one clearly named `Surface Controls` node
group per material.

Three supplied views govern the signature finishes:

- `reference/1F/villa_v1_1F_bathroom.png` establishes a polished, high-contrast
  black/white breccia. `marble` combines a broad mineral cloud, two separately
  scaled warped vein fields, and a Voronoi hairline fracture network. The
  result is directional and layered rather than a flat noise color.
- `reference/B1/villa_v1_b1_library_2.png` establishes warm walnut, fine long
  grain, herringbone flooring, satin bronze, cognac leather, and visible woven
  upholstery. `walnut` and `oak` use elongated object-space coordinates so the
  grain runs along local +Y; furniture/floor builders can rotate it with the
  exposed `Grain Rotation (rad)` control.
- `reference/3F/villa_v1_3F_bathroom.png` establishes restrained warm-grey
  polished stone, dark walnut vanity fronts, clear glass, satin metal, ceramic,
  and dense neutral textiles. `stone` supplies varied limestone/grey-stone
  roughness and pore relief; `glass` uses physical transmission and volume
  absorption rather than an alpha-only transparency shortcut.

The reference PNGs remain visual references only. They are not embedded,
sampled, projected, or used as textures.

## Palette contract

The returned mapping contains these exact keys:

`stone`, `marble`, `dark_marble`, `walnut`, `oak`, `black`, `bronze`, `glass`,
`cream`, `taupe`, `charcoal`, `leather`, `rubber`, `acoustic`, `ceramic`,
`water`, `foliage`, `soil`, `emission`, `book_0` through `book_5`, `mirror`,
`plaster`, `carpet`, and `stainless`.

Each datablock has a `SUMMIT ::` display name, a `summit_key` custom property,
and a fake user so it remains available in `blender/summit_materials.blend`
when no object currently uses it. Calling `build_materials()` repeatedly in
the same file returns the same datablocks and does not create `.001` copies.

## Physical scale and orientation

Blender scene units are metres. Texture node groups use the shader **Object**
coordinate because it preserves local material orientation and, with applied
object scale, makes one coordinate unit equal one metre. Apply object scale
(`Ctrl+A > Scale`) before final material tuning. Generated coordinates were
avoided because they normalize every object to 0–1 and would make grain,
weave, pores, and veins change size from object to object.

Editable scale sockets include `Feature Scale (m)`, `Grain Width (m)`,
`Weave Scale (m)`, `Fleck Scale (m)`, `Brushing Scale (m)`, and
`Ripple Scale (m)`. Rotations are radians around local Z. Wood grain is
authored lengthwise along local +Y. For a floorboard modeled along local X,
set `Grain Rotation (rad)` to approximately 1.5708. Rotate alternate
herringbone boards with their objects or use opposite signed group rotations.

Representative defaults:

| Material family | Default physical feature |
|---|---:|
| Pale/breccia marble | 0.58–0.72 m major vein field |
| Limestone | 0.32 m mineral mottling |
| Walnut/oak | 6–7.5 mm fine grain spacing |
| Upholstery/acoustic textile | 2–3.2 mm thread repeat |
| Dense carpet | 5.5 mm repeat |
| Gym rubber | 7 mm aggregate field |
| Satin metal | 0.8–1.2 mm brushing field |
| Water | 55 mm micro-ripple field |

## PBR behavior

- Stone families vary roughness independently from color. Marble has a light
  polish coat and restrained vein relief; limestone has fine pore relief.
- Walnut and oak combine broad drift, warped growth bands, and fine pores.
  Relief stays below 1 mm so the shader reads as finished timber rather than
  carved grooves.
- Cream, taupe, charcoal, acoustic, and carpet cross two directional wave
  fields to form an over/under weave, then use the result for color, sheen,
  and micro-normal variation.
- Rubber uses sparse brighter EPDM-like flecks with millimetre relief.
- Bronze and stainless use metallic response, directional anisotropy,
  variable satin roughness, and fine brushing normals.
- Glass uses IOR 1.45 and thickness absorption. It should be assigned to a
  closed mesh at least 6 mm thick; facade panes are typically 10–12 mm.
  Water uses IOR 1.333 and must also be a closed volume.
- `emission` is driven by a Blackbody node set to 3000 K. It represents the
  visible diffuser and should be paired with an actual light object for stable
  architectural illumination and sampling.

## Validation

`tests/test_materials.py` runs inside Blender, builds the palette twice, and
checks exact keys, stable datablock reuse, linked PBR surfaces, fake-user
persistence, signature procedural node families, editable physical controls,
glass/water IOR metadata, and the 3000 K Blackbody source.

To test, rebuild, and save the standalone material-only library:

```bash
tools/blender-4.5.3-linux-x64/blender --background --factory-startup \
  --python tests/test_materials.py -- \
  --save-library blender/summit_materials.blend
```

To compile the signature shaders in a CPU-only Cycles smoke render:

```bash
tools/blender-4.5.3-linux-x64/blender --background \
  blender/summit_materials.blend --python tests/test_materials.py -- \
  --render-smoke /tmp/summit_materials_cpu_smoke.png
```
