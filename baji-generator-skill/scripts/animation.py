"""V1.5 rotation export backed by the shared curved model renderer."""
import math
import numpy as np
from PIL import Image
from model_renderer import DEFAULT_CONFIG, RIM_COLORS, geometry_for_angle as model_geometry, render_model
from model_backend import render_rotation as backend_render_rotation

DISC_RATIO=DEFAULT_CONFIG.object_diameter_ratio
THICKNESS_RATIO=DEFAULT_CONFIG.body_thickness_ratio*DEFAULT_CONFIG.object_diameter_ratio/2
TRANSITION_EPSILON=.035

def _back(size,rim):
    return render_model(Image.new('RGBA',(size,size),(190,190,190,255)),size,rim,(0,0,0,0),True,math.pi)

def monotonic_source_u(u):
    """Strictly increasing source warp; derivative is 0.96 + 0.12*u^2 > 0."""
    values=.96*np.asarray(u,dtype=np.float32)+.04*np.asarray(u,dtype=np.float32)**3
    return values

def projection_lut(samples=257):
    u=np.linspace(-1,1,samples,dtype=np.float32); source=monotonic_source_u(u)
    assert np.all(np.diff(source)>0),"non-monotonic inverse projection LUT"
    return source

def geometry_for_angle(size,theta):
    mask,data=model_geometry(size,theta); surface=data[0]
    c=math.cos(theta); kind=1 if c>TRANSITION_EPSILON else (-1 if c<-TRANSITION_EPSILON else 0)
    # Keep the V1.4 tuple contract for existing integrations and tests.
    yy,xx=np.nonzero(mask); x_min=np.full((size,1),size,np.float32); x_max=np.full((size,1),-1,np.float32)
    for y in np.unique(yy): row=xx[yy==y]; x_min[y,0]=row.min(); x_max[y,0]=row.max()
    face=(surface==1)|(surface==2)|(surface==5) if kind==1 else (surface==4 if kind==-1 else np.zeros_like(mask))
    return mask,face,kind,np.full((size,1),(size-1)/2,np.float32),np.maximum(0,(x_max-x_min)/2),np.linspace(-1,1,size,dtype=np.float32)[:,None],x_min,x_max

def _bilinear(texture,sx,sy):
    h,w,_=texture.shape; sx=np.clip(sx,0,w-1); sy=np.clip(sy,0,h-1); x0=np.floor(sx).astype(np.int32); y0=np.floor(sy).astype(np.int32); x1=np.minimum(x0+1,w-1); y1=np.minimum(y0+1,h-1); fx=(sx-x0)[:,None]; fy=(sy-y0)[:,None]
    top=texture[y0,x0]*(1-fx)+texture[y0,x1]*fx; bottom=texture[y1,x0]*(1-fx)+texture[y1,x1]*fx; return top*(1-fy)+bottom*fy

def _alpha_over_pixels(base,indices,source):
    if not len(indices[0]):return
    ys,xs=indices; dst=base[ys,xs].astype(np.float32); src=source.astype(np.float32); a=src[:,3:4]/255; base[ys,xs,:3]=(src[:,:3]*a+dst[:,:3]*(1-a)).astype(np.uint8); base[ys,xs,3]=255

def _texture_crop(image,size):
    p=round(size*.105); return np.asarray(image.crop((p,p,size-p,size-p)).convert('RGBA'),dtype=np.float32)

def render_frame_rgba(front_texture,back_texture,highlight_texture,size,rim,background,transparent,theta):
    texture=Image.fromarray(np.clip(front_texture,0,255).astype(np.uint8),'RGBA') if isinstance(front_texture,np.ndarray) else front_texture
    return render_model(texture,size,rim,background,transparent,theta,return_buffers=True)[0],model_geometry(size,theta)[0]

def render_rotation(art,size,rim,background,transparent,inner,frames=58,duration=40,return_masks=False,backend='pillow',effect='glossy'):
    projection_lut(); result=backend_render_rotation(art,size,rim,background,transparent,effect,frames,backend,return_masks)
    if return_masks:
        images,masks,_chosen=result; return images,masks
    images,_chosen=result; return images

def save_rotation(path,art,size,rim,background,transparent,inner,frames=58,duration=40,backend='auto',effect='glossy'):
    images=render_rotation(art,size,rim,background,transparent,inner,frames,duration,False,backend,effect); images[0].save(path,save_all=True,append_images=images[1:],duration=duration,loop=0,optimize=False,disposal=2)
