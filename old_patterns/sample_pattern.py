import random
import colorsys
from .base import Pattern as BasePattern

# --- Adjustable Parameters ---
PARAMS = {
    "SATURATION": {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.1},
    "MIN_VALUE": {"default": 0.5, "min": 0.0, "max": 1.0, "step": 0.1},
    "MAX_VALUE": {"default": 1.0, "min": 0.1, "max": 1.0, "step": 0.1},
    "VALUE_STEP": {"default": 0.1, "min": 0.01, "max": 0.5, "step": 0.01},
    "COLORMAP": {
        "default": "jet",
        "options": ["jet", "hot", "cool", "warm_rainbow", "ocean", "viridis_approx", "lava_art"]
    }
}

class Pattern(BasePattern):
    def __init__(self, width, height, params=None):
        super().__init__(width, height, params)


    def render(self, lfo_signals=None):
        s = self.params["SATURATION"]
        v_min = self.params["MIN_VALUE"]
        v_max = self.params["MAX_VALUE"]
        v_step = self.params["VALUE_STEP"]

        # Clamp for safety
        v_min = max(0.0, min(v_min, 1.0))
        v_max = max(v_min, min(v_max, 1.0))
        steps = int((v_max - v_min) / v_step) + 1
        v_choices = [round(v_min + i * v_step, 2) for i in range(steps)]

        frame = []
        for _ in range(self.width * self.height):
            h = random.random()
            v = random.choice(v_choices)
            r, g, b = colorsys.hsv_to_rgb(h, s, v)
            frame.append((int(r * 255), int(g * 255), int(b * 255), 0))

        return frame
