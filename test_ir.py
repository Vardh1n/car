import RPi.GPIO as GPIO
import time

# Test IR sensor directly
GPIO.setmode(GPIO.BCM)
IR_PIN = 13
GPIO.setup(IR_PIN, GPIO.IN)

try:
    print("Testing IR sensor directly...")
    for i in range(100):  # Test for 10 seconds
        value = GPIO.input(IR_PIN)
        print(f"IR Value: {value}")
        time.sleep(0.1)
except KeyboardInterrupt:
    print("Test stopped")
finally:
    GPIO.cleanup()