# patterns/kinect_depth.py

import numpy as np
import freenect
from .base import Pattern as BasePattern
from colormaps import COLORMAPS

# --- Adjustable Parameters ---
PARAMS = {
    "COLORMAP": {
        "default": "viridis_approx",
        "options": list(COLORMAPS.keys())
    },
    "DEPTH_MIN": { 
        "default": 500, "min": 500, "max": 4500, "step": 100
    },
    "DEPTH_MAX": {
        "default": 4000, "min": 500, "max": 4500, "step": 100
    },
}

class Pattern(BasePattern):
    def __init__(self, width, height, params=None):
        super().__init__(width, height, params)
        # nothing else to init

    def render(self, lfo_signals=None):
        # 1) grab one frame of depth (11-bit, 0–2047)
        depth_raw, _ = freenect.sync_get_depth()
        # freenect returns 480×640; convert to millimeters-ish
        depth_mm = depth_raw.astype(np.float32)

        # 2) clip & normalize
        dmin = self.params["DEPTH_MIN"]
        dmax = self.params["DEPTH_MAX"]
        clipped = np.clip(depth_mm, dmin, dmax)
        norm = (clipped - dmin) / float(dmax - dmin)  # in [0..1]

        # 3) downsample to LED matrix size
        #    we'll do simple block averaging
        src_h, src_w = norm.shape
        block_h = src_h // self.height
        block_w = src_w // self.width

        # reshape into (self.height, block_h, self.width, block_w)
        small = norm[: block_h * self.height, : block_w * self.width] \
            .reshape(self.height, block_h, self.width, block_w) \
            .mean(axis=(1, 3))

        # 4) map each value through the selected colormap
        cmap = COLORMAPS.get(self.params["COLORMAP"], COLORMAPS["viridis_approx"])
        n = len(cmap)

        frame = []
        for y in range(self.height):
            for x in range(self.width):
                v = small[y, x]
                idx = int(v * (n - 1))
                r, g, b = cmap[idx]
                frame.append((r, g, b, 0))

        return frame
