import asyncio
from typing import AsyncIterator, Optional
from .base import BaseTranscriber, TranscriptEvent
import io
import json
import tempfile
import os
import logging

try:
    from pydub import AudioSegment
except Exception:  # pragma: no cover - pydub optional
    AudioSegment = None

try:
    from vosk import Model, KaldiRecognizer
except Exception:  # pragma: no cover - vosk optional
    Model = None
    KaldiRecognizer = None


class VoskTranscriber(BaseTranscriber):
    def __init__(self, model_path: Optional[str] = None, sample_rate: int = 16000):
        self.model_path = model_path
        self.sample_rate = sample_rate
        self.model = None
        self.recognizer = None
        self._q: asyncio.Queue[TranscriptEvent] = asyncio.Queue()
        self._closed = False

    async def start(self) -> None:
        if AudioSegment is None or Model is None:
            raise RuntimeError('pydub and vosk must be installed to use VoskTranscriber')

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._load_model)

    def _load_model(self):
        path = self.model_path
        if not path:
            raise RuntimeError('Vosk model path not provided')
        self.model = Model(path)
        self.recognizer = KaldiRecognizer(self.model, self.sample_rate)
        try:
            self.recognizer.SetWords(True)
        except Exception:
            pass

    async def send_audio(self, audio_bytes: bytes, mime_type: str) -> None:
        """Decode incoming audio bytes (webm/opus) to PCM16 and feed to Vosk.

        This is synchronous decoding executed in the event loop; for heavy loads
        consider moving decoding to an executor.
        """
        if AudioSegment is None:
            await self._q.put(TranscriptEvent(type='error', text='pydub not available'))
            return

        logger = logging.getLogger(__name__)

        # infer a likely format from the mime type
        fmt = None
        try:
            if mime_type:
                mt = mime_type.lower()
                if 'webm' in mt:
                    fmt = 'webm'
                elif 'ogg' in mt:
                    fmt = 'ogg'
                elif 'wav' in mt or 'wav' in mt:
                    fmt = 'wav'
        except Exception:
            fmt = None

        # If the client sent raw PCM bytes (browser decoded to PCM), accept them
        # directly and skip pydub/ffmpeg decoding which fails on partial
        # container fragments.
        mt_lower = (mime_type or '').lower()
        if 'pcm' in mt_lower or 'raw' in mt_lower:
            raw = audio_bytes
        else:
            # Try in-memory decode first, then fall back to a temp file if ffmpeg
            # fails to parse piped input (some container formats require file seek).
            try:
                if fmt:
                    audio = AudioSegment.from_file(io.BytesIO(audio_bytes), format=fmt)
                else:
                    audio = AudioSegment.from_file(io.BytesIO(audio_bytes))
                audio = audio.set_frame_rate(self.sample_rate).set_channels(1).set_sample_width(2)
                raw = audio.raw_data
            except Exception as exc_in_memory:
                # fallback: write bytes to a temp file and try again
                tmp = None
                try:
                    suffix = f'.{fmt}' if fmt else '.audio'
                    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
                    tmp.write(audio_bytes)
                    tmp.flush()
                    tmp.close()
                    try:
                        audio = AudioSegment.from_file(tmp.name, format=fmt)
                        audio = audio.set_frame_rate(self.sample_rate).set_channels(1).set_sample_width(2)
                        raw = audio.raw_data
                    except Exception as exc_file:
                        # include both errors for easier debugging
                        msg = f'decode_error: in-memory: {exc_in_memory}; file: {exc_file}'
                        logger.warning('Audio decode failed (in-memory and file): %s', msg)
                        await self._q.put(TranscriptEvent(type='error', text=msg))
                        return
                finally:
                    if tmp is not None:
                        try:
                            os.unlink(tmp.name)
                        except Exception:
                            pass

        # feed to recognizer in chunks
        chunk_size = 4000
        offset = 0
        while offset < len(raw):
            end = min(offset + chunk_size, len(raw))
            chunk = raw[offset:end]
            try:
                accepted = self.recognizer.AcceptWaveform(chunk)
                if accepted:
                    res = json.loads(self.recognizer.Result())
                    text = res.get('text', '').strip()
                    if text:
                        await self._q.put(TranscriptEvent(type='final', text=text))
                else:
                    part = json.loads(self.recognizer.PartialResult())
                    ptext = part.get('partial', '').strip()
                    if ptext:
                        await self._q.put(TranscriptEvent(type='partial', text=ptext))
            except Exception as exc:
                await self._q.put(TranscriptEvent(type='error', text=f'recognizer_error: {exc}'))
            offset = end

    async def events(self) -> AsyncIterator[TranscriptEvent]:
        while not self._closed:
            ev = await self._q.get()
            yield ev

    async def close(self) -> None:
        self._closed = True
        try:
            if self.recognizer:
                final = json.loads(self.recognizer.FinalResult() or '{}')
                text = final.get('text', '').strip()
                if text:
                    await self._q.put(TranscriptEvent(type='final', text=text))
        except Exception:
            pass
