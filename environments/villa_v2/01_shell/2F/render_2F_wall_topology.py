"""Render a true orthographic, color-coded 2F wall topology audit view."""
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUT=Path(__file__).resolve().parent
projection=json.loads((OUT/'2F_alignment_projection.json').read_text())
audit=json.loads((OUT/'2F_shell_validation.json').read_text())
schedule=audit['wall_audit']['opening_schedule']

W,H=2400,1700
margin_left,margin_top,margin_bottom=120,110,120
legend_width=650
world=(-20.5,-14.2,20.5,13.5)
plot_right=W-legend_width-60
sx=(plot_right-margin_left)/(world[2]-world[0])
sy=(H-margin_top-margin_bottom)/(world[3]-world[1])
scale=min(sx,sy)

def point_px(point):
    x,y=point
    return (margin_left+(x-world[0])*scale,
            H-margin_bottom-(y-world[1])*scale)

def rect_px(rect):
    x0,y0,x1,y1=rect
    a=point_px((x0,y1)); b=point_px((x1,y0))
    return (a[0],a[1],b[0],b[1])

font_path='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
bold_path='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
def font(size,bold=False):
    try: return ImageFont.truetype(bold_path if bold else font_path,size)
    except OSError: return ImageFont.load_default()

im=Image.new('RGB',(W,H),(248,248,246))
draw=ImageDraw.Draw(im,'RGBA')

for value in range(-20,21,5):
    x=point_px((value,0))[0]
    draw.line((x,margin_top,x,H-margin_bottom),fill=(80,80,80,24),width=1)
for value in range(-10,11,5):
    y=point_px((0,value))[1]
    draw.line((margin_left,y,plot_right,y),fill=(80,80,80,24),width=1)

styles={
    'floor':((210,215,210,90),(150,155,150,130)),
    'bridge_floor':((181,222,198,145),(40,135,88,210)),
    'terrace':((221,207,155,130),(145,118,36,200)),
    'wall':((42,45,49,245),(20,22,24,255)),
    'column':((103,58,116,245),(62,26,75,255)),
    'glass':((38,174,220,155),(0,105,170,255)),
    'railing_glass':((62,209,225,125),(0,124,146,240)),
    'railing_toprail':((20,70,82,220),(10,35,42,255)),
    'stair':((77,151,133,175),(18,95,80,245)),
}
order=('floor','bridge_floor','terrace','wall','column','glass','railing_glass','railing_toprail','stair')
faces=projection['2F']
for kind in order:
    fill,outline=styles[kind]
    for face in faces:
        if face['kind']!=kind: continue
        points=[point_px(p) for p in face['xy_m']]
        draw.polygon(points,fill=fill,outline=outline)

# Void and exact 1F stair aperture are authoritative clear zones.
void=[(-142)*35.6/954,(-93)*22.8/648,(129)*35.6/954,(105)*22.8/648]
stair=[4.5899371069182395,-10.837037037037037,6.940880503144654,-4.890740740740741]
draw.rectangle(rect_px(void),outline=(122,45,181,255),width=7)
draw.text((rect_px(void)[0]+18,rect_px(void)[1]+16),'OPEN TO BELOW',fill=(100,28,155,255),font=font(22,True))
draw.rectangle(rect_px(stair),outline=(244,130,20,255),width=7)
draw.text((rect_px(stair)[0]+12,rect_px(stair)[1]+12),'STAIR APERTURE',fill=(164,76,0,255),font=font(18,True))

door_index=0; circulation_index=0
for opening in schedule:
    rect=opening.get('clear_aperture_world_xyxy_m',opening.get('aperture_world_xyxy_m'))
    if not rect: continue
    box=rect_px(rect)
    if opening['classification']=='intentional_doorway':
        door_index+=1; color=(27,164,83,235); label=f'D{door_index}'
    else:
        circulation_index+=1; color=(238,137,24,245); label=f'C{circulation_index}'
    draw.rectangle(box,fill=(*color[:3],85),outline=color,width=5)
    draw.text((box[0]+4,box[1]+2),label,fill=color,font=font(15,True))

# Title and legend.
draw.rounded_rectangle((55,34,1050,94),radius=14,fill=(255,255,255,235),outline=(90,90,90,150),width=2)
draw.text((82,49),'2F WALL TOPOLOGY — ORTHOGRAPHIC AUDIT',fill=(20,20,20,255),font=font(28,True))
legend_x=plot_right+45
draw.rounded_rectangle((legend_x,55,W-45,H-55),radius=18,fill=(255,255,255,238),outline=(110,110,110,160),width=2)
draw.text((legend_x+28,82),'OPENING SCHEDULE',fill=(20,20,20,255),font=font(25,True))
y=132
for i,opening in enumerate([o for o in schedule if o['classification']=='intentional_doorway'],1):
    width=opening['width_m']
    draw.rectangle((legend_x+30,y+5,legend_x+52,y+23),fill=(27,164,83,170),outline=(18,115,55,255),width=2)
    draw.text((legend_x+65,y),f'D{i}  {opening["name"]}  {width:.3f} m',fill=(30,30,30,255),font=font(17))
    y+=36
y+=12
for i,opening in enumerate([o for o in schedule if o['classification']=='circulation_opening'],1):
    draw.rectangle((legend_x+30,y+5,legend_x+52,y+23),fill=(238,137,24,170),outline=(168,79,0,255),width=2)
    draw.text((legend_x+65,y),f'C{i}  {opening["name"]}',fill=(30,30,30,255),font=font(17))
    y+=36
y+=22
draw.text((legend_x+28,y),'TOPOLOGY RESULT',fill=(20,20,20,255),font=font(22,True)); y+=42
wa=audit['wall_audit']
lines=[
    f'Intentional doorways: {wa["intentional_doorway_count"]}',
    f'Circulation openings: {wa["circulation_opening_count"]}',
    f'Accidental gaps corrected: {wa["accidental_gaps_corrected"]}/{wa["accidental_gaps_found"]}',
    f'Wall/glass cracks corrected: {wa["wall_to_glass_cracks_corrected"]}/{wa["wall_to_glass_cracks_found"]}',
    f'Unexplained gaps remaining: {wa["unexplained_gaps_remaining"]}',
    f'Blocked openings: {len(wa["blocked_openings"])}',
    f'Duplicate wall overlaps: {len(wa["duplicate_wall_overlaps"])}',
]
for line in lines:
    draw.text((legend_x+30,y),line,fill=(25,25,25,255),font=font(18)); y+=34
y+=18
legend=[('Solid wall',(42,45,49,245)),('Structural column',(103,58,116,245)),
        ('Full-height glazing',(38,174,220,210)),('Door opening',(27,164,83,220)),
        ('Circulation opening',(238,137,24,230)),('OPEN TO BELOW',(122,45,181,255)),
        ('Stair aperture',(244,130,20,255))]
for label,color in legend:
    draw.rectangle((legend_x+30,y+4,legend_x+58,y+25),fill=color)
    draw.text((legend_x+72,y),label,fill=(30,30,30,255),font=font(18)); y+=34

draw.text((plot_right-85,50),'N  ↑',fill=(15,15,15,255),font=font(30,True))
draw.text((75,H-64),'Every visible wall interruption is classified by source evidence. Scale is uniform in world X/Y.',
          fill=(35,35,35,255),font=font(18))
im.save(OUT/'2F_wall_topology_validation.png')
print('WROTE',OUT/'2F_wall_topology_validation.png',im.size)
