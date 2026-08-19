"""V1.5 shared axisymmetric badge model and CPU ray-surface renderer.

The model is expressed in radius units.  Orthographic camera rays are solved
against the front dome, rolled rim, cylindrical wall and shallow stamped back;
the nearest valid hit is selected by a z-buffer equivalent depth comparison.
"""
from dataclasses import dataclass
from functools import lru_cache
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter


@dataclass(frozen=True)
class BadgeModelConfig:
    radius: float = 1.0
    front_art_radius: float = 0.972
    dome_depth_ratio: float = 0.046
    dome_power: float = 1.05
    rim_bevel_width_ratio: float = 0.028
    rim_roll_depth_ratio: float = 0.012
    body_thickness_ratio: float = 0.050
    back_curve_depth_ratio: float = 0.012
    perspective_strength: float = 0.0
    object_diameter_ratio: float = 0.790
    inner_border_ratio: float = 0.004
    ray_iterations: int = 7
    back_accessory: object = None
    profile: str = "compat"


DEFAULT_CONFIG = BadgeModelConfig()
MASTER_CONFIG = BadgeModelConfig(
    front_art_radius=.978,
    dome_depth_ratio=2.65/29,
    dome_power=2.15,
    rim_bevel_width_ratio=.022,
    rim_roll_depth_ratio=.72/29,
    body_thickness_ratio=2.04/29,
    back_curve_depth_ratio=1.45/29,
    ray_iterations=8,
    back_accessory="obj-groups",
    profile="master58",
)
RIM_COLORS = {
    "silver": ((244,247,249),(157,165,171),(67,73,78)),
    "gold": ((255,231,153),(184,128,43),(91,57,15)),
    "black": ((132,137,143),(45,48,53),(8,10,13)),
}
SURFACE_NONE=0; SURFACE_FRONT=1; SURFACE_RIM=2; SURFACE_SIDE=3; SURFACE_BACK=4; SURFACE_INNER=5


def smoothstep01(x):
    x=np.clip(x,0.0,1.0); return x*x*(3.0-2.0*x)


def front_depth(r, config=DEFAULT_CONFIG):
    """Outward shallow crown plus a C1 rolled transition at the outer rim."""
    if config.profile=="master58":
        rr=np.asarray(r,dtype=np.float32); shoulder=.72/(1+np.exp(-(rr-.88)*34))
        return (.58+2.65*(1-np.clip(rr,0,1)**2.15)-shoulder)/29
    a=config.front_art_radius; half=config.body_thickness_ratio*.5
    rr=np.asarray(r,dtype=np.float32); q=np.clip(1.0-(rr/a)**2,0.0,1.0)
    crown=half+config.dome_depth_ratio*q**config.dome_power
    t=np.clip((rr-a)/max(1e-6,1-a),0,1); roll=smoothstep01(t)
    edge=half-config.rim_roll_depth_ratio
    return np.where(rr<=a,crown,crown*(1-roll)+edge*roll)


def back_depth(r, config=DEFAULT_CONFIG):
    if config.profile=="master58":
        rr=np.asarray(r,dtype=np.float32); pan=.86*(1-np.exp(-((np.clip(rr,0,1)/.72)**8))); rim=.62/(1+np.exp(-(rr-.86)*35))
        return (-.72-pan-rim)/29
    rr=np.asarray(r,dtype=np.float32); half=config.body_thickness_ratio*.5
    return -half-config.back_curve_depth_ratio*np.clip(1.0-rr*rr,0,1)**1.35


def radial_derivative(function, r, config=DEFAULT_CONFIG):
    rr=np.asarray(r,dtype=np.float32); h=2e-4
    return (function(np.minimum(1,rr+h),config)-function(np.maximum(0,rr-h),config))/(2*h)


def profile_samples(config=DEFAULT_CONFIG, samples=512):
    r=np.linspace(0,1,samples,dtype=np.float32)
    return r,front_depth(r,config),back_depth(r,config)


def validate_geometry(config=DEFAULT_CONFIG):
    r,zf,zb=profile_samples(config,2049)
    values=np.concatenate((r,zf,zb,radial_derivative(front_depth,r,config),radial_derivative(back_depth,r,config)))
    assert np.isfinite(values).all()
    assert zf[0]>zf[-1] and (zf[0]-zf[-1])>.03
    assert abs(zf[-1]-(config.body_thickness_ratio*.5-config.rim_roll_depth_ratio))<5e-4
    assert abs(zb[-1]+config.body_thickness_ratio*.5)<5e-4
    assert np.max(np.abs(np.diff(zf)))<.006
    assert (zb.max()-zb.min()) < (zf.max()-zf.min())
    return {"front_center":float(zf[0]),"front_edge":float(zf[-1]),"back_center":float(zb[0]),"back_edge":float(zb[-1])}

@lru_cache(maxsize=8)
def build_validation_mesh(config=DEFAULT_CONFIG,radial_segments=32,angular_segments=128):
    """Expose the analytic profile as an indexed mesh for topology/UV tests."""
    vertices=[]; normals=[]; uvs=[]; surfaces=[]; triangles=[]
    for function,kind,flip in ((front_depth,SURFACE_FRONT,False),(back_depth,SURFACE_BACK,True)):
        offset=len(vertices)
        for j in range(radial_segments+1):
            r=j/radial_segments; dz=float(radial_derivative(function,np.array([r]),config)[0]); inv=1/math.sqrt(1+dz*dz)
            for i in range(angular_segments):
                p=2*math.pi*i/angular_segments; cp,sp=math.cos(p),math.sin(p)
                vertices.append((r*cp,r*sp,float(function(np.array([r]),config)[0])))
                normals.append(((dz if flip else -dz)*cp*inv,(dz if flip else -dz)*sp*inv,-inv if flip else inv))
                uvs.append((.5+r*cp/(2*config.front_art_radius),.5+r*sp/(2*config.front_art_radius))); surfaces.append(kind)
        for j in range(radial_segments):
            for i in range(angular_segments):
                a=offset+j*angular_segments+i; b=offset+j*angular_segments+(i+1)%angular_segments; c=offset+(j+1)*angular_segments+i; d=offset+(j+1)*angular_segments+(i+1)%angular_segments
                triangles.extend(((a,c,b),(b,c,d)) if flip else ((a,b,c),(b,d,c)))
    fo=radial_segments*angular_segments; bo=(radial_segments+1)*angular_segments+fo
    for i in range(angular_segments):
        j=(i+1)%angular_segments; triangles.extend(((fo+i,fo+j,bo+i),(fo+j,bo+j,bo+i)))
    return {"position":np.asarray(vertices,np.float32),"normal":np.asarray(normals,np.float32),"uv":np.asarray(uvs,np.float32),"surface":np.asarray(surfaces,np.uint8),"triangles":np.asarray(triangles,np.int32)}


def _bilinear(texture,u,v):
    h,w,_=texture.shape; sx=np.clip(u,0,1)*(w-1); sy=np.clip(v,0,1)*(h-1)
    x0=np.floor(sx).astype(np.int32); y0=np.floor(sy).astype(np.int32); x1=np.minimum(x0+1,w-1); y1=np.minimum(y0+1,h-1)
    fx=(sx-x0)[...,None]; fy=(sy-y0)[...,None]
    return texture[y0,x0]*(1-fx)*(1-fy)+texture[y0,x1]*fx*(1-fy)+texture[y1,x0]*(1-fx)*fy+texture[y1,x1]*fx*fy


@lru_cache(maxsize=256)
def _hits(size, angle_key, config=DEFAULT_CONFIG):
    """Return nearest surface, object coordinates, normals and connected mask."""
    theta=angle_key/1_000_000; c=math.cos(theta); s=math.sin(theta)
    radius=size*config.object_diameter_ratio*.5; cx=cy=(size-1)*.5
    yy,xx=np.mgrid[0:size,0:size].astype(np.float32); X=(xx-cx)/radius; Y=(yy-cy)/radius
    best=np.full((size,size),-1e9,np.float32); sid=np.zeros((size,size),np.uint8)
    ox=np.zeros_like(X); oy=Y.copy(); oz=np.zeros_like(X); nx=np.zeros_like(X); ny=np.zeros_like(X); nz=np.zeros_like(X)

    def accept(valid,x,z,kind,nxo,nyo,nzo):
        depth=-x*s+z*c; take=valid&(depth>best)
        best[take]=depth[take]; sid[take]=kind; ox[take]=x[take]; oz[take]=z[take]
        nx[take]=nxo[take]; ny[take]=nyo[take]; nz[take]=nzo[take]

    # Newton solve X=x*cos(theta)+z(r)*sin(theta) for both smooth caps.
    for function,kind,sign in ((front_depth,SURFACE_FRONT,1.0),(back_depth,SURFACE_BACK,-1.0)):
        x=np.clip(X*c,-1,1)
        for _ in range(config.ray_iterations):
            r=np.sqrt(x*x+Y*Y); z=function(r,config); dz=radial_derivative(function,r,config)
            drdx=np.divide(x,np.maximum(r,1e-6)); f=x*c+z*s-X; df=c+dz*drdx*s
            x=np.clip(x-np.divide(f,df,out=np.zeros_like(f),where=np.abs(df)>1e-4),-1.03,1.03)
        r=np.sqrt(x*x+Y*Y); z=function(r,config); residual=np.abs(x*c+z*s-X)
        valid=(r<=1.0005)&(residual<max(.008,1.8/radius))
        dz=radial_derivative(function,r,config); inv=1/np.sqrt(1+dz*dz)
        if sign>0: nxo=-dz*np.divide(x,np.maximum(r,1e-6))*inv; nyo=-dz*np.divide(Y,np.maximum(r,1e-6))*inv; nzo=inv
        else: nxo=dz*np.divide(x,np.maximum(r,1e-6))*inv; nyo=dz*np.divide(Y,np.maximum(r,1e-6))*inv; nzo=-inv
        accept(valid,x,z,kind,nxo,nyo,nzo)

    # Exact intersection with the radius-one wall. Its z interval connects both caps.
    xr=np.sqrt(np.clip(1-Y*Y,0,1))
    for x in (xr,-xr):
        if abs(s)>1e-5: z=(X-x*c)/s
        else: z=np.zeros_like(X)
        top=front_depth(np.ones_like(X),config); bottom=back_depth(np.ones_like(X),config)
        valid=(np.abs(Y)<=1)&(z>=bottom-1e-4)&(z<=top+1e-4)&(np.abs(x*c+z*s-X)<max(.008,1.8/radius))
        inv=np.ones_like(X); accept(valid,x,z,SURFACE_SIDE,x*inv,Y*inv,np.zeros_like(X))

    # An opaque solid projects to one interval on every active scanline.
    # Numerical root tangencies can leave subpixel gaps near 90/270 degrees;
    # fill only those interior gaps as the visible rolled shell cross-section.
    covered=sid>0; active=covered.any(axis=1); first=np.argmax(covered,axis=1); last=size-1-np.argmax(covered[:,::-1],axis=1)
    fill=active[:,None]&(np.arange(size)[None,:]>=first[:,None])&(np.arange(size)[None,:]<=last[:,None])&~covered
    if np.any(fill):
        side_x=-math.copysign(1.0,s if abs(s)>1e-6 else 1.0)*np.sqrt(np.clip(1-Y*Y,0,1))
        sid[fill]=SURFACE_SIDE; ox[fill]=side_x[fill]; oz[fill]=np.clip((X-side_x*c)/s if abs(s)>1e-6 else 0,back_depth(np.sqrt(side_x*side_x+Y*Y),config),front_depth(np.sqrt(side_x*side_x+Y*Y),config))[fill]
        nx[fill]=side_x[fill]; ny[fill]=Y[fill]; nz[fill]=0

    r=np.sqrt(ox*ox+oy*oy); front=(sid==SURFACE_FRONT)
    # A cap seen at a grazing angle is the rolled shell edge, not readable art.
    # Keeping its geometry while switching its material prevents texture bleed
    # at 90/270 degrees without a discontinuous face on/off threshold.
    view_facing=-nx*s+nz*c
    sid[front&(view_facing<.08)]=SURFACE_RIM
    front=(sid==SURFACE_FRONT)
    inner_start=config.front_art_radius-config.inner_border_ratio
    sid[front&(r>config.front_art_radius)]=SURFACE_RIM
    sid[front&(r>inner_start)&(r<=config.front_art_radius)]=SURFACE_INNER
    return sid,ox,oy,oz,nx,ny,nz,best


def geometry_for_angle(size,theta,config=DEFAULT_CONFIG):
    data=_hits(size,round(theta*1_000_000),config); return data[0]>0,data


def _shade(base,nx,ny,nz,theta,surface,rim,surface_style='glossy'):
    c=math.cos(theta); s=math.sin(theta)
    # Rotate object normals into the fixed studio-light coordinate system.
    vx=nx*c+nz*s; vy=ny; vz=-nx*s+nz*c
    length=np.sqrt(vx*vx+vy*vy+vz*vz); vx/=np.maximum(length,1e-6); vy/=np.maximum(length,1e-6); vz/=np.maximum(length,1e-6)
    light=np.array([-0.38,-0.46,0.80],np.float32); light/=np.linalg.norm(light)
    dot=np.clip(vx*light[0]+vy*light[1]+vz*light[2],0,1)
    diffuse=.91+.09*dot
    # Broad white reflections are additive, so their alpha fringe never darkens.
    rx=2*dot*vx-light[0]; ry=2*dot*vy-light[1]; rz=2*dot*vz-light[2]
    style={
        'glossy':(18,.20,.045),'white-ceramic':(22,.18,.040),
        'brushed-silver-glitter':(15,.14,.032),'surface-holographic':(12,.22,.050),
        'star-holographic':(13,.21,.048),'matte-frosted':(8,.060,.015),
        'fluffy-cookie':(5,.025,.008),
    }.get(surface_style,(18,.20,.045))
    power,strength,secondary=style
    spec=np.clip(rz,0,1)**power*strength + np.clip(vx*(-.30)+vy*(-.20)+vz*.93,0,1)**6*secondary
    rgb=base[...,:3]*diffuse[...,None]+255*spec[...,None]
    metal=(surface==SURFACE_RIM)|(surface==SURFACE_SIDE)|(surface==SURFACE_BACK)
    rgb[metal]=base[metal,:3]*(.78+.22*dot[metal,None])+255*(np.clip(rz[metal],0,1)**28*.36)[:,None]
    return np.clip(rgb,0,255)


def back_texture(size,rim):
    hi,mid,lo=RIM_COLORS[rim]; y,x=np.mgrid[0:size,0:size].astype(np.float32); q=np.sqrt(((x-(size-1)/2)/(size/2))**2+((y-(size-1)/2)/(size/2))**2)
    tone=.96-.045*q+.004*np.cos(q*6*math.pi); a=np.empty((size,size,4),np.float32)
    a[...,:3]=np.array(mid)*tone[...,None]+np.array(hi)*(1-tone[...,None])*.18; a[...,3]=255; return a


def studio_shadow(size,transparent=False,width_scale=1.0):
    sh=Image.new('RGBA',(size,size)); d=ImageDraw.Draw(sh); cx=size*.5; half=size*.225*width_scale
    d.ellipse((cx-half,size*.825,cx+half,size*.872),fill=(18,22,27,70 if transparent else 54))
    return sh.filter(ImageFilter.GaussianBlur(max(1,size*.017)))


def render_model(texture,size,rim='silver',background=(255,255,255,255),transparent=False,theta=0.0,config=DEFAULT_CONFIG,gray_model=False,return_buffers=False,include_shadow=True,surface_style='glossy'):
    """Render the shared curved entity at one yaw angle."""
    sid,x,y,z,nx,ny,nz,depth=_hits(size,round(theta*1_000_000),config); mask=sid>0
    bg=(0,0,0,0) if transparent else background; canvas=Image.new('RGBA',(size,size),bg)
    if include_shadow: canvas=Image.alpha_composite(canvas,studio_shadow(size,transparent,max(.26,abs(math.cos(theta)))))
    out=np.asarray(canvas).copy().astype(np.float32); base=np.zeros((size,size,4),np.float32); base[...,3]=255
    tex=np.asarray(texture.convert('RGBA').resize((max(2,size),max(2,size)),Image.Resampling.LANCZOS),dtype=np.float32)
    r=np.sqrt(x*x+y*y); u=.5+x/(2*config.front_art_radius); v=.5+y/(2*config.front_art_radius)
    front=(sid==SURFACE_FRONT); sampled=_bilinear(tex,u,v); base[front]=sampled[front]
    base[sid==SURFACE_INNER]=(250,250,250,255)
    hi,mid,lo=RIM_COLORS[rim]
    for kind,color in ((SURFACE_RIM,mid),(SURFACE_SIDE,mid)):
        sel=sid==kind; base[sel,:3]=color; base[sel,3]=255
    back=back_texture(size,rim); sel=sid==SURFACE_BACK; base[sel]=back[sel]
    if gray_model:
        base[mask,:3]=(174,177,181); base[(sid==SURFACE_RIM)|(sid==SURFACE_SIDE),:3]=(132,136,141); base[sid==SURFACE_BACK,:3]=(158,161,165)
    lit=_shade(base,nx,ny,nz,theta,sid,rim,surface_style)
    alpha=base[...,3:4]/255; out[mask,:3]=lit[mask]*alpha[mask]+out[mask,:3]*(1-alpha[mask]); out[mask,3]=255 if not transparent else base[mask,3]
    image=Image.fromarray(np.clip(out,0,255).astype(np.uint8),'RGBA')
    if return_buffers:return image,{"mask":mask,"surface":sid,"depth":depth,"position":(x,y,z),"normal":(nx,ny,nz)}
    return image


def render_profile_diagram(size=1000,config=DEFAULT_CONFIG):
    im=Image.new('RGB',(size,size//2),(250,250,252)); d=ImageDraw.Draw(im); r,zf,zb=profile_samples(config,600)
    sx=size*.43; sy=size*2.5; cx=size*.5; cy=size*.27
    def pts(rad,z):return [(cx+float(a)*sx,cy-float(b)*sy) for a,b in zip(rad,z)]
    fp=pts(r,zf); bp=pts(r[::-1],zb[::-1]); d.polygon(fp+bp,fill=(174,178,183),outline=(55,60,66))
    d.line(fp,fill=(55,125,210),width=4); d.line(pts(r,zb),fill=(130,80,165),width=4)
    a=config.front_art_radius; x=cx+a*sx; d.line((x,40,x,size*.44),fill=(215,90,80),width=2)
    d.text((45,35),'V1.5 axisymmetric profile: front dome / rolled rim / wall / shallow back',fill=(25,28,32))
    d.text((cx-size*.34,cy-size*.20),'front dome',fill=(55,105,185)); d.text((x-45,cy-size*.15),'rolled rim',fill=(185,65,55)); d.text((x+12,cy-12),'wall',fill=(55,60,66)); d.text((cx-size*.20,cy+size*.08),'shallow back',fill=(105,60,145))
    return im


validate_geometry()
