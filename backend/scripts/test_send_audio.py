import asyncio
import json
import base64
import websockets
import io
import wave
import math
import struct


def make_sine_wav(duration_s=1.0, sr=16000, freq=440.0):
    n_samples = int(duration_s * sr)
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        for i in range(n_samples):
            t = i / sr
            # sine wave
            val = int(16000 * 0.5 * math.sin(2 * math.pi * freq * t))
            wf.writeframes(struct.pack('<h', val))
    return buf.getvalue()


async def main():
    uri = 'ws://localhost:8000/ws/live/testsession'
    audio = make_sine_wav()
    async with websockets.connect(uri) as ws:
        await ws.send(json.dumps({"type": "session.start"}))
        print(await ws.recv())

        payload = {
            'type': 'audio.chunk',
            'payload': {
                'dataBase64': base64.b64encode(audio).decode('ascii'),
                'mimeType': 'audio/wav'
            }
        }
        await ws.send(json.dumps(payload))

        # collect a few messages (partial/final)
        for _ in range(6):
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
                print(msg)
            except asyncio.TimeoutError:
                break

        await ws.send(json.dumps({"type": "session.stop"}))
        print(await ws.recv())

if __name__ == '__main__':
    asyncio.run(main())
