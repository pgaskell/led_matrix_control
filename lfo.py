import math
import time

# Global BPM (can be changed externally)
BPM = 120.0

# Time-tracking start (used for phase calc)
start_time = time.time()

# LFO config: two LFOs, identified as "lfo1" and "lfo2"
LFO_CONFIG = {
    "lfo1": {
        "waveform": "sine",
        "depth": 1.0,
        "sync_mode": "quantized",  # "free" or "quantized"
        "hz": 0.5,
        "period_beats": 1.0,  # Only used if quantized
        "phase": 0.0
    },
    "lfo2": {
        "waveform": "triangle",
        "depth": 1.0,
        "sync_mode": "free",
        "hz": 0.2,
        "period_beats": 2.0,
        "phase": 0.0
    }
}


def _get_time():
    return time.time() - start_time


def _waveform(phase, shape):
    """Given phase ∈ [0, 1), return waveform value ∈ [-1, 1]"""
    if shape == "sine":
        return math.sin(2 * math.pi * phase)
    elif shape == "square":
        return 1.0 if phase < 0.5 else -1.0
    elif shape == "triangle":
        return 4.0 * abs(phase - 0.5) - 1.0
    elif shape == "saw":
        return 2.0 * (phase - 0.5)
    else:
        return 0.0  # fallback


def evaluate_lfos():
    """Returns dict: { 'lfo1': value, 'lfo2': value }"""
    now = _get_time()
    lfo_signals = {}

    for key, config in LFO_CONFIG.items():
        depth = config.get("depth", 1.0)
        shape = config.get("waveform", "sine")
        phase_offset = config.get("phase", 0.0)

        # Determine phase
        if config.get("sync_mode") == "quantized":
            beats_per_sec = BPM / 60.0
            bars         = config.get("period_beats", 1.0)
            period_beats = bars * 4
            period       = period_beats / beats_per_sec
        else:
            period = 1.0 / max(config.get("hz", 0.1), 0.001)

        phase = ((now + phase_offset) % period) / period
        raw_value = _waveform(phase, shape)
        modulated = (raw_value * 0.5 + 0.5) * depth
        modulated = max(-depth, min(raw_value * depth, depth))
        lfo_signals[key] = modulated

    return lfo_signals
