import spidev
import time

class LEDColor:
    """Represents an RGBW color for the WS2814"""
    def __init__(self, red=0, green=0, blue=0, white=0):
        self.red = red
        self.green = green
        self.blue = blue
        self.white = white

class WS2814:
    def __init__(self, spi_device='/dev/spidev0.0', num_leds=8, spi_speed_khz=800):
        """Initialize the Pi5Neo class with SPI device, number of LEDs, and speed"""
        self.num_leds = num_leds
        self.spi_speed = spi_speed_khz * 1000 * 8  # Convert kHz to bytes per second this is 6.4MHz
        print(self.spi_speed)
        self.spi = spidev.SpiDev()  # Create SPI device instance
        self.raw_data = [0] * (self.num_leds * 32)  # Placeholder for raw data sent via SPI
        self.led_state = [LEDColor()] * self.num_leds  # Initial state for each LED (off)
        

        # Open the SPI device
        if self.open_spi_device(spi_device):
            time.sleep(0.1)  # Short delay to ensure device is ready
            self.clear_strip()  # Clear the strip on startup
            self.update_strip()

    def open_spi_device(self, device_path):
        """Open the SPI device with the provided path"""
        try:
            bus, device = map(int, device_path[-3:].split('.'))
            self.spi.open(bus, device)
            self.spi.max_speed_hz = self.spi_speed
            self.spi.mode = 0
            print(f"Opened SPI device: {device_path}")
            return True
        except Exception as e:
            print(f"Failed to open SPI device: {e}")
            return False

    def send_spi_data(self):
        """Send the raw data buffer to the NeoPixel strip via SPI"""
        pause = [0x00] * 250
        spi_message = bytes(pause + self.raw_data + pause)
        self.spi.xfer3(list(spi_message))  #previously spi.xfer2


    def bitmask(self, byte, position):
        """Retrieve the value of a specific bit in a byte"""
        return bool(byte & (1 << (7 - position)))

    def byte_to_bitstream(self, byte):
        """Convert a byte to the NeoPixel timing bitstream"""
        bitstream = [0xC0] * 8  # Initialize with LOW bits
        for i in range(8):
            if self.bitmask(byte, i):
                bitstream[i] = 0xF8  # Set HIGH bits for '1'
        return bitstream

    # def rgb_to_spi_bitstream(self, red, green, blue):
    #     """Convert RGB values to the NeoPixel bitstream format for SPI"""
    #     green_bits = self.byte_to_bitstream(green)  # Send green first
    #     red_bits = self.byte_to_bitstream(red)  # Then red
    #     blue_bits = self.byte_to_bitstream(blue)  # Then blue
    #     return green_bits + red_bits + blue_bits  # Concatenate GRB order

    def rgbw_to_spi_bitstream(self, red, green, blue, white):
        """Convert RGB values to the NeoPixel bitstream format for SPI"""
        white_bits = self.byte_to_bitstream(white)
        green_bits = self.byte_to_bitstream(green)  # Send green first
        red_bits = self.byte_to_bitstream(red)  # Then red
        blue_bits = self.byte_to_bitstream(blue)  # Then blue
        return  white_bits + red_bits + green_bits + blue_bits # Concatenate WGRB order

    def clear_strip(self):
        """Turn off all LEDs on the strip"""
        self.fill_strip(0, 0, 0, 0)

    def fill_strip(self, red=0, green=0, blue=0, white=0):
        """Fill the entire strip with a specific color"""
        color = LEDColor(red, green, blue, white)
        self.led_state = [color] * self.num_leds  # Set all LEDs to the same color

    def set_led_color(self, index, red, green, blue, white):
        """Set the color of an individual LED"""
        if 0 <= index < self.num_leds:
            self.led_state[index] = LEDColor(red, green, blue, white)
            return True
        return False

    def update_strip(self):
        """Send the current state of the LED strip to the LEDs
        """
        total_bytes = 0
        for i in range(self.num_leds):
            led = self.led_state[i]  # Get the color for each LED
            bitstream = self.rgbw_to_spi_bitstream(led.red, led.green, led.blue, led.white)
            for j in range(32):
                self.raw_data[total_bytes] = bitstream[j]
                total_bytes += 1
        self.send_spi_data()


