import asyncio
import json
import io
import websockets
import numpy as np
import cv2
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from ultralytics import YOLO
from PIL import Image

app = FastAPI()

# Use different port to avoid conflict with Pi camera
PI_CAMERA_WS = "ws://192.168.196.140:8000/ws/camera"

# Load YOLOv8 model with error handling
try:
    model = YOLO("yolov8n.pt")
    print("YOLO model loaded successfully")
except Exception as e:
    print(f"Error loading YOLO model: {e}")
    model = None

def detect_and_render(frame_bytes):
    """Process frame with YOLO detection and render bounding boxes"""
    try:
        # Convert bytes to image
        img = Image.open(io.BytesIO(frame_bytes)).convert("RGB")
        frame = np.array(img)
        
        # Skip detection if model failed to load
        if model is None:
            _, jpeg = cv2.imencode('.jpg', cv2.cvtColor(frame, cv2.COLOR_RGB2BGR), 
                                 [int(cv2.IMWRITE_JPEG_QUALITY), 95])
            return jpeg.tobytes(), []
        
        # Run YOLO detection
        results = model(frame)[0]
        detections = []
        
        # Process detections
        if results.boxes is not None:
            for box in results.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                conf = float(box.conf[0])
                cls = int(box.cls[0])
                label = f"{model.names[cls]} {conf:.2f}"
                
                detections.append({
                    "class": model.names[cls],
                    "confidence": conf,
                    "bbox": [x1, y1, x2, y2]
                })
                
                # Draw bounding box and label
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(frame, label, (x1, y1 - 10), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        # Encode frame as JPEG
        _, jpeg = cv2.imencode('.jpg', cv2.cvtColor(frame, cv2.COLOR_RGB2BGR), 
                             [int(cv2.IMWRITE_JPEG_QUALITY), 95])
        return jpeg.tobytes(), detections
        
    except Exception as e:
        print(f"Error in detect_and_render: {e}")
        # Return original frame on error
        return frame_bytes, []

@app.websocket("/ws/proxy_camera")
async def proxy_camera(websocket: WebSocket):
    """Proxy camera feed from Pi with YOLO detection"""
    await websocket.accept()
    pi_ws = None
    
    try:
        print(f"Connecting to Pi camera at {PI_CAMERA_WS}")
        pi_ws = await websockets.connect(PI_CAMERA_WS)
        print("Connected to Pi camera")
        
        while True:
            try:
                # Receive frame from Pi camera
                frame = await asyncio.wait_for(pi_ws.recv(), timeout=5.0)
                
                # Skip if frame is not bytes
                if not isinstance(frame, (bytes, bytearray)):
                    print(f"Received non-bytes frame: {type(frame)}")
                    continue
                
                # Process frame with YOLO detection
                rendered, detections = detect_and_render(frame)
                
                # Send detections as JSON
                detection_msg = json.dumps({"detections": detections})
                await websocket.send_text(detection_msg)
                
                # Send processed image as bytes
                await websocket.send_bytes(rendered)
                
            except asyncio.TimeoutError:
                print("Timeout waiting for frame from Pi camera")
                break
            except websockets.exceptions.ConnectionClosed:
                print("Pi camera connection closed")
                break
            except Exception as e:
                print(f"Error processing frame: {e}")
                continue
                
    except websockets.exceptions.InvalidURI:
        print(f"Invalid Pi camera URI: {PI_CAMERA_WS}")
    except websockets.exceptions.ConnectionRefused:
        print("Connection refused by Pi camera")
    except WebSocketDisconnect:
        print("Client disconnected")
    except Exception as e:
        print(f"Proxy error: {e}")
    finally:
        if pi_ws:
            await pi_ws.close()
        try:
            await websocket.close()
        except:
            pass

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"message": "Camera proxy server running"}

if __name__ == "__main__":
    import uvicorn
    # Use different port (8001) to avoid conflict with Pi camera (8000)
    uvicorn.run("client:app", host="0.0.0.0", port=8001, reload=True)