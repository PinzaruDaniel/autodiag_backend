import json
from datetime import datetime, timezone
from typing import Any

from azure.core.exceptions import ResourceNotFoundError
from azure.data.tables import TableServiceClient, UpdateMode

from app.core.config import get_settings


class AzureTableRepository:
    def __init__(self) -> None:
        self._settings = get_settings()
        if not self._settings.azure_table_enabled:
            raise RuntimeError(
                "Azure Storage is required. Missing variable: AZURE_STORAGE_CONNECTION_STRING"
            )

        self._service = TableServiceClient.from_connection_string(
            self._settings.azure_storage_connection_string
        )
        self._users = self._service.create_table_if_not_exists(
            self._settings.azure_table_users
        )
        self._refresh_tokens = self._service.create_table_if_not_exists(
            self._settings.azure_table_refresh_tokens
        )
        self._audio_results = self._service.create_table_if_not_exists(
            self._settings.azure_table_audio_results
        )

    @staticmethod
    def _utc_now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _is_expired(expires_at: str) -> bool:
        return datetime.fromisoformat(expires_at) < datetime.now(timezone.utc)

    @staticmethod
    def _entity_to_dict(entity: Any) -> dict[str, Any]:
        return {k: v for k, v in entity.items() if not k.startswith("odata")}

    @staticmethod
    def _deserialize_predictions(item: dict[str, Any]) -> dict[str, Any]:
        result = dict(item)
        if isinstance(result.get("predictions"), str):
            try:
                result["predictions"] = json.loads(result["predictions"])
            except (json.JSONDecodeError, TypeError):
                result["predictions"] = []
        return result

    def create_user(self, *, email: str, password_hash: str) -> bool:
        if self.get_user(email=email):
            return False
        self._users.create_entity(
            {
                "PartitionKey": "user",
                "RowKey": email,
                "email": email,
                "password_hash": password_hash,
                "created_at": self._utc_now_iso(),
            }
        )
        return True

    def get_user(self, *, email: str) -> dict[str, Any] | None:
        try:
            entity = self._users.get_entity(partition_key="user", row_key=email)
            return self._entity_to_dict(entity)
        except ResourceNotFoundError:
            return None

    def update_user_password(self, *, email: str, new_password_hash: str) -> bool:
        try:
            entity = self._users.get_entity(partition_key="user", row_key=email)
        except ResourceNotFoundError:
            return False
        entity["password_hash"] = new_password_hash
        self._users.update_entity(entity, mode=UpdateMode.REPLACE)
        return True

    def store_refresh_token(
        self,
        *,
        token_id: str,
        user_email: str,
        issued_at: str,
        expires_at: str,
    ) -> None:
        self._refresh_tokens.create_entity(
            {
                "PartitionKey": user_email,
                "RowKey": token_id,
                "user_email": user_email,
                "issued_at": issued_at,
                "expires_at": expires_at,
                "revoked": False,
            }
        )

    def get_refresh_token(self, *, token_id: str, user_email: str) -> dict[str, Any] | None:
        try:
            entity = self._refresh_tokens.get_entity(
                partition_key=user_email, row_key=token_id
            )
            return self._entity_to_dict(entity)
        except ResourceNotFoundError:
            return None

    def revoke_refresh_token(self, *, token_id: str, user_email: str) -> None:
        try:
            entity = self._refresh_tokens.get_entity(
                partition_key=user_email, row_key=token_id
            )
        except ResourceNotFoundError:
            return
        entity["revoked"] = True
        entity["revoked_at"] = self._utc_now_iso()
        self._refresh_tokens.update_entity(entity, mode=UpdateMode.REPLACE)

    def validate_refresh_token(self, *, token_id: str, user_email: str) -> bool:
        token_item = self.get_refresh_token(token_id=token_id, user_email=user_email)
        if not token_item:
            return False
        if token_item.get("revoked"):
            return False
        expires_at = token_item.get("expires_at")
        if not expires_at:
            return False
        return not self._is_expired(expires_at)

    def create_audio_result(
        self,
        *,
        result_id: str,
        user_email: str,
        filename: str,
        size_bytes: int,
        storage: str,
        location: str,
        model_name: str,
        predictions: list[dict[str, Any]],
    ) -> dict[str, Any]:
        created_at = self._utc_now_iso()
        self._audio_results.create_entity(
            {
                "PartitionKey": user_email,
                "RowKey": result_id,
                "id": result_id,
                "user_email": user_email,
                "filename": filename,
                "size_bytes": size_bytes,
                "storage": storage,
                "location": location,
                "model_name": model_name,
                "predictions": json.dumps(predictions),
                "created_at": created_at,
            }
        )
        return self._deserialize_predictions(
            {
                "id": result_id,
                "user_email": user_email,
                "filename": filename,
                "size_bytes": size_bytes,
                "storage": storage,
                "location": location,
                "model_name": model_name,
                "predictions": predictions,
                "created_at": created_at,
            }
        )

    def get_audio_result(self, *, result_id: str, user_email: str) -> dict[str, Any] | None:
        try:
            entity = self._audio_results.get_entity(
                partition_key=user_email, row_key=result_id
            )
            return self._deserialize_predictions(self._entity_to_dict(entity))
        except ResourceNotFoundError:
            return None

    def list_audio_results(
        self, *, user_email: str, limit: int, offset: int
    ) -> list[dict[str, Any]]:
        filter_str = f"PartitionKey eq '{user_email}'"
        entities = list(self._audio_results.query_entities(filter_str))
        entities.sort(key=lambda e: e.get("created_at", ""), reverse=True)
        sliced = entities[offset : offset + limit]
        return [
            self._deserialize_predictions(self._entity_to_dict(e)) for e in sliced
        ]


azure_table_repository = AzureTableRepository()
