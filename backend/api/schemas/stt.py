"""STT schemas — 语音转文字 API 的请求/响应 DTO。"""

from pydantic import BaseModel


class TranscribeResponse(BaseModel):
    """转写结果响应。"""

    text: str
    language: str
    duration_seconds: float
