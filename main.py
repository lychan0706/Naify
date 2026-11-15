# import
import fastapi
import time
import threading

from concurrent.futures import Future

from Naify.core.cache import CACHE_DIR
from Naify.core.generator import generation_queue
from Naify.core.novelAI import generate_image
from Naify.core.utility import print_log

# FastAPI 앱 생성
app = fastapi.FastAPI(debug=False)

# 서브루틴 선언
def get_or_generate_image(image_id: str, prompt: str) -> bytes:
    # cache에 image_id를 가진 webp 파일 검사
    image_path = CACHE_DIR / f"{image_id}.webp"
    is_cached = image_path.is_file()

    if is_cached:
        print_log(image_id, "getting image from cache")
        image_bytes = get_image_from_cache(image_id)
    else:
        print_log(image_id, "generating")
        future = Future()
        generation_queue.put((image_id, prompt, future))
        image_bytes = future.result()

    return image_bytes

def generation_worker() -> None:
    while True:
        image_id, prompt, future = generation_queue.get()

        try:
            image_path = CACHE_DIR / f"{image_id}.webp"

            if image_path.is_file():
                image_bytes = get_image_from_cache(image_id)
            else:
                image_bytes = generate_image(image_id, prompt)
                save_image_to_cache(image_id, image_bytes)

            future.set_result(image_bytes)

        except Exception as e:
            future.set_exception(e)

        finally:
            generation_queue.task_done()

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

    if image_id == "virtual": 
        return
    
    image_path = CACHE_DIR / f"{image_id}.webp"
    image_path.write_bytes(image_bytes)

    return

# 라우트 선언
@app.get("/get_image/{image_id}")
def get_image(image_id: str, prompt: str) -> fastapi.Response:
    """
    이미지 요청에 대한 라우트

    Returns:
        fastapi.Response: WebP 이미지가 포함된 HTTP 응답.
    """
    image_bytes: bytes
    requested_webp: fastapi.Response

    process_initiation_time = time.perf_counter()

    print_log(image_id, "Requested")

    image_bytes = get_or_generate_image(image_id=image_id, prompt=prompt)
    requested_webp = fastapi.Response(
        content=image_bytes,
        media_type="image/webp"
    )

    process_termination_time = time.perf_counter()
    total_elapsed = process_termination_time - process_initiation_time
    print_log(image_id, f"{round(total_elapsed,2)}sec")

    return requested_webp

worker_thread = threading.Thread(
    target=generation_worker,
    daemon=True
)

worker_thread.start()

# 서버 실행
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True, access_log=False)

# url : http://127.0.0.1:8000/get_image/A00001?prompt=girl