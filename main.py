# import
import fastapi
import time
import threading
from core import image_fetcher 
from core.utility import print_log

# FastAPI 앱 생성
app = fastapi.FastAPI(debug=False)

# 라우트 선언
@app.get("/get_image")
def get_image(prompt: str) -> fastapi.Response:
    """
    이미지 요청에 대한 라우트

    Returns:
        fastapi.Response: WebP 이미지가 포함된 HTTP 응답.
    """
    image_bytes: bytes
    requested_webp: fastapi.Response
    image_id: str = image_fetcher.make_image_id(prompt)

    process_initiation_time = time.perf_counter()

    print_log(image_id, "Requested")

    image_bytes = image_fetcher.get_or_generate_image(image_id=image_id, prompt=prompt)
    requested_webp = fastapi.Response(
        content=image_bytes,
        media_type="image/webp"
    )

    process_termination_time = time.perf_counter()
    total_elapsed = process_termination_time - process_initiation_time
    print_log(image_id, f"{round(total_elapsed,2)}sec")

    return requested_webp

# 스레드 설정
worker_thread = threading.Thread(
    target=image_fetcher.generation_request_worker,
    daemon=True
)

worker_thread.start()

# 서버 실행
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True, access_log=False)

# url : http://127.0.0.1:8000/get_image/A00001?prompt=girl