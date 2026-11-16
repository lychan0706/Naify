# import
import fastapi
import time
import threading
import re
from core import naify_image_fetcher, naify_cache
from core.naify_utility import print_log
from core.naify_config import NaifySecrets, NaifyConfig, load_config, save_config, save_secrets, load_secrets
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from fastapi import Request
from starlette.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from core.naify_utility import open_manager


@asynccontextmanager
async def lifespan(app: fastapi.FastAPI):

    worker_thread = threading.Thread(
        target=naify_image_fetcher.generation_request_queue_processor,
        daemon=True
    )

    worker_thread.start()

    threading.Timer(1.0, open_manager).start()

    yield


# FastAPI 앱 생성
app = fastapi.FastAPI(debug=False, lifespan=lifespan)

app.mount(
    "/static",
    StaticFiles(directory="web"),
    name="static"
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=[
        "127.0.0.1",
        "localhost"
    ]
)


# Config 가져오기
naify_config: NaifyConfig = load_config()
naify_secrets: NaifySecrets = load_secrets()


# 라우트 선언
@app.get("/")
def home() -> FileResponse:

    print_log(content="got home request")

    response: FileResponse = FileResponse("web/index.html")

    return response


@app.get("/config")
def get_config() -> NaifyConfig:

    print_log(content="got config request")

    config = naify_config

    return config


@app.put("/config")
def update_config(config: NaifyConfig) -> None:
    global naify_config
    
    naify_config = config

    save_config(naify_config)

    print_log(content="config updated")

    return


@app.get("/secrets/status")
def get_secrets_status() -> dict:
    
    print_log(content="got secrets status request")

    is_configured = bool(naify_secrets.nai_api_key)
    
    secrets_status = {
        "configured": is_configured
    }

    return secrets_status


@app.put("/secrets")
def update_secrets(secrets: NaifySecrets, request: Request) -> None:

    origin : str | None = request.headers.get("origin")

    if origin != "http://127.0.0.1:8000":
        raise fastapi.HTTPException(
            status_code=403,
            detail="Forbidden"
        )

    global naify_secrets

    naify_secrets = secrets
    save_secrets(naify_secrets)

    print_log(content="secrets updated")

    return


# 캐시 갤러리에서 사용하는 읽기 전용 엔드포인트.
@app.get("/cache/status")
def get_cache_status() -> dict:
    return naify_cache.get_cache_status()


@app.get("/cache/image/{image_id}")
def get_cached_image(image_id: str) -> fastapi.Response:
    # 이미지 ID는 SHA-256 해시로만 구성되며, 임의의 파일 경로를 허용하지 않는다.
    if re.fullmatch(r"[0-9a-f]{64}", image_id) is None:
        raise fastapi.HTTPException(status_code=400, detail="Invalid image ID")

    image_bytes = naify_cache.get_image_from_cache(image_id)
    if image_bytes is None:
        raise fastapi.HTTPException(status_code=404, detail="Cached image not found")

    return fastapi.Response(
        content=image_bytes,
        media_type="image/webp",
        headers={"Cache-Control": "no-store"}
    )


@app.delete("/cache")
def delete_all_cache(request: Request) -> dict:
    # 다른 사이트에서 사용자의 로컬 캐시를 지우는 요청을 차단한다.
    origin = request.headers.get("origin")
    action = request.headers.get("x-naify-action")
    if origin != "http://127.0.0.1:8000" or action != "clear-cache":
        raise fastapi.HTTPException(status_code=403, detail="Forbidden")

    deleted_count = naify_cache.clear_cache()
    return {"deleted_count": deleted_count}


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
    image_bytes = naify_image_fetcher.fetch_image(image_id=image_id, secrets=naify_secrets, config=naify_config, prompt=prompt)
    requested_webp = fastapi.Response(
        content=image_bytes,
        media_type="image/webp"
    )

    # 소요 시간 계산
    process_termination_time = time.perf_counter()
    total_elapsed = process_termination_time - process_initiation_time
    print_log(image_id, f"{round(total_elapsed,2)}sec")

    return requested_webp


# 서버 실행
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False, access_log=False)

# test urls : 
# http://127.0.0.1:8000/
# http://127.0.0.1:8000/config
# http://127.0.0.1:8000/secrets
# http://127.0.0.1:8000/secrets/status
# http://127.0.0.1:8000/get_image?prompt=1girl