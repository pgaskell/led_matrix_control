# patterns/plaidimation.py
import time
import math
from .base import Pattern as BasePattern, apply_modulation
from colormaps import COLORMAPS

# — Adjustable Parameters —
PARAMS = {
    "SIZE": {
        "default": 8.0,   # how many pixels per stripe period
        "min":     1.0,
        "max":    32.0,
        "step":    0.5,
        "modulatable": True
    },
    "SPEED": {
        "default": 0.5,   # animation speed in cycles/sec
        "min":     0.0,
        "max":     5.0,
        "step":    0.1,
        "modulatable": True
    },
    "CENTER": {
        "default": 0.5,   # center of the colormap (0..1)
        "min":     0.0,
        "max":     1.0,
        "step":    0.01,
        "modulatable": True
    },
    "SPREAD": {
        "default": 0.5,   # fraction of the LUT around CENTER
        "min":     0.0,
        "max":     1.0,
        "step":    0.01,
        "modulatable": True
    }
}

class Pattern(BasePattern):
    def __init__(self, width, height, params=None):
        super().__init__(width, height, params)
        self.param_meta = PARAMS
        self.start_time = time.time()

    def render(self, lfo_signals=None):
        t = time.time() - self.start_time

        # 1) Read raw params
        size   = self.params["SIZE"]
        speed  = self.params["SPEED"]
        center = self.params["CENTER"]
        spread = self.params["SPREAD"]

        # 2) Apply modulation properly by extracting the scalar amt
        for key in ("SIZE","SPEED","CENTER","SPREAD"):
            meta = self.param_meta[key]
            if meta.get("modulatable") and meta.get("mod_active"):
                src = meta.get("mod_source")
                # grab the numeric value for this mod source (LFO or ENV)
                amt = (lfo_signals or {}).get(src, 0.0)
                # apply_modulation(base_value, meta_dict, amt) → float
                mod_val = apply_modulation(self.params[key], meta, amt)
                if   key == "SIZE":   size   = mod_val
                elif key == "SPEED":  speed  = mod_val
                elif key == "CENTER": center = mod_val
                elif key == "SPREAD": spread = mod_val

        # 3) Pick colormap
        cmap = COLORMAPS.get(self.params.get("COLORMAP","jet"), COLORMAPS["jet"])
        N    = len(cmap)

        # 4) Render plaid
        out = []
        for y in range(self.height):
            for x in range(self.width):
                u = (x/size + t*speed) % 1.0
                v = (y/size + t*speed) % 1.0
                wx = 0.5*(1 + math.sin(2*math.pi*u))
                wy = 0.5*(1 + math.sin(2*math.pi*v))
                intensity = (wx + wy)*0.5  # in [0..1]

                lo = center - spread/2
                hi = center + spread/2
                frac = lo + intensity*(hi - lo)
                frac = max(0.0, min(1.0, frac))
                idx = int(frac*(N-1))

                r,g,b = cmap[idx]
                out.append((r,g,b,0))
        return out
