from .base import BaseTranscriber, TranscriptEvent
from typing import AsyncIterator, Optional


class OpenAIRealtimeTranscriber(BaseTranscriber):
    """Placeholder for OpenAI Realtime transcription adapter.

    This is a stub with the expected async interface. Integration requires
    setting up an authenticated WebSocket/WebRTC session with the provider.
    """

    async def start(self) -> None:
        # TODO: implement provider session startup
        raise NotImplementedError()

    async def send_audio(self, audio_bytes: bytes, mime_type: str) -> None:
        # TODO: stream audio bytes to provider
        raise NotImplementedError()

    async def events(self) -> AsyncIterator[TranscriptEvent]:
        # TODO: yield TranscriptEvent objects from provider responses
        if False:
            yield TranscriptEvent(type='partial', text='')

    async def close(self) -> None:
        # TODO: close provider connection
        raise NotImplementedError()
