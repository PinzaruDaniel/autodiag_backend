from typing import Any
from uuid import uuid4

from fastapi import HTTPException, status

from app.repositories.azure_cosmos import azure_cosmos_repository


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
        result_id = str(uuid4())
        item = azure_cosmos_repository.create_audio_result(
            result_id=result_id,
            user_email=user_email,
            filename=filename,
            size_bytes=size_bytes,
            storage=storage,
            location=location,
            model_name=model_name,
            predictions=predictions,
        )
        return self._normalize_result(item)

    def list_results(self, *, user_email: str, limit: int, offset: int) -> list[dict]:
        items = azure_cosmos_repository.list_audio_results(
            user_email=user_email, limit=limit, offset=offset
        )
        return [self._normalize_result(item) for item in items]

    def get_result(self, *, user_email: str, result_id: str) -> dict:
        result = azure_cosmos_repository.get_audio_result(
            result_id=result_id, user_email=user_email
        )
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Classification result not found"
            )
        return self._normalize_result(result)


audio_result_service = AudioResultService()
