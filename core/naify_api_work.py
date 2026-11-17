import fastapi
import httpx
from typing import Final

from core.naify_utility import extract_image_from_zip, print_log
from core.naify_config import NaifyConfig, NaifySecrets


NAI_API_URL: Final[str] = "https://image.novelai.net/ai/generate-image"


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
    except Exception as e:
        print_log(content=f"잔여 Anlas 조회 실패: {e}")
        return None
    else:
        return remaining_anlas


def generate_image(image_id: str, naify_secrets: NaifySecrets, naify_config: NaifyConfig, prompt: str) -> bytes:

    prompt = prompt.replace("_", " ")
    prompt = prompt.replace(",", ", ")
    prompt = prompt.replace(",  ", ", ")

    generation_response = httpx.post(
            timeout=120.0,
            url=NAI_API_URL,
            headers={"Authorization": f"Bearer {naify_secrets.nai_api_key}"},
            json = {
                "action": "generate",
                "input": naify_config.prompt.base_prompt,
                "model": naify_config.generation.model,
                "parameters": {
                    "width": naify_config.generation.width,
                    "height": naify_config.generation.height,
                    "n_samples": 1,
                    "negative_prompt": naify_config.prompt.negative_prompt,
                    "steps": naify_config.generation.steps,
                    # -1은 자동 시드 선택을 뜻하므로 API 기본 동작에 맡긴다.
                    **({"seed": naify_config.generation.seed} if naify_config.generation.seed >= 0 else {}),
                    "scale": naify_config.generation.prompt_guidance,
                    "sampler": naify_config.generation.sampler,
                    "noise_schedule": naify_config.generation.noise_schedule,
                    "cfg_rescale": naify_config.generation.prompt_guidance_rescale,
                    "params_version": 3,
                    "image_format": "webp",
                    "v4_prompt": {
                        "caption": {
                            "base_caption": naify_config.prompt.base_prompt,
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
                            "base_caption": naify_config.prompt.negative_prompt,
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
        try:
            error_data = generation_response.json()
            error_message = (
                error_data.get("message") or generation_response.text
                if isinstance(error_data, dict) else generation_response.text
            )
        except ValueError:
            error_message = generation_response.text
        print_log(image_id, f"error - {generation_response.status_code} - {str(error_message)[:500]}")

        raise fastapi.HTTPException(
            status_code=502,
            detail="NovelAI Image Generation Failed"
        )

    image_bytes = extract_image_from_zip(zip_data=generation_response.content)

    return image_bytes
