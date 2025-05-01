from .base import Pattern as BasePattern
from colormaps import COLORMAPS

# --- Adjustable Parameters ---
PARAMS = {
    "COLORMAP": {
        "default": "jet",
        "options": [
            "jet",
            "hot",
            "cool",
            "warm_rainbow",
            "ocean",
            "viridis_approx",
            "lava_art"
        ]
    }
}

class Pattern(BasePattern):
    def __init__(self, width, height, params=None):
        super().__init__(width, height, params)

    def render(self, lfo_signals=None):
        cmap_name = self.params.get("COLORMAP", "jet")
        cmap = COLORMAPS.get(cmap_name, COLORMAPS["jet"])
        resolution = len(cmap)

        frame = []
        for y in range(self.height):
            for x in range(self.width):
                scalar = x / max(1, self.width - 1)  # ensure in [0, 1]
                index = min(int(scalar * (resolution - 1)), resolution - 1)
                r, g, b = cmap[index]
                frame.append((r, g, b, 0))

        return frame
