from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status

from app.core.config import get_settings
from app.dependencies import get_current_user
from app.models.audio import AudioResult, AudioResultsResponse
from app.services.audio_result_service import audio_result_service
from app.services.audio_storage_service import audio_storage_service
from app.services.classification_service import classification_service

router = APIRouter(prefix="/audio", tags=["audio"])


@router.post("/send")
async def send_audio(
    audio: UploadFile = File(...),
    user: dict[str, str] = Depends(get_current_user),
) -> dict:
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
    classification = classification_service.classify_audio(
        audio_content=bytes(content),
        content_type=audio.content_type,
        filename=audio.filename,
    )
    result = audio_result_service.create_result(
        user_email=user["email"],
        filename=audio.filename,
        size_bytes=total_size,
        storage=storage_backend,
        location=location,
        model_name=classification["model_name"],
        predictions=classification["predictions"],
    )

    return {
        "message": "Audio received",
        "result_id": result["result_id"],
        "created_at": result.get("created_at"),
        "filename": audio.filename,
        "size_bytes": total_size,
        "uploaded_by": user["email"],
        "storage": storage_backend,
        "location": location,
        "classification": {
            "model_name": classification["model_name"],
            "predictions": classification["predictions"],
        },
    }


@router.get("/results", response_model=AudioResultsResponse)
def list_results(
    user: dict[str, str] = Depends(get_current_user),
    limit: int = Query(10, ge=1, le=100),
    page: int = Query(1, ge=1),
) -> AudioResultsResponse:
    items = audio_result_service.list_results(
        user_email=user["email"],
        limit=limit,
        page=page,
    )
    return AudioResultsResponse(items=items, limit=limit, page=page)


@router.get("/results/{result_id}", response_model=AudioResult)
def get_result(
    result_id: int,
    user: dict[str, str] = Depends(get_current_user),
) -> AudioResult:
    result = audio_result_service.get_result(
        user_email=user["email"],
        result_id=result_id,
    )
    return AudioResult(**result)
