import random
from .base import Pattern as BasePattern
from colormaps import COLORMAPS

PARAMS = {
    "RIPPLE_INTERVAL": {"default": 0.7, "min": 0.1, "max": 5.0, "step": 0.1},
    "RIPPLE_SPEED": {"default": 6.0, "min": 0.1, "max": 30.0, "step": 0.1},
    "RIPPLE_LIFESPAN": {"default": 4.0, "min": 0.5, "max": 10.0, "step": 0.1},
    "MAX_RIPPLES": {"default": 7, "min": 1, "max": 15, "step": 1},
    "MAX_INTENSITY": {"default": 255, "min": 10, "max": 255, "step": 5},
    "ENABLE_FADE": {"default": True, "min": 0, "max": 1, "step": 1},
    "FADE_MULTIPLIER": {"default": 0.9, "min": 0.0, "max": 1.0, "step": 0.1},
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

        interval = self.params["RIPPLE_INTERVAL"]
        speed = self.params["RIPPLE_SPEED"]
        lifespan = self.params["RIPPLE_LIFESPAN"]
        max_ripples = self.params["MAX_RIPPLES"]
        max_intensity = self.params["MAX_INTENSITY"]
        fade_mult = self.params["FADE_MULTIPLIER"]
        fade_enabled = self.params["ENABLE_FADE"]
        cmap_name = self.params.get("COLORMAP", "jet")
        cmap = COLORMAPS.get(cmap_name, COLORMAPS["jet"])
        cmap_size = len(cmap)

        # Add a new ripple at a random position
        if len(self.ripples) < max_ripples and self.frame_count % int(interval * 30) == 0:
            x = random.randint(0, self.width - 1)
            y = random.randint(0, self.height - 1)
            self.ripples.append((x, y, 0))

        # Age and remove expired ripples
        self.ripples = [(x, y, age + 1) for (x, y, age) in self.ripples if age < lifespan * 30]

        frame = []
        for j in range(self.height):
            for i in range(self.width):
                intensity = 0.0
                color_scalar = 0.0

                for rx, ry, age in self.ripples:
                    dx = i - rx
                    dy = j - ry
                    dist = (dx**2 + dy**2)**0.5
                    ripple_radius = age * speed / 30.0
                    delta = abs(dist - ripple_radius)
                    strength = max(0.0, 1.0 - delta)
                    intensity += strength
                    color_scalar += (dist % 1.0) * strength  # color modulation by distance

                intensity = min(int(intensity * max_intensity), 255)
                if fade_enabled:
                    intensity = int(intensity * fade_mult)
                v = intensity / 255.0

                index = int((color_scalar % 1.0) * (cmap_size - 1))
                r, g, b = cmap[index]
                r = int(r * v)
                g = int(g * v)
                b = int(b * v)
                frame.append((r, g, b, 0))

        return frame
