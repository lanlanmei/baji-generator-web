"""Local CPU renderer for the fixed 58 mm OBJ master and rear hardware."""
from functools import lru_cache
from pathlib import Path
import math
import numpy as np
from PIL import Image
from model_renderer import MASTER_CONFIG,render_model

ROOT=Path(__file__).parents[1]
MODEL=ROOT/'assets'/'models'/'badge_master_58mm.obj'
ACCESSORY_SURFACE=6
ACCESSORY_GROUPS={'pin_needle','pin_hinge','pin_clasp','hinge_foot','clasp_foot'}

@lru_cache(maxsize=2)
def load_accessory_mesh(path=str(MODEL)):
    vertices=[]; faces=[]; group=''
    with Path(path).open(encoding='utf-8') as handle:
        for line in handle:
            parts=line.split()
            if not parts: continue
            if parts[0]=='v': vertices.append(tuple(map(float,parts[1:4])))
            elif parts[0]=='g': group=parts[1]
            elif parts[0]=='f' and group in ACCESSORY_GROUPS:
                idx=[int(x.split('/')[0])-1 for x in parts[1:]]
                for i in range(1,len(idx)-1): faces.append((idx[0],idx[i],idx[i+1]))
    source=np.asarray(vertices,np.float32); tri=np.asarray(faces,np.int32)
    # OBJ X is depth, Y/Z are the 58 mm face. Renderer uses x/y/z.
    position=np.column_stack((source[:,1],source[:,2],source[:,0])).astype(np.float32)/29.0
    normal=np.zeros_like(position)
    fn=np.cross(position[tri[:,1]]-position[tri[:,0]],position[tri[:,2]]-position[tri[:,0]])
    for corner in range(3): np.add.at(normal,tri[:,corner],fn)
    normal/=np.maximum(np.linalg.norm(normal,axis=1,keepdims=True),1e-8)
    return position,normal,tri

def model_metadata(path=MODEL):
    position,normal,tri=load_accessory_mesh(str(path)); all_vertices=[]; groups=set(); materials=set(); mtl=None
    with Path(path).open(encoding='utf-8') as handle:
        for line in handle:
            p=line.split()
            if not p: continue
            if p[0]=='v': all_vertices.append(tuple(map(float,p[1:4])))
            elif p[0]=='g': groups.add(p[1])
            elif p[0]=='usemtl': materials.add(p[1])
            elif p[0]=='mtllib': mtl=p[1]
    v=np.asarray(all_vertices,np.float32)
    return {'vertices':len(v),'accessory_triangles':len(tri),'bounds_min':v.min(0),'bounds_max':v.max(0),'groups':groups,'materials':materials,'mtllib':mtl}

def _rasterize_accessories(image,buffers,size,theta):
    position,normal,tri=load_accessory_mesh(); c=math.cos(theta); s=math.sin(theta)
    px=position[:,0]*c+position[:,2]*s; py=position[:,1]; depth=-position[:,0]*s+position[:,2]*c
    nx=normal[:,0]*c+normal[:,2]*s; ny=normal[:,1]; nz=-normal[:,0]*s+normal[:,2]*c
    radius=size*MASTER_CONFIG.object_diameter_ratio*.5; center=(size-1)*.5
    sx=center+px*radius; sy=center+py*radius
    out=np.asarray(image).copy(); zbuf=buffers['depth'].copy(); surface=buffers['surface'].copy(); mask=buffers['mask'].copy()
    light=np.array([-.38,-.46,.80],np.float32); light/=np.linalg.norm(light)
    for face in tri:
        x0,x1,x2=sx[face]; y0,y1,y2=sy[face]
        xmin=max(0,int(math.floor(min(x0,x1,x2)))); xmax=min(size-1,int(math.ceil(max(x0,x1,x2))))
        ymin=max(0,int(math.floor(min(y0,y1,y2)))); ymax=min(size-1,int(math.ceil(max(y0,y1,y2))))
        if xmax<xmin or ymax<ymin: continue
        den=(y1-y2)*(x0-x2)+(x2-x1)*(y0-y2)
        if abs(den)<1e-7: continue
        yy,xx=np.mgrid[ymin:ymax+1,xmin:xmax+1].astype(np.float32); xx+=.5; yy+=.5
        a=((y1-y2)*(xx-x2)+(x2-x1)*(yy-y2))/den; b=((y2-y0)*(xx-x2)+(x0-x2)*(yy-y2))/den; w=1-a-b
        inside=(a>=-1e-5)&(b>=-1e-5)&(w>=-1e-5)
        if not np.any(inside): continue
        dep=a*depth[face[0]]+b*depth[face[1]]+w*depth[face[2]]; local=zbuf[ymin:ymax+1,xmin:xmax+1]; take=inside&(dep>local+1e-5)
        if not np.any(take): continue
        nnx=a*nx[face[0]]+b*nx[face[1]]+w*nx[face[2]]; nny=a*ny[face[0]]+b*ny[face[1]]+w*ny[face[2]]; nnz=a*nz[face[0]]+b*nz[face[1]]+w*nz[face[2]]
        length=np.sqrt(nnx*nnx+nny*nny+nnz*nnz); nnx/=np.maximum(length,1e-6); nny/=np.maximum(length,1e-6); nnz/=np.maximum(length,1e-6)
        flip=nnz<0; nnx=np.where(flip,-nnx,nnx); nny=np.where(flip,-nny,nny); nnz=np.where(flip,-nnz,nnz)
        diffuse=np.clip(nnx*light[0]+nny*light[1]+nnz*light[2],0,1); spec=np.clip(nnz,0,1)**28
        color=np.clip(np.array([151,158,164])[None,None,:]*(.72+.28*diffuse[...,None])+255*(.24*spec[...,None]),0,255).astype(np.uint8)
        tile=out[ymin:ymax+1,xmin:xmax+1]; tile[take,:3]=color[take]; tile[take,3]=255; local[take]=dep[take]
        st=surface[ymin:ymax+1,xmin:xmax+1]; st[take]=ACCESSORY_SURFACE; mm=mask[ymin:ymax+1,xmin:xmax+1]; mm[take]=True
    result=Image.fromarray(out,'RGBA'); updated=dict(buffers); updated.update(mask=mask,surface=surface,depth=zbuf)
    return result,updated

def render_obj(texture,size,rim='silver',background=(255,255,255,255),transparent=False,theta=0.0,effect='glossy',gray_model=False,return_buffers=False):
    if not MODEL.is_file(): raise FileNotFoundError(f'Missing fixed OBJ model: {MODEL}')
    image,buffers=render_model(texture,size,rim,background,transparent,theta,MASTER_CONFIG,gray_model,True,True,effect)
    # Rear hardware is fully occluded for the frontal half except near the side.
    if math.cos(theta)<.34: image,buffers=_rasterize_accessories(image,buffers,size,theta)
    return (image,buffers) if return_buffers else image
