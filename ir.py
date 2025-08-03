import RPi.GPIO as GPIO
import time
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GPIO.setmode(GPIO.BCM)
IR_PIN = 13

# Try to auto-detect if sensor is active HIGH or LOW
def detect_ir_type():
    """Detect if IR sensor is active HIGH or LOW"""
    GPIO.setup(IR_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    time.sleep(0.1)
    
    readings = []
    for _ in range(10):
        readings.append(GPIO.input(IR_PIN))
        time.sleep(0.05)
    
    # If we get mostly 1s, sensor might be active LOW
    # If we get mostly 0s, sensor might be active HIGH or not connected
    ones_count = sum(readings)
    logger.info(f"IR detection readings: {readings}")
    logger.info(f"Ones count: {ones_count}/10")
    
    if ones_count >= 8:
        logger.info("IR sensor appears to be active LOW or not connected properly")
        return "LOW"
    elif ones_count <= 2:
        logger.info("IR sensor appears to be active HIGH or shorted")
        return "HIGH"
    else:
        logger.info("IR sensor readings are mixed - check connections")
        return "UNKNOWN"

# Initialize with pull-up resistor (common for IR sensors)
GPIO.setup(IR_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
sensor_type = detect_ir_type()

def ir_stream(fps=30):
    """Generator that yields IR sensor value at specified FPS."""
    interval = 1.0 / fps
    logger.info(f"Starting IR stream at {fps} FPS (interval: {interval:.3f}s)")
    logger.info(f"Sensor type detected as: {sensor_type}")
    
    try:
        while True:
            try:
                raw_value = GPIO.input(IR_PIN)
                
                # For debugging, yield both raw and interpreted values
                if sensor_type == "LOW":
                    # Active LOW: 0 = detected, 1 = not detected
                    interpreted_value = "detected" if raw_value == 0 else "clear"
                else:
                    # Active HIGH: 1 = detected, 0 = not detected
                    interpreted_value = "detected" if raw_value == 1 else "clear"
                
                # Yield a dict with both values for debugging
                result = {
                    "raw": raw_value,
                    "interpreted": interpreted_value,
                    "sensor_type": sensor_type
                }
                
                logger.debug(f"IR reading: raw={raw_value}, interpreted={interpreted_value}")
                yield result
                time.sleep(interval)
            except Exception as e:
                logger.error(f"Error reading IR sensor: {e}")
                yield {"error": str(e)}
                time.sleep(interval)
    except GeneratorExit:
        logger.info("IR stream generator exit")
        pass
    except Exception as e:
        logger.error(f"IR stream error: {e}")
    finally:
        logger.info("Cleaning up IR GPIO")
        GPIO.cleanup(IR_PIN)

def test_ir_sensor():
    """Test function to verify IR sensor is working"""
    try:
        logger.info("Testing IR sensor...")
        logger.info("Cover and uncover the sensor to see changes...")
        
        for i in range(20):
            raw_value = GPIO.input(IR_PIN)
            
            if sensor_type == "LOW":
                interpreted = "DETECTED" if raw_value == 0 else "CLEAR"
            else:
                interpreted = "DETECTED" if raw_value == 1 else "CLEAR"
            
            logger.info(f"Test {i+1}: Raw={raw_value}, Interpreted={interpreted}")
            time.sleep(0.5)
        return True
    except Exception as e:
        logger.error(f"IR sensor test failed: {e}")
        return False