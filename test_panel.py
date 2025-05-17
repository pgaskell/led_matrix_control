from ws2814 import WS2814
import time
panel = WS2814('/dev/spidev0.0', 64, 800)

def main():
    panel.clear_strip()
    panel.update_strip()
    #panel.fill_strip(255, 0, 0, 0) # R G B W
    panel.set_led_color(0, 255, 0, 0, 0)
    panel.update_strip()

if __name__ == "__main__":
    main()