"""Store and read Naify regeneration requests in WebP EXIF XPComment.

The original NovelAI EXIF/XMP is preserved separately by the optimizer.
No API keys or server paths are written to an image.
"""
import json
from io import BytesIO

from PIL import Image

from core.naify_config import NaifyConfig


COMMENT_TAG = 40092  # EXIF XPComment; leaves NovelAI UserComment untouched
COMMENT_PREFIX = b"ASCII\x00\x00\x00Naify:"
MAX_COMMENT_BYTES = 256 * 1024


def make_regeneration_metadata(
    prompt: str, char1: str, char2: str, char3: str, config: NaifyConfig
) -> dict:
    """Snapshot every generation-affecting setting, not sensitive data."""
    return {
        "schema": 1,
        "prompt": prompt,
        "char1": char1,
        "char2": char2,
        "char3": char3,
        "generation": config.generation.model_dump(mode="json"),
        "prompt_settings": config.prompt.model_dump(mode="json"),
    }


def encode_regeneration_metadata(metadata: dict) -> bytes:
    """Windows XPComment is UTF-16LE; never overwrite NovelAI UserComment."""
    return (COMMENT_PREFIX + json.dumps(
        metadata, ensure_ascii=False, separators=(",", ":")
    )).encode("utf-16le") + b"\\x00\\x00"


def read_regeneration_metadata(image_bytes: bytes) -> dict | None:
    """Return validated metadata, or None for old/invalid cached images."""
    try:
        with Image.open(BytesIO(image_bytes)) as image:
            comment = image.getexif().get(COMMENT_TAG)
        if not isinstance(comment, bytes) or len(comment) > MAX_COMMENT_BYTES:
            return None
        text = comment.decode("utf-16le").rstrip("\\x00")
        if not text.startswith(COMMENT_PREFIX):
            return None
        data = json.loads(text[len(COMMENT_PREFIX):])
        if not isinstance(data, dict) or data.get("schema") != 1:
            return None
        for key in ("prompt", "char1", "char2", "char3"):
            if not isinstance(data.get(key), str):
                return None
        config = NaifyConfig.model_validate({
            "generation": data["generation"],
            "prompt": data["prompt_settings"]
        })
        return {
            "prompt": data["prompt"], "char1": data["char1"],
            "char2": data["char2"], "char3": data["char3"],
            "config": config,
        }
    except (KeyError, ValueError, TypeError, UnicodeError, OSError):
        return None
