import RPi.GPIO as GPIO
import time
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GPIO.setmode(GPIO.BCM)
IR_PIN = 17

# Initialize IR pin
GPIO.setup(IR_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

def ir_stream(fps=30):
    """Generator that yields raw IR sensor value at specified FPS."""
    interval = 1.0 / fps
    logger.info(f"Starting IR stream at {fps} FPS (interval: {interval:.3f}s)")
    
    try:
        while True:
            try:
                value = GPIO.input(IR_PIN)
                yield value
                time.sleep(interval)
            except Exception as e:
                logger.error(f"Error reading IR sensor: {e}")
                yield "error"
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
        for i in range(20):
            value = GPIO.input(IR_PIN)
            logger.info(f"Test {i+1}: IR Value = {value}")
            time.sleep(0.5)
        return True
    except Exception as e:
        logger.error(f"IR sensor test failed: {e}")
        return False