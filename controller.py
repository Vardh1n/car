from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import RPi.GPIO as GPIO
import time
from contextlib import asynccontextmanager
import platform
from pydantic import BaseModel

# GPIO pin definitions
ENA = 18  # Right motors enable
ENB = 13  # Left motors enable
IN1 = 23  # Right motor 1
IN2 = 24  # Right motor 2
IN3 = 27  # Left motor 1
IN4 = 22  # Left motor 2

# Add this after imports
RUNNING_ON_PI = platform.machine().startswith('arm') or platform.machine().startswith('aarch64')

# Pydantic models for request bodies
class MotorControl(BaseModel):
    speed: int = 50  # 0-100
    direction: str = "forward"  # forward, backward, stop

class PinControl(BaseModel):
    state: bool

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    if RUNNING_ON_PI:
        GPIO.setmode(GPIO.BCM)
        GPIO.setup([ENA, ENB, IN1, IN2, IN3, IN4], GPIO.OUT)
        
        # Initialize PWM for speed control
        global pwm_ena, pwm_enb
        pwm_ena = GPIO.PWM(ENA, 1000)  # 1000Hz frequency
        pwm_enb = GPIO.PWM(ENB, 1000)
        pwm_ena.start(0)
        pwm_enb.start(0)
    
    yield
    
    # Shutdown
    if RUNNING_ON_PI:
        GPIO.cleanup()

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Motor control functions
def set_motor_speed(pin, speed):
    if RUNNING_ON_PI:
        if pin == ENA:
            pwm_ena.ChangeDutyCycle(speed)
        elif pin == ENB:
            pwm_enb.ChangeDutyCycle(speed)

def set_motor_direction(in1, in2, direction):
    if not RUNNING_ON_PI:
        return
    
    if direction == "forward":
        GPIO.output(in1, GPIO.HIGH)
        GPIO.output(in2, GPIO.LOW)
    elif direction == "backward":
        GPIO.output(in1, GPIO.LOW)
        GPIO.output(in2, GPIO.HIGH)
    else:  # stop
        GPIO.output(in1, GPIO.LOW)
        GPIO.output(in2, GPIO.LOW)

# Individual motor control endpoints
@app.post("/motor/right")
async def control_right_motor(motor: MotorControl):
    """Control right motor (ENA, IN1, IN2)"""
    set_motor_direction(IN1, IN2, motor.direction)
    speed = motor.speed if motor.direction != "stop" else 0
    set_motor_speed(ENA, speed)
    return {"status": "success", "motor": "right", "speed": speed, "direction": motor.direction}

@app.post("/motor/left")
async def control_left_motor(motor: MotorControl):
    """Control left motor (ENB, IN3, IN4)"""
    set_motor_direction(IN3, IN4, motor.direction)
    speed = motor.speed if motor.direction != "stop" else 0
    set_motor_speed(ENB, speed)
    return {"status": "success", "motor": "left", "speed": speed, "direction": motor.direction}

# Car movement endpoints
@app.post("/car/forward")
async def move_forward(speed: int = 50):
    """Move car forward"""
    set_motor_direction(IN1, IN2, "forward")
    set_motor_direction(IN3, IN4, "forward")
    set_motor_speed(ENA, speed)
    set_motor_speed(ENB, speed)
    return {"status": "success", "action": "forward", "speed": speed}

@app.post("/car/backward")
async def move_backward(speed: int = 50):
    """Move car backward"""
    set_motor_direction(IN1, IN2, "backward")
    set_motor_direction(IN3, IN4, "backward")
    set_motor_speed(ENA, speed)
    set_motor_speed(ENB, speed)
    return {"status": "success", "action": "backward", "speed": speed}

@app.post("/car/left")
async def turn_left(speed: int = 50):
    """Turn car left"""
    set_motor_direction(IN1, IN2, "forward")  # Right motor forward
    set_motor_direction(IN3, IN4, "backward")  # Left motor backward
    set_motor_speed(ENA, speed)
    set_motor_speed(ENB, speed)
    return {"status": "success", "action": "left", "speed": speed}

@app.post("/car/right")
async def turn_right(speed: int = 50):
    """Turn car right"""
    set_motor_direction(IN1, IN2, "backward")  # Right motor backward
    set_motor_direction(IN3, IN4, "forward")  # Left motor forward
    set_motor_speed(ENA, speed)
    set_motor_speed(ENB, speed)
    return {"status": "success", "action": "right", "speed": speed}

@app.post("/car/stop")
async def stop_car():
    """Stop all motors"""
    set_motor_direction(IN1, IN2, "stop")
    set_motor_direction(IN3, IN4, "stop")
    set_motor_speed(ENA, 0)
    set_motor_speed(ENB, 0)
    return {"status": "success", "action": "stop"}

# Individual pin control endpoints
@app.post("/pin/{pin_number}")
async def control_pin(pin_number: int, control: PinControl):
    """Control individual GPIO pin"""
    if RUNNING_ON_PI:
        try:
            GPIO.setup(pin_number, GPIO.OUT)
            GPIO.output(pin_number, GPIO.HIGH if control.state else GPIO.LOW)
            return {"status": "success", "pin": pin_number, "state": control.state}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    return {"status": "success", "pin": pin_number, "state": control.state, "note": "Not running on Pi"}

# Get pin status
@app.get("/pin/{pin_number}")
async def get_pin_status(pin_number: int):
    """Get GPIO pin status"""
    if RUNNING_ON_PI:
        try:
            GPIO.setup(pin_number, GPIO.IN)
            state = GPIO.input(pin_number)
            return {"pin": pin_number, "state": bool(state)}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    return {"pin": pin_number, "state": False, "note": "Not running on Pi"}

# Status endpoint
@app.get("/status")
async def get_status():
    """Get system status"""
    return {
        "running_on_pi": RUNNING_ON_PI,
        "platform": platform.machine(),
        "gpio_pins": {
            "ENA": ENA,
            "ENB": ENB,
            "IN1": IN1,
            "IN2": IN2,
            "IN3": IN3,
            "IN4": IN4
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)