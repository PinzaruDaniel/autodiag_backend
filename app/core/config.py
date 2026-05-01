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
    azure_table_users: str = "users"
    azure_table_refresh_tokens: str = "refreshtokens"
    azure_table_audio_results: str = "audioresults"
    ai_model_name: str = "laion/clap-htsat-unfused"
    ai_inference_endpoint: str | None = None
    ai_inference_token: str | None = None
    ai_default_labels: str = (
        "engine_knock,engine_misfire,engine_idle,engine_normal,"
        "engine_overheating,engine_startup,engine_acceleration,engine_stall"
    )

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
    def azure_table_enabled(self) -> bool:
        return bool(self.azure_storage_connection_string)


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
        azure_table_users=os.getenv("AZURE_TABLE_USERS", "users"),
        azure_table_refresh_tokens=os.getenv("AZURE_TABLE_REFRESH_TOKENS", "refreshtokens"),
        azure_table_audio_results=os.getenv("AZURE_TABLE_AUDIO_RESULTS", "audioresults"),
        ai_model_name=os.getenv("AI_MODEL_NAME", "laion/clap-htsat-unfused"),
        ai_inference_endpoint=os.getenv("AI_INFERENCE_ENDPOINT"),
        ai_inference_token=os.getenv("AI_INFERENCE_TOKEN"),
        ai_default_labels=os.getenv(
            "AI_DEFAULT_LABELS",
            "engine_knock,engine_misfire,engine_idle,engine_normal,"
            "engine_overheating,engine_startup,engine_acceleration,engine_stall",
        ),
    )
