from .base import Pattern as BasePattern, apply_modulation
from colormaps import COLORMAPS

# --- Adjustable Parameters ---
PARAMS = {
    "SQUARE_X": {
        "default": 0.5, "min": 0.0, "max": 1.0, "step": 0.01,
        "modulatable": True
    },
    "SQUARE_Y": {
        "default": 0.5, "min": 0.0, "max": 1.0, "step": 0.01,
        "modulatable": True
    },
    "LUT_INDEX": {
        "default": 0.5, "min": 0.0, "max": 1.0, "step": 0.01,
        "modulatable": True
    }  
}

class Pattern(BasePattern):
    def __init__(self, width, height, params=None):
        super().__init__(width, height, params)
        self.param_meta = PARAMS

    def render(self, lfo_signals=None):
        # Load base values
        x_norm = self.params["SQUARE_X"]
        y_norm = self.params["SQUARE_Y"]
        lut_index = self.params["LUT_INDEX"]

        # Apply modulation
        for key in ["SQUARE_X", "SQUARE_Y", "LUT_INDEX"]:
            meta = self.param_meta.get(key)
            if (
                meta.get("modulatable")
                and "mod_active" in meta
                and meta["mod_active"]
                and meta.get("mod_source") in (lfo_signals or {})
            ):
                mod_val = apply_modulation(self.params[key], meta, lfo_signals or {})
                if key == "SQUARE_X":
                    x_norm = mod_val
                elif key == "SQUARE_Y":
                    y_norm = mod_val
                elif key == "LUT_INDEX":
                    lut_index = mod_val

        # Get color from colormap
        cmap = COLORMAPS.get(self.params["COLORMAP"], COLORMAPS["jet"])
        cmap_len = len(cmap)
        index = int(lut_index * (cmap_len - 1))
        index = max(0, min(index, cmap_len - 1))
        color = cmap[index]

        # Convert normalized x/y to pixel coordinates
        x = int(round(x_norm * (self.width - 1)))
        y = int(round(y_norm * (self.height - 1)))

        # Draw square
        frame = [(0, 0, 0, 0)] * (self.width * self.height)
        square_size = 3
        for j in range(-square_size, square_size + 1):
            for i in range(-square_size, square_size + 1):
                px = x + i
                py = y + j
                if 0 <= px < self.width and 0 <= py < self.height:
                    idx = py * self.width + px
                    frame[idx] = (*color, 0)

        return frame
