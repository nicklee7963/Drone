"""Rebuild the independent second-floor villa shell from calibrated 2F.png.

Usage:
    blender -b --factory-startup --python-exit-code 1 --python build_2F_shell.py
    blender -b --factory-startup --python-exit-code 1 --python build_2F_shell.py -- --skip-renders

All trace coordinates are pixels in the original 1448 x 1086 image. The
validated 1F transform is reused exactly so 1F and 2F stack at XY pose 0,0.
"""
import bpy
import bmesh
import json
import math
import shutil
import sys
from pathlib import Path
from mathutils import Vector

OUT = Path(__file__).resolve().parent
IMAGE = OUT / '2F.png'
BLEND = OUT / '2F_shell.blend'
PX_WIDTH_MARKERS_1F = (108.0, 1062.0)
PX_DEPTH_MARKERS_1F = (189.0, 837.0)
ARCH_WIDTH_M, ARCH_DEPTH_M = 35.6, 22.8
SX = ARCH_WIDTH_M / (PX_WIDTH_MARKERS_1F[1] - PX_WIDTH_MARKERS_1F[0])
SY = ARCH_DEPTH_M / (PX_DEPTH_MARKERS_1F[1] - PX_DEPTH_MARKERS_1F[0])
CX, CY = 585.0, 513.0
WALL_HEIGHT = 3.2
SLAB_THICKNESS = .20
GLASS_THICKNESS = .020
EXTERIOR_WALL_THICKNESS = .28
INTERIOR_WALL_THICKNESS = .18
STAIRWELL_WALL_THICKNESS = .22
STOREY_RISE = 3.2
RAILING_GLASS_THICKNESS = .020
RAILING_GLASS_HEIGHT = 1.05
RAILING_HEIGHT = 1.10
RAILING_TOPRAIL_WIDTH = .040
RAILING_END_INSET = .040

# Exact measured 1F_Opening_StairB source rectangle. This is authoritative for
# the inter-floor aperture even though the revised 2F arrow graphic is shorter.
STAIR_DOWN_1F = (708, 652, 771, 821)
STAIR_UP_3F = (607, 676, 684, 817)
OPEN_TO_BELOW = (443, 408, 714, 606)

# Orthogonal union follows the revised-plan occupied footprint. The central
# south Art Gallery reaches the source-drawn glazed facade at Y=881.
FOOTPRINT = [
    # The Family Lounge slab meets its north glazing at Y=257. Guest/media
    # wings retain their source Y=255 north edge.
    (78,255,367,560), (367,257,790,560), (790,255,1086,560),
    (78,560,385,606), (773,560,1086,606),
    (103,599,375,787), (782,599,1044,787),
    (367,560,803,805), (357,790,800,881),
    # North terrace-door returns, excluding the independently modeled terrace.
    (350,212,367,267), (367,247,405,267),
    (752,247,790,267), (790,212,807,267),
]
BRIDGE_FOOTPRINT = [
    (385,408,443,606), (714,408,773,606), (385,606,773,650),
]
# Approved luxury proportion: exactly 10.0 m wide by 2.7 m deep (27.0 m2),
# centered on the Family Lounge glazing at X=(459+697)/2. Its south edge is
# the shared glazing/slab boundary at Y=257; its X edges fall inside the two
# existing Family Lounge structural columns.
FAMILY_TERRACE_CENTER_X_PX = (459.0 + 697.0) / 2.0
FAMILY_TERRACE_WIDTH_M = 10.0
FAMILY_TERRACE_DEPTH_M = 2.7
FAMILY_TERRACE_WEST_X_PX = FAMILY_TERRACE_CENTER_X_PX - FAMILY_TERRACE_WIDTH_M/(2*SX)
FAMILY_TERRACE_EAST_X_PX = FAMILY_TERRACE_CENTER_X_PX + FAMILY_TERRACE_WIDTH_M/(2*SX)
FAMILY_TERRACE_SOUTH_Y_PX = 257.0
FAMILY_TERRACE_NORTH_Y = FAMILY_TERRACE_SOUTH_Y_PX - FAMILY_TERRACE_DEPTH_M/SY
FAMILY_TERRACE = [(FAMILY_TERRACE_WEST_X_PX,FAMILY_TERRACE_NORTH_Y,
                   FAMILY_TERRACE_EAST_X_PX,FAMILY_TERRACE_SOUTH_Y_PX)]

# Distinct solid-black structural blocks. Light double-line marks at the void
# are treated as balustrade/edge graphics and are not made full-height columns.
COLUMNS = [
    ('NorthWest_Facade',(99,216,120,255)),
    ('FamilyTerrace_West',(351,219,392,267)),
    ('FamilyLounge_NorthWest',(436,236,456,267)),
    ('FamilyLounge_NorthEast',(701,236,722,267)),
    ('FamilyTerrace_East',(765,219,790,267)),
    ('NorthEast_Facade',(1044,216,1066,255)),
    ('SouthWest_Junction',(192,763,223,787)),
    ('ArtGallery_SouthWest',(356,790,387,805)),
    ('ArtGallery_SouthEast',(770,790,801,805)),
    ('SouthEast_Junction',(940,763,973,787)),
]

# Traced wall-band endpoints keep every visible door gap. The thickness helper
# replaces raster-band thickness with the validated metric convention.
EXTERIOR_WALLS = [
 ('GuestA_NorthWest',[(78,255,143,268),(78,268,90,328)]),
 ('GuestA_WestMid',[(78,420,90,466),(78,444,115,453)]),
 ('LeftCorridor_West',[(78,543,90,618)]),
 ('GuestA_NorthEast',[(321,255,348,268)]),
 ('Gaming_NorthWest',[(811,255,841,268)]),
 ('Gaming_NorthEast',[(1017,255,1086,268),(1073,268,1086,328)]),
 ('Gaming_EastMid',[(1073,420,1086,466),(1046,444,1086,453)]),
 ('RightCorridor_East',[(1073,543,1086,618)]),
 ('Ensuite1_West',[(118,599,133,648),(118,721,133,780)]),
 ('Ensuite1_South',[(118,763,143,780),(164,763,201,787)]),
 ('Guest1_South',[(214,774,227,787),(329,774,375,787)]),
 ('Guest1_EastSouth',[(351,599,375,760),(351,760,387,805)]),
 ('ArtGallery_SouthWest',[(357,790,387,805)]),
 ('ArtGallery_SouthEast',[(770,790,800,805)]),
 ('Guest2_WestSouth',[(782,599,803,760),(782,760,827,787)]),
 ('Guest2_South',[(827,774,830,787),(937,774,973,787)]),
 ('Ensuite2_South',[(966,763,999,780),(1019,763,1044,780)]),
 ('Ensuite2_East',[(1030,599,1044,648),(1030,721,1044,780)]),
]
EXTERIOR_ANCHORS = {
 'GuestA_NorthWest':['N','W'], 'GuestA_WestMid':['W','N'],
 'LeftCorridor_West':['W'], 'GuestA_NorthEast':['N'],
 'Gaming_NorthWest':['N'], 'Gaming_NorthEast':['N','E'],
 'Gaming_EastMid':['E','N'], 'RightCorridor_East':['E'],
 'Ensuite1_West':['W','W'], 'Ensuite1_South':['S','S'], 'Guest1_South':['S','S'],
 'Guest1_EastSouth':['E','S'], 'ArtGallery_SouthWest':['S'],
 'ArtGallery_SouthEast':['S'], 'Guest2_WestSouth':['W','S'],
 'Guest2_South':['S','S'], 'Ensuite2_South':['S','S'], 'Ensuite2_East':['E','E'],
}

INTERIOR_WALLS = [
 ('GuestA_FamilyLounge',[(377,267,385,445),(377,486,385,560)]),
 ('GuestA_ABath_ACloset',[(139,445,334,452),(360,445,385,452)]),
 ('ABath_ACloset',[(217,452,224,560)]),
 ('AService_Corridor',[(78,560,320,567),(345,560,385,567)]),
 ('LeftCorridor_South',[(78,599,184,606),(208,599,320,606),(345,599,385,606)]),
 ('Ensuite1_Guest1',[(214,606,223,787)]),
 ('Guest1_ArtGallery',[(367,606,375,760)]),
 ('FamilyLounge_Gaming',[(773,267,782,445),(773,486,782,560)]),
 ('Gaming_BCloset_BBath',[(773,445,798,452),(825,445,1023,452),(1046,445,1086,452)]),
 ('BCloset_BBath',[(929,452,936,560)]),
 # The source plan shows this as one continuous service/corridor boundary.
 # The former 856..880 and 1006..1030 breaks were accidental 0.896 m gaps.
 ('BService_Corridor',[(773,560,1086,567)]),
 ('RightCorridor_South',[(773,599,825,606),(856,599,895,606),(922,599,982,606),(1006,599,1086,606)]),
 ('Powder_Guest2',[(849,606,856,721),(782,714,849,721)]),
 ('Guest2_Ensuite2',[(966,606,973,787)]),
]

STAIRWELL_WALLS = [
 ('DownTo1F_West',[(694,678,703,812)]),
 ('DownTo1F_East',[(782,640,790,760)]),
]

GLAZING = [
 ('GuestA_North',(143,261),(321,261)),
 ('GuestA_West_North',(82,328),(82,420)),
 ('GuestA_West_South',(82,466),(82,543)),
 ('FamilyTerrace_West_Return',(407,241),(433,241)),
 ('FamilyLounge_North',(456,257),(701,257)),
 ('FamilyTerrace_East_Return',(724,241),(750,241)),
 ('Gaming_North',(841,261),(1017,261)),
 ('Gaming_East_North',(1078,328),(1078,420)),
 ('Gaming_East_South',(1078,466),(1078,543)),
 ('Ensuite1_West',(124,648),(124,721)),
 ('Ensuite1_South',(143,769),(164,769)),
 ('Guest1_South',(227,781),(329,781)),
 ('Guest2_South',(830,781),(937,781)),
 ('Ensuite2_South',(999,769),(1019,769)),
 ('Ensuite2_East',(1037,648),(1037,721)),
 ('ArtGallery_South',(387,877),(770,877)),
]

DOOR_PATHS = [
 ('GuestA_ABath',(116,460),(138,460)), ('GuestA_ACloset',(335,460),(359,460)),
 ('ACloset_Corridor',(321,576),(344,576)), ('Corridor_Ensuite1',(185,614),(207,614)),
 ('Corridor_Guest1',(321,614),(344,614)), ('GuestA_FamilyLounge',(365,466),(397,466)),
 ('FamilyLounge_Gaming',(761,466),(794,466)), ('Gaming_BCloset',(799,460),(824,460)),
 ('Gaming_BBath',(1024,460),(1045,460)), ('BCloset_Gallery',(760,580),(795,580)),
 ('Corridor_Powder',(826,614),(855,614)), ('Corridor_Guest2',(896,614),(921,614)),
 ('Corridor_Ensuite2',(983,614),(1005,614)), ('ArtGallery_StairDown',(771,785),(805,785)),
]

# Machine-readable topology schedule. Apertures are the exact wall-band gaps
# traced from 2F.png. Door widths follow the gap axis; the two circulation
# openings remain separately classified so validation never closes them as
# unexplained wall discontinuities.
WALL_OPENING_SCHEDULE = [
 {'name':'GuestA_ABath','classification':'intentional_doorway','aperture_px':(115,445,139,452),'width_axis':'x','reason':'source door swing'},
 {'name':'GuestA_ACloset','classification':'intentional_doorway','aperture_px':(334,445,360,452),'width_axis':'x','reason':'source door swing'},
 {'name':'ACloset_Corridor','classification':'intentional_doorway','aperture_px':(320,560,345,567),'width_axis':'x','reason':'source door swing'},
 {'name':'Corridor_Ensuite1','classification':'intentional_doorway','aperture_px':(184,599,208,606),'width_axis':'x','reason':'source door swing'},
 {'name':'Corridor_Guest1','classification':'intentional_doorway','aperture_px':(320,599,345,606),'width_axis':'x','reason':'source door swing'},
 {'name':'GuestA_FamilyLounge','classification':'intentional_doorway','aperture_px':(377,445,385,486),
  'clear_aperture_px':(377,452,385,486),'width_axis':'y','reason':'source wide side door'},
 {'name':'FamilyLounge_Gaming','classification':'intentional_doorway','aperture_px':(773,445,782,486),
  'clear_aperture_px':(773,452,782,486),'width_axis':'y','reason':'source wide side door'},
 {'name':'Gaming_BCloset','classification':'intentional_doorway','aperture_px':(798,445,825,452),'width_axis':'x','reason':'source door swing'},
 {'name':'Gaming_BBath','classification':'intentional_doorway','aperture_px':(1023,445,1046,452),'width_axis':'x','reason':'source door swing'},
 {'name':'Corridor_Powder','classification':'intentional_doorway','aperture_px':(825,599,856,606),'width_axis':'x','reason':'source door swing'},
 {'name':'Corridor_Guest2','classification':'intentional_doorway','aperture_px':(895,599,922,606),'width_axis':'x','reason':'source door swing'},
 {'name':'Corridor_Ensuite2','classification':'intentional_doorway','aperture_px':(982,599,1006,606),'width_axis':'x','reason':'source door swing'},
 {'name':'BCloset_Gallery','classification':'circulation_opening','marker_path_px':((760,580),(795,580)),
  'aperture_px':(760,568,795,592),'reason':'source open gallery circulation'},
 {'name':'ArtGallery_StairDown','classification':'circulation_opening','marker_path_px':((771,785),(805,785)),
  'aperture_px':(708,640,771,676),'reason':'open north approach to the 1F stair aperture'},
]

WALL_TOPOLOGY_CORRECTIONS = {
 'accidental_gaps': [
   {'wall':'BService_Corridor','source_gap_px':(856,560,880,567)},
   {'wall':'BService_Corridor','source_gap_px':(1006,560,1030,567)},
 ],
 'wall_to_glass_junctions': [
   {'glass':'GuestA_West_North','endpoint':'north'},
   {'glass':'GuestA_West_South','endpoint':'north'},
   {'glass':'GuestA_West_South','endpoint':'south'},
   {'glass':'Gaming_East_North','endpoint':'north'},
   {'glass':'Gaming_East_South','endpoint':'north'},
   {'glass':'Gaming_East_South','endpoint':'south'},
   {'glass':'Ensuite1_West','endpoint':'south'},
   {'glass':'Ensuite2_East','endpoint':'north'},
   {'glass':'Ensuite2_East','endpoint':'south'},
   {'glass':'FamilyLounge_North','endpoint':'west'},
   {'glass':'FamilyLounge_North','endpoint':'east'},
 ],
 'preserved_clearances': [
   'FamilyTerrace_West_Return structural/doorway zone',
   'FamilyTerrace_East_Return structural/doorway zone',
   'ArtGallery_South west open return',
   'ArtGallery_South east open return',
 ],
}


def xy(px, py):
    return (px - CX) * SX, (CY - py) * SY


def world_rect(rect):
    x0, y1 = xy(rect[0], rect[1])
    x1, y0 = xy(rect[2], rect[3])
    return x0, y0, x1, y1


def intersects(a, b):
    return min(a[2],b[2]) > max(a[0],b[0]) and min(a[3],b[3]) > max(a[1],b[1])


def resize_rect(rect, thickness, anchor='CENTER'):
    x0,y0,x1,y1 = map(float,rect)
    assert x1>x0 and y1>y0, f'Malformed source rectangle: {rect}'
    vertical = (y1-y0)*SY > (x1-x0)*SX
    if anchor in {'W','E'} or (anchor == 'CENTER' and vertical):
        pixels = thickness/SX
        if anchor == 'W': x1=x0+pixels
        elif anchor == 'E': x0=x1-pixels
        else:
            c=(x0+x1)/2; x0,x1=c-pixels/2,c+pixels/2
    else:
        pixels = thickness/SY
        if anchor == 'N': y1=y0+pixels
        elif anchor == 'S': y0=y1-pixels
        else:
            c=(y0+y1)/2; y0,y1=c-pixels/2,c+pixels/2
    return x0,y0,x1,y1


def collection(name,parent=None):
    coll=bpy.data.collections.new(name)
    (parent or bpy.context.scene.collection).children.link(coll)
    return coll


def material(name,rgba,glass=False):
    mat=bpy.data.materials.new(name)
    mat.diffuse_color=rgba
    mat.use_nodes=True
    bsdf=mat.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value=rgba
    bsdf.inputs['Roughness'].default_value=.75
    if glass:
        bsdf.inputs['Alpha'].default_value=.32
        bsdf.inputs['Roughness'].default_value=.25
        bsdf.inputs['Transmission Weight'].default_value=.15
        mat.surface_render_method='DITHERED'
    return mat


def mesh_object(name,vertices,faces,coll,mat,kind):
    mesh=bpy.data.meshes.new(name+'_Mesh')
    mesh.from_pydata(vertices,[],faces)
    mesh.update()
    bm=bmesh.new(); bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    bmesh.ops.dissolve_limit(bm,angle_limit=.0001,verts=list(bm.verts),edges=list(bm.edges),use_dissolve_boundaries=False)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    bm.to_mesh(mesh); bm.free()
    obj=bpy.data.objects.new(name,mesh); coll.objects.link(obj)
    obj.data.materials.append(mat)
    obj['shell_geometry']=True; obj['element_type']=kind
    center=Vector(tuple((min(v.co[k] for v in mesh.vertices)+max(v.co[k] for v in mesh.vertices))/2 for k in range(3)))
    for v in mesh.vertices: v.co-=center
    obj.location=center; mesh.update()
    return obj


def rect_solid(name,rects,z0,z1,coll,mat,kind,subtract=()):
    cuts=[r for r in subtract if any(intersects(r,a) for a in rects)]
    edges=list(rects)+cuts
    xs=sorted(set(v for r in edges for v in (r[0],r[2])))
    ys=sorted(set(v for r in edges for v in (r[1],r[3])))
    def contains(rs,x,y): return any(r[0]<x<r[2] and r[1]<y<r[3] for r in rs)
    cells={(i,j) for i in range(len(xs)-1) for j in range(len(ys)-1)
           if contains(rects,(xs[i]+xs[i+1])/2,(ys[j]+ys[j+1])/2)
           and not contains(cuts,(xs[i]+xs[i+1])/2,(ys[j]+ys[j+1])/2)}
    if not cells: return None
    verts=[]; faces=[]; ids={}
    def vertex(i,j,k):
        key=(i,j,k)
        if key not in ids:
            ids[key]=len(verts); verts.append((xs[i],ys[j],z1 if k else z0))
        return ids[key]
    for i,j in sorted(cells):
        corners=[(i,j),(i+1,j),(i+1,j+1),(i,j+1)]
        low=[vertex(a,b,0) for a,b in corners]; high=[vertex(a,b,1) for a,b in corners]
        faces += [low[::-1],high]
        for edge,neighbor in enumerate(((i,j-1),(i+1,j),(i,j+1),(i-1,j))):
            if neighbor not in cells:
                nxt=(edge+1)%4; faces.append([low[edge],low[nxt],high[nxt],high[edge]])
    obj=mesh_object(name,verts,faces,coll,mat,kind)
    obj['footprint_rectangles_world']=json.dumps(rects)
    obj['subtracted_rectangles_world']=json.dumps(cuts)
    obj['z_min']=z0; obj['z_max']=z1
    return obj


def traced_solid(name,rects,z0,z1,coll,mat,kind,subtract=()):
    obj=rect_solid(name,[world_rect(r) for r in rects],z0,z1,coll,mat,kind,
                   [world_rect(r) for r in subtract])
    if obj: obj['source_pixel_rectangles']=json.dumps(rects)
    return obj


def make_wall(name,rects,wall_class,coll,mat,occupied,anchors=None):
    nominal={'exterior':EXTERIOR_WALL_THICKNESS,'interior':INTERIOR_WALL_THICKNESS,
             'stairwell':STAIRWELL_WALL_THICKNESS}[wall_class]
    anchors=anchors or ['CENTER']*len(rects)
    resized=[resize_rect(r,nominal,a) for r,a in zip(rects,anchors)]
    obj=traced_solid(name,resized,0,WALL_HEIGHT,coll,mat,'wall',occupied)
    if obj:
        obj['wall_class']=wall_class
        obj['nominal_thickness_m']=nominal
        obj['measured_thicknesses_m']=json.dumps([nominal]*len(resized))
        obj['original_source_pixel_rectangles']=json.dumps(rects)
        obj['alignment_rule']='preserve exterior face' if wall_class=='exterior' else ('preserve stair clearance' if wall_class=='stairwell' else 'preserve centerline')
    occupied.extend(resized)
    return obj


def helper(name,rect,z0,z1,coll):
    x0,y0,x1,y1=world_rect(rect)
    obj=bpy.data.objects.new(name,None); coll.objects.link(obj)
    obj.empty_display_type='CUBE'; obj.empty_display_size=1
    obj.location=((x0+x1)/2,(y0+y1)/2,(z0+z1)/2)
    obj.scale=((x1-x0)/2,(y1-y0)/2,(z1-z0)/2)
    obj.hide_render=True; obj.hide_set(True); obj['non_export_helper']=True
    obj['source_pixel_rectangle']=json.dumps(rect)
    obj['bounds_world_m']=json.dumps([x0,y0,z0,x1,y1,z1])
    return obj


def railing_segment(name, a, b, floor_normal, zone, protected_edge, coll, glass_mat, rail_mat):
    """Create a frameless glass guard and thin top rail outside a drop edge.

    ``a`` and ``b`` are world-space points on the exposed slab edge;
    ``floor_normal`` points away from the opening and onto usable floor. The
    glass therefore preserves the full void/stair clear opening dimensions.
    """
    x0,y0=a; x1,y1=b; nx,ny=floor_normal
    length=math.hypot(x1-x0,y1-y0)
    assert length>2*RAILING_END_INSET
    ux,uy=(x1-x0)/length,(y1-y0)/length
    ax,ay=x0+ux*RAILING_END_INSET,y0+uy*RAILING_END_INSET
    bx,by=x1-ux*RAILING_END_INSET,y1-uy*RAILING_END_INSET
    if abs(ax-bx)<1e-7:
        gx0,gx1=sorted((ax,ax+nx*RAILING_GLASS_THICKNESS))
        gy0,gy1=sorted((ay,by))
        tx0,tx1=sorted((ax,ax+nx*RAILING_TOPRAIL_WIDTH))
        ty0,ty1=gy0,gy1
    else:
        gx0,gx1=sorted((ax,bx)); gy0,gy1=sorted((ay,ay+ny*RAILING_GLASS_THICKNESS))
        tx0,tx1=gx0,gx1; ty0,ty1=sorted((ay,ay+ny*RAILING_TOPRAIL_WIDTH))
    panel=rect_solid(name,[(gx0,gy0,gx1,gy1)],0,RAILING_GLASS_HEIGHT,coll,glass_mat,'railing_glass')
    top=rect_solid(name+'_TopRail',[(tx0,ty0,tx1,ty1)],RAILING_GLASS_HEIGHT,RAILING_HEIGHT,
                   coll,rail_mat,'railing_toprail')
    coverage=(length-2*RAILING_END_INSET)/length
    for obj in (panel,top):
        obj['railing_zone']=zone; obj['protected_edge']=protected_edge
        obj['guardrail_height_m']=RAILING_HEIGHT; obj['edge_length_m']=length
        obj['edge_coverage_ratio']=coverage
        obj['collision_policy']='Export as collision and visual geometry'
    panel['nominal_thickness_m']=RAILING_GLASS_THICKNESS
    panel['glass_height_m']=RAILING_GLASS_HEIGHT
    top['nominal_thickness_m']=RAILING_TOPRAIL_WIDTH
    return panel,top


def stair_up_north(name,shaft,coll,mat):
    """Watertight 2F-to-3F stair starting south and ascending north."""
    x0,y0,x1,y1=world_rect(shaft)
    risers=18; tread=.26; riser=STOREY_RISE/risers; waist=.40
    run=(risers-1)*tread; length=y1-y0
    assert length-run>.45
    profile=[(0,0)]
    for i in range(risers-1):
        profile.extend([(i*tread,(i+1)*riser),((i+1)*tread,(i+1)*riser)])
    profile += [(run,STOREY_RISE),(length,STOREY_RISE),(length,STOREY_RISE-waist),
                (run,STOREY_RISE-waist),(0,-waist)]
    n=len(profile)
    verts=[(x,y0+s,z) for x in (x0,x1) for s,z in profile]
    faces=[list(range(n-1,-1,-1)),list(range(n,2*n))]
    faces += [[i,(i+1)%n,(i+1)%n+n,i+n] for i in range(n)]
    obj=mesh_object(name,verts,faces,coll,mat,'stair')
    obj['source_pixel_rectangles']=json.dumps([shaft])
    obj['xmin']=x0; obj['xmax']=x1; obj['start_y']=y0; obj['end_y']=y1
    obj['risers']=risers; obj['treads']=risers-1; obj['riser_m']=riser; obj['tread_m']=tread
    obj['run_m']=run; obj['landing_depth_m']=length-run; obj['terminal_elevation_m']=STOREY_RISE
    obj['direction']='north (+Y), up to 3F'
    return obj


def camera(name,location,target,coll,ortho=None):
    data=bpy.data.cameras.new(name); obj=bpy.data.objects.new(name,data); coll.objects.link(obj)
    obj.location=location; obj.rotation_euler=(Vector(target)-obj.location).to_track_quat('-Z','Y').to_euler()
    if ortho: data.type='ORTHO'; data.ortho_scale=ortho
    else: data.lens=45
    data.clip_end=250
    return obj


def main():
    if BLEND.exists():
        shutil.copy2(BLEND,OUT/'2F_shell_before_rebuild.blend')
    bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
    for coll in list(bpy.data.collections): bpy.data.collections.remove(coll)
    scene=bpy.context.scene
    scene.unit_settings.system='METRIC'; scene.unit_settings.length_unit='METERS'; scene.unit_settings.scale_length=1
    scene['floor_id']='2F'
    scene['local_finished_floor_z_m']=0.0
    scene['reference_source']='2F.png; XY transform and Stair B opening measured from read-only 1F_shell.blend'
    scene['alignment_calibration_json']=json.dumps({'origin_pixel':[CX,CY],'origin_xy_m':[0.0,0.0],
        'meters_per_pixel_x':SX,'meters_per_pixel_y':SY,'x_axis':'east/right','y_axis':'north/top'})
    scene['source_dimension_spans_json']=json.dumps({'written_width_m':35.6,'written_depth_m':22.8,
        '2f_tick_width_under_1f_transform_m':(1067-102)*SX,
        '2f_tick_depth_under_1f_transform_m':(792-186)*SY,
        'policy':'Use established 1F transform for stacking; preserve 2F source pixels.'})
    scene['major_anchor_errors_json']=json.dumps({'centerline':0.0,'stair_opening':0.0,
        'west_outer_face':abs(world_rect((78,255,90,268))[0]-world_rect((80,268,98,282))[0]),
        'east_outer_face':abs(world_rect((1073,255,1086,268))[2]-world_rect((1073,268,1089,282))[2])})
    scene['facade_offsets_vs_1f_json']=json.dumps({
        'north_main_face_m':world_rect((78,255,90,268))[3]-world_rect((80,268,98,282))[3],
        'south_guest_setback_m':world_rect((214,774,375,787))[1]-world_rect((214,805,388,825))[1],
        'south_central_glass_vs_1f_entry_porch_m':xy(585,877)[1]-xy(585,868)[1]})
    scene['assumptions']=('Local 2F floor top Z=0; wall/storey height 3.2m; slab 0.20m; wall thicknesses '
        '0.28m exterior, 0.18m interior, 0.22m stair; glass 0.020m floor-to-ceiling. Door gaps are full height. '
        'The exact 1F Stair B aperture is retained and the already-modeled 1F flight is not duplicated. '
        'The 2F-to-3F stair rises north. Open-drop guards use 1.05m glass plus a thin top rail at 1.10m. '
        'The Family Terrace is a centered 10.0m by 2.7m (27m2) slab joined to the lounge glazing interface. '
        'No ceiling, furniture, fixtures, decoration, or other floors.')
    scene['railing_spec_json']=json.dumps({'overall_height_m':RAILING_HEIGHT,
        'glass_height_m':RAILING_GLASS_HEIGHT,'glass_thickness_m':RAILING_GLASS_THICKNESS,
        'toprail_width_m':RAILING_TOPRAIL_WIDTH,'collision_geometry':True})
    opening_schedule=[]
    for item in WALL_OPENING_SCHEDULE:
        record=dict(item)
        if item['classification']=='intentional_doorway':
            rect=item['aperture_px']
            record['width_m']=(rect[2]-rect[0])*SX if item['width_axis']=='x' else (rect[3]-rect[1])*SY
            record['aperture_world_xyxy_m']=world_rect(rect)
            if item.get('clear_aperture_px'):
                record['clear_aperture_world_xyxy_m']=world_rect(item['clear_aperture_px'])
        else:
            a,b=item['marker_path_px']
            record['marker_center_world_xy_m']=xy((a[0]+b[0])/2,(a[1]+b[1])/2)
            record['aperture_world_xyxy_m']=world_rect(item['aperture_px'])
        opening_schedule.append(record)
    scene['wall_opening_schedule_json']=json.dumps(opening_schedule)
    scene['wall_topology_corrections_json']=json.dumps(WALL_TOPOLOGY_CORRECTIONS)
    scene['plan_ambiguities_json']=json.dumps([
        'The 2F down-arrow points south while the validated 1F flight rises south; exact 1F aperture retained.',
        'Plan note 8 says curved stair to 3F, but the drawn flight is straight and rectangular; drawn geometry retained.',
        'The revised sheet dimension graphics are not uniformly proportional under the established 1F transform.',
        'The source-drawn OPEN TO BELOW extends 1.091 m south of the provisional 1F Great Room helper.'
    ])

    root=collection('2F_SHELL')
    cols={name:collection(name,root) for name in ['2F_FLOOR','2F_WALLS_EXTERIOR','2F_WALLS_INTERIOR',
          '2F_COLUMNS','2F_GLASS','2F_RAILINGS','2F_STAIRS','2F_TERRACES','2F_OPENINGS','2F_DEBUG']}
    refs=collection('REFERENCE_2F'); views=collection('2F_VALIDATION_CAMERAS')
    mats={'wall':material('Placeholder_Wall_Gray',(.13,.15,.17,1)),
          'floor':material('Placeholder_Floor_Gray',(.67,.68,.69,1)),
          'terrace':material('Placeholder_Terrace_Gray',(.78,.79,.79,1)),
          'column':material('Placeholder_Structural_DarkGray',(.20,.23,.25,1)),
          'glass':material('Placeholder_Glass_Blue',(.13,.54,.70,.32),True),
          'railing_glass':material('Placeholder_Railing_Glass',(.10,.62,.78,.38),True),
          'railing_metal':material('Placeholder_Railing_TopRail',(.10,.12,.14,1)),
          'stair':material('Placeholder_Stair_Gray',(.49,.53,.56,1))}

    image=bpy.data.images.load(str(IMAGE),check_existing=True); image.pack()
    ref=bpy.data.objects.new('2F_Reference_Plan',None); refs.objects.link(ref)
    ref.empty_display_type='IMAGE'; ref.data=image; ref.empty_display_size=image.size[0]*SX
    ref.scale=(1,SY/SX,1); ref.location=(*xy(image.size[0]/2,image.size[1]/2),-.24)
    ref.color[3]=.65; ref.empty_image_depth='BACK'; ref.hide_render=True; ref.hide_select=True
    ref.lock_location=(True,True,True); ref.lock_rotation=(True,True,True); ref.lock_scale=(True,True,True)
    ref['meters_per_pixel_x']=SX; ref['meters_per_pixel_y']=SY
    ref['calibration']='Exact 1F transform: origin pixel 585,513; X 108..1062=35.6m; Y 189..837=22.8m'

    floor_cuts=[OPEN_TO_BELOW,STAIR_DOWN_1F]+BRIDGE_FOOTPRINT
    traced_solid('2F_Floor_Main',FOOTPRINT,-SLAB_THICKNESS,0,cols['2F_FLOOR'],mats['floor'],'floor',floor_cuts)
    traced_solid('2F_Floor_Bridge',BRIDGE_FOOTPRINT,-SLAB_THICKNESS,0,cols['2F_FLOOR'],mats['floor'],'bridge_floor',[OPEN_TO_BELOW,STAIR_DOWN_1F])
    family_terrace=traced_solid('2F_Terrace_Family',FAMILY_TERRACE,-SLAB_THICKNESS,0,
                                cols['2F_TERRACES'],mats['terrace'],'terrace',FOOTPRINT)
    family_terrace['architectural_program']='Exterior Family Terrace north of Family Lounge'
    family_terrace['target_usable_area_m2']=27.0
    family_terrace['approved_dimensions_m']=json.dumps([FAMILY_TERRACE_WIDTH_M,FAMILY_TERRACE_DEPTH_M])
    family_terrace['interface']='Shares Y=257 boundary with Family Lounge slab and glazing'

    occupied=[]
    for i,(label,rect) in enumerate(COLUMNS,1):
        obj=traced_solid(f'2F_Column_{i:03d}_{label}',[rect],0,WALL_HEIGHT,cols['2F_COLUMNS'],mats['column'],'column')
        obj['structural_interpretation']='solid black block in 2F.png'
        occupied.append(rect)
    for i,(label,rects) in enumerate(EXTERIOR_WALLS,1):
        make_wall(f'2F_Wall_Exterior_{i:03d}_{label}',rects,'exterior',cols['2F_WALLS_EXTERIOR'],mats['wall'],occupied,EXTERIOR_ANCHORS[label])
    for i,(label,rects) in enumerate(INTERIOR_WALLS,1):
        make_wall(f'2F_Wall_Interior_{i:03d}_{label}',rects,'interior',cols['2F_WALLS_INTERIOR'],mats['wall'],occupied)
    for i,(label,rects) in enumerate(STAIRWELL_WALLS,1):
        make_wall(f'2F_Wall_Stair_{i:03d}_{label}',rects,'stairwell',cols['2F_WALLS_INTERIOR'],mats['wall'],occupied)

    glass_cuts=[world_rect(r) for r in occupied]
    for i,(label,a,b) in enumerate(GLAZING,1):
        x0,y0=xy(*a); x1,y1=xy(*b)
        if abs(x1-x0)<1e-7:
            rect=(x0-GLASS_THICKNESS/2,min(y0,y1),x0+GLASS_THICKNESS/2,max(y0,y1))
            if label.startswith('Gaming_East_'):
                # Meet the west/inner face of the east exterior wall exactly;
                # the source centerline is 8.5 mm west due to raster rounding.
                east_inner_x=xy(1086,0)[0]-EXTERIOR_WALL_THICKNESS
                rect=(east_inner_x-GLASS_THICKNESS,min(y0,y1),east_inner_x,max(y0,y1))
        else:
            rect=(min(x0,x1),y0-GLASS_THICKNESS/2,max(x0,x1),y0+GLASS_THICKNESS/2)
        obj=rect_solid(f'2F_Glass_{i:03d}_{label}',[rect],0,WALL_HEIGHT,cols['2F_GLASS'],mats['glass'],'glass',glass_cuts)
        if obj is None:
            raise RuntimeError(f'Glazing {label} was completely consumed by solid cuts: {rect}')
        obj['source_pixel_line']=json.dumps([a,b]); obj['nominal_thickness_m']=GLASS_THICKNESS
        obj['collision_policy']='Separate candidate collider; choose visual/collision policy at Gazebo export'
        glass_cuts.append(rect)

    # Modern minimal guards: four source-drawn void edges, plus side guards on
    # the 1F stair aperture. The stair east guard ends before the 1.086 m south
    # terminal landing so the required +X exit stays completely clear.
    vr=world_rect(OPEN_TO_BELOW)
    void_edges=[
        ('2F_Railing_OpenToBelow_North',(vr[0],vr[3]),(vr[2],vr[3]),(0,1),'north'),
        ('2F_Railing_OpenToBelow_South',(vr[0],vr[1]),(vr[2],vr[1]),(0,-1),'south'),
        ('2F_Railing_OpenToBelow_East',(vr[2],vr[1]),(vr[2],vr[3]),(1,0),'east'),
        ('2F_Railing_OpenToBelow_West',(vr[0],vr[1]),(vr[0],vr[3]),(-1,0),'west'),
    ]
    for name,a,b,normal,edge in void_edges:
        railing_segment(name,a,b,normal,'open_to_below',edge,cols['2F_RAILINGS'],
                        mats['railing_glass'],mats['railing_metal'])
    sr=world_rect(STAIR_DOWN_1F); landing_depth=1.0862962962962959
    stair_edges=[
        ('2F_Railing_Stair_001_West',(sr[0],sr[1]),(sr[0],sr[3]),(-1,0),'west'),
        ('2F_Railing_Stair_002_East_North',(sr[2],sr[1]+landing_depth),(sr[2],sr[3]),(1,0),'east_north'),
    ]
    for name,a,b,normal,edge in stair_edges:
        railing_segment(name,a,b,normal,'stair_down_to_1f',edge,cols['2F_RAILINGS'],
                        mats['railing_glass'],mats['railing_metal'])

    # Family Terrace safety guards. The Family Lounge structural columns
    # protect the south portions of the west/east edges, so the side panels
    # stop at their north faces rather than overlapping them. The lounge side
    # remains open to its full-height glazing and doors.
    terrace_x0=xy(FAMILY_TERRACE_WEST_X_PX,0)[0]
    terrace_x1=xy(FAMILY_TERRACE_EAST_X_PX,0)[0]
    terrace_north_y=xy(0,FAMILY_TERRACE_NORTH_Y)[1]
    terrace_column_north_y=xy(0,236)[1]
    terrace_edges=[
        ('2F_Railing_FamilyTerrace_North',(terrace_x0,terrace_north_y),
         (terrace_x1,terrace_north_y),(0,-1),'north'),
        ('2F_Railing_FamilyTerrace_West',(terrace_x0,terrace_column_north_y),
         (terrace_x0,terrace_north_y),(1,0),'west'),
        ('2F_Railing_FamilyTerrace_East',(terrace_x1,terrace_column_north_y),
         (terrace_x1,terrace_north_y),(-1,0),'east'),
    ]
    for name,a,b,normal,edge in terrace_edges:
        railing_segment(name,a,b,normal,'family_terrace',edge,cols['2F_RAILINGS'],
                        mats['railing_glass'],mats['railing_metal'])

    stair=stair_up_north('2F_Stair_UpTo3F',STAIR_UP_3F,cols['2F_STAIRS'],mats['stair'])
    open_helper=helper('2F_OpenToBelow',OPEN_TO_BELOW,-SLAB_THICKNESS,STOREY_RISE,cols['2F_OPENINGS'])
    open_helper['instruction']='No 2F slab or collision face may cross this source-drawn void.'
    down=helper('2F_Opening_DownTo1F',STAIR_DOWN_1F,-STOREY_RISE,STOREY_RISE,cols['2F_OPENINGS'])
    down['alignment_source']='Exact 1F_Opening_StairB bounds; physical flight remains in 1F_shell.blend.'
    helper('2F_Opening_UpTo3F',STAIR_UP_3F,-SLAB_THICKNESS,STOREY_RISE*2,cols['2F_OPENINGS'])
    conn=bpy.data.objects.new('2F_Connection_1F',None); cols['2F_OPENINGS'].objects.link(conn)
    sr=world_rect(STAIR_DOWN_1F)
    conn.location=(sr[2],sr[1]+1.0862962962962959/2,0)
    conn.empty_display_type='ARROWS'; conn.empty_display_size=.6; conn.hide_render=True; conn.hide_set(True)
    conn['paired_object']='1F_Connection_2F'; conn['xy_error_m']=0.0
    upper=bpy.data.objects.new('2F_Connection_3F',None); cols['2F_OPENINGS'].objects.link(upper)
    upper.location=(stair['xmax'],stair['end_y']-stair['landing_depth_m']/2,STOREY_RISE)
    upper.empty_display_type='ARROWS'; upper.empty_display_size=.6; upper.hide_render=True; upper.hide_set(True)
    for label,a,b in DOOR_PATHS:
        marker=bpy.data.objects.new('2F_Opening_'+label,None); cols['2F_OPENINGS'].objects.link(marker)
        marker.location=(*xy((a[0]+b[0])/2,(a[1]+b[1])/2),1.2)
        marker.empty_display_type='PLAIN_AXES'; marker.empty_display_size=.15; marker.hide_render=True; marker.hide_set(True)

    top=camera('2F_Camera_Top_Orthographic',(0,0,55),(0,0,0),views,42.5); top.rotation_euler=(0,0,0)
    front=camera('2F_Camera_Perspective_Front',(0,-49,31),(0,0,.4),views)
    corner=camera('2F_Camera_Perspective_Corner',(34,-39,39),(0,0,.4),views)
    open_view=camera('2F_Camera_OpenToBelow_Validation',(18,-23,19),(0,-.4,.35),views)
    open_view.data.lens=52
    terrace_view=camera('2F_Camera_FamilyTerrace_Validation',(17,27,13),(-.25,8.7,.15),views)
    terrace_view.data.lens=50
    # CPU Cycles keeps validation rendering reproducible on headless hosts
    # without a live GL/EGL display context.
    scene.render.engine='CYCLES'; scene.cycles.device='CPU'; scene.cycles.samples=16
    scene.cycles.use_denoising=True
    scene.world.use_nodes=True
    scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.86,.86,.86,1)
    scene.world.node_tree.nodes['Background'].inputs[1].default_value=.8
    light_data=bpy.data.lights.new('Validation_Area_Light','AREA'); light=bpy.data.objects.new(light_data.name,light_data)
    views.objects.link(light); light.location=(0,-4,28); light_data.energy=3000; light_data.shape='DISK'; light_data.size=22
    scene.render.image_settings.file_format='PNG'; scene.render.film_transparent=False
    scene.render.resolution_percentage=100; scene.view_settings.view_transform='Standard'
    scene.camera=top; ref.hide_set(True)
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=='VIEW_3D':
                area.spaces.active.clip_end=250; area.spaces.active.region_3d.view_distance=46
                area.spaces.active.region_3d.view_location=(0,0,0); area.spaces.active.region_3d.view_perspective='ORTHO'
                area.spaces.active.shading.color_type='MATERIAL'; area.spaces.active.overlay.show_floor=False
    text=bpy.data.texts.new('README_2F_SHELL')
    text.write(__doc__+'\n\n'+scene['assumptions']+'\n\n'+ref['calibration'])
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND))
    sys.path.insert(0,str(OUT)); import validate_2F_shell
    result=validate_2F_shell.run()
    if '--skip-renders' not in sys.argv:
        for cam,name,width,height in [(top,'2F_shell_top.png',2400,1700),
                (front,'2F_shell_perspective_front.png',1800,1300),
                (corner,'2F_shell_perspective_corner.png',1800,1300),
                (open_view,'2F_open_to_below_validation.png',1800,1300),
                (terrace_view,'2F_family_terrace_validation.png',1800,1300)]:
            scene.camera=cam; scene.render.resolution_x=width; scene.render.resolution_y=height
            scene.render.filepath=str(OUT/name); bpy.ops.render.render(write_still=True)
        scene.camera=top; scene.render.resolution_x=2400; scene.render.resolution_y=1700
        scene.render.filepath=str(OUT/'2F_shell_top.png')
        bpy.ops.wm.save_as_mainfile(filepath=str(BLEND))
    print('2F SHELL BUILD COMPLETE',json.dumps({'passed':result['passed'],'failed':result['failed'],
          'meshes':result['mesh_objects'],'dimensions_m':result['bounds_m']['dimensions']}))


if __name__=='__main__':
    main()
