from datetime import datetime, timezone
from typing import Any

from azure.cosmos import CosmosClient, exceptions
from azure.cosmos.container import ContainerProxy

from app.core.config import get_settings


class AzureCosmosRepository:
    def __init__(self) -> None:
        self._settings = get_settings()
        if not self._settings.azure_cosmos_enabled:
            raise RuntimeError(
                "Azure Cosmos DB is required. Set AZURE_COSMOS_ENDPOINT and AZURE_COSMOS_KEY."
            )

        self._client = CosmosClient(
            url=self._settings.azure_cosmos_endpoint,
            credential=self._settings.azure_cosmos_key,
        )
        self._database = self._client.create_database_if_not_exists(
            self._settings.azure_cosmos_database
        )

        self._users = self._database.create_container_if_not_exists(
            id=self._settings.azure_cosmos_users_container,
            partition_key={"paths": ["/email"], "kind": "Hash"},
        )
        self._refresh_tokens = self._database.create_container_if_not_exists(
            id=self._settings.azure_cosmos_refresh_tokens_container,
            partition_key={"paths": ["/user_email"], "kind": "Hash"},
        )
        self._audio_results = self._database.create_container_if_not_exists(
            id=self._settings.azure_cosmos_audio_results_container,
            partition_key={"paths": ["/user_email"], "kind": "Hash"},
        )

    @staticmethod
    def _utc_now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _is_expired(expires_at: str) -> bool:
        return datetime.fromisoformat(expires_at) <= datetime.now(timezone.utc)

    @staticmethod
    def _container_read_item(
        container: ContainerProxy, *, item_id: str, partition_key: str
    ) -> dict[str, Any] | None:
        try:
            return container.read_item(item=item_id, partition_key=partition_key)
        except exceptions.CosmosResourceNotFoundError:
            return None

    def create_user(self, *, email: str, password_hash: str) -> bool:
        existing = self.get_user(email=email)
        if existing:
            return False
        self._users.create_item(
            {
                "id": email,
                "email": email,
                "password_hash": password_hash,
                "created_at": self._utc_now_iso(),
            }
        )
        return True

    def get_user(self, *, email: str) -> dict[str, Any] | None:
        return self._container_read_item(self._users, item_id=email, partition_key=email)

    def store_refresh_token(
        self,
        *,
        token_id: str,
        user_email: str,
        issued_at: str,
        expires_at: str,
    ) -> None:
        self._refresh_tokens.create_item(
            {
                "id": token_id,
                "token_id": token_id,
                "user_email": user_email,
                "issued_at": issued_at,
                "expires_at": expires_at,
                "revoked": False,
                "revoked_at": None,
            }
        )

    def get_refresh_token(self, *, token_id: str, user_email: str) -> dict[str, Any] | None:
        return self._container_read_item(
            self._refresh_tokens, item_id=token_id, partition_key=user_email
        )

    def revoke_refresh_token(self, *, token_id: str, user_email: str) -> None:
        token_item = self.get_refresh_token(token_id=token_id, user_email=user_email)
        if not token_item:
            return
        token_item["revoked"] = True
        token_item["revoked_at"] = self._utc_now_iso()
        self._refresh_tokens.replace_item(item=token_item["id"], body=token_item)

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
        item = {
            "id": result_id,
            "result_id": result_id,
            "user_email": user_email,
            "filename": filename,
            "size_bytes": size_bytes,
            "storage": storage,
            "location": location,
            "model_name": model_name,
            "predictions": predictions,
            "created_at": self._utc_now_iso(),
        }
        self._audio_results.create_item(item)
        return item

    def get_audio_result(self, *, result_id: str, user_email: str) -> dict[str, Any] | None:
        return self._container_read_item(
            self._audio_results, item_id=result_id, partition_key=user_email
        )

    def list_audio_results(
        self, *, user_email: str, limit: int, offset: int
    ) -> list[dict[str, Any]]:
        query = (
            "SELECT * FROM c WHERE c.user_email = @user_email "
            "ORDER BY c.created_at DESC OFFSET @offset LIMIT @limit"
        )
        params = [
            {"name": "@user_email", "value": user_email},
            {"name": "@offset", "value": offset},
            {"name": "@limit", "value": limit},
        ]
        return list(
            self._audio_results.query_items(
                query=query,
                parameters=params,
                enable_cross_partition_query=False,
            )
        )


azure_cosmos_repository = AzureCosmosRepository()
