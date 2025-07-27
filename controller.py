from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import RPi.GPIO as GPIO
import time
from contextlib import asynccontextmanager
import platform

# GPIO pin definitions
ENA = 18  # Right motors enable
ENB = 13  # Left motors enable
IN1 = 23  # Right motor 1
IN2 = 24  # Right motor 2
IN3 = 27  # Left motor 1
IN4 = 22  # Left motor 2

# Add this after imports
RUNNING_ON_PI = platform.machine().startswith('arm') or platform.machine().startswith('aarch64')

if not RUNNING_ON_PI:
    print("Warning: Not running on Raspberry Pi. GPIO operations will be simulated.")
    # Mock GPIO for development
    class MockGPIO:
        BCM = "BCM"
        OUT = "OUT"
        HIGH = 1
        LOW = 0
        
        @staticmethod
        def setmode(mode): pass
        @staticmethod
        def setup(pins, mode): pass
        @staticmethod
        def output(pins, state): 
            print(f"GPIO output: {pins} -> {state}")
        @staticmethod
        def cleanup(): pass
        @staticmethod
        def PWM(pin, freq): 
            return MockPWM()
    
    class MockPWM:
        def start(self, duty): pass
        def ChangeDutyCycle(self, duty): 
            print(f"PWM duty cycle: {duty}")
        def stop(self): pass
    
    GPIO = MockGPIO()

# Setup GPIO
def setup_gpio():
    try:
        GPIO.setmode(GPIO.BCM)
        GPIO.setup([ENA, ENB, IN1, IN2, IN3, IN4], GPIO.OUT)
        
        # Setup PWM for motor speed control
        global pwm_ena, pwm_enb
        pwm_ena = GPIO.PWM(ENA, 1000)  # 1000Hz frequency
        pwm_enb = GPIO.PWM(ENB, 1000)
        pwm_ena.start(0)
        pwm_enb.start(0)
        print("GPIO setup completed successfully")
    except Exception as e:
        print(f"GPIO setup failed: {e}")
        raise

def cleanup_gpio():
    try:
        if 'pwm_ena' in globals():
            pwm_ena.stop()
        if 'pwm_enb' in globals():
            pwm_enb.stop()
        GPIO.cleanup()
        print("GPIO cleanup completed")
    except Exception as e:
        print(f"GPIO cleanup failed: {e}")

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
    # Right motors forward (assuming wheel 3 needs direction swap)
    GPIO.output(IN1, GPIO.HIGH)
    GPIO.output(IN2, GPIO.LOW)
    # Left motors forward (assuming wheel 4 needs direction swap)  
    GPIO.output(IN3, GPIO.LOW)   # Swapped from HIGH
    GPIO.output(IN4, GPIO.HIGH)  # Swapped from LOW
    # Set speed
    pwm_ena.ChangeDutyCycle(speed)
    pwm_enb.ChangeDutyCycle(speed)

def backward(speed=80):
    """Move car backward"""
    # Right motors backward
    GPIO.output(IN1, GPIO.LOW)
    GPIO.output(IN2, GPIO.HIGH)
    # Left motors backward
    GPIO.output(IN3, GPIO.HIGH)  # Swapped from LOW
    GPIO.output(IN4, GPIO.LOW)   # Swapped from HIGH
    # Set speed
    pwm_ena.ChangeDutyCycle(speed)
    pwm_enb.ChangeDutyCycle(speed)

def turn_left(speed=80):
    """Turn car left (right motors forward, left motors backward)"""
    # Right motors forward
    GPIO.output(IN1, GPIO.HIGH)
    GPIO.output(IN2, GPIO.LOW)
    # Left motors backward
    GPIO.output(IN3, GPIO.HIGH)  # Swapped from LOW
    GPIO.output(IN4, GPIO.LOW)   # Swapped from HIGH
    # Set speed
    pwm_ena.ChangeDutyCycle(speed)
    pwm_enb.ChangeDutyCycle(speed)

def turn_right(speed=80):
    """Turn car right (left motors forward, right motors backward)"""
    # Right motors backward
    GPIO.output(IN1, GPIO.LOW)
    GPIO.output(IN2, GPIO.HIGH)
    # Left motors forward
    GPIO.output(IN3, GPIO.LOW)   # Swapped from HIGH
    GPIO.output(IN4, GPIO.HIGH)  # Swapped from LOW
    # Set speed
    pwm_ena.ChangeDutyCycle(speed)
    pwm_enb.ChangeDutyCycle(speed)

def right_motor_forward(speed=80):
    """Move right motor forward"""
    GPIO.output(IN1, GPIO.HIGH)
    GPIO.output(IN2, GPIO.LOW)
    pwm_ena.ChangeDutyCycle(speed)

def right_motor_backward(speed=80):
    """Move right motor backward"""
    GPIO.output(IN1, GPIO.LOW)
    GPIO.output(IN2, GPIO.HIGH)
    pwm_ena.ChangeDutyCycle(speed)

def right_motor_stop():
    """Stop right motor"""
    GPIO.output(IN1, GPIO.LOW)
    GPIO.output(IN2, GPIO.LOW)
    pwm_ena.ChangeDutyCycle(0)

def left_motor_forward(speed=80):
    """Move left motor forward"""
    GPIO.output(IN3, GPIO.LOW)   # Swapped from HIGH
    GPIO.output(IN4, GPIO.HIGH)  # Swapped from LOW
    pwm_enb.ChangeDutyCycle(speed)

def left_motor_backward(speed=80):
    """Move left motor backward"""
    GPIO.output(IN3, GPIO.HIGH)  # Swapped from LOW
    GPIO.output(IN4, GPIO.LOW)   # Swapped from HIGH
    pwm_enb.ChangeDutyCycle(speed)

def left_motor_stop():
    """Stop left motor"""
    GPIO.output(IN3, GPIO.LOW)
    GPIO.output(IN4, GPIO.LOW)
    pwm_enb.ChangeDutyCycle(0)

# Individual motor control endpoints
@app.post("/right-motor/forward")
async def right_motor_forward_endpoint(speed: int = 80):
    """Move right motor forward"""
    if not 0 <= speed <= 100:
        return {"error": "Speed must be between 0 and 100"}
    right_motor_forward(speed)
    return {"action": "right_motor_forward", "speed": speed}

@app.post("/right-motor/backward")
async def right_motor_backward_endpoint(speed: int = 80):
    """Move right motor backward"""
    if not 0 <= speed <= 100:
        return {"error": "Speed must be between 0 and 100"}
    right_motor_backward(speed)
    return {"action": "right_motor_backward", "speed": speed}

@app.post("/right-motor/stop")
async def right_motor_stop_endpoint():
    """Stop right motor"""
    right_motor_stop()
    return {"action": "right_motor_stop"}

@app.post("/left-motor/forward")
async def left_motor_forward_endpoint(speed: int = 80):
    """Move left motor forward"""
    if not 0 <= speed <= 100:
        return {"error": "Speed must be between 0 and 100"}
    left_motor_forward(speed)
    return {"action": "left_motor_forward", "speed": speed}

@app.post("/left-motor/backward")
async def left_motor_backward_endpoint(speed: int = 80):
    """Move left motor backward"""
    if not 0 <= speed <= 100:
        return {"error": "Speed must be between 0 and 100"}
    left_motor_backward(speed)
    return {"action": "left_motor_backward", "speed": speed}

@app.post("/left-motor/stop")
async def left_motor_stop_endpoint():
    """Stop left motor"""
    left_motor_stop()
    return {"action": "left_motor_stop"}

# Basic movement control endpoints (add these after the individual motor functions)
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
async def turn_left_endpoint(speed: int = 80):
    """Turn car left"""
    if not 0 <= speed <= 100:
        return {"error": "Speed must be between 0 and 100"}
    turn_left(speed)
    return {"action": "left", "speed": speed}

@app.post("/right")
async def turn_right_endpoint(speed: int = 80):
    """Turn car right"""
    if not 0 <= speed <= 100:
        return {"error": "Speed must be between 0 and 100"}
    turn_right(speed)
    return {"action": "right", "speed": speed}

@app.post("/stop")
async def stop_car():
    """Stop all motors"""
    stop_motors()
    return {"action": "stop"}

# Test individual pins endpoint
@app.post("/test/pin/{pin_name}")
async def test_pin(pin_name: str, state: str = "high"):
    """Test individual GPIO pin - for debugging"""
    pin_map = {
        "in1": IN1,
        "in2": IN2,
        "in3": IN3,
        "in4": IN4
    }
    
    if pin_name.lower() not in pin_map:
        return {"error": f"Invalid pin name. Available: {list(pin_map.keys())}"}
    
    if state.lower() not in ["high", "low"]:
        return {"error": "State must be 'high' or 'low'"}
    
    pin = pin_map[pin_name.lower()]
    gpio_state = GPIO.HIGH if state.lower() == "high" else GPIO.LOW
    GPIO.output(pin, gpio_state)
    
    return {"action": f"set_pin_{pin_name}", "pin": pin, "state": state}

@app.post("/test/pwm/{motor}")
async def test_pwm(motor: str, duty_cycle: int = 50):
    """Test PWM for individual motor - for debugging"""
    if not 0 <= duty_cycle <= 100:
        return {"error": "Duty cycle must be between 0 and 100"}
    
    if motor.lower() == "right":
        pwm_ena.ChangeDutyCycle(duty_cycle)
        return {"action": "test_right_pwm", "duty_cycle": duty_cycle}
    elif motor.lower() == "left":
        pwm_enb.ChangeDutyCycle(duty_cycle)
        return {"action": "test_left_pwm", "duty_cycle": duty_cycle}
    else:
        return {"error": "Motor must be 'right' or 'left'"}

@app.get("/status")
async def get_status():
    """Get car status"""
    return {
        "status": "ready", 
        "available_commands": [
            "forward", "backward", "left", "right", "stop",
            "right-motor/forward", "right-motor/backward", "right-motor/stop",
            "left-motor/forward", "left-motor/backward", "left-motor/stop",
            "test/pin/{pin_name}", "test/pwm/{motor}"
        ],
        "pin_mapping": {
            "ENA": ENA, "ENB": ENB,
            "IN1": IN1, "IN2": IN2, "IN3": IN3, "IN4": IN4
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)