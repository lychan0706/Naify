# import
import fastapi
import httpx
import os
import io
import zipfile
import time
import threading


from concurrent.futures import Future
from queue import Queue
from pathlib import Path
from typing import Final

# 상수 및 설정 
NAI_API_URL: Final[str] = "https://image.novelai.net/ai/generate-image"
NAI_API_KEY: Final[str] = os.environ["NOVELAI_API_KEY"]
MODEL: Final[str] = "nai-diffusion-4-5-full"
WIDTH: Final[int] = 1216
HEIGHT: Final[int] = 832
STEPS: Final[int] = 28
# BASE_PROMPT: Final[str] = """1girl, -1::multiple views::, -5::artist collaboration::, year 2025, year 2024, newest, 1.7::artist:umigraphics, artist:hoo bamon::, 2.5::artist:sofra::, 3.0::artist:maratang::, 1.5::artist:ratatatat74 ::, 1.4::artist:norisukexxy::, 1.1::artist:ms. tsu::, 0.9::artist:yomu (sgt epper)::, 0.7::artist:wanke::, 0.5::artist:kurono mitsuki ::,  -3::child::, flat chest, 4::3d, blender (medium), flat color, cel rendering, hatching (texture)::, -3::unfinished, sketch, outline::, pale color, 2::official art, best illustration::, masterpiece, best quality, very aesthetic, incredibly absurdres, highly detailed"""
BASE_PROMPT: Final[str] = """1girl, -1::multiple views::, 3d, 

0.9::artist:teshima nari::, 
1.9::artist:ie (raarami)::, 
1.5::artist:umigraphics, artist:hoo bamon::, 
0.9::artist:gogalking::, 
1.7::artist:ratatatat74 ::, 
1.7::artist:yomu (sgt epper)::, 
2.5::artist:sofra::, 
1.5::artist:ms. tsu::, 
1.1::artist:2n5 ::, 
0.5::artist:teshima nari::, 

-5::artist collaboration::, year 2025, year 2024, newest, 

flat color, -1::nose, lips::, dot nose, pale color, 

-2::big hair::, 0.5::expressionless::, mature female, -2::child::, -1::loli::, -3::muscular::, -1::skinny::, 3::small breasts::, flat chest, 

-2::simple illustration, simple background::, detailed background, 2::official art, commission, best illustration, clear image, blender (medium), photoshop (medium)::, masterpiece, best quality, very aesthetic, incredibly absurdres, highly detailed,
full body, ::cowboy shot::, -2::portrait, straight-on::, 4::dutch angle:: 
"""
# NEGATIVE_PROMPT:Final[str] = """natsuki karin, text, logo, watermark, too many watermarks, blank page, text-only page, reference, username, signature, artist collaboration, variant set, large variant set, 4koma, 2koma, toon (style), chibi, turnaround, film grain, monochrome, dithering, halftone, screentones, dated, old, 1990s (style), mutation, deformed, distorted, disfigured, artistic error, distorted anatomy, anatomical structure error, asymmetrical face, unnatural hair, bad eyes, cloudy eyes, blank eyes, bad proportions, bad limb, extra digits, fewer digits, bad legs, extra legs, amputee, distorted composition, bad perspective, multiple views, negative space, animation error, chromatic aberration, disorganized colors, scan artifacts, jpeg artifacts, vertical lines, vertical banding, worst quality, bad quality, lowres, blurry, upscaled, fewer details, unfinished, incomplete, amateur, cheesy, unsatisfactory, inadequate, deficient, subpar, poor, displeasing, very displeasing, bad illustration, bad portrait, sketch, artist:xinzoruo, artist:milkpanda, makeup"""
NEGATIVE_PROMPT:Final[str] = """text, logo, watermark, too many watermarks, blank page, text-only page, reference, username, signature, 

artist collaboration, 

variant set, large variant set, 4koma, 2koma, toon (style), chibi, turnaround, 

film grain, monochrome, dithering, halftone, screentones, dated, old, 1990s (style), 

mutation, deformed, distorted, disfigured, artistic error, distorted anatomy, anatomical structure error, asymmetrical face, unnatural hair, bad eyes, cloudy eyes, blank eyes, bad proportions, bad limb, extra digits, fewer digits, bad legs, extra legs, amputee, distorted composition, bad perspective, 

multiple views, negative space, animation error, chromatic aberration, disorganized colors, scan artifacts, jpeg artifacts, vertical lines, vertical banding, 

worst quality, bad quality, lowres, blurry, upscaled, fewer details, unfinished, incomplete, amateur, cheesy, unsatisfactory, inadequate, deficient, subpar, poor, displeasing, very displeasing, bad illustration, bad portrait, sketch, 

artist:xinzoruo, artist:milkpanda, makeup, """
CACHE_DIR: Final[Path] = Path(__file__).resolve().parent / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
generation_queue = Queue()

# FastAPI 앱 생성
app = fastapi.FastAPI(debug=False)

# 유틸리티 함수 선언
def print_log(image_id:str = "SERVER", content: str = "") -> None:
    """
    현재 시각을 HH:MM:SS 형식으로 표시하고 로그를 출력한다.
    """
    timestamp = time.strftime("%H:%M:%S")
    print(f"[{image_id}] {timestamp} - {content}")

def get_anlas_balance() -> int | None:
    """
    NovelAI API에서 현재 남은 Anlas 잔액을 조회한다.

    Returns:
        int: 구독 Anlas와 구매 Anlas의 합계.
        None: 조회 실패 시 반환.
    """
    try:
        subscription_info_response = httpx.get(
            "https://image.novelai.net/user/subscription",
            headers={"Authorization": f"Bearer {NAI_API_KEY}"},
            timeout=10.0
        )
        subscription_info_response.raise_for_status()
        anlas_data = subscription_info_response.json().get("trainingStepsLeft")
        remaining_anlas = anlas_data["fixedTrainingStepsLeft"] + anlas_data["purchasedTrainingSteps"]
    except Exception as e:
        print_log(content=f"잔여 Anlas 조회 실패: {e}")
        return None
    else:
        return remaining_anlas

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

def generate_image(image_id: str, prompt: str) -> bytes:
    initial_anlas = get_anlas_balance()
    
    prompt = prompt.replace("_", " ")
    prompt = prompt.replace(",", ", ")
    prompt = prompt.replace(",  ", ", ")

    generation_response = httpx.post(
            timeout=120.0,
            url=NAI_API_URL,
            headers={"Authorization": f"Bearer {NAI_API_KEY}"},
            json = {
                "action": "generate",
                "input": BASE_PROMPT,
                "model": MODEL,
                "parameters": {
                    "width": WIDTH,
                    "height": HEIGHT,
                    "n_samples": 1,
                    "steps": STEPS,
                    "scale": 7,
                    "sampler": "k_euler_ancestral",
                    "noise_schedule": "karras",
                    "cfg_rescale": 0.4,
                    "params_version": 3,
                    "image_format": "webp",
                    "v4_prompt": {
                        "caption": {
                            "base_caption": BASE_PROMPT,
                            "char_captions": [
                                {
                                    "char_caption": prompt,
                                    "centers": [
                                        {
                                            "x": 0.5,
                                            "y": 0.5
                                        }
                                    ]
                                }
                            ]
                        },
                        "use_coords": False,
                        "use_order": True
                    },
                    "v4_negative_prompt": {
                        "caption": {
                            "base_caption": NEGATIVE_PROMPT,
                            "char_captions": [
                                {
                                    "char_caption": "",
                                    "centers": [
                                        {
                                            "x": 0.5,
                                            "y": 0.5
                                        }
                                    ]
                                }
                            ]
                        },
                        "legacy_uc": False,
                        "use_coords": False,
                        "use_order": True
                    }
                }
            }
        )

    if generation_response.status_code != 200:
        print_log(f"status_code: {generation_response.status_code},\nerror: {generation_response.json().get("message")}")
        raise fastapi.HTTPException(
            status_code=502,
            detail="NovelAI Imamge Generation Failed"
        )

    image_bytes = extract_image_from_zip(zip_data=generation_response.content)
    
    remaining_anlas = get_anlas_balance()
    if initial_anlas is not None and remaining_anlas is not None:
        used_anlas = initial_anlas - remaining_anlas
        print_log(image_id, f"{used_anlas} Anlas")
    
    return image_bytes

def extract_image_from_zip(zip_data: bytes) -> bytes:
    """
    ZIP 바이너리 데이터에서 첫 번째 이미지 파일을 추출한다.

    Args:
        zip_data: ZIP 파일의 바이너리 데이터.

    Returns:
        bytes: 압축 해제된 이미지 데이터.
    """

    zip_file = io.BytesIO(zip_data)
    with zipfile.ZipFile(zip_file, "r") as response_zip:
        image_bytes = response_zip.read(response_zip.namelist()[0])
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