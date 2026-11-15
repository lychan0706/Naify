from typing import Final
import fastapi
from core.config import BASE_PROMPT, HEIGHT, MODEL, NAI_API_KEY, STEPS, WIDTH
from core.utility import extract_image_from_zip, print_log
from core.config import NEGATIVE_PROMPT
import httpx


NAI_API_URL: Final[str] = "https://image.novelai.net/ai/generate-image"


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