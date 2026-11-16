from concurrent.futures import Future
from queue import Queue
from hashlib import sha256
from core.naify_cache import CACHE_DIR, get_image_from_cache
from core.naify_api_work import generate_image
from core.naify_utility import print_log
from core import naify_cache
from core.naify_config import NaifyConfig
import time


generation_request_queue = Queue()


def fetch_image(image_id: str, config: NaifyConfig, prompt: str) -> bytes:
    # cache에 image_id를 가진 webp 파일 검사
    image_path = CACHE_DIR / f"{image_id}.webp"
    is_cached = image_path.is_file()

    if is_cached:
        print_log(image_id, "getting image from cache")
        image_bytes = get_image_from_cache(image_id)
    else:
        print_log(image_id, "generating")
        future = Future()
        generation_request_queue.put((image_id, config, prompt, future))
        image_bytes = future.result()

    return image_bytes


def generation_request_queue_processor() -> None:
    """
    이미지 생성 요청 큐의 요청들을 관리하는 함수.
    캐시를 재조회해 중복 생성을 막는다.
    """
    while True:
        image_id, config, prompt, future = generation_request_queue.get()

        try:
            image_path = CACHE_DIR / f"{image_id}.webp"

            if image_path.is_file():
                image_bytes = get_image_from_cache(image_id)
            else:
                image_bytes = generate_image(config, prompt)
                naify_cache.save_image_to_cache(image_id, image_bytes)
                naify_cache.trim_cache(config.cache)
                time.sleep(0.5)

            future.set_result(image_bytes)

        except Exception as e:
            future.set_exception(e)

        finally:
            generation_request_queue.task_done()

def make_image_id(prompt: str) -> str:
    image_id = sha256(prompt.encode("utf-8")).hexdigest()

    return image_id