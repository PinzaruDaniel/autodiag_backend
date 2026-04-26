from dataclasses import dataclass
from functools import lru_cache
import os


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

    @property
    def max_audio_size_bytes(self) -> int:
        return self.max_audio_size_mb * self.mb_in_bytes

    @property
    def chunk_size_bytes(self) -> int:
        return self.mb_in_bytes

    @property
    def azure_enabled(self) -> bool:
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
    )
