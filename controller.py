from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import RPi.GPIO as GPIO
import time
from contextlib import asynccontextmanager

# GPIO pin definitions
ENA = 18  # Right motors enable
ENB = 13  # Left motors enable
IN1 = 23  # Right motor 1
IN2 = 24  # Right motor 2
IN3 = 27  # Left motor 1
IN4 = 22  # Left motor 2

# Setup GPIO
def setup_gpio():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup([ENA, ENB, IN1, IN2, IN3, IN4], GPIO.OUT)
    
    # Setup PWM for motor speed control
    global pwm_ena, pwm_enb
    pwm_ena = GPIO.PWM(ENA, 1000)  # 1000Hz frequency
    pwm_enb = GPIO.PWM(ENB, 1000)
    pwm_ena.start(0)
    pwm_enb.start(0)

def cleanup_gpio():
    GPIO.cleanup()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    setup_gpio()
    yield
    # Shutdown
    cleanup_gpio()

app = FastAPI(title="RC Car Controller", lifespan=lifespan)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

def stop_motors():
    """Stop all motors"""
    GPIO.output([IN1, IN2, IN3, IN4], GPIO.LOW)
    pwm_ena.ChangeDutyCycle(0)
    pwm_enb.ChangeDutyCycle(0)

def forward(speed=80):
    """Move car forward"""
    # Right motors forward
    GPIO.output(IN1, GPIO.HIGH)
    GPIO.output(IN2, GPIO.HIGH)
    # Left motors forward
    GPIO.output(IN3, GPIO.HIGH)
    GPIO.output(IN4, GPIO.HIGH)
    # Set speed
    pwm_ena.ChangeDutyCycle(speed)
    pwm_enb.ChangeDutyCycle(speed)

def backward(speed=80):
    """Move car backward"""
    # Right motors backward
    GPIO.output(IN1, GPIO.LOW)
    GPIO.output(IN2, GPIO.LOW)
    # Left motors backward
    GPIO.output(IN3, GPIO.LOW)
    GPIO.output(IN4, GPIO.LOW)
    # Set speed
    pwm_ena.ChangeDutyCycle(speed)
    pwm_enb.ChangeDutyCycle(speed)

def turn_left(speed=80):
    """Turn car left (right motors forward, left motors backward)"""
    # Right motors forward
    GPIO.output(IN1, GPIO.HIGH)
    GPIO.output(IN2, GPIO.HIGH)
    # Left motors backward
    GPIO.output(IN3, GPIO.LOW)
    GPIO.output(IN4, GPIO.LOW)
    # Set speed
    pwm_ena.ChangeDutyCycle(speed)
    pwm_enb.ChangeDutyCycle(speed)

def turn_right(speed=80):
    """Turn car right (left motors forward, right motors backward)"""
    # Right motors backward
    GPIO.output(IN1, GPIO.LOW)
    GPIO.output(IN2, GPIO.LOW)
    # Left motors forward
    GPIO.output(IN3, GPIO.HIGH)
    GPIO.output(IN4, GPIO.HIGH)
    # Set speed
    pwm_ena.ChangeDutyCycle(speed)
    pwm_enb.ChangeDutyCycle(speed)

@app.get("/")
async def root():
    return {"message": "RC Car Controller API", "status": "running"}

@app.post("/forward")
async def move_forward(speed: int = 80):
    """Move car forward"""
    if not 0 <= speed <= 100:
        return {"error": "Speed must be between 0 and 100"}
    forward(speed)
    return {"action": "forward", "speed": speed}

@app.post("/backward")
async def move_backward(speed: int = 80):
    """Move car backward"""
    if not 0 <= speed <= 100:
        return {"error": "Speed must be between 0 and 100"}
    backward(speed)
    return {"action": "backward", "speed": speed}

@app.post("/left")
async def turn_car_left(speed: int = 80):
    """Turn car left"""
    if not 0 <= speed <= 100:
        return {"error": "Speed must be between 0 and 100"}
    turn_left(speed)
    return {"action": "left", "speed": speed}

@app.post("/right")
async def turn_car_right(speed: int = 80):
    """Turn car right"""
    if not 0 <= speed <= 100:
        return {"error": "Speed must be between 0 and 100"}
    turn_right(speed)
    return {"action": "right", "speed": speed}

@app.post("/stop")
async def stop_car():
    """Stop the car"""
    stop_motors()
    return {"action": "stop"}

@app.get("/status")
async def get_status():
    """Get car status"""
    return {"status": "ready", "available_commands": ["forward", "backward", "left", "right", "stop"]}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)