"""Deterministic procedural badge surface materials."""
import math, random
from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter

EFFECTS = ("glossy", "white-ceramic", "brushed-silver-glitter", "surface-holographic", "star-holographic", "matte-frosted", "fluffy-cookie")


def _noise(size, seed, low=0, high=255, blur=0):
    rng = random.Random(seed)
    im = Image.new("L", (size, size)); im.putdata([rng.randint(low, high) for _ in range(size * size)])
    return im.filter(ImageFilter.GaussianBlur(blur)) if blur else im


def _overlay(base, color, alpha):
    layer = Image.new("RGBA", base.size, (*color, alpha))
    return Image.alpha_composite(base, layer)


def apply_material(art, effect, seed=42):
    n = art.width; rng = random.Random(seed); out = art.copy()
    if effect == "glossy":
        return out
    if effect == "white-ceramic":
        out = ImageEnhance.Color(out).enhance(.88); out = _overlay(out, (245, 248, 250), 48)
        glaze = Image.new("RGBA", out.size); d = ImageDraw.Draw(glaze); d.ellipse((-n*.05, -n*.18, n*.76, n*.54), fill=(255,255,255,42))
        return Image.alpha_composite(out, glaze.filter(ImageFilter.GaussianBlur(n*.06)))
    if effect == "brushed-silver-glitter":
        out = ImageEnhance.Color(out).enhance(.65); out = _overlay(out, (210,218,224), 55)
        tex = Image.new("RGBA", out.size); d = ImageDraw.Draw(tex)
        for y in range(0,n,max(2,n//260)):
            a=rng.randint(4,22); d.line((0,y,n,y+rng.choice((-1,0,1))),fill=(255,255,255,a),width=1)
        for _ in range(n//2):
            x,y=rng.randrange(n),rng.randrange(n); a=rng.randint(30,105); d.point((x,y),fill=(255,255,255,a))
        return Image.alpha_composite(out, tex)
    if effect in ("surface-holographic", "star-holographic"):
        holo=Image.new("RGBA",out.size); d=ImageDraw.Draw(holo)
        palette=((255,90,150),(70,210,255),(255,220,70),(155,90,255),(100,255,190))
        for i in range(30 if effect=="surface-holographic" else 18):
            x,y=rng.randrange(n),rng.randrange(n); s=rng.randrange(max(8,n//80),max(16,n//16)); c=palette[(x+y)//max(1,n//5)%len(palette)]
            d.polygon([(x,y-s),(x+s,y),(x,y+s),(x-s,y)],fill=(*c,rng.randint(12,36)))
        if effect == "star-holographic":
            for _ in range(34):
                x,y=rng.randrange(n),rng.randrange(n); ro=rng.randrange(max(6,n//110),max(12,n//35)); ri=ro*.42
                pts=[]
                for k in range(10):
                    a=-math.pi/2+k*math.pi/5; r=ro if k%2==0 else ri; pts.append((x+math.cos(a)*r,y+math.sin(a)*r))
                c=rng.choice(palette); d.polygon(pts,fill=(*c,rng.randint(35,85)))
        return Image.alpha_composite(_overlay(out,(225,232,238),20),holo.filter(ImageFilter.GaussianBlur(.35)))
    if effect == "matte-frosted":
        out=ImageEnhance.Color(out).enhance(.72); out=_overlay(out,(180,190,200),42)
        grain=_noise(n,seed+11,95,160,.45); grain.putalpha(grain.point(lambda p: 25))
        return Image.alpha_composite(out,grain.convert("RGBA"))
    if effect == "fluffy-cookie":
        out=ImageEnhance.Color(out).enhance(.82); out=_overlay(out,(245,194,128),48)
        fur=Image.new("RGBA",out.size); d=ImageDraw.Draw(fur)
        for _ in range(n*3):
            x,y=rng.randrange(n),rng.randrange(n); ln=rng.randint(1,max(2,n//170)); d.line((x,y,x+rng.choice((-1,0,1)),y+ln),fill=(255,231,189,rng.randint(12,38)))
        return Image.alpha_composite(out,fur)
    raise ValueError(f"Unsupported effect: {effect}")
