"""STT router — 语音转文字 API。"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile

from backend.api.dependencies import get_current_user, get_settings
from backend.api.schemas.stt import TranscribeResponse
from backend.clients import groq_stt
from backend.core.config import Settings
from backend.core.logger import get_logger
from backend.models.user import User

logger = get_logger(__name__)

router = APIRouter(prefix="/api/stt", tags=["stt"])

ALLOWED_CONTENT_TYPES = {
    "audio/webm",
    "audio/ogg",
    "audio/mp4",
    "audio/mpeg",
    "audio/wav",
    "audio/x-wav",
    "audio/flac",
}
MAX_AUDIO_SIZE_BYTES = 25 * 1024 * 1024  # 25MB (Groq limit)


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe_audio(
    file: UploadFile,
    language: str = "zh",
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_current_user),
) -> TranscribeResponse:
    """接收音频文件，调用 Groq Whisper 转写为文本。"""
    if not settings.groq_api_key:
        raise HTTPException(
            status_code=503,
            detail="Groq STT service not configured (GROQ_API_KEY missing)",
        )

    if file.content_type and file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported audio format: {file.content_type}",
        )

    audio_data = await file.read()
    if len(audio_data) > MAX_AUDIO_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"Audio file too large (max {MAX_AUDIO_SIZE_BYTES // 1024 // 1024}MB)",
        )

    try:
        result = await groq_stt.transcribe(
            audio_data=audio_data,
            filename=file.filename or "audio.webm",
            api_key=settings.groq_api_key,
            language=language,
            model=settings.groq_stt_model,
        )
    except Exception as exc:
        logger.error("stt_transcribe_failed", error=str(exc))
        raise HTTPException(status_code=502, detail="Transcription failed") from exc

    return TranscribeResponse(
        text=result.text,
        language=result.language,
        duration_seconds=result.duration_seconds,
    )
