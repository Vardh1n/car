from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import logging
import cv2
import asyncio
from concurrent.futures import ThreadPoolExecutor
from car import TankCar
import time
from starlette.responses import StreamingResponse
from contextlib import asynccontextmanager

# Try to import ir module, handle if it doesn't exist
try:
    from ir import ir_stream
    IR_AVAILABLE = True
except ImportError:
    IR_AVAILABLE = False
    logging.warning("IR module not available")

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global variables
car: TankCar = None
global_camera = None
camera_lock = asyncio.Lock()
executor = ThreadPoolExecutor(max_workers=4)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan - startup and shutdown"""
    global car, global_camera
    
    # Startup
    try:
        # Initialize car
        car = TankCar()
        logger.info("Tank car initialized")
        
        # Initialize camera
        global_camera = cv2.VideoCapture(0)
        if global_camera.isOpened():
            global_camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            global_camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            global_camera.set(cv2.CAP_PROP_FPS, 30)
            global_camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            logger.info("Camera initialized successfully")
        else:
            logger.warning("Camera initialization failed")
            global_camera = None
            
    except Exception as e:
        logger.error(f"Failed to initialize resources: {e}")
        # Don't raise here, let the app start but with limited functionality
    
    yield
    
    # Shutdown
    try:
        if car:
            car.stop()  # Stop car before cleanup
            car.cleanup()
            logger.info("Car cleaned up")
    except Exception as e:
        logger.error(f"Error cleaning up car: {e}")
    
    try:
        if global_camera:
            global_camera.release()
            logger.info("Camera released")
    except Exception as e:
        logger.error(f"Error releasing camera: {e}")
    
    try:
        executor.shutdown(wait=True)
        logger.info("Executor shutdown")
    except Exception as e:
        logger.error(f"Error shutting down executor: {e}")

app = FastAPI(
    title="Tank Car Controller", 
    description="Simple tank drive car control system", 
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
class TankDriveCommand(BaseModel):
    left_speed: float = Field(..., ge=-100, le=100, description="Left motor speed (-100 to 100)")
    right_speed: float = Field(..., ge=-100, le=100, description="Right motor speed (-100 to 100)")

class DirectionalCommand(BaseModel):
    speed: float = Field(50, ge=0, le=100, description="Motor speed (0-100%)")

# Helper function to check if car is available
def check_car_available():
    if car is None:
        raise HTTPException(status_code=503, detail="Car not initialized")

# Car control endpoints
@app.post("/car/move")
async def move_car(command: TankDriveCommand):
    """Control both motors independently (tank drive)"""
    try:
        check_car_available()
        car.move(command.left_speed, command.right_speed)
        return {
            "message": "Car move command executed", 
            "left_speed": command.left_speed, 
            "right_speed": command.right_speed
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error moving car: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/car/forward")
async def move_forward(command: DirectionalCommand = DirectionalCommand()):
    """Move forward at specified speed"""
    try:
        check_car_available()
        car.forward(command.speed)
        return {"message": f"Moving forward at {command.speed}% speed"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error moving forward: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/car/backward")
async def move_backward(command: DirectionalCommand = DirectionalCommand()):
    """Move backward at specified speed"""
    try:
        check_car_available()
        car.backward(command.speed)
        return {"message": f"Moving backward at {command.speed}% speed"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error moving backward: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/car/left")
async def turn_left(command: DirectionalCommand = DirectionalCommand()):
    """Turn left (spin in place)"""
    try:
        check_car_available()
        car.turn_left(command.speed)
        return {"message": f"Turning left at {command.speed}% speed"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error turning left: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/car/right")
async def turn_right(command: DirectionalCommand = DirectionalCommand()):
    """Turn right (spin in place)"""
    try:
        check_car_available()
        car.turn_right(command.speed)
        return {"message": f"Turning right at {command.speed}% speed"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error turning right: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/car/pivot-left")
async def pivot_left(command: DirectionalCommand = DirectionalCommand()):
    """Pivot left (only right motor moves)"""
    try:
        check_car_available()
        car.pivot_left(command.speed)
        return {"message": f"Pivoting left at {command.speed}% speed"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error pivoting left: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/car/pivot-right")
async def pivot_right(command: DirectionalCommand = DirectionalCommand()):
    """Pivot right (only left motor moves)"""
    try:
        check_car_available()
        car.pivot_right(command.speed)
        return {"message": f"Pivoting right at {command.speed}% speed"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error pivoting right: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/car/stop")
async def stop_car():
    """Stop the car"""
    try:
        check_car_available()
        car.stop()
        return {"message": "Car stopped"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error stopping car: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Camera functions
async def capture_frame_async():
    """Capture a frame from camera in thread pool"""
    if not global_camera or not global_camera.isOpened():
        return None
    
    def _capture():
        try:
            ret, frame = global_camera.read()
            if not ret or frame is None:
                return None
            # Use lower quality for faster encoding
            _, jpeg = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
            return jpeg.tobytes()
        except Exception as e:
            logger.error(f"Frame encoding error: {e}")
            return None
    
    try:
        return await asyncio.get_event_loop().run_in_executor(executor, _capture)
    except Exception as e:
        logger.error(f"Frame capture async error: {e}")
        return None

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
        consecutive_errors = 0
        max_consecutive_errors = 10
        
        while True:
            try:
                # Use camera lock to prevent conflicts
                async with camera_lock:
                    frame_data = await capture_frame_async()
                
                if frame_data is None:
                    consecutive_errors += 1
                    if consecutive_errors >= max_consecutive_errors:
                        await websocket.send_text("Too many camera errors, stopping stream")
                        break
                    await asyncio.sleep(0.1)
                    continue
                
                consecutive_errors = 0  # Reset error counter
                
                # Send frame
                await websocket.send_bytes(frame_data)
                
                # FPS monitoring
                frame_count += 1
                if frame_count % 30 == 0:
                    current_time = time.time()
                    fps = 30 / (current_time - last_fps_time)
                    logger.info(f"Camera FPS: {fps:.1f}")
                    last_fps_time = current_time
                
                # Control frame rate
                await asyncio.sleep(0.033)  # ~30 FPS
                
            except asyncio.CancelledError:
                break
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Frame streaming error: {e}")
                consecutive_errors += 1
                if consecutive_errors >= max_consecutive_errors:
                    break
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

@app.websocket("/ws/control")
async def car_control_websocket(websocket: WebSocket):
    """WebSocket for real-time car control commands"""
    await websocket.accept()
    
    try:
        if car is None:
            await websocket.send_json({"error": "Car not initialized"})
            return
        
        logger.info("Car control WebSocket connected")
        
        while True:
            try:
                # Wait for command with timeout
                data = await asyncio.wait_for(websocket.receive_json(), timeout=30.0)
                command = data.get("command")
                speed = data.get("speed", 50)
                
                # Validate speed
                if not isinstance(speed, (int, float)) or speed < 0 or speed > 100:
                    await websocket.send_json({"error": "Invalid speed value"})
                    continue
                
                # Execute command immediately
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
                    # Validate motor speeds
                    if not all(isinstance(s, (int, float)) and -100 <= s <= 100 
                              for s in [left_speed, right_speed]):
                        await websocket.send_json({"error": "Invalid motor speed values"})
                        continue
                    car.move(left_speed, right_speed)
                else:
                    await websocket.send_json({"error": f"Unknown command: {command}"})
                    continue
                
                # Send confirmation
                await websocket.send_json({
                    "status": "ok", 
                    "command": command, 
                    "speed": speed,
                    "timestamp": time.time()
                })
                
            except asyncio.TimeoutError:
                # Send heartbeat
                await websocket.send_json({"status": "heartbeat"})
            except Exception as e:
                logger.error(f"Command execution error: {e}")
                await websocket.send_json({"error": str(e)})
                
    except WebSocketDisconnect:
        logger.info("Car control WebSocket disconnected")
    except Exception as e:
        logger.error(f"Car control WebSocket error: {e}")
    finally:
        # Stop car when client disconnects for safety
        try:
            if car:
                car.stop()
        except Exception as e:
            logger.error(f"Error stopping car on disconnect: {e}")

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "message": "Tank Car Controller API running", 
        "status": "healthy",
        "car_available": car is not None,
        "camera_available": global_camera is not None and global_camera.isOpened(),
        "ir_available": IR_AVAILABLE
    }

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
    if not IR_AVAILABLE:
        raise HTTPException(status_code=503, detail="IR sensor not available")
    
    def event_stream():
        try:
            logger.info("Starting IR event stream")
            count = 0
            for value in ir_stream(fps=30):
                count += 1
                if count % 30 == 0:  # Log every second
                    logger.info(f"IR stream: sent {count} values, current: {value}")
                yield f"data: {value}\n\n"
        except Exception as e:
            logger.error(f"IR stream error: {e}")
            yield f"data: error:{str(e)}\n\n"
    
    return StreamingResponse(
        event_stream(), 
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
        }
    )

# Add a simple test endpoint
@app.get("/ir/test")
async def test_ir():
    """Test IR sensor directly"""
    if not IR_AVAILABLE:
        raise HTTPException(status_code=503, detail="IR sensor not available")
    
    try:
        from ir import test_ir_sensor
        success = test_ir_sensor()
        return {"status": "success" if success else "failed", "message": "IR sensor test completed"}
    except Exception as e:
        logger.error(f"IR test error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")