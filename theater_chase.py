#Theater Chase Effect (Classic moving LED chase effect)
import time
from ws2814 import WS2814
num_leds = 99
def chase(neo, color, delay=0.1):
    while True:
        for i in range(num_leds):
            leds.set_led_color(i, 255, 0, 0, 255)  # Turn off other LEDs
            leds.update_strip()
        for i in range(num_leds):
            leds.set_led_color(i, 0, 255, 0, 255)  # Turn off other LEDs
            leds.update_strip()
        for i in range(num_leds):
            leds.set_led_color(i, 0, 0, 255, 255)  # Turn off other LEDs
            leds.update_strip()
        for i in range(num_leds):
            leds.set_led_color(i, 0, 0, 0, 255)  # Turn off other LEDs
            leds.update_strip()

# Initialize Pi5Neo with 10 LEDs
leds = WS2814('/dev/spidev0.0', 100, 800)

chase(leds, (0, 0, 0, 255))