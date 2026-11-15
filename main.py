# import
import fastapi
import time
import threading
from core import naify_image_fetcher 
from core.naify_utility import print_log
# from core.naify_api_work import get_anlas_balance
from core.naify_config import NaifyConfig, load_config, save_config
from fastapi.responses import FileResponse
from fastapi import Body

# FastAPI 앱 생성
app = fastapi.FastAPI(debug=False)

# Config 가져오기
naify_config: NaifyConfig = load_config()

# 라우트 선언
@app.get("/")
def home() -> FileResponse:

    print_log(content="got home request")

    response: FileResponse = FileResponse("web/index.html")

    return response

@app.get("/config")
def get_config() -> fastapi.Response:

    print_log(content="got config request")

    config = naify_config

    return config

@app.put("/config")
def update_config(config: NaifyConfig) -> None:
    global naify_config
    
    naify_config = config

    save_config(naify_config)

    print_log(content="config updated")

@app.get("/get_image")
def get_image(prompt: str) -> fastapi.Response:
    """
    이미지 요청에 대한 라우트

    Returns:
        fastapi.Response: WebP 이미지가 포함된 HTTP 응답.
    """
    # 이미지 id 생성
    image_id: str = naify_image_fetcher.make_image_id(prompt)

    # 초기 상태 기록
    process_initiation_time = time.perf_counter()

    print_log(image_id, "Requested")

    # 이미지 제공
    image_bytes = naify_image_fetcher.fetch_image(image_id=image_id, config=naify_config, prompt=prompt)
    requested_webp = fastapi.Response(
        content=image_bytes,
        media_type="image/webp"
    )

    # 소요 시간 계산
    process_termination_time = time.perf_counter()
    total_elapsed = process_termination_time - process_initiation_time
    print_log(image_id, f"{round(total_elapsed,2)}sec")

    return requested_webp

# 스레드 설정
worker_thread = threading.Thread(
    target=naify_image_fetcher.generation_request_queue_processor,
    daemon=True
)

worker_thread.start()

# 서버 실행
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True, access_log=False)

# url : 
# http://127.0.0.1:8000/
# http://127.0.0.1:8000/config
# http://127.0.0.1:8000/get_image?prompt=1girl