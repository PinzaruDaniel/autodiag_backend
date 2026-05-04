from typing import Any
from datetime import datetime, timezone

from fastapi import HTTPException, status

from app.repositories.azure_table import azure_table_repository


class AudioResultService:
    @staticmethod
    def _normalize_result(item: dict) -> dict:
        normalized = dict(item)
        normalized["result_id"] = str(normalized.get("id", ""))
        normalized.pop("id", None)
        return normalized

    def create_result(
        self,
        *,
        user_email: str,
        filename: str,
        size_bytes: int,
        storage: str,
        location: str,
        model_name: str,
        predictions: list[dict[str, Any]],
    ) -> dict:
        result_id = int(datetime.now(timezone.utc).timestamp() * 1_000_000)
        item = azure_table_repository.create_audio_result(
            result_id=str(result_id),
            user_email=user_email,
            filename=filename,
            size_bytes=size_bytes,
            storage=storage,
            location=location,
            model_name=model_name,
            predictions=predictions,
        )
        return self._normalize_result(item)

    def list_results(self, *, user_email: str, limit: int, page: int) -> list[dict]:
        items = azure_table_repository.list_audio_results(
            user_email=user_email, limit=limit, page=page
        )
        return [self._normalize_result(item) for item in items]

    def get_result(self, *, user_email: str, result_id: str) -> dict:
        result = azure_table_repository.get_audio_result(
            result_id=result_id, user_email=user_email
        )
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Classification result not found"
            )
        return self._normalize_result(result)


audio_result_service = AudioResultService()
