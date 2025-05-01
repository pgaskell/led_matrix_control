import math
from .base import Pattern as BasePattern, apply_modulation
from colormaps import COLORMAPS

# --- Adjustable Parameters ---
PARAMS = {
    "SPIRAL_SPEED": {
        "default": 0.05, "min": -1.0, "max": 1.0, "step": 0.01,
        "modulatable": True
    },
    "NUM_ARMS": {
        "default": 4, "min": 1, "max": 8, "step": 1,
        "modulatable": True
    },
    "ARM_THICKNESS": {
        "default": 0.1, "min": 0.01, "max": 0.5, "step": 0.01,
        "modulatable": True,
    }
}

class Pattern(BasePattern):
    def __init__(self, width, height, params=None):
        super().__init__(width, height, params)
        self.param_meta = PARAMS
        self.frame_count = 0

    def render(self, lfo_signals=None):
        self.frame_count += 1

        # Start with base parameters
        speed = self.params["SPIRAL_SPEED"]
        num_arms = self.params["NUM_ARMS"]
        thickness = self.params["ARM_THICKNESS"]

        # Apply LFO modulation
        for key in ["SPIRAL_SPEED", "NUM_ARMS"]:
            meta = self.param_meta.get(key)
            if (
                meta.get("modulatable")
                and "mod_active" in meta
                and meta["mod_active"]
                and meta.get("mod_source") in (lfo_signals or {})
            ):
                mod_val = apply_modulation(self.params[key], meta, lfo_signals or {})
                if key == "SPIRAL_SPEED":
                    speed = mod_val
                elif key == "NUM_ARMS":
                    num_arms = int(round(mod_val))

        # Generate frame
        cmap = COLORMAPS.get(self.params["COLORMAP"], COLORMAPS["jet"])
        cmap_len = len(cmap)

        cx = self.width / 2
        cy = self.height / 2
        time_offset = self.frame_count * speed

        frame = []
        for y in range(self.height):
            for x in range(self.width):
                dx = x - cx
                dy = y - cy
                r = math.hypot(dx, dy)
                theta = math.atan2(dy, dx)
                theta = (theta + math.pi) / (2 * math.pi)  # normalize to [0, 1)

                spin = (theta + r * 0.05 - time_offset) * num_arms
                v = 0.5 + 0.5 * math.cos(spin * 2 * math.pi)
                v = max(0.0, min(1.0, v ** (1.0 / thickness)))

                index = int(v * (cmap_len - 1))
                r_col, g_col, b_col = cmap[index]
                frame.append((r_col, g_col, b_col, 0))

        return frame
