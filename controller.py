from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import logging
import cv2
import asyncio
from concurrent.futures import ThreadPoolExecutor
from car import TankCar
import time
# Add this import:
from ir import ir_stream
from starlette.responses import StreamingResponse

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Tank Car Controller", description="Simple tank drive car control system")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global car instance
car: TankCar = None

# Thread executor for blocking operations
executor = ThreadPoolExecutor(max_workers=4)

# Global camera instance for sharing across connections
global_camera = None
camera_lock = asyncio.Lock()

# Pydantic models
class TankDriveCommand(BaseModel):
    left_speed: float = Field(..., ge=-100, le=100, description="Left motor speed (-100 to 100)")
    right_speed: float = Field(..., ge=-100, le=100, description="Right motor speed (-100 to 100)")

class DirectionalCommand(BaseModel):
    speed: float = Field(50, ge=0, le=100, description="Motor speed (0-100%)")

# Initialize car
@app.on_event("startup")
async def startup_event():
    global car, global_camera
    try:
        car = TankCar()
        logger.info("Tank car initialized")
        
        # Initialize shared camera
        global_camera = cv2.VideoCapture(0)
        if global_camera.isOpened():
            global_camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            global_camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            global_camera.set(cv2.CAP_PROP_FPS, 30)
            global_camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Reduce buffer for lower latency
            logger.info("Camera initialized")
        else:
            logger.warning("Camera initialization failed")
            
    except Exception as e:
        logger.error(f"Failed to initialize car: {e}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    global car, global_camera
    try:
        if car:
            car.cleanup()
        if global_camera:
            global_camera.release()
        logger.info("Car and camera cleaned up")
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")

# Car control endpoints - these should be instant
@app.post("/car/move")
async def move_car(command: TankDriveCommand):
    """Control both motors independently (tank drive)"""
    try:
        car.move(command.left_speed, command.right_speed)
        return {
            "message": "Car move command executed", 
            "left_speed": command.left_speed, 
            "right_speed": command.right_speed
        }
    except Exception as e:
        logger.error(f"Error moving car: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/car/forward")
async def move_forward(command: DirectionalCommand = DirectionalCommand()):
    """Move forward at specified speed"""
    try:
        car.forward(command.speed)
        return {"message": f"Moving forward at {command.speed}% speed"}
    except Exception as e:
        logger.error(f"Error moving forward: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/car/backward")
async def move_backward(command: DirectionalCommand = DirectionalCommand()):
    """Move backward at specified speed"""
    try:
        car.backward(command.speed)
        return {"message": f"Moving backward at {command.speed}% speed"}
    except Exception as e:
        logger.error(f"Error moving backward: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/car/left")
async def turn_left(command: DirectionalCommand = DirectionalCommand()):
    """Turn left (spin in place)"""
    try:
        car.turn_left(command.speed)
        return {"message": f"Turning left at {command.speed}% speed"}
    except Exception as e:
        logger.error(f"Error turning left: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/car/right")
async def turn_right(command: DirectionalCommand = DirectionalCommand()):
    """Turn right (spin in place)"""
    try:
        car.turn_right(command.speed)
        return {"message": f"Turning right at {command.speed}% speed"}
    except Exception as e:
        logger.error(f"Error turning right: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/car/pivot-left")
async def pivot_left(command: DirectionalCommand = DirectionalCommand()):
    """Pivot left (only right motor moves)"""
    try:
        car.pivot_left(command.speed)
        return {"message": f"Pivoting left at {command.speed}% speed"}
    except Exception as e:
        logger.error(f"Error pivoting left: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/car/pivot-right")
async def pivot_right(command: DirectionalCommand = DirectionalCommand()):
    """Pivot right (only left motor moves)"""
    try:
        car.pivot_right(command.speed)
        return {"message": f"Pivoting right at {command.speed}% speed"}
    except Exception as e:
        logger.error(f"Error pivoting right: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/car/stop")
async def stop_car():
    """Stop the car - INSTANT RESPONSE"""
    try:
        car.stop()
        return {"message": "Car stopped"}
    except Exception as e:
        logger.error(f"Error stopping car: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Optimized camera streaming functions
async def capture_frame_async():
    """Capture a frame from camera in thread pool"""
    if not global_camera or not global_camera.isOpened():
        return None
    
    def _capture():
        ret, frame = global_camera.read()
        if not ret:
            return None
        # Use lower quality for faster encoding
        _, jpeg = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
        return jpeg.tobytes()
    
    return await asyncio.get_event_loop().run_in_executor(executor, _capture)

@app.websocket("/ws/camera")
async def webcam_stream(websocket: WebSocket):
    """WebSocket endpoint to stream webcam footage with minimal latency."""
    await websocket.accept()
    
    try:
        if not global_camera or not global_camera.isOpened():
            await websocket.send_text("Camera not available")
            return
        
        logger.info("Camera stream started")
        frame_count = 0
        last_fps_time = time.time()
        
        while True:
            try:
                # Capture frame asynchronously to not block other operations
                frame_data = await capture_frame_async()
                
                if frame_data is None:
                    await websocket.send_text("Camera read error")
                    await asyncio.sleep(0.1)  # Brief pause before retry
                    continue
                
                # Send frame
                await websocket.send_bytes(frame_data)
                
                # FPS monitoring
                frame_count += 1
                if frame_count % 30 == 0:
                    current_time = time.time()
                    fps = 30 / (current_time - last_fps_time)
                    logger.info(f"Camera FPS: {fps:.1f}")
                    last_fps_time = current_time
                
                # Minimal delay to maintain ~30 FPS but allow other operations
                await asyncio.sleep(0.025)  # ~40 FPS max, but yields control frequently
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Frame capture error: {e}")
                await asyncio.sleep(0.1)
                
    except WebSocketDisconnect:
        logger.info("Camera stream client disconnected")
    except Exception as e:
        logger.error(f"Camera stream error: {e}")
        try:
            await websocket.send_text(f"Camera error: {str(e)}")
        except:
            pass
    finally:
        logger.info("Camera stream ended")

# WebSocket for real-time car control
@app.websocket("/ws/control")
async def car_control_websocket(websocket: WebSocket):
    """WebSocket for real-time car control commands"""
    await websocket.accept()
    
    try:
        logger.info("Car control WebSocket connected")
        
        while True:
            # Wait for command
            data = await websocket.receive_json()
            command = data.get("command")
            speed = data.get("speed", 50)
            
            # Execute command immediately
            try:
                if command == "forward":
                    car.forward(speed)
                elif command == "backward":
                    car.backward(speed)
                elif command == "left":
                    car.turn_left(speed)
                elif command == "right":
                    car.turn_right(speed)
                elif command == "pivot_left":
                    car.pivot_left(speed)
                elif command == "pivot_right":
                    car.pivot_right(speed)
                elif command == "stop":
                    car.stop()
                elif command == "move":
                    left_speed = data.get("left_speed", 0)
                    right_speed = data.get("right_speed", 0)
                    car.move(left_speed, right_speed)
                else:
                    await websocket.send_json({"error": f"Unknown command: {command}"})
                    continue
                
                # Send confirmation
                await websocket.send_json({"status": "ok", "command": command, "speed": speed})
                
            except Exception as e:
                logger.error(f"Command execution error: {e}")
                await websocket.send_json({"error": str(e)})
                
    except WebSocketDisconnect:
        logger.info("Car control WebSocket disconnected")
        # Stop car when client disconnects for safety
        try:
            car.stop()
        except:
            pass
    except Exception as e:
        logger.error(f"Car control WebSocket error: {e}")

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"message": "Tank Car Controller API running", "status": "healthy"}

@app.get("/camera/status")
async def camera_status():
    """Check camera status"""
    if global_camera and global_camera.isOpened():
        return {"status": "available", "message": "Camera is ready"}
    else:
        return {"status": "unavailable", "message": "Camera not available"}

@app.get("/ir/stream")
async def stream_ir():
    """Stream IR sensor value at 30 FPS as server-sent events."""
    def event_stream():
        for value in ir_stream(fps=30):
            yield f"data: {value}\n\n"
    return StreamingResponse(event_stream(), media_type="text/event-stream")
