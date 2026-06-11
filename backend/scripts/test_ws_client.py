import asyncio
import json
import base64
import websockets

async def main():
    uri = "ws://localhost:8000/ws/live/testsession"
    async with websockets.connect(uri) as ws:
        await ws.send(json.dumps({"type": "session.start"}))
        print(await ws.recv())
        # send stop to end the session
        await ws.send(json.dumps({"type": "session.stop"}))
        print(await ws.recv())

if __name__ == '__main__':
    asyncio.run(main())
