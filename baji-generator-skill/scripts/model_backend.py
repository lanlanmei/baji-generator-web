"""Backend selection and unified static/rotation rendering API."""
import math
from pathlib import Path
from PIL import Image
import blender_renderer,glb_renderer
from obj_renderer import MODEL,render_obj
from model_renderer import render_model

BACKENDS=('auto','blender','obj','glb','pillow')

def capabilities():
    return {'blender':blender_renderer.available(),'obj':MODEL.is_file(),'glb':glb_renderer.available(),'pillow':True}

def select_backend(requested='auto',available=None):
    if requested not in BACKENDS: raise ValueError(f'Unsupported backend: {requested}')
    cap=capabilities() if available is None else available
    if requested=='auto':
        for name in ('blender','obj','glb','pillow'):
            if cap.get(name): return name
    elif cap.get(requested): return requested
    if requested=='blender': raise ValueError('Blender backend requested, but Blender is not installed or not discoverable.')
    if requested=='glb': raise ValueError('GLB backend requested, but no validated headless WebGL runtime is available.')
    if requested=='obj': raise ValueError(f'OBJ backend requested, but the fixed model is missing: {MODEL}')
    raise ValueError('No rendering backend is available.')

def _quantize(frames,size):
    rgb=[x.convert('RGB') for x in frames]; swatches=Image.new('RGB',(size*min(8,len(rgb)),size))
    for j in range(min(8,len(rgb))): swatches.paste(rgb[round(j*len(rgb)/min(8,len(rgb)))%len(rgb)],(j*size,0))
    palette=swatches.resize((size,max(1,size//8))).quantize(colors=255,method=Image.Quantize.MEDIANCUT)
    return [f.quantize(palette=palette,dither=Image.Dither.FLOYDSTEINBERG) for f in rgb]

def render_static(texture,size,rim,background,transparent,effect,backend='auto'):
    chosen=select_backend(backend)
    if chosen=='blender': return blender_renderer.render_frames(texture,size,rim,background,transparent,effect,[0.0])[0],chosen
    if chosen=='obj': return render_obj(texture,size,rim,background,transparent,0.0,effect),chosen
    if chosen=='glb': raise ValueError(glb_renderer.unavailable_reason())
    return render_model(texture,size,rim,background,transparent,0.0,surface_style=effect),chosen

def render_rotation(texture,size,rim,background,transparent,effect,frames=58,backend='auto',return_masks=False):
    chosen=select_backend(backend); angles=[2*math.pi*i/frames for i in range(frames)]; masks=[]
    # GIF palette export has no reliable partial alpha; preserve the established
    # compatibility behavior by compositing transparent requests on near-white.
    gif_background=(248,248,248,255) if transparent else background; gif_transparent=False
    if chosen=='blender': rgba=blender_renderer.render_frames(texture,size,rim,gif_background,gif_transparent,effect,angles)
    elif chosen=='obj':
        rgba=[]
        for angle in angles:
            if return_masks:
                image,buffers=render_obj(texture,size,rim,gif_background,gif_transparent,angle,effect,return_buffers=True); masks.append(buffers['mask'])
            else: image=render_obj(texture,size,rim,gif_background,gif_transparent,angle,effect)
            rgba.append(image)
    elif chosen=='glb': raise ValueError(glb_renderer.unavailable_reason())
    else:
        rgba=[]
        for angle in angles:
            if return_masks:
                image,buffers=render_model(texture,size,rim,gif_background,gif_transparent,angle,return_buffers=True,surface_style=effect); masks.append(buffers['mask'])
            else: image=render_model(texture,size,rim,gif_background,gif_transparent,angle,surface_style=effect)
            rgba.append(image)
    result=_quantize(rgba,size)
    return (result,masks,chosen) if return_masks else (result,chosen)
