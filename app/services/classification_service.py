import json
import logging
from typing import Any
from urllib import error, request

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class ClassificationService:
    def __init__(self) -> None:
        self._settings = get_settings()

    def classify_audio(
        self, *, audio_content: bytes, content_type: str, filename: str
    ) -> dict[str, Any]:
        endpoint = self._settings.ai_inference_endpoint
        if endpoint:
            remote_result = self._classify_with_remote_endpoint(
                endpoint=endpoint,
                audio_content=audio_content,
                content_type=content_type,
            )
            if remote_result is not None:
                return remote_result

        labels = [
            value.strip()
            for value in self._settings.ai_default_labels.split(",")
            if value.strip()
        ]
        label = labels[0] if labels else "unknown"
        return {
            "model_name": self._settings.ai_model_name,
            "predictions": [{"label": label, "score": 0.0}],
            "source": "fallback",
            "filename": filename,
        }

    def _classify_with_remote_endpoint(
        self, *, endpoint: str, audio_content: bytes, content_type: str
    ) -> dict[str, Any] | None:
        headers = {"Content-Type": content_type}
        if self._settings.ai_inference_token:
            headers["Authorization"] = f"Bearer {self._settings.ai_inference_token}"

        req = request.Request(
            url=endpoint,
            data=audio_content,
            headers=headers,
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=30) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            predictions = self._normalize_predictions(payload)
            return {
                "model_name": self._settings.ai_model_name,
                "predictions": predictions,
                "source": "remote",
            }
        except error.HTTPError as exc:
            body = ""
            try:
                body = exc.read().decode("utf-8")
            except Exception:
                body = "<unavailable>"
            logger.exception(
                "Audio classification HTTP error for endpoint %s: status=%s body=%s",
                endpoint,
                exc.code,
                body,
            )
            return None
        except (error.URLError, json.JSONDecodeError) as exc:
            logger.exception(
                "Audio classification failed for endpoint %s: %s. Using fallback prediction.",
                endpoint,
                str(exc),
            )
            return None

    @staticmethod
    def _normalize_predictions(payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, dict) and isinstance(payload.get("predictions"), list):
            raw_predictions = payload["predictions"]
        elif isinstance(payload, list):
            raw_predictions = payload
        else:
            return []

        normalized: list[dict[str, Any]] = []
        for item in raw_predictions:
            if not isinstance(item, dict):
                continue
            label = item.get("label")
            score = item.get("score")
            if isinstance(label, str) and isinstance(score, (int, float)):
                normalized.append({"label": label, "score": float(score)})
        return normalized


classification_service = ClassificationService()
