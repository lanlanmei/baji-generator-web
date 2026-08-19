import io
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_BYTES = 10 * 1024 * 1024
MAX_PIXELS = 36_000_000
FORMATS = {"PNG", "JPEG", "WEBP", "GIF"}

class UploadProblem(ValueError):
    pass

def validate_image(data: bytes) -> Image.Image:
    if len(data) > MAX_BYTES:
        raise UploadProblem("图片不能超过10MB，请重新选择。")
    try:
        Image.MAX_IMAGE_PIXELS = MAX_PIXELS
        with Image.open(io.BytesIO(data)) as source:
            if source.format not in FORMATS:
                raise UploadProblem("暂不支持这种图片格式，请上传 PNG、JPG、JPEG、WebP 或 GIF 图片。")
            if source.width * source.height > MAX_PIXELS:
                raise UploadProblem("图片尺寸过大，请选择较小的图片。")
            if getattr(source, "is_animated", False):
                source.seek(0)
            return ImageOps.exif_transpose(source).convert("RGBA").copy()
    except UploadProblem:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise UploadProblem("暂不支持这种图片格式，请上传 PNG、JPG、JPEG、WebP 或 GIF 图片。")
