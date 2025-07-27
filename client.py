import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import websockets

app = FastAPI()

PI_CAMERA_WS = "ws://192.168.196.140:8000/ws/camera"

@app.websocket("/ws/proxy_camera")
async def proxy_camera(websocket: WebSocket):
    await websocket.accept()
    try:
        async with websockets.connect(PI_CAMERA_WS) as pi_ws:
            while True:
                frame = await pi_ws.recv()
                await websocket.send_bytes(frame)
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        await websocket.close()