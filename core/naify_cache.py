from pathlib import Path
from typing import Final
from core.naify_utility import print_log
from core.naify_config import CacheConfig

CACHE_DIR: Final[Path] = Path(__file__).resolve().parent.parent / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def get_image_from_cache(image_id: str) -> bytes:
    """
    캐시에 저장된 WebP 이미지의 바이너리 데이터를 읽는다.

    Args:
        image_id: 이미지의 고유 식별자.

    Returns:
        bytes: 캐시에서 읽은 WebP 데이터.
    """
    image_path = CACHE_DIR / f"{image_id}.webp"
    image_bytes = image_path.read_bytes()

    return image_bytes


def save_image_to_cache(image_id: str, image_bytes: bytes) -> None:

    image_path = CACHE_DIR / f"{image_id}.webp"
    image_path.write_bytes(image_bytes)

    return

def get_cache_size() -> int:
    cache_size: int = 0
    cache_images = CACHE_DIR.glob("*.webp")

    for cache_image in cache_images:
        cache_size += cache_image.stat().st_size
    
    return cache_size

def trim_cache(cache_config: CacheConfig) -> None:
    cache_size = get_cache_size()
    cache_images = CACHE_DIR.glob("*.webp")
    
    cache_images = sorted(
        cache_images, 
        key=lambda cache_image: cache_image.stat().st_mtime,
        reverse=True
    )
    
    while (cache_size > cache_config.max_cache_size or len(cache_images) > cache_config.max_images) and cache_images:
        oldest_image = cache_images.pop()
        cache_size -= oldest_image.stat().st_size
        oldest_image.unlink()

        print_log(content=f"Deleted cache: {oldest_image.name}")