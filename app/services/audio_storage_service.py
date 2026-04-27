import logging
from pathlib import Path
from uuid import uuid4

from app.core.config import get_settings

logger = logging.getLogger(__name__)

try:
    from azure.storage.blob import BlobServiceClient, ContentSettings
except ImportError:  # pragma: no cover
    BlobServiceClient = None  # type: ignore[assignment]
    ContentSettings = None  # type: ignore[assignment]


class AudioStorageService:
    def __init__(self) -> None:
        self._settings = get_settings()

    def store_audio(
        self, *, filename: str, content_type: str | None, content: bytes
    ) -> tuple[str, str]:
        safe_filename = f"{uuid4()}-{Path(filename).name}"
        if self._settings.azure_enabled:
            azure_location = self._try_store_in_azure(
                blob_name=safe_filename,
                content_type=content_type or "application/octet-stream",
                content=content,
            )
            if azure_location:
                return "azure", azure_location

        local_location = self._store_locally(safe_filename=safe_filename, content=content)
        return "local", local_location

    def _try_store_in_azure(
        self, *, blob_name: str, content_type: str, content: bytes
    ) -> str | None:
        if not self._settings.azure_storage_connection_string or BlobServiceClient is None:
            return None

        try:
            blob_service_client = BlobServiceClient.from_connection_string(
                self._settings.azure_storage_connection_string
            )
            container_client = blob_service_client.get_container_client(
                self._settings.azure_storage_container
            )
            if not container_client.exists():
                container_client.create_container()

            blob_client = container_client.get_blob_client(blob_name)
            blob_client.upload_blob(
                content,
                overwrite=True,
                content_settings=ContentSettings(content_type=content_type),
            )
            return f"{self._settings.azure_storage_container}/{blob_name}"
        except Exception:
            logger.exception("Azure upload failed; falling back to local storage.")
            return None

    def _store_locally(self, *, safe_filename: str, content: bytes) -> str:
        local_dir = Path(self._settings.local_audio_dir)
        local_dir.mkdir(parents=True, exist_ok=True)
        target_path = local_dir / safe_filename
        target_path.write_bytes(content)
        return str(target_path)


audio_storage_service = AudioStorageService()
