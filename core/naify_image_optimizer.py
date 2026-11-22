"""Re-encode new WebP images at the configured quality with their metadata."""
from io import BytesIO

from PIL import Image

from core.naify_regeneration import COMMENT_TAG, encode_regeneration_metadata


WEBP_METHOD = 4


def optimize_image(image_bytes: bytes, quality: int = 90, metadata: dict | None = None) -> bytes:
    """Preserve EXIF/XMP/ICC and optionally add Naify regeneration metadata."""
    if not 1 <= quality <= 100:
        raise ValueError("WebP quality must be between 1 and 100")

    with Image.open(BytesIO(image_bytes)) as image:
        if getattr(image, "n_frames", 1) != 1:
            raise ValueError("Animated WebP is not supported for cache optimization")
        options = {"format": "WEBP", "quality": quality, "method": WEBP_METHOD}
        for key in ("xmp", "icc_profile"):
            value = image.info.get(key)
            if value:
                options[key] = value

        if metadata is not None:
            exif = image.getexif()
            exif[COMMENT_TAG] = encode_regeneration_metadata(metadata)
            options["exif"] = exif.tobytes()
        elif image.info.get("exif"):
            options["exif"] = image.info["exif"]

        with BytesIO() as output:
            image.save(output, **options)
            return output.getvalue()
