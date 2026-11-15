# 상수 및 설정 
import os
from typing import Final
from pydantic import BaseModel, field_validator
from pydantic import ConfigDict
from pydantic import Field
from pathlib import Path

CONFIG_PATH: Path = Path(__file__).resolve().parent.parent / "config.json"
NAI_API_KEY: Final[str] = os.environ["NOVELAI_API_KEY"]
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
NEGATIVE_PROMPT:Final[str] = """text, logo, watermark, too many watermarks, blank page, text-only page, reference, username, signature, 

artist collaboration, 

variant set, large variant set, 4koma, 2koma, toon (style), chibi, turnaround, 

film grain, monochrome, dithering, halftone, screentones, dated, old, 1990s (style), 

mutation, deformed, distorted, disfigured, artistic error, distorted anatomy, anatomical structure error, asymmetrical face, unnatural hair, bad eyes, cloudy eyes, blank eyes, bad proportions, bad limb, extra digits, fewer digits, bad legs, extra legs, amputee, distorted composition, bad perspective, 

multiple views, negative space, animation error, chromatic aberration, disorganized colors, scan artifacts, jpeg artifacts, vertical lines, vertical banding, 

worst quality, bad quality, lowres, blurry, upscaled, fewer details, unfinished, incomplete, amateur, cheesy, unsatisfactory, inadequate, deficient, subpar, poor, displeasing, very displeasing, bad illustration, bad portrait, sketch, 

artist:xinzoruo, artist:milkpanda, makeup, """


class GenerationPrompt(BaseModel):

    model_config = ConfigDict(
        validate_default=True,
        validate_assignment=True
    )

    base_prompt: str = BASE_PROMPT
    negative_prompt: str = NEGATIVE_PROMPT


class GenerationConfig(BaseModel):

    model_config = ConfigDict(
        validate_default=True,
        validate_assignment=True
    )

    model: str = "nai-diffusion-4-5-full"
    width: int = 1216
    height: int = 832
    steps: int = 28
    prompt_guidance: float = 7
    seed: int = -1
    sampler: str = "k_euler_ancestral"
    prompt_guidance_rescale: float = 0.4
    noise_schedule: str = "karras"

    @field_validator("width", "height")
    @classmethod
    def normalize_resolution(cls, value: int) -> int:
        normalized_value: int = max(512, round(value / 64) * 64)
        
        return normalized_value

    @field_validator("steps")
    @classmethod
    def normalize_step_count(cls, value: int):
        if value > 50 : value = 50
        if value < 1 : value = 1

        return value

    @field_validator("prompt_guidance")
    @classmethod
    def normalize_prompt_guidance(cls, value: float):
        if value > 10 : value = 10
        if value < 0 : value = 0

        return value

    @field_validator("prompt_guidance_rescale")
    @classmethod
    def normalize_prompt_guidance_rescale(cls, value: float):
        if value > 1 : value = 1
        if value < 0 : value = 0

        return value


class CacheConfig(BaseModel):

    model_config = ConfigDict(
        validate_default=True,
        validate_assignment=True
    )

    max_cache_size: int = Field(
        default=100 * 1024 * 1024,
        gt=0
    )

    max_images: int = Field(
        default=100,
        gt=0
    )


class NaifyConfig(BaseModel):
    generation: GenerationConfig = Field(default_factory=GenerationConfig)
    prompt: GenerationPrompt = Field(default_factory=GenerationPrompt)
    cache: CacheConfig = Field(default_factory=CacheConfig)


def save_config(nai_config: NaifyConfig):
    config_json: str = nai_config.model_dump_json(indent=4)
    with open(CONFIG_PATH, "w", encoding="utf-8") as json_file:
        json_file.write(config_json)


def load_config() -> NaifyConfig:
    naify_config: NaifyConfig

    if not CONFIG_PATH.exists():
        naify_config = NaifyConfig()
        save_config(naify_config)
        return naify_config

    with open(CONFIG_PATH, "r", encoding="utf-8") as json_file:
        config_json: str = json_file.read()

    naify_config = NaifyConfig.model_validate_json(config_json)

    return naify_config