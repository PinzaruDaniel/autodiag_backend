import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    mb_in_bytes: int = 1024 * 1024
    max_audio_size_mb: int = 10
    local_audio_dir: str = "data/audio"
    azure_storage_connection_string: str | None = None
    azure_storage_container: str = "audio"
    azure_cosmos_endpoint: str | None = None
    azure_cosmos_key: str | None = None
    azure_cosmos_database: str = "autodiag"
    azure_cosmos_users_container: str = "users"
    azure_cosmos_refresh_tokens_container: str = "refresh_tokens"
    azure_cosmos_audio_results_container: str = "audio_results"
    ai_model_name: str = "laion/clap-htsat-fused"
    ai_inference_endpoint: str | None = None
    ai_inference_token: str | None = None
    ai_default_labels: str = "engine,brake,tire,road_noise,silence"

    @property
    def max_audio_size_bytes(self) -> int:
        return self.max_audio_size_mb * self.mb_in_bytes

    @property
    def chunk_size_bytes(self) -> int:
        return self.mb_in_bytes

    @property
    def azure_enabled(self) -> bool:
        return bool(self.azure_storage_connection_string)

    @property
    def azure_cosmos_enabled(self) -> bool:
        return bool(self.azure_cosmos_endpoint and self.azure_cosmos_key)


@lru_cache
def get_settings() -> Settings:
    jwt_secret = os.getenv("JWT_SECRET")
    if not jwt_secret:
        raise RuntimeError("JWT_SECRET environment variable must be set")

    return Settings(
        jwt_secret=jwt_secret,
        azure_storage_connection_string=os.getenv("AZURE_STORAGE_CONNECTION_STRING"),
        azure_storage_container=os.getenv("AZURE_STORAGE_CONTAINER", "audio"),
        local_audio_dir=os.getenv("LOCAL_AUDIO_DIR", "data/audio"),
        azure_cosmos_endpoint=os.getenv("AZURE_COSMOS_ENDPOINT"),
        azure_cosmos_key=os.getenv("AZURE_COSMOS_KEY"),
        azure_cosmos_database=os.getenv("AZURE_COSMOS_DATABASE", "autodiag"),
        azure_cosmos_users_container=os.getenv(
            "AZURE_COSMOS_USERS_CONTAINER", "users"
        ),
        azure_cosmos_refresh_tokens_container=os.getenv(
            "AZURE_COSMOS_REFRESH_TOKENS_CONTAINER", "refresh_tokens"
        ),
        azure_cosmos_audio_results_container=os.getenv(
            "AZURE_COSMOS_AUDIO_RESULTS_CONTAINER", "audio_results"
        ),
        ai_model_name=os.getenv("AI_MODEL_NAME", "laion/clap-htsat-fused"),
        ai_inference_endpoint=os.getenv("AI_INFERENCE_ENDPOINT"),
        ai_inference_token=os.getenv("AI_INFERENCE_TOKEN"),
        ai_default_labels=os.getenv(
            "AI_DEFAULT_LABELS", "engine,brake,tire,road_noise,silence"
        ),
    )
