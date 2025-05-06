# patterns/kinect_video.py

import numpy as np
import colorsys
import freenect
from .base import Pattern as BasePattern

# ─── Adjustable Parameters ──────────────────────────────────────────────────
PARAMS = {
    "SATURATION": {
        "default": 1.5,  # 1.0 = original, >1.0 = more saturated
        "min":     0.0,
        "max":     3.0,
        "step":    0.1
    },
    "BRIGHTNESS": {
        "default": 1.0,  # 1.0 = original, >1.0 = brighter
        "min":     0.1,
        "max":     2.0,
        "step":    0.1
    }
}

class Pattern(BasePattern):
    def __init__(self, width, height, params=None):
        super().__init__(width, height, params)
        # nothing else to keep between frames

    def render(self, lfo_signals=None):
        # fetch a fresh video frame from the Kinect
        # returns (H×W×3 uint8 array, timestamp)
        frame_rgb, _ = freenect.sync_get_video()
        # normalize to [0.0..1.0]
        video = frame_rgb.astype(np.float32) / 255.0

        sat_mul = self.params["SATURATION"]
        bri_mul = self.params["BRIGHTNESS"]

        in_h, in_w, _ = video.shape
        out = []

        # map each LED pixel to a down-sampled source pixel
        for y in range(self.height):
            src_y = int(y * in_h / self.height)
            for x in range(self.width):
                src_x = int(x * in_w / self.width)
                r, g, b = video[src_y, src_x]

                # convert to HSV, boost S and V, clamp to [0,1]
                h, s, v = colorsys.rgb_to_hsv(r, g, b)
                s = min(s * sat_mul, 1.0)
                v = min(v * bri_mul, 1.0)
                r2, g2, b2 = colorsys.hsv_to_rgb(h, s, v)

                # store as 0–255 ints
                out.append((int(r2 * 255), int(g2 * 255), int(b2 * 255), 0))

        return out
