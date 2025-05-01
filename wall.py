from config import USE_SIMULATOR, GPIO_PIN
try:
    import neopixel
    import board
except ImportError:
    neopixel = None

try:
    from simulator.simulator_display import Simulator
except ImportError:
    Simulator = None

class Wall:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.num_pixels = width * height

        if USE_SIMULATOR:
            self.simulator = True
            self.driver = Simulator(width, height)
        else:
            self.simulator = False
            self.pixels = neopixel.NeoPixel(
                board.D18, self.num_pixels, pixel_order=neopixel.GRBW
            )

    def show(self, frame):
        if self.simulator:
            self.driver.show(frame)  # Simulator uses regular 'show'
        else:
            self._show(frame)        # NeoPixel uses '_show'

    def clear(self):
        blank = [(0,0,0,0)] * self.width * self.height
        self.show(blank)

    def _show(self, frame):  # NeoPixel-only
        for y in range(self.height):
            for x in range(self.width):
                # Convert from row-major to serpentine
                logical_idx = y * self.width + x
                if y % 2 == 0:
                    physical_idx = logical_idx
                else:
                    physical_idx = y * self.width + (self.width - 1 - x)
                
                self.pixels[physical_idx] = frame[logical_idx]
        self.pixels.show()
