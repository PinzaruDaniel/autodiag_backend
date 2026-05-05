import io
import logging
from typing import Any

import numpy as np
import soundfile as sf
import torch
from transformers import ClapModel, ClapProcessor

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class ClassificationService:
    def __init__(self) -> None:
        self._model: ClapModel | None = None
        self._processor: ClapProcessor | None = None

    def _load_model(self) -> None:
        if self._model is not None:
            return
        model_name = get_settings().ai_model_name
        logger.info("Loading CLAP model '%s'…", model_name)
        self._processor = ClapProcessor.from_pretrained(model_name)
        self._model = ClapModel.from_pretrained(model_name)
        self._model.eval()
        logger.info("CLAP model loaded.")

    def classify_audio(
        self, *, audio_content: bytes, content_type: str, filename: str
    ) -> dict[str, Any]:
        settings = get_settings()
        labels = [
            value.strip()
            for value in settings.ai_default_labels.split(",")
            if value.strip()
        ]

        try:
            self._load_model()
            audio_array, sample_rate = sf.read(io.BytesIO(audio_content))
            # Convert stereo/multi-channel to mono
            if audio_array.ndim > 1:
                audio_array = audio_array.mean(axis=1)
            audio_array = audio_array.astype(np.float32)

            # CLAP requires 48000 Hz; resample if needed
            target_sr = 48000
            if sample_rate != target_sr:
                num_samples = int(round(len(audio_array) * target_sr / sample_rate))
                audio_array = np.interp(
                    np.linspace(0, len(audio_array) - 1, num_samples),
                    np.arange(len(audio_array)),
                    audio_array,
                )
                sample_rate = target_sr

            inputs = self._processor(
                audios=audio_array,
                text=labels,
                return_tensors="pt",
                padding=True,
                sampling_rate=sample_rate,
            )

            with torch.no_grad():
                outputs = self._model(**inputs)
                probs = outputs.logits_per_audio.softmax(dim=-1).squeeze(0).tolist()

            predictions = sorted(
                [
                    {"label": label, "score": float(score)}
                    for label, score in zip(labels, probs)
                ],
                key=lambda x: x["score"],
                reverse=True,
            )

            return {
                "model_name": settings.ai_model_name,
                "predictions": predictions,
                "source": "local",
                "filename": filename,
            }

        except Exception as exc:
            logger.exception(
                "Local AI classification failed for '%s': %s. Using fallback.",
                filename,
                str(exc),
            )
            label = labels[0] if labels else "unknown"
            return {
                "model_name": settings.ai_model_name,
                "predictions": [{"label": label, "score": 0.0}],
                "source": "fallback",
                "filename": filename,
            }


classification_service = ClassificationService()
