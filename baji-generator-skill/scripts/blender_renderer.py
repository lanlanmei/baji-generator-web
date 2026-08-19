"""Optional Blender headless backend for the fixed OBJ master."""
from pathlib import Path
import os,shutil,subprocess,tempfile
from PIL import Image

ROOT=Path(__file__).parents[1]
MODEL=ROOT/'assets'/'models'/'badge_master_58mm.obj'
DRIVER=Path(__file__).with_name('blender_scene.py')

def find_blender():
    explicit=os.environ.get('BAJI_BLENDER')
    candidates=[explicit,shutil.which('blender'),shutil.which('blender.exe')]
    base=Path(os.environ.get('ProgramFiles',os.sep))/'Blender Foundation'
    if base.exists(): candidates.extend(str(p) for p in sorted(base.glob('Blender*/blender.exe'),reverse=True))
    return next((str(Path(x)) for x in candidates if x and Path(x).is_file()),None)

def available(): return bool(find_blender() and MODEL.is_file() and DRIVER.is_file())

def render_frames(texture,size,rim,background,transparent,effect,angles):
    exe=find_blender()
    if not exe: raise RuntimeError('Blender backend requested, but blender executable was not found. Use --backend auto, obj, or pillow.')
    with tempfile.TemporaryDirectory(prefix='baji-blender-') as tmp:
        tmp=Path(tmp); texture_path=tmp/'front.png'; texture.convert('RGBA').save(texture_path)
        bg=','.join(str(int(x)) for x in background)
        angle_text=','.join(f'{x:.9f}' for x in angles)
        command=[exe,'--background','--python',str(DRIVER),'--','--model',str(MODEL),'--texture',str(texture_path),'--output',str(tmp),'--size',str(size),'--rim',rim,'--background',bg,'--effect',effect,'--angles',angle_text]
        if transparent: command.append('--transparent')
        result=subprocess.run(command,capture_output=True,text=True,timeout=max(180,45*len(angles)))
        if result.returncode: raise RuntimeError('Blender render failed: '+(result.stderr or result.stdout)[-2000:])
        return [Image.open(tmp/f'frame-{i:04d}.png').convert('RGBA').copy() for i in range(len(angles))]
