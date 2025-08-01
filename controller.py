from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, Optional
import RPi.GPIO as GPIO
import logging
import cv2
import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="GPIO Controller", description="Modular GPIO control system")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# GPIO pin definitions
AVAILABLE_PINS = {
    "ENA": 18,
    "ENB": 13,
    "IN1": 23,
    "IN2": 24,
    "IN3": 27,
    "IN4": 22
}

# PWM instances storage
pwm_instances: Dict[int, GPIO.PWM] = {}
pin_states: Dict[int, Dict] = {}

# Thread executor for blocking operations
executor = ThreadPoolExecutor(max_workers=4)

# Pydantic models
class PinConfig(BaseModel):
    pin: int = Field(..., description="GPIO pin number")
    mode: str = Field(..., description="Pin mode: 'output' or 'input'")
    initial_state: Optional[bool] = Field(None, description="Initial state for output pins")
    pull_up_down: Optional[str] = Field(None, description="Pull resistor: 'up', 'down', or 'floating'")

class DigitalWrite(BaseModel):
    pin: int = Field(..., description="GPIO pin number")
    state: bool = Field(..., description="Pin state: True (HIGH) or False (LOW)")

class PWMConfig(BaseModel):
    pin: int = Field(..., description="GPIO pin number")
    frequency: float = Field(..., ge=0.1, le=40000, description="PWM frequency in Hz")
    duty_cycle: float = Field(0, ge=0, le=100, description="PWM duty cycle (0-100%)")

class PWMUpdate(BaseModel):
    pin: int = Field(..., description="GPIO pin number")
    duty_cycle: float = Field(..., ge=0, le=100, description="PWM duty cycle (0-100%)")

class TankDriveCommand(BaseModel):
    left_speed: float = Field(..., ge=-100, le=100, description="Left motor speed (-100 to 100)")
    right_speed: float = Field(..., ge=-100, le=100, description="Right motor speed (-100 to 100)")

class DirectionalCommand(BaseModel):
    speed: float = Field(50, ge=0, le=100, description="Motor speed (0-100%)")

# Initialize GPIO
@app.on_event("startup")
async def startup_event():
    try:
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        logger.info("GPIO initialized")
    except Exception as e:
        logger.error(f"Failed to initialize GPIO: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    try:
        # Stop all PWM instances
        for pwm in pwm_instances.values():
            try:
                pwm.stop()
            except Exception as e:
                logger.error(f"Error stopping PWM: {e}")
        pwm_instances.clear()
        GPIO.cleanup()
        logger.info("GPIO cleaned up")
    except Exception as e:
        logger.error(f"Error during GPIO cleanup: {e}")

# Helper function for thread-safe GPIO operations
def run_in_thread(func, *args, **kwargs):
    """Run blocking function in thread executor"""
    loop = asyncio.get_event_loop()
    return loop.run_in_executor(executor, func, *args, **kwargs)

# Pin configuration endpoints
@app.post("/pin/configure")
async def configure_pin(config: PinConfig):
    """Configure a GPIO pin as input or output"""
    try:
        pin = config.pin
        
        # Cleanup existing PWM if present
        if pin in pwm_instances:
            pwm_instances[pin].stop()
            del pwm_instances[pin]
        
        if config.mode.lower() == "output":
            GPIO.setup(pin, GPIO.OUT)
            if config.initial_state is not None:
                GPIO.output(pin, config.initial_state)
            pin_states[pin] = {"mode": "output", "state": config.initial_state}
            
        elif config.mode.lower() == "input":
            pull = GPIO.PUD_OFF
            if config.pull_up_down:
                if config.pull_up_down.lower() == "up":
                    pull = GPIO.PUD_UP
                elif config.pull_up_down.lower() == "down":
                    pull = GPIO.PUD_DOWN
            
            GPIO.setup(pin, GPIO.IN, pull_up_down=pull)
            pin_states[pin] = {"mode": "input", "pull": config.pull_up_down}
        
        else:
            raise HTTPException(status_code=400, detail="Mode must be 'input' or 'output'")
        
        logger.info(f"Pin {pin} configured as {config.mode}")
        return {"message": f"Pin {pin} configured successfully", "config": pin_states[pin]}
    
    except Exception as e:
        logger.error(f"Error configuring pin {config.pin}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/pin/{pin}/status")
async def get_pin_status(pin: int):
    """Get the current status of a GPIO pin"""
    try:
        if pin not in pin_states:
            raise HTTPException(status_code=404, detail="Pin not configured")
        
        status = pin_states[pin].copy()
        try:
            status["current_value"] = GPIO.input(pin)
        except Exception as e:
            logger.error(f"Error reading pin {pin}: {e}")
            status["current_value"] = None
        
        if pin in pwm_instances:
            status["pwm_active"] = True
        
        return status
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Digital control endpoints
@app.post("/digital/write")
async def digital_write(data: DigitalWrite):
    """Set digital output state"""
    try:
        pin = data.pin
        
        if pin not in pin_states or pin_states[pin]["mode"] != "output":
            raise HTTPException(status_code=400, detail="Pin must be configured as output")
        
        GPIO.output(pin, data.state)
        pin_states[pin]["state"] = data.state
        
        logger.info(f"Pin {pin} set to {data.state}")
        return {"message": f"Pin {pin} set to {'HIGH' if data.state else 'LOW'}"}
    
    except Exception as e:
        logger.error(f"Error writing to pin {data.pin}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/digital/read/{pin}")
async def digital_read(pin: int):
    """Read digital input state"""
    try:
        if pin not in pin_states:
            raise HTTPException(status_code=404, detail="Pin not configured")
        
        value = GPIO.input(pin)
        return {"pin": pin, "value": value, "state": "HIGH" if value else "LOW"}
    
    except Exception as e:
        logger.error(f"Error reading pin {pin}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# PWM control endpoints
@app.post("/pwm/start")
async def start_pwm(config: PWMConfig):
    """Start PWM on a pin"""
    try:
        pin = config.pin
        
        if pin not in pin_states or pin_states[pin]["mode"] != "output":
            raise HTTPException(status_code=400, detail="Pin must be configured as output")
        
        # Stop existing PWM if present
        if pin in pwm_instances:
            pwm_instances[pin].stop()
            del pwm_instances[pin]
        
        pwm = GPIO.PWM(pin, config.frequency)
        pwm.start(config.duty_cycle)
        pwm_instances[pin] = pwm
        
        pin_states[pin]["pwm"] = {
            "frequency": config.frequency,
            "duty_cycle": config.duty_cycle
        }
        
        logger.info(f"PWM started on pin {pin}: {config.frequency}Hz, {config.duty_cycle}%")
        return {"message": f"PWM started on pin {pin}", "config": config.dict()}
    
    except Exception as e:
        logger.error(f"Error starting PWM on pin {config.pin}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/pwm/update")
async def update_pwm_duty_cycle(data: PWMUpdate):
    """Update PWM duty cycle"""
    try:
        pin = data.pin
        
        if pin not in pwm_instances:
            raise HTTPException(status_code=404, detail="PWM not active on this pin")
        
        pwm_instances[pin].ChangeDutyCycle(data.duty_cycle)
        if pin in pin_states and "pwm" in pin_states[pin]:
            pin_states[pin]["pwm"]["duty_cycle"] = data.duty_cycle
        
        logger.info(f"PWM duty cycle updated on pin {pin}: {data.duty_cycle}%")
        return {"message": f"PWM duty cycle updated on pin {pin}", "duty_cycle": data.duty_cycle}
    
    except Exception as e:
        logger.error(f"Error updating PWM on pin {data.pin}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/pwm/stop/{pin}")
async def stop_pwm(pin: int):
    """Stop PWM on a pin"""
    try:
        if pin not in pwm_instances:
            raise HTTPException(status_code=404, detail="PWM not active on this pin")
        
        pwm_instances[pin].stop()
        del pwm_instances[pin]
        
        if pin in pin_states and "pwm" in pin_states[pin]:
            del pin_states[pin]["pwm"]
        
        logger.info(f"PWM stopped on pin {pin}")
        return {"message": f"PWM stopped on pin {pin}"}
    
    except Exception as e:
        logger.error(f"Error stopping PWM on pin {pin}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Bulk operations
@app.get("/pins/all")
async def get_all_pins():
    """Get status of all configured pins"""
    return {"pins": pin_states, "available_pins": AVAILABLE_PINS}

@app.post("/pins/cleanup")
async def cleanup_all_pins():
    """Stop all PWM and cleanup GPIO"""
    try:
        for pin, pwm in list(pwm_instances.items()):
            try:
                pwm.stop()
            except Exception as e:
                logger.error(f"Error stopping PWM on pin {pin}: {e}")
        
        pwm_instances.clear()
        pin_states.clear()
        GPIO.cleanup()
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        
        logger.info("All pins cleaned up")
        return {"message": "All pins cleaned up successfully"}
    
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Predefined pin shortcuts
@app.get("/pins/predefined")
async def get_predefined_pins():
    """Get predefined pin mappings"""
    return {"predefined_pins": AVAILABLE_PINS}

@app.post("/pins/predefined/{pin_name}/digital")
async def control_predefined_pin_digital(pin_name: str, state: bool):
    """Control predefined pin digitally"""
    if pin_name not in AVAILABLE_PINS:
        raise HTTPException(status_code=404, detail="Predefined pin not found")
    
    pin = AVAILABLE_PINS[pin_name]
    return await digital_write(DigitalWrite(pin=pin, state=state))

@app.post("/pins/predefined/{pin_name}/pwm")
async def control_predefined_pin_pwm(pin_name: str, duty_cycle: float):
    """Control predefined pin PWM duty cycle"""
    if pin_name not in AVAILABLE_PINS:
        raise HTTPException(status_code=404, detail="Predefined pin not found")
    
    pin = AVAILABLE_PINS[pin_name]
    
    if pin not in pwm_instances:
        # Start PWM with default frequency if not active
        await start_pwm(PWMConfig(pin=pin, frequency=1000, duty_cycle=duty_cycle))
    else:
        await update_pwm_duty_cycle(PWMUpdate(pin=pin, duty_cycle=duty_cycle))
    
    return {"message": f"PWM updated on {pin_name} (pin {pin})", "duty_cycle": duty_cycle}

# High/Low control endpoints
@app.post("/digital/high/{pin}")
async def set_pin_high(pin: int):
    """Set a pin to HIGH state"""
    return await digital_write(DigitalWrite(pin=pin, state=True))

@app.post("/digital/low/{pin}")
async def set_pin_low(pin: int):
    """Set a pin to LOW state"""
    return await digital_write(DigitalWrite(pin=pin, state=False))

@app.post("/pins/predefined/{pin_name}/high")
async def set_predefined_pin_high(pin_name: str):
    """Set predefined pin to HIGH"""
    if pin_name not in AVAILABLE_PINS:
        raise HTTPException(status_code=404, detail="Predefined pin not found")
    
    pin = AVAILABLE_PINS[pin_name]
    return await digital_write(DigitalWrite(pin=pin, state=True))

@app.post("/pins/predefined/{pin_name}/low")
async def set_predefined_pin_low(pin_name: str):
    """Set predefined pin to LOW"""
    if pin_name not in AVAILABLE_PINS:
        raise HTTPException(status_code=404, detail="Predefined pin not found")
    
    pin = AVAILABLE_PINS[pin_name]
    return await digital_write(DigitalWrite(pin=pin, state=False))

# Motor initialization helper
async def ensure_motor_pins_configured():
    """Ensure all motor pins are configured as outputs"""
    motor_pins = ["ENA", "ENB", "IN1", "IN2", "IN3", "IN4"]
    for pin_name in motor_pins:
        pin = AVAILABLE_PINS[pin_name]
        if pin not in pin_states:
            try:
                GPIO.setup(pin, GPIO.OUT)
                GPIO.output(pin, GPIO.LOW)  # Start with motors off
                pin_states[pin] = {"mode": "output", "state": False}
            except Exception as e:
                logger.error(f"Error configuring motor pin {pin_name}: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to configure motor pin {pin_name}")

# Tank drive control endpoints
@app.post("/motor/tank")
async def tank_drive(command: TankDriveCommand):
    """Control both motors independently (tank drive)"""
    try:
        await ensure_motor_pins_configured()
        
        # Left motor control
        left_speed = abs(command.left_speed)
        if command.left_speed > 0:
            # Forward
            GPIO.output(AVAILABLE_PINS["IN1"], GPIO.HIGH)
            GPIO.output(AVAILABLE_PINS["IN2"], GPIO.LOW)
        elif command.left_speed < 0:
            # Backward
            GPIO.output(AVAILABLE_PINS["IN1"], GPIO.LOW)
            GPIO.output(AVAILABLE_PINS["IN2"], GPIO.HIGH)
        else:
            # Stop
            GPIO.output(AVAILABLE_PINS["IN1"], GPIO.LOW)
            GPIO.output(AVAILABLE_PINS["IN2"], GPIO.LOW)
        
        # Right motor control
        right_speed = abs(command.right_speed)
        if command.right_speed > 0:
            # Forward
            GPIO.output(AVAILABLE_PINS["IN3"], GPIO.HIGH)
            GPIO.output(AVAILABLE_PINS["IN4"], GPIO.LOW)
        elif command.right_speed < 0:
            # Backward
            GPIO.output(AVAILABLE_PINS["IN3"], GPIO.LOW)
            GPIO.output(AVAILABLE_PINS["IN4"], GPIO.HIGH)
        else:
            # Stop
            GPIO.output(AVAILABLE_PINS["IN3"], GPIO.LOW)
            GPIO.output(AVAILABLE_PINS["IN4"], GPIO.LOW)
        
        # Set PWM speeds
        for pin_name, speed in [("ENA", left_speed), ("ENB", right_speed)]:
            pin = AVAILABLE_PINS[pin_name]
            try:
                if pin in pwm_instances:
                    pwm_instances[pin].ChangeDutyCycle(speed)
                else:
                    pwm = GPIO.PWM(pin, 1000)  # 1kHz frequency
                    pwm.start(speed)
                    pwm_instances[pin] = pwm
                    pin_states[pin]["pwm"] = {"frequency": 1000, "duty_cycle": speed}
            except Exception as e:
                logger.error(f"Error setting PWM for {pin_name}: {e}")
        
        logger.info(f"Tank drive: Left={command.left_speed}%, Right={command.right_speed}%")
        return {"message": "Tank drive command executed", "left_speed": command.left_speed, "right_speed": command.right_speed}
    
    except Exception as e:
        logger.error(f"Error in tank drive: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/motor/forward")
async def move_forward(command: DirectionalCommand = DirectionalCommand()):
    """Move forward at specified speed"""
    return await tank_drive(TankDriveCommand(left_speed=command.speed, right_speed=command.speed))

@app.post("/motor/backward")
async def move_backward(command: DirectionalCommand = DirectionalCommand()):
    """Move backward at specified speed"""
    return await tank_drive(TankDriveCommand(left_speed=-command.speed, right_speed=-command.speed))

@app.post("/motor/left")
async def turn_left(command: DirectionalCommand = DirectionalCommand()):
    """Turn left by stopping left motor and running right motor"""
    return await tank_drive(TankDriveCommand(left_speed=0, right_speed=command.speed))

@app.post("/motor/right")
async def turn_right(command: DirectionalCommand = DirectionalCommand()):
    """Turn right by stopping right motor and running left motor"""
    return await tank_drive(TankDriveCommand(left_speed=command.speed, right_speed=0))

@app.post("/motor/spin-left")
async def spin_left(command: DirectionalCommand = DirectionalCommand()):
    """Spin left by running motors in opposite directions"""
    return await tank_drive(TankDriveCommand(left_speed=-command.speed, right_speed=command.speed))

@app.post("/motor/spin-right")
async def spin_right(command: DirectionalCommand = DirectionalCommand()):
    """Spin right by running motors in opposite directions"""
    return await tank_drive(TankDriveCommand(left_speed=command.speed, right_speed=-command.speed))

@app.post("/motor/stop")
async def stop_motors():
    """Stop all motors"""
    return await tank_drive(TankDriveCommand(left_speed=0, right_speed=0))

@app.get("/motor/status")
async def get_motor_status():
    """Get current motor status"""
    try:
        status = {}
        for motor in ["ENA", "ENB", "IN1", "IN2", "IN3", "IN4"]:
            pin = AVAILABLE_PINS[motor]
            if pin in pin_states:
                try:
                    status[motor] = {
                        "pin": pin,
                        "state": pin_states[pin].get("state", False),
                        "current_value": GPIO.input(pin)
                    }
                    if pin in pwm_instances:
                        status[motor]["pwm"] = pin_states[pin].get("pwm", {})
                except Exception as e:
                    logger.error(f"Error reading motor pin {motor}: {e}")
                    status[motor] = {"pin": pin, "error": str(e)}
        
        return {"motor_status": status}
    
    except Exception as e:
        logger.error(f"Error getting motor status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Camera streaming functions
def capture_frame(cap):
    """Capture a frame from camera (blocking operation)"""
    ret, frame = cap.read()
    if not ret:
        return None
    _, jpeg = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    return jpeg.tobytes()

@app.websocket("/ws/camera")
async def webcam_stream(websocket: WebSocket):
    """WebSocket endpoint to stream webcam footage as JPEG frames."""
    await websocket.accept()
    cap = None
    
    try:
        # Initialize camera
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            await websocket.send_text("Camera initialization failed")
            return
        
        # Set camera properties for better performance
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, 30)
        
        logger.info("Camera stream started")
        
        while True:
            # Capture frame in thread to avoid blocking
            frame_data = await run_in_thread(capture_frame, cap)
            
            if frame_data is None:
                await websocket.send_text("Camera read error")
                break
            
            await websocket.send_bytes(frame_data)
            
            # Small delay to prevent overwhelming the connection
            await asyncio.sleep(0.033)  # ~30 FPS
            
    except WebSocketDisconnect:
        logger.info("Camera stream client disconnected")
    except Exception as e:
        logger.error(f"Camera stream error: {e}")
        try:
            await websocket.send_text(f"Camera error: {str(e)}")
        except:
            pass
    finally:
        if cap:
            cap.release()
        try:
            await websocket.close()
        except:
            pass
        logger.info("Camera stream ended")

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"message": "GPIO Controller API running", "status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
