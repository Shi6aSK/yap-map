from abc import ABC, abstractmethod
from typing import AsyncIterator, Optional
from pydantic import BaseModel


class TranscriptEvent(BaseModel):
    type: str  # "partial" or "final"
    text: str
    speaker: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    confidence: Optional[float] = None


class BaseTranscriber(ABC):
    @abstractmethod
    async def start(self) -> None:
        pass

    @abstractmethod
    async def send_audio(self, audio_bytes: bytes, mime_type: str) -> None:
        pass

    @abstractmethod
    async def events(self) -> AsyncIterator[TranscriptEvent]:
        pass

    @abstractmethod
    async def close(self) -> None:
        pass
