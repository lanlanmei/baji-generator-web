"""Gentle local upscaling and sharpening."""
from PIL import Image, ImageFilter


def is_pixel_art(im):
    sample = im.convert("RGB").resize((min(128, im.width), min(128, im.height)))
    colors = sample.getcolors(sample.width * sample.height)
    return bool(colors and len(colors) <= 96 and min(im.size) <= 512)


def prepare(im, size):
    pixel = is_pixel_art(im)
    method = Image.Resampling.NEAREST if pixel else Image.Resampling.LANCZOS
    out = im.resize((size, size), method)
    if not pixel and min(im.size) < size:
        out = out.filter(ImageFilter.UnsharpMask(radius=1.2, percent=75, threshold=4))
    return out, pixel
