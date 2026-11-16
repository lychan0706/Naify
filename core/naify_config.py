# 상수 및 설정 
from pydantic import BaseModel, field_validator
from pydantic import ConfigDict
from pydantic import Field
from core.naify_paths import CONFIG_PATH, SECRETS_PATH

class NaifySecrets(BaseModel):
    nai_api_key: str = ""


class GenerationPrompt(BaseModel):

    model_config = ConfigDict(
        validate_default=True,
        validate_assignment=True
    )

    base_prompt: str = ""
    negative_prompt: str = ""


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


def save_config(naify_config: NaifyConfig) -> None:
    config_json: str = naify_config.model_dump_json(indent=4)
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


def save_secrets(naify_secrets: NaifySecrets) -> None:
    secrets_json: str = naify_secrets.model_dump_json(indent=4)
    with open (SECRETS_PATH, "w", encoding="utf-8") as json_file:
        json_file.write(secrets_json)


def load_secrets() -> NaifySecrets:
    naify_secrets: NaifySecrets

    if not SECRETS_PATH.exists():
        naify_secrets = NaifySecrets()
        save_secrets(naify_secrets)
        return naify_secrets

    with open(SECRETS_PATH, "r", encoding="utf-8") as json_file:
        secrets_json: str = json_file.read()

    naify_secrets = NaifySecrets.model_validate_json(secrets_json)

    return naify_secrets
