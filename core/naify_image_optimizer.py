"""Newly generated WebP images: preserve original metadata and encode at quality 80."""
from io import BytesIO

from PIL import Image


WEBP_QUALITY = 80
WEBP_METHOD = 4


def optimize_image(image_bytes: bytes) -> bytes:
    """Re-encode a generated image once, preserving its dimensions, EXIF, XMP and ICC profile."""
    with Image.open(BytesIO(image_bytes)) as image:
        if getattr(image, "n_frames", 1) != 1:
            raise ValueError("Animated WebP is not supported for cache optimization")
        with BytesIO() as output:
            options = {"format": "WEBP", "quality": WEBP_QUALITY, "method": WEBP_METHOD}
            for metadata_key in ("exif", "xmp", "icc_profile"):
                metadata = image.info.get(metadata_key)
                if metadata:
                    options[metadata_key] = metadata
            image.save(output, **options)
            return output.getvalue()
