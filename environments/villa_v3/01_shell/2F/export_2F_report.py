"""Export the 2F source overlay, alignment projection data, and final report."""
import bpy
import base64
import html
import json
from pathlib import Path

OUT=Path(__file__).resolve().parent
ONE_F=OUT.parent/'1F'
SX,SY=35.6/954.0,22.8/648.0
CX,CY=585.0,513.0


def projected_faces(objects):
    records=[]
    for obj in objects:
        kind=obj.get('element_type','unknown')
        for face in obj.data.polygons:
            normal=obj.matrix_world.to_3x3() @ face.normal
            if normal.z < .9:
                continue
            points=[obj.matrix_world @ obj.data.vertices[i].co for i in face.vertices]
            records.append({'object':obj.name,'kind':kind,'xy_m':[[p.x,p.y] for p in points]})
    return records


def main():
    audit=json.loads((OUT/'2F_shell_validation.json').read_text())
    assert audit['failed']==0
    objects=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.get('shell_geometry')]
    images={}
    for name in ('2F_shell_top.png','2F_shell_perspective_front.png','2F_shell_perspective_corner.png',
                 '2F_open_to_below_validation.png','2F_family_terrace_validation.png',
                 '2F_wall_topology_validation.png'):
        path=OUT/name
        assert path.exists() and path.stat().st_size>10000, name
        image=bpy.data.images.load(str(path),check_existing=False)
        images[name]=list(image.size); bpy.data.images.remove(image)
    audit['validation_images']=images

    source=base64.b64encode((OUT/'2F.png').read_bytes()).decode('ascii')
    svg=['<svg xmlns="http://www.w3.org/2000/svg" width="1448" height="1086" viewBox="0 0 1448 1086">',
         '<title>2F actual mesh footprints over calibrated source drawing</title>',
         '<rect width="1448" height="1086" fill="white"/>',
         f'<image href="data:image/png;base64,{source}" width="1448" height="1086" opacity="0.62"/>']
    styles={'floor':('#4caa62',.12,.7),'bridge_floor':('#00a36c',.22,1.0),'terrace':('#b2a26b',.15,.8),
            'wall':('#d12645',.42,.7),'column':('#85315e',.54,.8),'glass':('#007fc9',.92,2.0),
            'railing_glass':('#00a9cf',.82,2.2),'railing_toprail':('#172b35',.75,1.6),
            'stair':('#00796b',.30,.8)}
    for kind,(color,opacity,width) in styles.items():
        for obj in [o for o in objects if o.get('element_type')==kind]:
            svg.append(f'<g fill="{color}" fill-opacity="{opacity}" stroke="{color}" stroke-width="{width}"><title>{html.escape(obj.name)}</title>')
            for face in obj.data.polygons:
                normal=obj.matrix_world.to_3x3() @ face.normal
                if normal.z<.9: continue
                pts=[obj.matrix_world @ obj.data.vertices[i].co for i in face.vertices]
                pixels=' '.join(f'{p.x/SX+CX:.2f},{CY-p.y/SY:.2f}' for p in pts)
                svg.append(f'<polygon points="{pixels}"/>')
            svg.append('</g>')
    ox0,oy1=(-5.29895178197065,3.6944444444444446)
    # Draw source-space validation rectangles directly for unambiguous review.
    svg += [
      '<rect x="443" y="408" width="271" height="198" fill="none" stroke="#742fb4" stroke-width="3" stroke-dasharray="9 5"/>',
      '<rect x="708" y="652" width="63" height="169" fill="none" stroke="#f28300" stroke-width="3" stroke-dasharray="7 4"/>',
      '<rect x="1105" y="125" width="330" height="650" fill="white" stroke="#555"/>']
    legend=['2F MODEL / SOURCE CHECK','Actual mesh top faces over 2F.png','Red: solid walls','Purple: structural columns',
            'Blue: full-height glass','Cyan/dark: glass guards + top rails','Teal: physical 2F→3F stair','Green: main and bridge floor','Purple dashed: OPEN TO BELOW',
            'Orange dashed: exact 1F stair aperture','','STACK CALIBRATION','Origin pixel 585,513 → XY 0,0',
            'X scale 0.0373166 m/pixel','Y scale 0.0351852 m/pixel','Stair XY max error 0.000000 m','','MANUAL REVIEW',
            '2F void extends 1.091 m south of 1F helper','2F down-arrow conflicts with 1F stair direction',
            'Door gaps are temporary full-height openings','Cyan/dark geometry protects exposed edges',
            'Family Terrace mesh top area: 27.000 m2']
    for i,line in enumerate(legend):
        svg.append(f'<text x="1120" y="{150+i*25}" font-family="sans-serif" font-size="{16 if i==0 else 13}" fill="#222">{html.escape(line)}</text>')
    svg.append('</svg>')
    (OUT/'2F_shell_source_overlay.svg').write_text('\n'.join(svg))

    projection={'calibration':{'origin_pixel':[CX,CY],'meters_per_pixel':[SX,SY]},
                '2F':projected_faces(objects),'1F':[]}
    with bpy.data.libraries.load(str(ONE_F/'1F_shell.blend'),link=False) as (data_from,data_to):
        data_to.objects=list(data_from.objects)
    temp=bpy.data.collections.new('__TEMP_1F_ALIGNMENT__')
    bpy.context.scene.collection.children.link(temp)
    for obj in [o for o in data_to.objects if o]:
        temp.objects.link(obj)
    bpy.context.view_layer.update()
    one_objects=[o for o in data_to.objects if o and o.type=='MESH' and o.get('shell_geometry')]
    projection['1F']=projected_faces(one_objects)
    (OUT/'2F_alignment_projection.json').write_text(json.dumps(projection))
    for obj in data_to.objects:
        if obj: bpy.data.objects.remove(obj,do_unlink=True)
    bpy.data.collections.remove(temp)

    audit['alignment']['alignment_projection_faces']={'1F':len(projection['1F']),'2F':len(projection['2F'])}
    (OUT/'2F_shell_validation.json').write_text(json.dumps(audit,indent=2))
    stair=bpy.data.objects['2F_Stair_UpTo3F']
    align=audit['alignment']
    railing=audit['railing']; open_dims=audit['open_to_below_dimensions_m']
    bridge_dims=audit['bridge_dimensions_m']; stair_opening_dims=audit['stair_opening_dimensions_m']
    family=audit['family_terrace']; detailed=align['detailed_anchor_measurements_m']
    wall_audit=audit['wall_audit']; regression=audit['unrelated_geometry_regression']
    railing_objects='\n'.join(f'- `{name}`' for name in railing['glass_objects']+railing['toprail_objects'])
    dims=audit['bounds_m']['dimensions']; lo=audit['bounds_m']['min']; hi=audit['bounds_m']['max']
    thickness=audit['wall_thicknesses_m']
    checklist=[
      '2F_shell.blend exists and opens successfully.','Scene uses meters, unit scale 1, and local floor Z=0.',
      'The exact 1F XY transform is reused.','The exact 1F Stair B opening is removed from the 2F slab.',
      'The central OPEN TO BELOW contains no floor collision face.','The Bridge / Upper Gallery is a separate floor object.',
      'Family Terrace is a separate slab.','Exterior, interior, and stair walls use the 1F thickness style.',
      'Family Terrace is connected to lounge glazing and has 27.000 m2 usable top area.',
      'Family Terrace uses the approved 10.0m by 2.7m luxury proportion.',
      'Family Terrace exposed edges have separate 1.10 m glass guards.',
      'Floor-to-ceiling glass is separate and 0.020 m thick.','The 2F→3F stair is physical, watertight geometry.',
      'Glass guardrails protect all exposed OPEN TO BELOW edges without shrinking the void.',
      'Stair-side guardrails preserve the active flight and +X landing exit.',
      'No duplicate mesh or object names were found.','All architectural meshes are closed positive-volume solids.',
      'All 12 intentional doorways and both circulation openings remain open.',
      'Both accidental B-service wall gaps and all 11 audited wall/glass endpoint cracks are corrected.',
      'Every mesh outside the approved wall/glass correction set matches the pre-correction backup.',
      'All architectural object scales are 1,1,1.','No ceiling, furniture, fixtures, decoration, landscaping, B1, 1F room model, or 3F room model was added.',
      'Top, front, corner, source-overlay, and 1F/2F alignment views were generated.'
    ]
    report=f'''# Second-floor shell implementation report

Created `{OUT/'2F_shell.blend'}` with Blender {bpy.app.version_string}. This is an independent second-floor shell whose finished floor is local `Z=0`; it contains no appended 1F scene and no 3F room/slab model.

## Deliverables

- [2F Blender shell](2F_shell.blend)
- [Reproducible generator](build_2F_shell.py)
- [Validation script](validate_2F_shell.py)
- [Machine-readable validation](2F_shell_validation.json)
- [Validation log](validation_2F_shell.log)
- [Top orthographic render](2F_shell_top.png) — {images['2F_shell_top.png'][0]} × {images['2F_shell_top.png'][1]}
- [Front perspective render](2F_shell_perspective_front.png) — {images['2F_shell_perspective_front.png'][0]} × {images['2F_shell_perspective_front.png'][1]}
- [Elevated corner render](2F_shell_perspective_corner.png) — {images['2F_shell_perspective_corner.png'][0]} × {images['2F_shell_perspective_corner.png'][1]}
- [Open-to-below validation render](2F_open_to_below_validation.png) — {images['2F_open_to_below_validation.png'][0]} × {images['2F_open_to_below_validation.png'][1]}
- [Family Terrace validation render](2F_family_terrace_validation.png) — {images['2F_family_terrace_validation.png'][0]} × {images['2F_family_terrace_validation.png'][1]}
- [Wall topology validation](2F_wall_topology_validation.png) — {images['2F_wall_topology_validation.png'][0]} × {images['2F_wall_topology_validation.png'][1]}
- [Source/model overlay](2F_shell_source_overlay.svg)
- [Source/model overlay PNG](2F_shell_source_overlay.png)
- [1F/2F alignment view](2F_vs_1F_alignment.png)
- [Implementation plan](IMPLEMENTATION_PLAN.md)

## Measured scale and geometry

The shell reuses the validated 1F transform exactly: source `(585,513)` maps to world `(0,0)`, X is east, Y is north, `SX={SX:.9f} m/pixel`, and `SY={SY:.9f} m/pixel`. The explicit 35.6 m × 22.8 m anchors therefore occupy the same world axes as 1F. The revised 2F sheet's own drawn dimension-tick spans are raster-distorted under that transform ({align['source_2f_dimension_tick_span_under_stack_transform_m']['2f_tick_width_under_1f_transform_m']:.3f} m × {align['source_2f_dimension_tick_span_under_stack_transform_m']['2f_tick_depth_under_1f_transform_m']:.3f} m), so they were not used to shift or rescale the second floor independently.

All architectural mesh bounds are minimum **({lo[0]:.6f}, {lo[1]:.6f}, {lo[2]:.6f}) m**, maximum **({hi[0]:.6f}, {hi[1]:.6f}, {hi[2]:.6f}) m**, dimensions **{dims[0]:.3f} × {dims[1]:.3f} × {dims[2]:.3f} m**. The X/Y envelope includes the source-drawn façade and Family Terrace projections; the printed dimensions are architectural anchors rather than a forced outer bounding box.

The Family Terrace correction leaves all non-terrace architectural XY bounds unchanged within **{audit['non_terrace_xy_regression_error_m']:.6f} m**. The north envelope changes only because the former oversized terrace projection was replaced with the measured 27 m² platform and its low guardrail.

## Construction

- Standard wall height: **3.200 m**.
- Main, bridge, and terrace slab thickness: **0.200 m**, top at local `Z=0`.
- Exterior walls: **{thickness['exterior'][0]:.3f} m**.
- Interior partitions: **{thickness['interior'][0]:.3f} m**.
- Stair/special walls: **{thickness['stairwell'][0]:.3f} m**.
- Floor-to-ceiling glazing: **{audit['glass_thicknesses_m'][0]:.3f} m**, separate objects.
- Structural columns: **10** solid-black façade/junction blocks traced as separate objects. Light void-corner marks were not promoted to full-height columns.
- Door openings are full-height shell gaps because no elevation or door-head dimensions were supplied.

## Guardrail correction

The shell contains nine frameless-glass guard sections and nine thin top rails: six retained around OPEN TO BELOW/stairs and three added at the Family Terrace. Glass is **0.020 m thick** and **1.050 m high**; the top rail brings the exact finished guard height to **1.100 m**. Every part is closed mesh geometry with unit scale and is tagged for visual and collision export.

{railing_objects}

The four central panels follow every exposed OPEN TO BELOW edge and sit entirely on the floor side of the original opening boundary, preserving the void dimensions. Coverage ratios are north/south **{railing['void_edge_coverage']['north']*100:.1f}%** and east/west **{railing['void_edge_coverage']['east']*100:.1f}%** after 0.040 m end clearances. Remaining bridge clear widths are **{railing['bridge_clearance_m']['west_m']:.3f} m west**, **{railing['bridge_clearance_m']['east_m']:.3f} m east**, and **{railing['bridge_clearance_m']['south_m']:.3f} m south**.

The stair guard follows the west side of the full 1F→2F aperture and the east side of the active flight. The east panel stops before the south terminal landing, leaving the measured +X landing exit unobstructed. No rail crosses the north stair approach or south landing.

The source-drawn OPEN TO BELOW rectangle is `(443,408)..(714,606)`, world X `{(443-CX)*SX:.6f}..{(714-CX)*SX:.6f} m`, Y `{(CY-606)*SY:.6f}..{(CY-408)*SY:.6f} m`. A 5×5 ray grid found no floor face there. It overlaps **{align['open_to_below_overlap_fraction']*100:.1f}%** of its area with the provisional 1F Great Room helper and extends **{align['open_to_below_source_extension_m']['south']:.3f} m south** of that helper. The 2F source controls the actual opening; clipping it to the provisional 1F helper would add an unsupported collision ledge.

Measured OPEN TO BELOW clear dimensions remain **{open_dims[0]:.3f} × {open_dims[1]:.3f} m**. The Bridge / Upper Gallery traced envelope is **{bridge_dims['overall_world'][0]:.3f} × {bridge_dims['overall_world'][1]:.3f} m**; its west/east/south walkable strips retain the clear widths listed above.

The Bridge / Upper Gallery is `2F_Floor_Bridge`, split from the main slab without coplanar duplication. Its west, east, and south strips border the opening and remain open toward the Family Lounge as drawn. The new low guardrails follow only the drop edges; no full-height wall or ceiling was added.

## Stair and XY alignment

The 1F→2F aperture matches the measured 1F `1F_Opening_StairB` at X `{align['stair_opening_2f_xyxy_m'][0]:.6f}..{align['stair_opening_2f_xyxy_m'][2]:.6f} m`, Y `{align['stair_opening_2f_xyxy_m'][1]:.6f}..{align['stair_opening_2f_xyxy_m'][3]:.6f} m`. Maximum XY error is **{align['stair_xy_error_m']:.6f} m**. The already-modeled 1F flight is not duplicated in this independent 2F export; `2F_Opening_DownTo1F` and `2F_Connection_1F` define the interface.

The stair aperture remains **{stair_opening_dims[0]:.3f} × {stair_opening_dims[1]:.3f} m**. Stair center, width, and depth errors against the live 1F Blender geometry are **{detailed['stair_center_xy_error_m']:.6f} m**, **{detailed['stair_width_error_m']:.6f} m**, and **{detailed['stair_depth_error_m']:.6f} m**.

Shared main-envelope X anchors differ by at most **{max(align['major_anchor_errors_m'].values()):.3f} m** because the revised black strokes move two to three source pixels. Origin/centerline error is **0.000000 m**. The revised 2F north façade is 0.457 m north of the 1F main façade, the south guest wings are set back 1.337 m, and the central Art Gallery glazing extends 0.317 m south of the 1F Entry Porch outline; these are source-drawn façade offsets, not model recentering.

The exact non-terrace XY regression error is **{audit['non_terrace_xy_regression_error_m']:.6f} m**. The origin and stair aperture errors remain **{align['origin_xy_error_m']:.6f} m** and **{align['stair_xy_error_m']:.6f} m**. This compares fixed architectural geometry directly and does not mistake the intentionally corrected terrace projection for a global floor offset.

## Family Terrace correction

`2F_Terrace_Family` is centered on the Family Lounge glazing and measures **{family['terrace_width_m']:.3f} × {family['terrace_depth_m']:.3f} m**. Its width/depth ratio is **{family['terrace_width_depth_ratio']:.3f}**, and its actual generated-mesh top area is **{family['terrace_area_m2']:.3f} m²**. The slab is **{family['terrace_slab_thickness_m']:.3f} m** thick with its top at local `Z=0`.

The terrace meets `2F_Glass_005_FamilyLounge_North` at world Y **{family['lounge_glazing_center_y_m']:.6f} m**. Measured gap to the glazing centerline is **{family['gap_to_lounge_glazing_m']:.6f} m**; measured overlap with the indoor/bridge floor is **{family['indoor_floor_overlap_m2']:.8f} m²**. The terrace remains an exterior platform and does not overlap OPEN TO BELOW.

The revised 2.700 m furnishing depth and 3.703:1 proportion give the terrace enough depth for a future outdoor seating group and circulation while retaining the 27 m² schedule area. In shell form it now reads as a substantial outdoor extension of the Family Lounge rather than a narrow edge balcony, matching the approved luxury-villa design intent.

Separate 1.10 m guards protect the exposed north edge and the short west/east portions above the existing façade columns: `2F_Railing_FamilyTerrace_North`, `2F_Railing_FamilyTerrace_West`, and `2F_Railing_FamilyTerrace_East`, each with its own `_TopRail`. No full-height outer enclosure was added.

`2F_Stair_UpTo3F` occupies source `(607,676)..(684,817)`, width **{stair.dimensions.x:.3f} m**, rises north (+Y), has **{stair['risers']} risers × {stair['riser_m']:.6f} m**, **{stair['treads']} treads × {stair['tread_m']:.3f} m**, run **{stair['run_m']:.3f} m**, and a **{stair['landing_depth_m']:.3f} m** terminal landing at provisional `Z=+3.2 m`.

## Validation and manual review

## Wall topology audit

The audit classifies **{wall_audit['intentional_doorway_count']} intentional doorways** and **{wall_audit['circulation_opening_count']} intentional circulation openings**. Doorway widths range from **{wall_audit['minimum_doorway_width_m']:.6f} m** to **{wall_audit['maximum_doorway_width_m']:.6f} m**; the two wider Family Lounge side doors remain source-derived and unchanged.

The continuous `2F_Wall_Interior_011_BService_Corridor` now closes both audited **0.896 m** accidental gaps. The topology scan reports **{wall_audit['accidental_gaps_corrected']}/{wall_audit['accidental_gaps_found']} accidental gaps corrected** and **{wall_audit['unexplained_gaps_remaining']} unexplained gaps remaining**.

Eight glazing objects were extended only at affected endpoints, with an 8.5 mm lateral alignment correction on the two east Gaming glazing panels, closing **{wall_audit['wall_to_glass_cracks_corrected']}/{wall_audit['wall_to_glass_cracks_found']} audited wall-to-glass cracks**. Measured junction clearance ranges from **{wall_audit['smallest_remaining_wall_glass_junction_clearance_m']:.6f} m** to **{wall_audit['maximum_remaining_wall_glass_junction_clearance_m']:.6f} m**. The source-drawn Family Terrace and Art Gallery open returns remain intentionally unchanged.

There are **{len(wall_audit['blocked_openings'])} blocked scheduled openings**, **{len(wall_audit['duplicate_wall_overlaps'])} duplicate wall overlaps**, and **{len(wall_audit['missed_wall_intersections'])} missed intended wall intersections**. Mesh signatures compared against `2F_shell_before_wall_topology_fix.blend` show **{regression['error_count']} unrelated geometry regressions**; only the nine approved wall/glass objects are exempt from that comparison.

**{audit['passed']} checks passed and {audit['failed']} failed**. The final scene contains **{audit['mesh_objects']} architectural mesh objects** and approximately **{audit['triangles']} triangles**. All scales are unit, all shell meshes are closed positive-volume solids, and no duplicate mesh signatures or non-column wall thicknesses over 0.30 m were found.

Manual review should focus on these source ambiguities:

- The 2F “Down to 1F” arrow points south, while the validated 1F stair rises south to its upper landing. Exact aperture geometry is aligned, but the arrow-direction conflict needs an architectural stair-section decision before multi-floor export.
- Plan note 8 calls the 2F→3F stair “curved,” while the drawn plan shows a straight rectangular flight. The model follows the drawn geometry, as required when annotations and geometry conflict.
- The 2F void extends 1.091 m south of the provisional 1F Great Room helper. The source-drawn 2F void is retained to keep the collision opening conservative.
- Printed sub-dimensions and raster spans are not mutually proportional. The existing 1F transform controls stacking.
- The approved 10.0 × 2.7 m luxury proportion takes precedence over the drawing's broader 16 m structural bay while remaining centered on the source glazing and preserving the 27 m² room-schedule area.
- Light double lines and small corner blocks around OPEN TO BELOW establish the balustrade location but not a detailed post system. The correction uses frameless glass with a thin top rail and retains the source edge position.
- The source shows full-height glass but no elevation details. Glass height follows the 3.2 m wall assumption.
- Door swings establish opening positions; door leaves and heads are not modeled.

## Completion checklist

{chr(10).join('- [x] '+item for item in checklist)}

## Rebuild

Run from `01_shell/2F/`:

```bash
blender -b --factory-startup --python-exit-code 1 --python build_2F_shell.py
blender -b 2F_shell.blend --python-exit-code 1 --python validate_2F_shell.py
blender -b 2F_shell.blend --python-exit-code 1 --python export_2F_report.py
python3 render_2F_alignment.py
python3 render_2F_wall_topology.py
```
'''
    (OUT/'2F_shell_report.md').write_text(report)
    print('2F REPORT/OVERLAY/PROJECTION EXPORTED')


if __name__=='__main__':
    main()
