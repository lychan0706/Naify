"""Newly generated WebP images: strip EXIF/XMP and encode at quality 80."""
from io import BytesIO

from PIL import Image


WEBP_QUALITY = 80
WEBP_METHOD = 4


def optimize_image(image_bytes: bytes) -> bytes:
    """Re-encode a generated image once, preserving its dimensions and ICC profile."""
    with Image.open(BytesIO(image_bytes)) as image:
        if getattr(image, "n_frames", 1) != 1:
            raise ValueError("Animated WebP is not supported for cache optimization")
        icc_profile = image.info.get("icc_profile")
        with BytesIO() as output:
            options = {"format": "WEBP", "quality": WEBP_QUALITY, "method": WEBP_METHOD}
            if icc_profile:
                options["icc_profile"] = icc_profile
            image.save(output, **options)
            return output.getvalue()
