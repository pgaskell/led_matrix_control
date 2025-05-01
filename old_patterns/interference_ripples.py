import random
import math
from .base import Pattern as BasePattern
from colormaps import COLORMAPS

PARAMS = {
    "RIPPLE_INTERVAL": {"default": 0.5, "min": 0.1, "max": 3.0, "step": 0.1},
    "RIPPLE_SPEED": {"default": 10.0, "min": 1.0, "max": 30.0, "step": 0.5},
    "RIPPLE_WAVELENGTH": {"default": 5.0, "min": 1.0, "max": 20.0, "step": 0.5},
    "MAX_RIPPLES": {"default": 5, "min": 1, "max": 10, "step": 1},
    "AMPLITUDE": {"default": 1.0, "min": 0.1, "max": 3.0, "step": 0.1},
    "FADE_MULTIPLIER": {"default": 0.8, "min": 0.0, "max": 1.0, "step": 0.1},
    "COLORMAP": {
        "default": "warm_rainbow",
        "options": ["jet", "hot", "cool", "warm_rainbow", "ocean", "viridis_approx", "lava_art"]
    }
}

class Pattern(BasePattern):
    def __init__(self, width, height, params=None):
        super().__init__(width, height, params)
        self.frame_count = 0
        self.ripples = []  # Each ripple is (x, y, age)

    def render(self, lfo_signals=None):
        self.frame_count += 1

        # Params
        interval = self.params["RIPPLE_INTERVAL"]
        speed = self.params["RIPPLE_SPEED"]
        wavelength = self.params["RIPPLE_WAVELENGTH"]
        max_ripples = self.params["MAX_RIPPLES"]
        amplitude = self.params["AMPLITUDE"]
        fade_mult = self.params["FADE_MULTIPLIER"]
        cmap_name = self.params["COLORMAP"]
        cmap = COLORMAPS.get(cmap_name, COLORMAPS["jet"])
        cmap_size = len(cmap)

        # Emit a new ripple at a random position periodically
        if len(self.ripples) < max_ripples and self.frame_count % int(interval * 30) == 0:
            x = random.randint(0, self.width - 1)
            y = random.randint(0, self.height - 1)
            self.ripples.append((x, y, 0))

        # Age ripples
        self.ripples = [(x, y, age + 1) for (x, y, age) in self.ripples]

        frame = []
        for j in range(self.height):
            for i in range(self.width):
                wave_sum = 0.0
                for rx, ry, age in self.ripples:
                    dx = i - rx
                    dy = j - ry
                    dist = math.hypot(dx, dy)
                    time = age / 30.0  # frames to seconds
                    phase = (2 * math.pi * (dist - speed * time)) / wavelength
                    wave_sum += math.sin(phase)

                # Normalize and scale to 0–1
                wave_height = wave_sum * amplitude
                scalar = (math.sin(wave_height) * 0.5 + 0.5) * fade_mult
                scalar = max(0.0, min(1.0, scalar))

                index = int(scalar * (cmap_size - 1))
                r, g, b = cmap[index]
                frame.append((r, g, b, 0))

        return frame
