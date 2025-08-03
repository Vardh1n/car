import RPi.GPIO as GPIO
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class TankCar:
    """Simple tank drive car controller"""
    
    def __init__(self):
        # Motor pins
        self.ENA = 18  # Left motor PWM
        self.ENB = 13  # Right motor PWM
        self.IN1 = 23  # Left motor direction 1
        self.IN2 = 24  # Left motor direction 2
        self.IN3 = 27  # Right motor direction 1
        self.IN4 = 22  # Right motor direction 2
        
        # PWM instances
        self.left_pwm: Optional[GPIO.PWM] = None
        self.right_pwm: Optional[GPIO.PWM] = None
        
        # Initialize GPIO
        self._setup_gpio()
    
    def _setup_gpio(self):
        """Initialize GPIO pins"""
        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            
            # Setup motor pins as outputs
            for pin in [self.ENA, self.ENB, self.IN1, self.IN2, self.IN3, self.IN4]:
                GPIO.setup(pin, GPIO.OUT)
                GPIO.output(pin, GPIO.LOW)
            
            # Initialize PWM (1kHz frequency)
            self.left_pwm = GPIO.PWM(self.ENA, 1000)
            self.right_pwm = GPIO.PWM(self.ENB, 1000)
            self.left_pwm.start(0)
            self.right_pwm.start(0)
            
            logger.info("Car GPIO initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize car GPIO: {e}")
            raise
    
    def _set_left_motor(self, speed: float):
        """Control left motor (-100 to 100)"""
        if speed > 0:
            # Clockwise
            GPIO.output(self.IN1, GPIO.HIGH)
            GPIO.output(self.IN2, GPIO.LOW)
        elif speed < 0:
            # Anticlockwise
            GPIO.output(self.IN1, GPIO.LOW)
            GPIO.output(self.IN2, GPIO.HIGH)
        else:
            # Stop
            GPIO.output(self.IN1, GPIO.LOW)
            GPIO.output(self.IN2, GPIO.LOW)
        
        # Set PWM speed
        if self.left_pwm:
            self.left_pwm.ChangeDutyCycle(abs(speed))
    
    def _set_right_motor(self, speed: float):
        """Control right motor (-100 to 100)"""
        if speed > 0:
            # Clockwise
            GPIO.output(self.IN3, GPIO.HIGH)
            GPIO.output(self.IN4, GPIO.LOW)
        elif speed < 0:
            # Anticlockwise
            GPIO.output(self.IN3, GPIO.LOW)
            GPIO.output(self.IN4, GPIO.HIGH)
        else:
            # Stop
            GPIO.output(self.IN3, GPIO.LOW)
            GPIO.output(self.IN4, GPIO.LOW)
        
        # Set PWM speed
        if self.right_pwm:
            self.right_pwm.ChangeDutyCycle(abs(speed))
    
    def move(self, left_speed: float, right_speed: float):
        """Move car with individual motor speeds (-100 to 100)"""
        # Clamp speeds to valid range
        left_speed = max(-100, min(100, left_speed))
        right_speed = max(-100, min(100, right_speed))
        
        self._set_left_motor(left_speed)
        self._set_right_motor(right_speed)
        
        logger.info(f"Car moving: left={left_speed}%, right={right_speed}%")
    
    def forward(self, speed: float = 50):
        """Move forward (both sides clockwise)"""
        self.move(speed, speed)
    
    def backward(self, speed: float = 50):
        """Move backward (both sides anticlockwise)"""
        self.move(-speed, -speed)
    
    def turn_left(self, speed: float = 50):
        """Turn left (right side clockwise, left side anticlockwise)"""
        self.move(-speed, speed)
    
    def turn_right(self, speed: float = 50):
        """Turn right (left side clockwise, right side anticlockwise)"""
        self.move(speed, -speed)
    
    def pivot_left(self, speed: float = 50):
        """Pivot left (only right side moves clockwise)"""
        self.move(0, speed)
    
    def pivot_right(self, speed: float = 50):
        """Pivot right (only left side moves clockwise)"""
        self.move(speed, 0)
    
    def stop(self):
        """Stop all motors"""
        self.move(0, 0)
    
    def cleanup(self):
        """Clean up GPIO resources"""
        try:
            if self.left_pwm:
                self.left_pwm.stop()
            if self.right_pwm:
                self.right_pwm.stop()
            GPIO.cleanup()
            logger.info("Car GPIO cleaned up")
        except Exception as e:
            logger.error(f"Error during car cleanup: {e}")