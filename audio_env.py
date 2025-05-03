# audio_env.py
import numpy as np, math
import sounddevice as sd

# ─── CONFIG ────────────────────────────────────────────────────────────────
SAMPLERATE  = 44100
BLOCKSIZE   = 512

# envelope bands
LOW_BAND    = (50, 150)
HIGH_BAND   = (1000, 5000)


LOW_GAIN      = 0.025
HIGH_GAIN     = 1.0

# This is your “panel” config, loadable/savable with patches:
ENV_CONFIG = {
    "envl": {
        "threshold": 0.01,   # raw RMS below this → 0
        "gain":      1.0,    # after smoothing
        "attack":    0.005,  # seconds
        "release":   0.100,  # seconds
        "mode":      "up"    # "up", "down", or "updown"
    },
    "envh": {
        "threshold": 0.01,
        "gain":      1.0,
        "attack":    0.005,
        "release":   0.100,
        "mode":      "up"
    }
}

# ─── PRECOMPUTE FFT BINS ────────────────────────────────────────────────────
freqs     = np.fft.rfftfreq(BLOCKSIZE, d=1.0/SAMPLERATE)
low_bins  = np.where((freqs >= LOW_BAND[0]) & (freqs <= LOW_BAND[1]))[0]
high_bins = np.where((freqs >= HIGH_BAND[0]) & (freqs <= HIGH_BAND[1]))[0]

# ─── INTERNAL STATE ─────────────────────────────────────────────────────────
_raw_l        = 0.0
_raw_h        = 0.0
_sm_l         = 0.0
_sm_h         = 0.0
_prev_above_l = False
_prev_above_h = False
_state_l      = True   # for updown toggle
_state_h      = True

# ─── AUDIO CALLBACK ─────────────────────────────────────────────────────────
def _audio_cb(indata, frames, time, status):
    global _raw_l, _raw_h

    mono   = (indata[:,0] * np.hanning(frames))
    spec   = np.fft.rfft(mono)
    mag2   = np.abs(spec)**2

    # instantaneous raw RMS per band
    _raw_l = LOW_GAIN * math.sqrt(np.mean(mag2[low_bins]))
    _raw_h = HIGH_GAIN * math.sqrt(np.mean(mag2[high_bins]))

# start the stream once on import
_stream = sd.InputStream(
    channels=1,
    samplerate=SAMPLERATE,
    blocksize=BLOCKSIZE,
    callback=_audio_cb
)
_stream.start()

# ─── EVALUATE ENVELOPES ────────────────────────────────────────────────────
def evaluate_env():
    """
    Returns dict { 'envl':float, 'envh':float } of the CURRENT
    envelope outputs, after threshold, gain, smoothing, and mode.
    """
    global _raw_l, _raw_h, _sm_l, _sm_h
    global _prev_above_l, _prev_above_h, _state_l, _state_h

    out = {}
    for name, raw in (("envl", _raw_l), ("envh", _raw_h)):
        cfg    = ENV_CONFIG[name]
        thr    = cfg["threshold"]
        gain   = cfg["gain"]
        atk_tc = cfg["attack"]
        rel_tc = cfg["release"]
        mode   = cfg["mode"]

        # compute alphas
        dt     = BLOCKSIZE / SAMPLERATE
        alpha_a = math.exp(-dt/atk_tc)
        alpha_r = math.exp(-dt/rel_tc)

        # select the right state vars
        if name=="envl":
            sm         = _sm_l
            prev_above = _prev_above_l
            state      = _state_l
        else:
            sm         = _sm_h
            prev_above = _prev_above_h
            state      = _state_h

        # threshold
        val = max(0.0, raw - thr)

        # smoothing
        if val > sm:
            sm = (1-alpha_a)*val + alpha_a*sm
        else:
            sm = (1-alpha_r)*val + alpha_r*sm

        # mode
        above = (val > 0.0)
        if mode == "up":
            sig = sm
        elif mode == "down":
            sig = -sm
        else:  # updown: toggle on each new crossing
            if above and not prev_above:
                state = not state
            sig = sm if state else -sm

        # apply gain
        sig *= gain

        # store back
        if name=="envl":
            _sm_l, _prev_above_l, _state_l = sm, above, state
        else:
            _sm_h, _prev_above_h, _state_h = sm, above, state

        out[name] = sig

    return out
