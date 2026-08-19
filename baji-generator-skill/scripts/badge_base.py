"""Compatibility helpers and the V1.5 shared-model static entry point."""
import math
from functools import lru_cache
from PIL import Image, ImageChops, ImageDraw, ImageFilter
from model_renderer import DEFAULT_CONFIG, RIM_COLORS, render_model, studio_shadow

DOME_GEOMETRY_STRENGTH=0.045
DOME_EDGE_START=0.38
DOME_LIGHT_STRENGTH=0.055
DOME_EDGE_SHADE_STRENGTH=0.048
LIGHT_DIRECTION=(-0.40,-0.48,0.78)
RIM_RATIO=0.0085
INNER_BORDER_RATIO=0.0030
HIGHLIGHT_MAIN_ALPHA=102
HIGHLIGHT_SECONDARY_ALPHA=38
HIGHLIGHT_BLUR_RATIO=0.012
OBJECT_BOX_RATIO=(0.105,0.105,0.895,0.895)
RIMS=RIM_COLORS

def ellipse_mask(size,box,blur=0):
    m=Image.new("L",(size,size)); ImageDraw.Draw(m).ellipse(box,fill=255)
    return m.filter(ImageFilter.GaussianBlur(blur)) if blur else m

def _smoothstep(a,b,x):
    q=max(0.0,min(1.0,(x-a)/(b-a))); return q*q*(3-2*q)

def dome_map(image,strength=DOME_GEOMETRY_STRENGTH,cells=32):
    """Continuous radial mapping: stable face center, progressively curved edge."""
    n=image.width; step=n/cells; mesh=[]
    def source(x,y):
        nx=2*x/n-1; ny=2*y/n-1; r=(nx*nx+ny*ny)**.5
        edge=_smoothstep(DOME_EDGE_START,1.0,min(r,1.0)); center=1-_smoothstep(0.0,.55,r)
        gain=1+strength*edge-strength*.10*center
        sx=(nx*gain+1)*n/2; sy=(ny*gain+1)*n/2
        return (max(0,min(n-1,sx)),max(0,min(n-1,sy)))
    for gy in range(cells):
        for gx in range(cells):
            x0=round(gx*step); y0=round(gy*step); x1=round((gx+1)*step); y1=round((gy+1)*step)
            mesh.append(((x0,y0,x1,y1),source(x0,y0)+source(x0,y1)+source(x1,y1)+source(x1,y0)))
    return image.transform((n,n),Image.Transform.MESH,mesh,Image.Resampling.BICUBIC)

@lru_cache(maxsize=8)
def _dome_light_maps(size):
    sample=min(320,size); bright=Image.new('L',(sample,sample)); dark=Image.new('L',(sample,sample)); bp=[]; dp=[]
    lx,ly,lz=LIGHT_DIRECTION; ll=(lx*lx+ly*ly+lz*lz)**.5; lx/=ll; ly/=ll; lz/=ll
    for y in range(sample):
        ny=2*(y+.5)/sample-1
        for x in range(sample):
            nx=2*(x+.5)/sample-1; rr=nx*nx+ny*ny
            if rr>=1: bp.append(0); dp.append(0); continue
            z=math.sqrt(max(.08,1-.72*rr)); nl=(nx*nx+ny*ny+z*z)**.5; dot=max(0,(nx*lx+ny*ly+z*lz)/nl)
            light=max(0,(dot-.68))*DOME_LIGHT_STRENGTH*2.0; shade=(rr**2.1)*DOME_EDGE_SHADE_STRENGTH
            bp.append(round(min(.10,light)*255)); dp.append(round(min(.075,shade)*255))
    bright.putdata(bp); dark.putdata(dp)
    return (bright.resize((size,size),Image.Resampling.BICUBIC),dark.resize((size,size),Image.Resampling.BICUBIC))

def apply_dome_lighting(image):
    bright,dark=_dome_light_maps(image.width)
    rgb=image.convert('RGB'); factor=Image.eval(dark,lambda p:255-p); shaded=ImageChops.multiply(rgb,Image.merge('RGB',(factor,factor,factor))).convert('RGBA'); shaded.putalpha(image.getchannel('A'))
    white=Image.new('RGBA',image.size,(255,255,255,0)); white.putalpha(bright); return Image.alpha_composite(shaded,white)

def _inset(box,p): return tuple(v+(p if i<2 else -p) for i,v in enumerate(box))

def _rim_layer(s,box,rim):
    hi,mid,lo=RIMS[rim]; diameter=box[2]-box[0]; w=max(2,round(diameter*RIM_RATIO)); layer=Image.new('RGBA',(s,s)); d=ImageDraw.Draw(layer)
    d.ellipse(box,fill=(*lo,255)); d.ellipse(_inset(box,max(1,w//4)),fill=(*hi,255)); d.ellipse(_inset(box,max(2,w//2)),fill=(*mid,255)); return layer,w

def object_geometry(size,scale=2):
    s=size*scale; box=tuple(round(s*v) for v in OBJECT_BOX_RATIO); diameter=box[2]-box[0]; rim=max(2,round(diameter*RIM_RATIO)); gap=max(1,round(diameter*INNER_BORDER_RATIO)); inner=_inset(box,rim+gap); art=_inset(box,rim+gap+max(1,round(diameter*.0015))); return s,box,inner,art

def film_highlight_layer(size,phase=0.0,opacity=1.0,scale=2):
    s,box,inner,disc=object_geometry(size,scale); l,t,r,b=disc; w=r-l; shift=math.sin(phase)*w*.075; mask=Image.new('L',(s,s))
    def soft_ellipse(width,height,peak,angle,x,y,blur):
        tile=Image.new('L',(max(4,round(width)),max(4,round(height)))); tw,th=tile.size; values=[]
        for py in range(th):
            ny=2*(py+.5)/th-1
            for px in range(tw):
                nx=2*(px+.5)/tw-1; radius=nx*nx+ny*ny; values.append(round(peak*max(0,1-radius)**2.2))
        tile.putdata(values)
        tile=tile.filter(ImageFilter.GaussianBlur(max(1,blur))).rotate(angle,Image.Resampling.BICUBIC,expand=True)
        mask.paste(ImageChops.lighter(mask.crop((round(x),round(y),round(x)+tile.width,round(y)+tile.height)),tile),(round(x),round(y)))
    soft_ellipse(w*.56,w*.115,HIGHLIGHT_MAIN_ALPHA*opacity,-22,l+w*.04+shift,t+w*.10,w*.012)
    soft_ellipse(w*.20,w*.095,HIGHLIGHT_MAIN_ALPHA*.58*opacity,-18,l+w*.13+shift,t+w*.035,w*.009)
    soft_ellipse(w*.40,w*.17,HIGHLIGHT_SECONDARY_ALPHA*opacity,-18,l+w*.54-shift,t+w*.70,w*.018)
    mask=mask.filter(ImageFilter.GaussianBlur(max(1,w*HIGHLIGHT_BLUR_RATIO))); mask=ImageChops.multiply(mask,ellipse_mask(s,disc))
    layer=Image.new('RGBA',(s,s),(255,255,255,0)); layer.putalpha(mask); return layer.resize((size,size),Image.Resampling.LANCZOS)

def make_badge_object(art,size,rim='silver',inner=(255,255,255,255),phase=0.0,highlights=True):
    # Transparent object render used by legacy callers; all V1.5 geometry,
    # normals and highlights come from model_renderer instead of flat layers.
    return render_model(art,size,rim,(0,0,0,0),True,0.0,DEFAULT_CONFIG,include_shadow=False)

def render_badge(art,size,rim='silver',background=(255,255,255,255),transparent=False,inner=(255,255,255,255)):
    return render_model(art,size,rim,background,transparent,0.0,DEFAULT_CONFIG)
