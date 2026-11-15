from concurrent.futures import Future
from queue import Queue
from hashlib import sha256
from core.cache import CACHE_DIR, get_image_from_cache
from core.novelAI import generate_image
from core.utility import print_log
from core.cache import save_image_to_cache
from core.config import NaifyConfig


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


def generation_request_worker() -> None:
    while True:
        image_id, config, prompt, future = generation_request_queue.get()

        try:
            image_path = CACHE_DIR / f"{image_id}.webp"

            if image_path.is_file():
                image_bytes = get_image_from_cache(image_id)
            else:
                image_bytes = generate_image(image_id, config, prompt)
                save_image_to_cache(image_id, image_bytes)

            future.set_result(image_bytes)

        except Exception as e:
            future.set_exception(e)

        finally:
            generation_request_queue.task_done()

def make_image_id(prompt: str) -> str:
    image_id = sha256(prompt.encode("utf-8")).hexdigest()

    return image_id