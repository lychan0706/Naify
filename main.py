# import
import fastapi
import threading
import re
import asyncio
import json
from contextlib import asynccontextmanager
from fastapi import Request
from pydantic import BaseModel
from starlette.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.responses import StreamingResponse
from fastapi import Request

from core import naify_image_fetcher, naify_cache, naify_api_work
from core.naify_config import NaifySecrets, NaifyConfig, PresetConfig, load_config_store, save_config_store, save_secrets, load_secrets
from core.naify_utility import open_manager, shutdown_server, print_log
from core.naify_paths import ensure_data_dirs, WEB_DIR
from core.naify_utility import wait_for_logs


@asynccontextmanager
async def lifespan(app: fastapi.FastAPI):
    app.state.api_key_status = await asyncio.to_thread(
        naify_api_work.validate_api_key, naify_secrets.nai_api_key
    )
    print_log(content=f"NovelAI API key status: {app.state.api_key_status}")

    worker_thread = threading.Thread(
        target=naify_image_fetcher.generation_request_queue_processor,
        daemon=True
    )

    app.state.generation_worker = worker_thread
    worker_thread.start()

    threading.Timer(1.0, open_manager).start()

    yield


# FastAPI 앱 생성 및 설정
app = fastapi.FastAPI(debug=False, lifespan=lifespan)

app.state.shutting_down = False
app.state.active_requests = 0
app.state.request_condition = threading.Condition()

app.mount(
    "/static",
    StaticFiles(directory=WEB_DIR),
    name="static"
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=[
        "127.0.0.1",
        "localhost"
    ]
)


# 경로 초기화 및 Config 가져오기
ensure_data_dirs()

config_lock = threading.RLock()
naify_preset_store = load_config_store()
naify_config: NaifyConfig = naify_preset_store.active_config()
naify_secrets: NaifySecrets = load_secrets()


# 라우트 선언
@app.get("/")
def home() -> FileResponse:

    print_log(content="got home request")

    response: FileResponse = FileResponse(WEB_DIR / "index.html")

    return response


@app.get("/logs/stream")
async def stream_logs(request: Request):
    async def generate_events():
        last_seen_id = 0

        while not request.app.state.shutting_down and not await request.is_disconnected():
            new_logs = await asyncio.to_thread(wait_for_logs, last_seen_id)

            # 종료 요청 중에는 SSE 스트림도 끝내야 Uvicorn이 연결을 기다리지 않는다.
            if request.app.state.shutting_down:
                break

            for log_id, log in new_logs:
                last_seen_id = log_id
                yield f"id: {log_id}\ndata: {json.dumps(log, ensure_ascii=False)}\n\n"

    log_stream = StreamingResponse(
        generate_events(),
        media_type="text/event-stream"
    )
    return log_stream

@app.get("/config")
def get_config() -> NaifyConfig:

    print_log(content="got config request")

    with config_lock:
        config = naify_config.model_copy(deep=True)

    return config


@app.put("/config")
def update_config(config: NaifyConfig, request: Request) -> None:
    global naify_config, naify_preset_store

    preferred = request.headers.get("x-naify-resolution-priority", "height")
    config.generation.fit_resolution(preferred)
    with config_lock:
        updated_store = naify_preset_store.model_copy(deep=True)
        updated_store.update_active(config)
        save_config_store(updated_store)
        naify_preset_store = updated_store
        naify_config = config
    naify_cache.trim_cache(config.cache)

    print_log(content="config updated")

    return


@app.get("/presets")
def list_presets() -> dict:
    with config_lock:
        return {"active_preset": naify_preset_store.active_preset,
                "names": list(naify_preset_store.presets)}


class PresetName(BaseModel):
    name: str


def check_preset_name(name: str) -> str:
    name = name.strip()
    if not name or len(name) > 60 or any(c in name for c in "\r\n\t"):
        raise fastapi.HTTPException(status_code=400, detail="Invalid preset name")
    return name


def verify_preset_action(request: Request) -> None:
    if request.headers.get("origin") != "http://127.0.0.1:8000" or request.headers.get("x-naify-action") != "manage-preset":
        raise fastapi.HTTPException(status_code=403, detail="Forbidden")


def commit_presets(store) -> None:
    global naify_preset_store, naify_config
    save_config_store(store)
    naify_preset_store = store
    naify_config = store.active_config()


@app.post("/presets", status_code=201)
def create_preset(data: PresetName, request: Request) -> dict:
    verify_preset_action(request)
    name = check_preset_name(data.name)
    with config_lock:
        if name in naify_preset_store.presets:
            raise fastapi.HTTPException(status_code=409, detail="Preset already exists")
        store = naify_preset_store.model_copy(deep=True)
        store.presets[name] = PresetConfig.model_validate(store.presets[store.active_preset].model_dump())
        commit_presets(store)
    return {"name": name}


@app.put("/presets/{name}")
def rename_preset(name: str, data: PresetName, request: Request) -> dict:
    verify_preset_action(request)
    new_name = check_preset_name(data.name)
    with config_lock:
        if name not in naify_preset_store.presets:
            raise fastapi.HTTPException(status_code=404, detail="Preset not found")
        if new_name != name and new_name in naify_preset_store.presets:
            raise fastapi.HTTPException(status_code=409, detail="Preset already exists")
        store = naify_preset_store.model_copy(deep=True)
        store.presets = {new_name if key == name else key: value for key, value in store.presets.items()}
        if store.active_preset == name:
            store.active_preset = new_name
        commit_presets(store)
    return {"name": new_name}


@app.delete("/presets/{name}")
def delete_preset(name: str, request: Request) -> dict:
    verify_preset_action(request)
    with config_lock:
        if name not in naify_preset_store.presets:
            raise fastapi.HTTPException(status_code=404, detail="Preset not found")
        if len(naify_preset_store.presets) == 1:
            raise fastapi.HTTPException(status_code=409, detail="Cannot delete last preset")
        store = naify_preset_store.model_copy(deep=True)
        del store.presets[name]
        if store.active_preset == name:
            store.active_preset = next(iter(store.presets))
        commit_presets(store)
    return {"active_preset": store.active_preset}


@app.post("/presets/{name}/activate")
def activate_preset(name: str, request: Request) -> dict:
    verify_preset_action(request)
    with config_lock:
        if name not in naify_preset_store.presets:
            raise fastapi.HTTPException(status_code=404, detail="Preset not found")
        store = naify_preset_store.model_copy(deep=True)
        store.active_preset = name
        commit_presets(store)
    return {"active_preset": name}


@app.get("/secrets/status")
def get_secrets_status() -> dict:
    
    print_log(content="got secrets status request")

    is_configured = bool(naify_secrets.nai_api_key)
    
    secrets_status = {
        "configured": is_configured,
        "validation": getattr(app.state, "api_key_status", "unchecked")
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

    validation = naify_api_work.validate_api_key(secrets.nai_api_key)
    if validation == "invalid":
        raise fastapi.HTTPException(status_code=401, detail="Invalid NovelAI API key")
    if validation != "valid":
        raise fastapi.HTTPException(status_code=503, detail="Could not verify NovelAI API key")

    save_secrets(secrets)
    naify_secrets = secrets
    app.state.api_key_status = "valid"

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


@app.delete("/cache/image/{image_id}")
def delete_cached_image(image_id: str, request: Request) -> dict:
    if request.headers.get("origin") != "http://127.0.0.1:8000" or request.headers.get("x-naify-action") != "delete-image":
        raise fastapi.HTTPException(status_code=403, detail="Forbidden")
    if re.fullmatch(r"[0-9a-f]{64}", image_id) is None:
        raise fastapi.HTTPException(status_code=400, detail="Invalid image ID")
    if not naify_cache.delete_image_from_cache(image_id):
        raise fastapi.HTTPException(status_code=404, detail="Cached image not found")
    return {"deleted": True}


@app.post("/queue/cancel_pending")
def cancel_pending_generation_requests(request: Request) -> dict:
    # 웹 관리자에서 발생한 명시적인 요청만 허용한다.
    origin = request.headers.get("origin")
    action = request.headers.get("x-naify-action")
    if origin != "http://127.0.0.1:8000" or action != "cancel-pending":
        raise fastapi.HTTPException(status_code=403, detail="Forbidden")

    if app.state.shutting_down:
        raise fastapi.HTTPException(status_code=409, detail="Server is shutting down")

    cancelled_count = naify_image_fetcher.cancel_pending_requests()
    response = {"cancelled_count": cancelled_count}

    return response


def parse_image_query(query_params) -> tuple[str, str, str, str, bool]:
    """기존 소문자 prompt와 새 대문자 PROMPT/CHAR1~3를 구별한다."""
    old_prompt = query_params.get("prompt")
    new_prompt = query_params.get("PROMPT")
    characters = tuple(query_params.get(f"CHAR{i}", "") for i in range(1, 4))
    if old_prompt is not None and (new_prompt is not None or any(characters)):
        raise fastapi.HTTPException(status_code=400, detail="Do not mix legacy prompt with PROMPT/CHAR")
    if old_prompt is not None:
        if not old_prompt.strip():
            raise fastapi.HTTPException(status_code=400, detail="Empty prompt")
        return "", old_prompt, "", "", True
    if not (new_prompt or "").strip() and not any(char.strip() for char in characters):
        raise fastapi.HTTPException(status_code=400, detail="At least one prompt is required")
    return new_prompt or "", *characters, False


@app.get("/get_image")
def get_image(request: Request) -> fastapi.Response:
    prompt, char1, char2, char3, legacy = parse_image_query(request.query_params)

    # 1. 종료 상태 검사 및 요청 수 증가
    with app.state.request_condition:

        if app.state.shutting_down:
            raise fastapi.HTTPException(
                status_code=503,
                detail="Server is shutting down"
            )

        app.state.active_requests += 1

    # 2. 등록에 성공한 요청만 try/finally로 관리
    try:
        # 이미지 ID 생성
        image_id: str = naify_image_fetcher.make_image_id(prompt, char1, char2, char3, legacy=legacy)

        print_log(image_id, "Requested")

        # 이미지 제공
        image_bytes = naify_image_fetcher.fetch_image(
            image_id=image_id,
            secrets=naify_secrets,
            config=naify_config,
            prompt=prompt,
            worker_thread=app.state.generation_worker,
            char1=char1,
            char2=char2,
            char3=char3
        )

        requested_webp = fastapi.Response(
            content=image_bytes,
            media_type="image/webp"
        )

        return requested_webp

    finally:
        # 3. 등록된 요청만 카운트 감소
        with app.state.request_condition:

            app.state.active_requests -= 1

            app.state.request_condition.notify_all()



@app.post("/shutdown")
def request_shutdown(request: Request) -> dict:

    request_origin = request.headers.get("origin")

    if request_origin != "http://127.0.0.1:8000":
        raise fastapi.HTTPException(
            status_code=403,
            detail="Forbidden"
        )

    server = request.app.state.uvicorn_server

    with app.state.request_condition:

        if app.state.shutting_down:
            raise fastapi.HTTPException(
                status_code=409,
                detail="Shutdown already requested"
            )

        app.state.shutting_down = True

    # 대기 중인 로그 스트림도 깨어나 종료 상태를 확인하도록 한다.
    print_log(content="Shutdown requested; closing log streams")

    shutdown_thread = threading.Thread(
        target=shutdown_server,
        args=(app, server,),
        daemon=True
    )

    shutdown_thread.start()

    response = {
        "message": "Server shutdown requested"
    }

    return response

    
# 서버 실행
if __name__ == "__main__":
    import uvicorn

    uvicorn_config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=8000,
        reload=False,
        access_log=False,
        use_colors=False
    )

    uvicorn_server = uvicorn.Server(uvicorn_config)

    app.state.uvicorn_server = uvicorn_server

    uvicorn_server.run()

# test urls : 
# http://127.0.0.1:8000/
# http://127.0.0.1:8000/config
# http://127.0.0.1:8000/secrets
# http://127.0.0.1:8000/secrets/status
# http://127.0.0.1:8000/get_image?prompt=1girl
