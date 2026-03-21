"""Groq Whisper STT client — 调用 Groq API 将音频转写为文本。"""

from dataclasses import dataclass

import httpx

from backend.core.logger import get_logger

logger = get_logger(__name__)

GROQ_TRANSCRIPTION_URL = "https://api.groq.com/openai/v1/audio/transcriptions"


@dataclass(frozen=True)
class TranscribeResult:
    """转写结果。"""

    text: str
    language: str
    duration_seconds: float


async def transcribe(
    audio_data: bytes,
    filename: str,
    api_key: str,
    language: str = "zh",
    model: str = "whisper-large-v3-turbo",
) -> TranscribeResult:
    """调用 Groq Whisper API 转写音频。"""
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            GROQ_TRANSCRIPTION_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            files={"file": (filename, audio_data)},
            data={
                "model": model,
                "language": language,
                "response_format": "verbose_json",
            },
        )
        response.raise_for_status()
        data = response.json()

    logger.info(
        "groq_stt_transcribed",
        language=data.get("language", language),
        duration=data.get("duration", 0),
    )

    return TranscribeResult(
        text=data["text"],
        language=data.get("language", language),
        duration_seconds=data.get("duration", 0.0),
    )
