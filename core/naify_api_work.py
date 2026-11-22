import fastapi
import httpx
import zipfile
import base64
import binascii
import json
from collections.abc import Callable
from typing import Final

from core.naify_utility import extract_image_from_zip, print_log
from core.naify_config import NaifyConfig, NaifySecrets


NAI_API_URL: Final[str] = "https://image.novelai.net/ai/generate-image"


def validate_api_key(api_key: str) -> str:
    """인증 확인: valid / invalid / unavailable / missing."""
    if not api_key.strip():
        return "missing"
    try:
        response = httpx.get(
            "https://image.novelai.net/user/subscription",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10.0
        )
    except httpx.RequestError:
        return "unavailable"

    if response.status_code == 200:
        return "valid"
    if response.status_code in (401, 403):
        return "invalid"
    return "unavailable"


def get_anlas_balance(naify_secrets: NaifySecrets) -> int | None:
    """
    NovelAI API에서 현재 남은 Anlas 잔액을 조회한다.

    Returns:
        int: 구독 Anlas와 구매 Anlas의 합계.
        None: 조회 실패 시 반환.
    """
    try:
        subscription_info_response = httpx.get(
            "https://image.novelai.net/user/subscription",
            headers={"Authorization": f"Bearer {naify_secrets.nai_api_key}"},
            timeout=10.0
        )
        subscription_info_response.raise_for_status()
        anlas_data = subscription_info_response.json().get("trainingStepsLeft")
        remaining_anlas = anlas_data["fixedTrainingStepsLeft"] + anlas_data["purchasedTrainingSteps"]
    except Exception:
        return None
    else:
        return remaining_anlas


def bulid_payload(
    config: NaifyConfig, prompt: str, char1: str, char2: str, char3: str
) -> dict:
    """공통 프롬프트와 캐릭터별 프롬프트를 NovelAI 생성 요청으로 구성한다."""
    base_prompt = config.prompt.base_prompt.strip()
    prompt = prompt.strip()
    base_caption = ", ".join(value for value in (base_prompt, prompt) if value)

    char_captions = [
        {"char_caption": character, "centers": [{"x": 0.5, "y": 0.5}]}
        for character in (char1, char2, char3)
        if character.strip()
    ]
    negative_char_captions = [
        {"char_caption": "", "centers": [{"x": 0.5, "y": 0.5}]}
        for _ in char_captions
    ]

    return {
        "action": "generate",
        "input": base_caption,
        "model": config.generation.model,
        "parameters": {
            "width": config.generation.width,
            "height": config.generation.height,
            "n_samples": 1,
            "negative_prompt": config.prompt.negative_prompt,
            "steps": config.generation.steps,
            "scale": config.generation.prompt_guidance,
            "sampler": config.generation.sampler,
            "noise_schedule": config.generation.noise_schedule,
            "cfg_rescale": config.generation.prompt_guidance_rescale,
            "params_version": 3,
            "image_format": "webp",
            "v4_prompt": {
                "caption": {
                    "base_caption": base_caption,
                    "char_captions": char_captions
                },
                "use_coords": False,
                "use_order": True
            },
            "v4_negative_prompt": {
                "caption": {
                    "base_caption": config.prompt.negative_prompt,
                    "char_captions": negative_char_captions
                },
                "legacy_uc": False,
                "use_coords": False,
                "use_order": True
            }
        }
    }


def generate_image(
    image_id: str, naify_secrets: NaifySecrets, naify_config: NaifyConfig,
    prompt: str, char1: str = "", char2: str = "", char3: str = ""
) -> bytes:
    try:
        generation_response = httpx.post(
            timeout=120.0,
            url=NAI_API_URL,
            headers={"Authorization": f"Bearer {naify_secrets.nai_api_key}"},
            json=bulid_payload(naify_config, prompt, char1, char2, char3)
        )
    except httpx.TimeoutException as exc:
        print_log(image_id, f"NovelAI request timed out: {type(exc).__name__}")
        raise fastapi.HTTPException(status_code=504, detail="NovelAI request timed out") from exc
    except httpx.RequestError as exc:
        print_log(image_id, f"NovelAI connection failed: {type(exc).__name__}")
        raise fastapi.HTTPException(status_code=502, detail="Could not connect to NovelAI") from exc

    if generation_response.status_code not in (200, 201):
        try:
            error_data = generation_response.json()
            error_message = (
                error_data.get("message") or generation_response.text
                if isinstance(error_data, dict) else generation_response.text
            )
        except ValueError:
            error_message = generation_response.text
        print_log(image_id, f"NovelAI HTTP {generation_response.status_code}: {str(error_message)[:500]}")

        if generation_response.status_code in (401, 403):
            detail = "NovelAI authentication failed"
            status_code = 502
        elif generation_response.status_code == 429:
            detail = "NovelAI generation is temporarily limited"
            status_code = 503
        else:
            detail = "NovelAI Image Generation Failed"
            status_code = 502

        raise fastapi.HTTPException(
            status_code=status_code,
            detail=detail
        )

    try:
        image_bytes = extract_image_from_zip(zip_data=generation_response.content)
    except (zipfile.BadZipFile, ValueError, RuntimeError, EOFError, OSError) as exc:
        print_log(image_id, f"Invalid NovelAI image archive: {type(exc).__name__}")
        raise fastapi.HTTPException(status_code=502, detail="Invalid NovelAI image response") from exc

    return image_bytes


NAI_STREAM_URL: Final[str] = "https://image.novelai.net/ai/generate-image-stream"


def iter_generation_events(lines):
    """NovelAI SSE 스트림에서 이벤트 이름과 JSON 데이터를 하나씩 꺼낸다."""
    event_name = ""
    data_lines = []

    def parse_event():
        if not data_lines:
            return None
        data = "\n".join(data_lines)
        if data == "[DONE]":
            return None
        try:
            payload = json.loads(data)
        except (json.JSONDecodeError, ValueError) as exc:
            raise fastapi.HTTPException(status_code=502, detail="Invalid NovelAI stream event") from exc
        if not isinstance(payload, dict):
            raise fastapi.HTTPException(status_code=502, detail="Invalid NovelAI stream event")
        return (event_name or payload.get("event_type", ""), payload)

    for line in lines:
        if not line.strip():
            parsed = parse_event()
            if parsed is not None:
                yield parsed
            event_name, data_lines = "", []
        elif line.startswith("event:"):
            event_name = line[6:].strip()
        elif line.startswith("data:"):
            data_lines.append(line[5:].lstrip(" "))

    parsed = parse_event()
    if parsed is not None:
        yield parsed


def generate_image_stream(
    image_id: str, naify_secrets: NaifySecrets, naify_config: NaifyConfig,
    prompt: str, char1: str = "", char2: str = "", char3: str = "",
    on_progress: Callable[[int], None] | None = None
) -> bytes:
    """NovelAI SSE 생성 결과에서 중간 이미지는 버리고 진행 단계와 최종 WebP만 처리한다."""
    payload = bulid_payload(naify_config, prompt, char1, char2, char3)
    payload["parameters"]["stream"] = "sse"

    final_image = None
    last_progress = -1

    try:
        with httpx.stream(
            "POST", NAI_STREAM_URL,
            headers={"Authorization": f"Bearer {naify_secrets.nai_api_key}"},
            json=payload, timeout=120.0
        ) as response:
            if response.status_code not in (200, 201):
                response.read()
                try:
                    error_data = response.json()
                    message = error_data.get("message", response.text) if isinstance(error_data, dict) else response.text
                except ValueError:
                    message = response.text
                print_log(image_id, f"NovelAI HTTP {response.status_code}: {str(message)[:500]}")
                if response.status_code in (401, 403):
                    detail, status_code = "NovelAI authentication failed", 502
                elif response.status_code == 429:
                    detail, status_code = "NovelAI generation is temporarily limited", 503
                else:
                    detail, status_code = "NovelAI Image Generation Failed", 502
                raise fastapi.HTTPException(status_code=status_code, detail=detail)

            for event_type, event in iter_generation_events(response.iter_lines()):
                if event_type == "error":
                    print_log(image_id, f"NovelAI stream error: {str(event.get('message', 'unknown'))[:500]}")
                    raise fastapi.HTTPException(status_code=502, detail="NovelAI image stream failed")

                if event_type == "intermediate":
                    step = event.get("step_ix")
                    steps = event.get("steps") or naify_config.generation.steps
                    if isinstance(step, int) and isinstance(steps, (int, float)) and steps > 0:
                        percent = max(0, min(99, round((step + 1) / steps * 100)))
                        if percent > last_progress:
                            last_progress = percent
                            if on_progress is not None:
                                on_progress(percent)

                elif event_type == "final":
                    encoded = event.get("image")
                    if not isinstance(encoded, str):
                        raise fastapi.HTTPException(status_code=502, detail="NovelAI final image missing")
                    try:
                        final_image = base64.b64decode(encoded, validate=True)
                    except (binascii.Error, ValueError) as exc:
                        raise fastapi.HTTPException(status_code=502, detail="Invalid NovelAI final image") from exc

    except httpx.TimeoutException as exc:
        print_log(image_id, f"NovelAI request timed out: {type(exc).__name__}")
        raise fastapi.HTTPException(status_code=504, detail="NovelAI request timed out") from exc
    except httpx.RequestError as exc:
        print_log(image_id, f"NovelAI connection failed: {type(exc).__name__}")
        raise fastapi.HTTPException(status_code=502, detail="Could not connect to NovelAI") from exc

    if final_image is None or len(final_image) < 12 or final_image[:4] != b"RIFF" or final_image[8:12] != b"WEBP":
        print_log(image_id, "Invalid NovelAI final WebP image")
        raise fastapi.HTTPException(status_code=502, detail="Invalid NovelAI image response")

    return final_image
