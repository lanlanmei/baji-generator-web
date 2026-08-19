"""Local heuristic square composition (not semantic AI recognition)."""
from PIL import Image, ImageChops, ImageFilter, ImageOps, ImageStat


def load_image(path):
    with Image.open(path) as source:
        if getattr(source, "is_animated", False):
            source.seek(0)
        return ImageOps.exif_transpose(source).convert("RGBA").copy()


def _content_box(im):
    alpha = im.getchannel("A")
    if alpha.getextrema()[0] < 250:
        box = alpha.point(lambda p: 255 if p > 12 else 0).getbbox()
        if box:
            return box
    thumb = ImageOps.contain(im.convert("RGB"), (256, 256))
    gray = ImageOps.grayscale(thumb).filter(ImageFilter.FIND_EDGES).filter(ImageFilter.GaussianBlur(2))
    threshold = max(20, int(ImageStat.Stat(gray).mean[0] * 1.6))
    box = gray.point(lambda p: 255 if p > threshold else 0).getbbox()
    if box:
        sx, sy = im.width / thumb.width, im.height / thumb.height
        return tuple(int(v * (sx if i % 2 == 0 else sy)) for i, v in enumerate(box))
    return (0, 0, im.width, im.height)


def square_crop(im, padding=0.12):
    """Crop to 1:1 around alpha/edge visual mass, then use stable center fallback."""
    w, h = im.size
    if w == h:
        return im.copy()
    l, t, r, b = _content_box(im)
    cx, cy = (l + r) / 2, (t + b) / 2
    subject = max(r - l, b - t)
    side = min(w, h)
    if subject < side:
        side = min(side, max(subject * (1 + 2 * padding), side * 0.72))
    left = min(max(cx - side / 2, 0), w - side)
    top = min(max(cy - side / 2, 0), h - side)
    return im.crop((round(left), round(top), round(left + side), round(top + side)))
