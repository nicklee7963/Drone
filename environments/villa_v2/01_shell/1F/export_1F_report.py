"""Export a source/model SVG comparison and the deliverable audit report.

Run inside Blender after rendering and validating the saved scene.
"""
import bpy
import base64
import html
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
SX,SY = 35.6/954,22.8/648


def main():
    audit = json.loads((OUT/'1F_shell_validation.json').read_text())
    assert audit['failed'] == 0, 'Resolve geometry validation before exporting report'
    objects = [o for o in bpy.context.scene.objects if o.type == 'MESH' and o.get('shell_geometry')]
    renders = {}
    for name in ['1F_shell_top.png','1F_shell_perspective_front.png',
                 '1F_shell_perspective_corner.png','1F_shell_greatroom_validation.png']:
        path = OUT/name
        assert path.exists() and path.stat().st_size > 10000
        img = bpy.data.images.load(str(path),check_existing=False)
        renders[name] = list(img.size)
        assert min(img.size) >= 1300
        bpy.data.images.remove(img)
    audit['validation_images'] = renders
    (OUT/'1F_shell_validation.json').write_text(json.dumps(audit,indent=2))

    # Native vector diagnostic: the unmodified source is embedded underneath
    # actual projected mesh faces. It contains no extra scene geometry.
    source = base64.b64encode((OUT/'1F.png').read_bytes()).decode('ascii')
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="1448" height="1086" viewBox="0 0 1448 1086">',
        '<title>1F actual mesh footprints over calibrated source drawing</title>',
        '<rect width="1448" height="1086" fill="white"/>',
        f'<image href="data:image/png;base64,{source}" width="1448" height="1086" opacity="0.62"/>']
    styles = {'floor':('#67aa79',.10,.55),'terrace':('#b6b7a1',.13,.65),
        'wall':('#c22645',.40,.6),'column':('#86335f',.50,.6),
        'glass':('#007fcd',.9,1.8),'stair':('#04796c',.28,.7)}
    for kind in styles:
        color,opacity,width = styles[kind]
        for obj in [o for o in objects if o.get('element_type') == kind]:
            svg.append(f'<g fill="{color}" fill-opacity="{opacity}" stroke="{color}" stroke-width="{width}"><title>{html.escape(obj.name)}</title>')
            for face in obj.data.polygons:
                if face.normal.z < .9:
                    continue
                vs = [obj.matrix_world @ obj.data.vertices[i].co for i in face.vertices]
                points = ' '.join(f'{v.x/SX+585:.2f},{513-v.y/SY:.2f}' for v in vs)
                svg.append(f'<polygon points="{points}"/>')
            svg.append('</g>')
    for door in audit['door_paths']:
        a,b = door['start'],door['end']
        svg.append(f'<path d="M{a[0]/SX+585},{513-a[1]/SY} L{b[0]/SX+585},{513-b[1]/SY}" fill="none" stroke="#e27d00" stroke-width="1.8"><title>{door["name"]}</title></path>')
    svg += ['<rect x="397" y="282" width="376" height="293" fill="none" stroke="#772eb3" stroke-width="2" stroke-dasharray="8 5"/>',
        '<rect x="1105" y="127" width="336" height="580" fill="white" stroke="#555"/>']
    legend = ['MODEL / SOURCE CHECK','Actual mesh projection over 1F.png','Red: solid walls','Purple squares: columns','Blue: separate glass','Teal: physical stair treads','Green outline: enclosed floor','Orange: checked opening paths','Purple dashed: future Great Room void','',
        'CALIBRATION','X 108..1062 px = 35.600 m','Y 189..837 px = 22.800 m','X scale: 0.0373166 m/pixel','Y scale: 0.0351852 m/pixel','',
        'MANUAL REVIEW','Stair B: provisional southbound ascent','Storage: inferred sliding-glass access','Storey elevations: provisional +/-3.2 m','Temporary door gaps are full height','Outline exceeds dimension markers','Terrace/porch outline inferred from strokes']
    for i,line in enumerate(legend):
        svg.append(f'<text x="1120" y="{153+i*23}" font-family="sans-serif" font-size="{16 if i==0 else 13}" fill="#222">{html.escape(line)}</text>')
    svg.append('</svg>')
    (OUT/'1F_shell_source_overlay.svg').write_text('\n'.join(svg))

    def bounds(obs):
        vs = [o.matrix_world @ v.co for o in obs for v in o.data.vertices]
        lo = [min(v[k] for v in vs) for k in range(3)]
        hi = [max(v[k] for v in vs) for k in range(3)]
        return lo,hi,[b-a for a,b in zip(lo,hi)]
    main_floor = bpy.data.objects['1F_Floor_Main']
    _,_,main_dims = bounds([main_floor])
    lo,hi,dim = bounds(objects)
    def fmt(values):
        return ', '.join(f'{v:.6f}' for v in values)
    stair_rows = []
    for name in ['1F_StairA_DownToB1','1F_StairB_UpTo2F']:
        o = bpy.data.objects[name]
        stair_rows.append(f'| {name} | {o.dimensions.x:.3f} m | {o["run_m"]:.3f} m | {o["landing_depth_m"]:.3f} m | {o["terminal_elevation_m"]:+.3f} m | {o["direction"]} |')
    glass_lines = '\n'.join(f'- `{o.name}` — source line `{o["source_pixel_line"]}`.' for o in objects if o.get('element_type') == 'glass')
    removed = json.loads(bpy.context.scene['wall_fix_removed_objects'])
    changed = json.loads(bpy.context.scene['wall_fix_changed_objects'])
    changed_lines = '\n'.join(f'- `{name}`' for name in changed)
    checklist = [
        'Blender scene uses meters (Metric, length Meters, unit scale 1).',
        'Reference image calibrated using the 35.6 m width and 22.8 m depth dimension markers; packed into the .blend.',
        'Main first-floor footprint modeled as a stepped slab, with both stair apertures.',
        'Exterior walls modeled from significant black bands.',
        'Interior walls modeled from significant black bands.',
        'Glass separated from walls (25 independent thin solid objects).',
        'Main Terrace modeled.', 'Left Outdoor Terrace modeled.', 'Dining Terrace modeled.', 'Entry Porch modeled.',
        'Garage modeled as an open shell.',
        'Grand Entry Foyer footprint, entrance gap, sidelights and circulation retained.',
        'Great Room modeled.', 'Great Room remains double height.',
        'OPEN TO ABOVE area is not covered; future-floor exclusion helper exists.',
        'Kitchen & Dining remains open within the traced shell.',
        'Guest Suite 1 partitions exist.', 'En-suite 1 partitions exist.',
        'Storage exists; inferred operable-glazing access is disclosed below.',
        'Utility exists.', 'Wine Cellar exists.', 'Guest Suite 2 partitions exist.',
        'En-suite 2 partitions exist.', 'Powder Room exists.',
        'Pantry / Prep Kitchen exists.', 'Mudroom / Shoe Gallery exists.',
        'Stair A physically descends south toward its provisional B1 landing.',
        'Stair B physically ascends south toward its provisional 2F landing; direction uncertainty disclosed.',
        'Stair openings exist; actual floor rays miss both shaft interiors.',
        'Great Room usable interior contains zero columns, piers, wall stubs, or remnants.',
        'Four former Great Room internal piers removed; 12 exterior/perimeter structural piers retained.',
        'Exterior walls measure 0.280 m; interior partitions 0.180 m; stairwell walls 0.220 m.',
        'Exterior faces, partition centerlines, and stair-void faces retain their specified alignment.',
        'No non-column wall geometry exceeds 0.300 m.',
        'Visible door openings preserved; 22 sampled opening/circulation paths unblocked.',
        'No furniture added.', 'No decorative objects added.',
        'No accidental complete duplicate meshes; no detected intersecting solid volumes.',
        'Normals checked: all structural meshes closed, positive signed volume, no degenerate faces.',
        'Mesh transforms checked: all scales 1,1,1; origins at individual mesh bounds centers.',
        'Top verification image exported and inspected.',
        'Front verification image exported and inspected.',
        'Corner verification image exported and inspected.',
        'Great Room validation image exported and inspected.',
    ]
    checks_md = '\n'.join('- [x] '+item for item in checklist)
    report = f'''# First-floor shell implementation report

Created: `{OUT/'1F_shell.blend'}` using Blender {bpy.app.version_string}.

The deliverable contains the first-floor shell and its two inter-floor stair continuations only. There are no other-floor room/slab models, ceilings, furniture, fixtures, textures, or landscaping.

## Files and inspection

- [Blender scene](1F_shell.blend)
- [Pre-correction backup](1F_shell_before_wall_fix.blend) — retained unchanged.
- [Top orthographic render](1F_shell_top.png) — 2400 × 1700; north is up.
- [Front perspective render](1F_shell_perspective_front.png) — 1800 × 1300.
- [Elevated corner render](1F_shell_perspective_corner.png) — 1800 × 1300.
- [Great Room validation render](1F_shell_greatroom_validation.png) — 1800 × 1300.
- [Actual mesh/source overlay](1F_shell_source_overlay.svg) — open in a browser for a zoomable comparison with object names on hover.
- [Reproducible generator](build_1F_shell.py), [geometry verifier](validate_1F_shell.py), [report exporter](export_1F_report.py).
- [Machine-readable audit](1F_shell_validation.json).
- [Backup invariant comparison](1F_wall_fix_comparison.json).

## Scale and measured bounds

The source is 1448 × 1086 pixels. Horizontal dimension ticks at X=108 and X=1062 calibrate to 35.6 m. Vertical ticks at Y=189 and Y=837 calibrate to 22.8 m. These yield X={SX:.9f} m/pixel and Y={SY:.9f} m/pixel. The reference therefore has a disclosed approximately 5.7% aspect correction; a uniform scale cannot satisfy both drawn dimensions. Dimension-marker center (585,513) maps to world (0,0). Source north maps to +Y.

| Geometry measured | X width | Y depth |
| --- | ---: | ---: |
| Dimension-marker span | 35.600 m | 22.800 m |
| Enclosed first-floor slab, including structural projections | {main_dims[0]:.3f} m | {main_dims[1]:.3f} m |
| All architectural meshes, including terraces and Entry Porch | {dim[0]:.3f} m | {dim[1]:.3f} m |

Full mesh bounds: minimum **({fmt(lo)}) m**, maximum **({fmt(hi)}) m**. Reference, cameras, lights and helpers are excluded. Z reaches -3.600 m because of Stair A's underside; the lower walking surface is -3.200 m.

**The modeled envelope is deliberately not forced to 35.6 × 22.8 m.** Black outer strokes extend to source X=80..1089; rear terrace and porch extend to Y=159..868. They exceed the dimension-marker extent. The sub-dimension proportions and printed room areas also disagree with the raster; as requested, room areas were not used to distort the trace. Confirm authoritative dimensions before aligning subsequent floors.

## Construction assumptions

- Wall tops: **Z=3.200 m**, all standard walls and piers; no global ceiling.
- Slabs: **0.200 m**, from Z=-0.200 to 0.000. Terrace and porch top surfaces also Z=0; no site elevations are supplied.
- Wall thickness is explicit metric geometry: **0.280 m exterior**, **0.180 m interior partition**, and **0.220 m stairwell**. Exterior faces remain at their pre-fix coordinates; partition centerlines remain unchanged; stair-void faces remain unchanged. Long-axis endpoints remain fixed, preserving door centers and opening widths.
- Four small internal Great Room piers were removed. The 12 remaining façade, terrace, entry, corner, and perimeter piers retain their source rectangles. Terrace pier height remains provisionally 3.2 m.
- Door/circulation gaps are temporarily **full wall height (3.2 m)**. Door heads and panels have not been invented from a plan with no elevation information. Visible swing arcs are not geometry. Source door widths are retained, including narrow approximately 0.75–0.85 m openings; the main entry is approximately 2.87 m wide.
- Glass: **0.020 m thick, 3.200 m high**, from Z=0 to the assumed wall top, matching the source note's floor-to-ceiling glazing; placeholder blue transparent material. Glazing remains separate for later collision/material decisions.
- Structural wall joints are rebuilt as clean, closed solids and trimmed into non-overlapping volumes. Components meet only at intentional construction interfaces. No thin intersection remnants or non-column wall bands over 0.30 m remain.

## Great Room and wall correction

The usable Great Room footprint was tested against actual mesh interiors at Z=1.2 m. It contains only the first-floor slab: **zero columns, zero piers, zero freestanding walls, and zero wall stubs**. The north glazing remains separate and unchanged, and the space remains open above the 3.2 m first-floor wall height.

Removed objects ({len(removed)}):

{chr(10).join(f'- `{name}`' for name in removed)}

All {len(changed)} generated wall objects had their cross-sectional thickness rebuilt while preserving the category-specific alignment rule:

{changed_lines}

Final measured wall bands: exterior **{audit['wall_thicknesses_m']['exterior'][0]:.3f} m**, interior partitions **{audit['wall_thicknesses_m']['interior'][0]:.3f} m**, stairwell walls **{audit['wall_thicknesses_m']['stairwell'][0]:.3f} m**, and glass **0.020 m**. Remaining non-column walls over 0.30 m: **none**.

## Stairs and future-level interfaces

Both straight flights have **19 risers × 0.168421 m**, **18 treads × 0.270 m**, and **4.860 m horizontal run**. Undersides are sloped with a 0.400 m vertical profile offset; the minimum web is above 0.23 m. These are low-density closed solids, not overlapping step boxes.

| Stair | Clear width | Flight run | Terminal landing depth | Terminal walking Z | Direction |
| --- | ---: | ---: | ---: | ---: | --- |
{chr(10).join(stair_rows)}

Stair A occupies source rectangle (388,650)..(464,821), world X=-7.351363..-4.515304 m, Y=-10.837037..-4.820370 m. It starts at the north corridor at Z=0, descends south, and has a side connection toward +X from its south lower landing. Walls are not extended through that basement connection. Only the stair/landing is modeled below 1F.

Stair B occupies source rectangle (708,652)..(771,821), world X=4.589937..6.940881 m, Y=-10.837037..-4.890741 m. It starts at the north corridor at Z=0 and ascends south. Its upper landing meets Z=3.2; the future 2F connection is toward +X, above the current first-floor wall top. No 2F slab was added.

**Stair B direction requires manual confirmation.** The source symbol contains arrowheads in both directions. The north end is the clear accessible mouth, so southbound ascent is the provisional interpretation raised during modeling. The drawn tread cluster is too short to represent a complete 3.2 m flight; treads have been redistributed within the same shaft to obtain realistic rise/run. No shaft or room was relocated.

`1F_Connection_B1` and `1F_Connection_2F` store the terminal connection points. `1F_Opening_StairA`, `1F_Opening_StairB`, and `VOID_GreatRoom_OpenToAbove` are hidden, non-rendering helpers. The Great Room helper follows source rectangle (397,282)..(773,575); its upper-floor exclusion must be reconciled with an authoritative 2F plan later. There is no roof or slab over this region.

## Glazing interpretation

Blue-gray/white narrow lines were interpreted as glass at the garage north/west, Storage west/north, the two north terrace-entry recesses, the Great Room's stepped north edge, kitchen/pantry north, pantry/mudroom east, both guest-suite and en-suite external edges, stair south ends, and the main-entry sidelights.

**Storage access is inferred:** its north boundary has glazing but no clear door arc. The fixed section follows source X=117..151 at Y=549.5; X=151..183 remains an approximately 1.194 m clear sliding-glass access. This is the only deliberately inferred operable bay. Guest Suite 1's shown north doorway opens through the Wine Cellar; that unusual circulation has been retained.

All 25 glazing objects and their original source endpoints:

{glass_lines}

## Verification and limits

**{audit['passed']} geometry checks passed, {audit['failed']} failed**, including saved-file validation. The scene has **{audit['mesh_objects']} architectural mesh objects**, approximately **{audit['triangles']} triangles** after triangulation. All structural meshes are closed, have positive signed volume, unit object scales and no degenerate faces. No complete duplicate meshes or intersecting structural volumes were detected. The overlap audit tests actual mesh interiors across orthogonal arrangement cells and the stair bounds; intentional touching joints are allowed.

The actual floor mesh is absent in both stair apertures. Physical tread samples confirm descending A and ascending B, with at least 2.1 m vertical clearance over sampled tread centers in this shell. Stair objects and apertures were not regenerated from changed parameters. The Great Room is clear internally and unobstructed above the walls. Twenty-two doorway/circulation line samples at Z=1.2 m are clear. A 0.10 m grid with center plus four radius samples connects the foyer to every room using an approximate 0.40 m UAV diameter. These are geometry checks; no Gazebo, ROS 2, PX4, dynamics or VIO testing was performed.

All four PNGs were produced from Blender geometry and visually inspected. The top render preserves full-height opening gaps and shows the actual stair geometry. The dedicated Great Room view exposes the cleared floor and retained north glazing. The SVG overlay provides an additional dimension-calibrated trace comparison. Stair A is visible below the shell in perspective because no B1 walls have been modeled.

Manual review priorities remain: source scale/dimension inconsistency; Stair B direction and both future landing elevations; Storage's sliding access; Guest Suite 1's access through Wine Cellar; full-height opening placeholders; retained perimeter/terrace pier sizes; and terrace/porch boundary strokes. The four gray piers previously traced inside the Great Room are deliberately omitted per the wall-fix requirement. The approach steps, outer front apron and narrow exterior perimeter outlines were treated as site/landscape graphics beyond the requested four exterior slabs and are not modeled.

## Required checklist

{checks_md}

## Rebuild and inspect

Run from this directory with Blender 4.5.3 LTS or a compatible bpy version:

```bash
blender -b --factory-startup --python-exit-code 1 --python build_1F_shell.py
blender -b 1F_shell.blend --python-exit-code 1 --python validate_1F_shell.py
blender -b 1F_shell.blend --python-exit-code 1 --python export_1F_report.py
```

To iterate geometry without rendering, append `-- --skip-renders` to the build command. Source rectangles and calibration constants are grouped near the top of the generator. The reference image is packed, locked and hidden under `REFERENCE_1F`; reveal it and hide shell collections for a direct top-view check. Helpers are individually hidden under `1F_OPENINGS`; reveal them for future level alignment. Every renderable mesh has `shell_geometry=True` and a separate `element_type` property for later export filtering.
'''
    (OUT/'1F_shell_report.md').write_text(report)
    print('REPORT AND SOURCE OVERLAY EXPORTED',renders)


if __name__ == '__main__':
    main()
