import io
import logging
from typing import Any

import librosa
import numpy as np
import soundfile as sf
import torch
from fastapi import HTTPException, status
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

    @staticmethod
    def _read_audio(
        audio_content: bytes, content_type: str, filename: str
    ) -> tuple[np.ndarray, int]:
        """Read audio file, handling both MP3 and other formats."""
        is_mp3 = (
            filename.lower().endswith(".mp3")
            or content_type.lower() in ("audio/mpeg", "audio/mp3")
        )

        logger.info(
            "Reading audio file '%s' (is_mp3=%s, content_type=%s)",
            filename,
            is_mp3,
            content_type,
        )

        try:
            if is_mp3:
                # Use librosa for MP3 files
                logger.debug("Using librosa to read MP3 file")
                audio_array, sample_rate = librosa.load(
                    io.BytesIO(audio_content), sr=None, mono=False
                )
            else:
                # Use soundfile for other formats (WAV, FLAC, OGG, etc.)
                logger.debug("Using soundfile to read audio file")
                audio_array, sample_rate = sf.read(io.BytesIO(audio_content))

            logger.debug(
                "Audio loaded: shape=%s, dtype=%s, sample_rate=%d",
                audio_array.shape,
                audio_array.dtype,
                sample_rate,
            )

            if audio_array.size == 0:
                raise ValueError("Audio array is empty after reading")

            return audio_array, sample_rate
        except Exception as exc:
            logger.error(
                "Failed to read audio file '%s': %s", filename, str(exc), exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Failed to read audio file: {str(exc)}",
            ) from exc

    def classify_audio(
        self, *, audio_content: bytes, content_type: str, filename: str
    ) -> dict[str, Any]:
        settings = get_settings()
        labels = [
            value.strip()
            for value in settings.ai_default_labels.split(",")
            if value.strip()
        ]

        logger.info(
            "Classifying audio: filename=%s, content_type=%s, size=%d bytes",
            filename,
            content_type,
            len(audio_content),
        )

        try:
            self._load_model()
            audio_array, sample_rate = self._read_audio(
                audio_content, content_type, filename
            )

            # Convert stereo/multi-channel to mono
            if audio_array.ndim > 1:
                logger.debug("Converting from %d channels to mono", audio_array.shape[1])
                audio_array = audio_array.mean(axis=1)
            audio_array = audio_array.astype(np.float32)

            # CLAP requires 48000 Hz; resample if needed
            target_sr = 48000
            if sample_rate != target_sr:
                logger.debug(
                    "Resampling from %d Hz to %d Hz", sample_rate, target_sr
                )
                num_samples = int(round(len(audio_array) * target_sr / sample_rate))
                audio_array = np.interp(
                    np.linspace(0, len(audio_array) - 1, num_samples),
                    np.arange(len(audio_array)),
                    audio_array,
                )
                sample_rate = target_sr

            logger.debug(
                "Preprocessing complete: shape=%s, sample_rate=%d",
                audio_array.shape,
                sample_rate,
            )

            inputs = self._processor(
                audio=audio_array,
                text=labels,
                return_tensors="pt",
                padding=True,
                sampling_rate=sample_rate,
            )

            logger.debug("Processing audio through CLAP model")
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

            logger.info("Classification successful: top label=%s, score=%.4f",
                       predictions[0]["label"] if predictions else "N/A",
                       predictions[0]["score"] if predictions else 0)

            return {
                "model_name": settings.ai_model_name,
                "predictions": predictions,
                "source": "local",
                "filename": filename,
            }

        except HTTPException:
            # Re-raise HTTPException (e.g., audio reading errors)
            raise
        except Exception as exc:
            logger.exception(
                "Local AI classification failed for '%s': %s",
                filename,
                str(exc),
            )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Audio classification failed: {str(exc)}",
            ) from exc


classification_service = ClassificationService()
