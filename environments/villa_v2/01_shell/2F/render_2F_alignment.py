"""Render a color-coded top projection of the measured 1F and 2F shells."""
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUT=Path(__file__).resolve().parent
data=json.loads((OUT/'2F_alignment_projection.json').read_text())
W,H=2200,1600
margin=150
world=(-20.5,-14.2,20.5,13.5)
sx=(W-2*margin)/(world[2]-world[0]); sy=(H-2*margin)/(world[3]-world[1])
scale=min(sx,sy)
def px(point):
    x,y=point
    return (margin+(x-world[0])*scale, H-margin-(y-world[1])*scale)

im=Image.new('RGB',(W,H),(247,247,245)); draw=ImageDraw.Draw(im,'RGBA')
font_path='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
def font(size):
    try: return ImageFont.truetype(font_path,size)
    except OSError: return ImageFont.load_default()
for value in range(-20,21,5):
    x=px((value,0))[0]; draw.line((x,margin,x,H-margin),fill=(80,80,80,25),width=1)
for value in range(-10,11,5):
    y=px((0,value))[1]; draw.line((margin,y,W-margin,y),fill=(80,80,80,25),width=1)
draw.line((*px((world[0],0)),*px((world[2],0))),fill=(30,30,30,100),width=2)
draw.line((*px((0,world[1])),*px((0,world[3]))),fill=(30,30,30,100),width=2)

def render_floor(key,fill,outline):
    faces=[f for f in data[key] if f['kind'] in {'floor','bridge_floor','terrace'}]
    for face in faces:
        draw.polygon([px(p) for p in face['xy_m']],fill=fill,outline=outline,width=1)

def render_structure(key,color):
    faces=[f for f in data[key] if f['kind'] in {'wall','column','glass','stair','railing_glass','railing_toprail'}]
    for face in faces:
        pts=[px(p) for p in face['xy_m']]
        draw.line(pts+[pts[0]],fill=color,width=3,joint='curve')

render_floor('1F',(35,115,215,40),(35,115,215,95))
render_structure('1F',(25,92,190,145))
render_floor('2F',(224,59,73,42),(224,59,73,100))
render_structure('2F',(205,38,58,185))

# Exact shared stair opening and source 2F void.
def rect_world(values,color,width=5):
    x0,y0,x1,y1=values
    draw.rectangle((*px((x0,y1)),*px((x1,y0))),outline=color,width=width)
rect_world([4.5899371069182395,-10.837037037037037,6.940880503144654,-4.890740740740741],(255,137,0,255),7)
rect_world([(-142)*35.6/954,(-93)*22.8/648,(129)*35.6/954,(105)*22.8/648],(111,45,180,255),6)

draw.rounded_rectangle((55,45,810,230),radius=18,fill=(255,255,255,228),outline=(90,90,90,160),width=2)
draw.text((85,70),'1F / 2F XY ALIGNMENT',fill=(20,20,20,255),font=font(28))
draw.rectangle((88,125,130,150),fill=(35,115,215,90)); draw.text((145,125),'1F projected shell',fill=(20,70,145,255),font=font(20))
draw.rectangle((390,125,432,150),fill=(224,59,73,95)); draw.text((447,125),'2F projected shell',fill=(160,25,40,255),font=font(20))
draw.rectangle((88,170,130,195),outline=(255,137,0,255),width=4); draw.text((145,170),'exact shared Stair B aperture: 0.000000 m max error',fill=(80,55,20,255),font=font(20))
draw.text((W-210,55),'N  ↑',fill=(15,15,15,255),font=font(32))
draw.text((W-710,H-80),'Origin and centerline error: 0.000000 m  |  Max shared X-anchor error: 0.112 m',fill=(30,30,30,255),font=font(18))
im.save(OUT/'2F_vs_1F_alignment.png')

# Raster companion to the zoomable SVG overlay, useful for CI artifacts and
# direct visual inspection without an SVG renderer.
source=Image.open(OUT/'2F.png').convert('RGBA')
overlay=Image.new('RGBA',source.size,(0,0,0,0)); od=ImageDraw.Draw(overlay,'RGBA')
source_styles={'floor':(44,166,78,28),'bridge_floor':(0,150,106,52),'terrace':(178,154,80,34),
               'wall':(215,36,65,110),'column':(126,40,91,140),'glass':(0,123,205,210),
               'railing_glass':(0,169,207,210),'railing_toprail':(18,40,49,210),'stair':(0,118,103,90)}
mx,my=data['calibration']['meters_per_pixel']; cx,cy=data['calibration']['origin_pixel']
def source_px(point): return (point[0]/mx+cx,cy-point[1]/my)
for face in data['2F']:
    color=source_styles.get(face['kind'])
    if color: od.polygon([source_px(p) for p in face['xy_m']],fill=color)
od.rectangle((443,408,714,606),outline=(112,43,180,255),width=4)
od.rectangle((708,652,771,821),outline=(247,133,0,255),width=4)
composite=Image.alpha_composite(source,overlay).convert('RGB')
composite.save(OUT/'2F_shell_source_overlay.png')
print('WROTE',OUT/'2F_vs_1F_alignment.png',im.size,'AND',OUT/'2F_shell_source_overlay.png',composite.size)
