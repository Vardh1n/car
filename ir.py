import RPi.GPIO as GPIO
import time

GPIO.setmode(GPIO.BCM)
IR_PIN = 13
GPIO.setup(IR_PIN, GPIO.IN)

def ir_stream(fps=30):
    """Generator that yields IR sensor value at specified FPS."""
    interval = 1.0 / fps
    try:
        while True:
            value = GPIO.input(IR_PIN)
            yield value
            time.sleep(interval)
    except GeneratorExit:
        pass
    finally:
        GPIO.cleanup(IR_PIN)