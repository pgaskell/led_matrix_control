import math
from .base import Pattern as BasePattern
from colormaps import COLORMAPS

# --- Adjustable Parameters ---
PARAMS = {
    "COLORMAP": {
        "default": "warm_rainbow",
        "options": ["jet", "hot", "cool", "warm_rainbow", "ocean", "viridis_approx", "lava_art"]
    },
    "NUM_STRIPES": {"default": 8, "min": 2, "max": 64, "step": 1},
    "ANGLE_DEGREES": {"default": 45, "min": 0, "max": 360, "step": 1},
    "SPEED": {"default": 0.1, "min": 0.01, "max": 1.0, "step": 0.01},
}

class Pattern(BasePattern):
    def __init__(self, width, height, params=None):
        super().__init__(width, height, params)
        self.frame_count = 0

    def render(self, lfo_signals=None):
        self.frame_count += 1

        colormap_name = self.params.get("COLORMAP", "jet")
        colormap = COLORMAPS.get(colormap_name, COLORMAPS["jet"])
        lut_size = len(colormap)

        num_stripes = self.params["NUM_STRIPES"]
        angle_deg = self.params["ANGLE_DEGREES"]
        speed = self.params["SPEED"]

        angle_rad = math.radians(angle_deg)
        dx = math.cos(angle_rad)
        dy = math.sin(angle_rad)

        # Use frame count to animate movement along the stripe direction
        shift = self.frame_count * speed

        frame = []
        for y in range(self.height):
            for x in range(self.width):
                # Compute stripe coordinate
                stripe_pos = (x * dx + y * dy + shift)
                scalar = (stripe_pos / num_stripes) % 1.0  # Normalize and wrap

                index = min(int(scalar * (lut_size - 1)), lut_size - 1)
                r, g, b = colormap[index]
                frame.append((r, g, b, 0))

        return frame
