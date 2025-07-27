from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, Optional
import RPi.GPIO as GPIO
import logging

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

# Initialize GPIO
@app.on_event("startup")
async def startup_event():
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    logger.info("GPIO initialized")

@app.on_event("shutdown")
async def shutdown_event():
    # Stop all PWM instances
    for pwm in pwm_instances.values():
        pwm.stop()
    GPIO.cleanup()
    logger.info("GPIO cleaned up")

# Pin configuration endpoints
@app.post("/pin/configure")
async def configure_pin(config: PinConfig):
    """Configure a GPIO pin as input or output"""
    try:
        pin = config.pin
        
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
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/pin/{pin}/status")
async def get_pin_status(pin: int):
    """Get the current status of a GPIO pin"""
    try:
        if pin not in pin_states:
            raise HTTPException(status_code=404, detail="Pin not configured")
        
        status = pin_states[pin].copy()
        if status["mode"] == "input":
            status["current_value"] = GPIO.input(pin)
        elif status["mode"] == "output":
            status["current_value"] = GPIO.input(pin)
        
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
        raise HTTPException(status_code=500, detail=str(e))

# PWM control endpoints
@app.post("/pwm/start")
async def start_pwm(config: PWMConfig):
    """Start PWM on a pin"""
    try:
        pin = config.pin
        
        if pin not in pin_states or pin_states[pin]["mode"] != "output":
            raise HTTPException(status_code=400, detail="Pin must be configured as output")
        
        if pin in pwm_instances:
            pwm_instances[pin].stop()
        
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
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/pwm/update")
async def update_pwm_duty_cycle(data: PWMUpdate):
    """Update PWM duty cycle"""
    try:
        pin = data.pin
        
        if pin not in pwm_instances:
            raise HTTPException(status_code=404, detail="PWM not active on this pin")
        
        pwm_instances[pin].ChangeDutyCycle(data.duty_cycle)
        pin_states[pin]["pwm"]["duty_cycle"] = data.duty_cycle
        
        logger.info(f"PWM duty cycle updated on pin {pin}: {data.duty_cycle}%")
        return {"message": f"PWM duty cycle updated on pin {pin}", "duty_cycle": data.duty_cycle}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/pwm/stop/{pin}")
async def stop_pwm(pin: int):
    """Stop PWM on a pin"""
    try:
        if pin not in pwm_instances:
            raise HTTPException(status_code=404, detail="PWM not active on this pin")
        
        pwm_instances[pin].stop()
        del pwm_instances[pin]
        
        if "pwm" in pin_states[pin]:
            del pin_states[pin]["pwm"]
        
        logger.info(f"PWM stopped on pin {pin}")
        return {"message": f"PWM stopped on pin {pin}"}
    
    except Exception as e:
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
        for pwm in pwm_instances.values():
            pwm.stop()
        pwm_instances.clear()
        pin_states.clear()
        GPIO.cleanup()
        GPIO.setmode(GPIO.BCM)
        
        logger.info("All pins cleaned up")
        return {"message": "All pins cleaned up successfully"}
    
    except Exception as e:
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
