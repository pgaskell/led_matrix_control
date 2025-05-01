import math
import random
from .base import Pattern as BasePattern, apply_modulation
from colormaps import COLORMAPS

PARAMS = {
    "NUM_GENERATORS": {
        "default": 4, "min": 1, "max": 10, "step": 1,
        "modulatable": True
    },
    "MOVE_SPEED": {
        "default": 0.1, "min": 0.01, "max": 1.0, "step": 0.01,
        "modulatable": True
    },
    "COLOR_CYCLE_SPEED": {
        "default": 0.0, "min": 0.0, "max": 0.1, "step": 0.001,
        "modulatable": True
    },
    "COLORMAP": {
        "default": "warm_rainbow",
        "options": list(COLORMAPS.keys())
    },
    "SPRITE": {
        "default": "none",
        "options": []
    }
}

class Pattern(BasePattern):
    def __init__(self, width, height, params=None):
        super().__init__(width, height, params)
        self.param_meta = PARAMS
        self.frame_count = 0
        self.circles = []  # (x, y, age)
    
    def render(self, lfo_signals=None):
        self.frame_count += 1

        # Params
        num_gen = self.params["NUM_GENERATORS"]
        move_speed = self.params["MOVE_SPEED"]
        color_shift = self.params["COLOR_CYCLE_SPEED"]

        # Modulate
        for key in ["NUM_GENERATORS", "MOVE_SPEED", "COLOR_CYCLE_SPEED"]:
            meta = self.param_meta.get(key, {})
            if meta.get("modulatable") and meta.get("mod_active") and meta.get("mod_source") in (lfo_signals or {}):
                val = apply_modulation(self.params[key], meta, lfo_signals)
                if key == "NUM_GENERATORS":
                    num_gen = int(max(1, round(val)))
                elif key == "MOVE_SPEED":
                    move_speed = val
                elif key == "COLOR_CYCLE_SPEED":
                    color_shift = val

        cmap = COLORMAPS.get(self.params["COLORMAP"], COLORMAPS["jet"])
        cmap_len = len(cmap)

        # Add new circle randomly if under limit
        if len(self.circles) < num_gen and random.random() < 0.2:
            x = random.randint(0, self.width - 1)
            y = random.randint(0, self.height - 1)
            self.circles.append((x, y, 0))  # age = 0

        # Update circle ages
        new_circles = []
        for cx, cy, age in self.circles:
            if age < 300:  # max age
                new_circles.append((cx, cy, age + 1))
        self.circles = new_circles

        hue_offset = self.frame_count * color_shift
        frame = []

        for y in range(self.height):
            for x in range(self.width):
                intensity = 0.0
                for cx, cy, age in self.circles:
                    radius = age * move_speed
                    dist = math.hypot(x - cx, y - cy)
                    delta = abs(dist - radius)
                    strength = max(0.0, 1.0 - delta)
                    intensity += strength
                intensity = min(intensity, 1.0)
                hue = (intensity + hue_offset) % 1.0
                index = int(hue * (cmap_len - 1))
                r, g, b = cmap[index]
                frame.append((r, g, b, 0))

        return frame
