class Pattern:
    def __init__(self, width, height, params=None):
        self.width = width
        self.height = height
        self.params = {k: v["default"] if isinstance(v, dict) else v for k, v in (params or {}).items()}

    def update_params(self, params):
        self.params.update(params)

    def render(self, lfo_signals=None):
        return [(0, 0, 0, 0)] * (self.width * self.height)

def apply_modulation(base, meta, signals):
    source = meta.get("mod_source")
    if not source or source not in signals:
        return base
    value = signals[source]

    mode = meta.get("mod_mode", "add")
    min_val = meta.get("min", 0.0)
    max_val = meta.get("max", 1.0)
    range_span = max_val - min_val

    if mode == "add":
        mod_val = base + value * 0.5 * range_span
    elif mode == "scale":
        mod_val = base * (1 + value)
    elif mode == "replace":
        mod_val = min_val + (value + 1) * 0.5 * range_span
    else:
        mod_val = base

    return max(min_val, min(mod_val, max_val))