#!/usr/bin/env python3
"""CLI entry point for baji-generator V1.5 shared curved-model rendering."""
import argparse, json, sys
from pathlib import Path
from PIL import Image, ImageColor

sys.path.insert(0,str(Path(__file__).parent))
from crop import load_image, square_crop
from enhance import prepare
from materials import EFFECTS, apply_material
from model_backend import BACKENDS,render_static,select_backend
from export import unique_output, animation_output
from animation import save_rotation

MAX_BYTES=10*1024*1024
BACKGROUNDS={"white":"#ffffff","transparent":"#00000000","soft-black":"#25272b","light-gray":"#e9eaec","mist-pink":"#ead9dc","cream":"#eee5d2","sage":"#d8dfd1","gray-blue":"#d6dfe7","pale-yellow":"#eee7bf","soft-peach":"#ecd8c9","pale-purple":"#dfd8e8","纯白":"#ffffff","透明":"#00000000","柔黑":"#25272b","浅灰":"#e9eaec","雾粉":"#ead9dc","奶油米":"#eee5d2","鼠尾草绿":"#d8dfd1","灰蓝":"#d6dfe7","淡黄":"#eee7bf","柔杏桃":"#ecd8c9","淡紫":"#dfd8e8"}
ALIASES={"光面":"glossy","白瓷":"white-ceramic","拉丝银葱":"brushed-silver-glitter","表面镭射":"surface-holographic","星星镭射":"star-holographic","哑光磨砂":"matte-frosted","毛绒饼干":"fluffy-cookie"}
RIM_ALIASES={"银色":"silver","金色":"gold","黑色":"black"}

def parse_color(value):
    value=BACKGROUNDS.get(value,value)
    try:return ImageColor.getcolor(value,"RGBA")
    except ValueError as e:raise argparse.ArgumentTypeError(f"Unsupported background/color: {value}") from e

def parse_inner(value):
    try:return ImageColor.getcolor(value,"RGBA")
    except ValueError as e:raise argparse.ArgumentTypeError(f"Invalid inner border color: {value}") from e

def build_parser():
    p=argparse.ArgumentParser(description="Render realistic circular button badge product images.")
    p.add_argument("inputs",nargs="+"); p.add_argument("--effects",nargs="+",default=None); p.add_argument("--preset",action="append",default=None,help="Single material preset; repeat for multiple presets.")
    p.add_argument("--rim",default="silver"); p.add_argument("--background",default="white")
    p.add_argument("--size",type=int,choices=(1024,2048,4096),default=1024); p.add_argument("--output",default="outputs")
    p.add_argument("--seed",type=int,default=42); p.add_argument("--inner-border-color",type=parse_inner,default=(255,255,255,255))
    anim=p.add_mutually_exclusive_group(); anim.add_argument("--animation",dest="animation",action="store_true"); anim.add_argument("--no-animation",dest="animation",action="store_false")
    p.set_defaults(animation=True); p.add_argument("--animation-size",type=int,default=640); p.add_argument("--animation-frames",type=int,default=58); p.add_argument("--animation-duration",type=int,default=40)
    p.add_argument("--backend",choices=BACKENDS,default="auto",help="auto: Blender, then local OBJ 3D, then GLB/WebGL, then Pillow compatibility mode.")
    p.add_argument("--preview",action="store_true",help="Print composition diagnostics.")
    return p

def render_one(path,args):
    path=Path(path)
    if not path.is_file():raise ValueError(f"Input does not exist: {path}")
    if path.stat().st_size>MAX_BYTES:raise ValueError(f"Input exceeds 10MB limit: {path}")
    if path.suffix.lower() not in {'.png','.jpg','.jpeg','.webp','.gif'}:raise ValueError(f"Unsupported input format: {path.suffix or '(none)'}")
    try:im=load_image(path)
    except Exception as e:raise ValueError(f"Cannot read image {path}: {e}") from e
    square=square_crop(im); work,pixel=prepare(square,max(1024,args.size))
    rim=RIM_ALIASES.get(args.rim,args.rim)
    if rim not in ('silver','gold','black'):raise ValueError(f"Unsupported rim: {args.rim}")
    bg=parse_color(args.background); transparent=bg[3]==0; results=[]
    requested=args.effects if args.effects is not None else (args.preset if args.preset else list(EFFECTS))
    chosen=select_backend(args.backend)
    if chosen=='pillow': print('warning: using Pillow/NumPy compatibility mode; real rear-pin 3D is unavailable.',file=sys.stderr)
    for raw in requested:
        effect=ALIASES.get(raw,raw)
        if effect not in EFFECTS:raise ValueError(f"Unsupported effect: {raw}")
        surface=apply_material(work,effect,args.seed)
        result,_=render_static(surface,args.size,rim,bg,transparent,effect,chosen)
        dest=unique_output(args.output,path.stem,effect,rim,args.background,args.size); result.save(dest,"PNG",optimize=True); results.append(dest)
        if args.animation:
            if not 128 <= args.animation_size <= 1024: raise ValueError("Animation size must be 128..1024")
            if not 8 <= args.animation_frames <= 120: raise ValueError("Animation frames must be 8..120")
            if not 20 <= args.animation_duration <= 500: raise ValueError("Animation duration must be 20..500 ms")
            gif=animation_output(dest); anim_art=surface.resize((args.animation_size,args.animation_size),Image.Resampling.LANCZOS); save_rotation(gif,anim_art,args.animation_size,rim,bg,transparent,args.inner_border_color,args.animation_frames,args.animation_duration,chosen,effect); results.append(gif)
    if args.preview:print(json.dumps({"input":str(path),"crop":square.size,"pixel_art":pixel,"backend":chosen},ensure_ascii=False))
    return results

def main(argv=None):
    args=build_parser().parse_args(argv); outputs=[]
    try:
        for item in args.inputs:outputs.extend(render_one(item,args))
    except ValueError as e:print(f"error: {e}",file=sys.stderr); return 2
    for p in outputs:print(p)
    return 0

if __name__=='__main__':raise SystemExit(main())
