import asyncio
from typing import AsyncIterator
from .base import BaseTranscriber, TranscriptEvent


class MockTranscriber(BaseTranscriber):
    """A simple mock transcriber that generates partial and final events from incoming audio."""

    def __init__(self) -> None:
        self._q: asyncio.Queue[TranscriptEvent] = asyncio.Queue()
        self._closed = False

    async def start(self) -> None:
        # nothing to initialize for mock
        self._closed = False

    async def send_audio(self, audio_bytes: bytes, mime_type: str) -> None:
        # simulate a partial event
        partial = TranscriptEvent(type="partial", text=f"(mock partial) {len(audio_bytes)} bytes")
        await self._q.put(partial)

        # schedule a final event shortly after
        async def _finalize():
            await asyncio.sleep(0.6)
            final = TranscriptEvent(type="final", text=f"(mock final) transcribed {len(audio_bytes)} bytes")
            await self._q.put(final)

        asyncio.create_task(_finalize())

    async def events(self) -> AsyncIterator[TranscriptEvent]:
        while not self._closed:
            ev = await self._q.get()
            yield ev

    async def close(self) -> None:
        self._closed = True
