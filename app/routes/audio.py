from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.core.config import get_settings
from app.dependencies import get_current_user
from app.services.audio_storage_service import audio_storage_service

router = APIRouter(prefix="/audio", tags=["audio"])


@router.post("/send")
async def send_audio(
    audio: UploadFile = File(...),
    user: dict[str, str] = Depends(get_current_user),
) -> dict[str, str | int]:
    settings = get_settings()
    if not audio.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No filename provided"
        )
    if not audio.content_type or not audio.content_type.startswith("audio/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="File must be audio"
        )

    total_size = 0
    content = bytearray()
    while True:
        chunk = await audio.read(settings.chunk_size_bytes)
        if not chunk:
            break
        total_size += len(chunk)
        if total_size > settings.max_audio_size_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Audio file too large",
            )
        content.extend(chunk)

    if total_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Empty audio file"
        )

    storage_backend, location = audio_storage_service.store_audio(
        filename=audio.filename,
        content_type=audio.content_type,
        content=bytes(content),
    )

    return {
        "message": "Audio received",
        "filename": audio.filename,
        "size_bytes": total_size,
        "uploaded_by": user["email"],
        "storage": storage_backend,
        "location": location,
    }
