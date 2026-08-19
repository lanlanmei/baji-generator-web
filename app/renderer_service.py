import sys
from pathlib import Path
from PIL import Image, ImageColor

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "baji-generator-skill" / "scripts"
sys.path.insert(0, str(SCRIPTS))
from enhance import prepare
from materials import EFFECTS, apply_material
from model_backend import render_static
from animation import save_rotation

BACKGROUNDS = {
    "white":"#ffffff", "transparent":"#00000000", "soft-black":"#25272b",
    "light-gray":"#e9eaec", "mist-pink":"#ead9dc", "cream":"#eee5d2",
    "sage":"#d8dfd1", "gray-blue":"#d6dfe7", "pale-yellow":"#eee7bf",
    "soft-peach":"#ecd8c9", "pale-purple":"#dfd8e8"
}
RIMS = {"silver", "gold", "black"}

def render_job(image: Image.Image, effect: str, rim: str, background: str, output: Path,
               animation_size: int = 640, animation_frames: int = 58) -> tuple[Path, Path]:
    if effect not in EFFECTS or rim not in RIMS or background not in BACKGROUNDS:
        raise ValueError("样式参数无效。")
    output.mkdir(parents=True, exist_ok=True)
    work, _ = prepare(image, 1024)
    surface = apply_material(work, effect, 42)
    bg = ImageColor.getcolor(BACKGROUNDS[background], "RGBA")
    transparent = bg[3] == 0
    png = output / f"baji-{effect}-{rim}-{background}.png"
    gif = output / f"baji-{effect}-{rim}-{background}.gif"
    result, chosen = render_static(surface, 1024, rim, bg, transparent, effect, "obj")
    if chosen != "obj":
        raise RuntimeError("OBJ renderer unavailable")
    result.save(png, "PNG", optimize=True)
    anim_art = surface.resize((animation_size, animation_size), Image.Resampling.LANCZOS)
    save_rotation(gif, anim_art, animation_size, rim, bg, transparent, (255,255,255,255),
                  animation_frames, 40, "obj", effect)
    return png, gif
