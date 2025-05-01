import math
from .base import Pattern as BasePattern, apply_modulation
from colormaps import COLORMAPS

PARAMS = {
    "STRIPE_SPEED": {
        "default": 0.1, "min": -1.0, "max": 1.0, "step": 0.01,
        "modulatable": True
    },
    "STRIPE_WIDTH": {
        "default": 1.0, "min": 0.5, "max": 5.0, "step": 0.5,
        "modulatable": True
    },
    "STRIPE_ANGLE": {
        "default": 45.0, "min": 0.0, "max": 360.0, "step": 1.0,
        "modulatable": True
    },
    "COLORMAP": {
        "default": "warm_rainbow",
        "options": list(COLORMAPS.keys())
    },
    "SPRITE": {
        "default": "none",
        "options": []  # filled dynamically in launch_ui
    }
}

class Pattern(BasePattern):
    def __init__(self, width, height, params=None):
        super().__init__(width, height, params)
        self.param_meta = PARAMS
        self.frame_count = 0

    def render(self, lfo_signals=None):
        self.frame_count += 1

        # Get base parameters
        speed = self.params["STRIPE_SPEED"]
        width = self.params["STRIPE_WIDTH"]
        angle_deg = self.params["STRIPE_ANGLE"]

        # Apply modulation if active
        for key in ["STRIPE_SPEED", "STRIPE_WIDTH", "STRIPE_ANGLE"]:
            meta = self.param_meta.get(key, {})
            if meta.get("modulatable") and meta.get("mod_active") and meta.get("mod_source") in (lfo_signals or {}):
                mod_val = apply_modulation(self.params[key], meta, lfo_signals)
                if key == "STRIPE_SPEED":
                    speed = mod_val
                elif key == "STRIPE_WIDTH":
                    width = mod_val
                elif key == "STRIPE_ANGLE":
                    angle_deg = mod_val

        # Colormap
        cmap = COLORMAPS.get(self.params["COLORMAP"], COLORMAPS["jet"])
        cmap_len = len(cmap)

        angle_rad = math.radians(angle_deg)
        dx = math.cos(angle_rad)
        dy = math.sin(angle_rad)

        t_offset = self.frame_count * speed

        frame = []
        for j in range(self.height):
            for i in range(self.width):
                stripe_coord = (i * dx + j * dy + t_offset) / width
                color_index = int(abs(stripe_coord) * 10) % cmap_len
                r, g, b = cmap[color_index]
                frame.append((r, g, b, 0))

        return frame
