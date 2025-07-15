# audio_env.py
import numpy as np, math
import sounddevice as sd
import numpy as np
from collections import deque

# ─── CONFIG ────────────────────────────────────────────────────────────────
SAMPLERATE  = 44100
BLOCKSIZE   = 1024

# envelope bands
LOW_BAND    = (50, 150)
HIGH_BAND   = (1000, 5000)
N_BANDS     = 24

LOW_GAIN      = 0.1
HIGH_GAIN     = 1.0

# This is your “panel” config, loadable/savable with patches:
ENV_CONFIG = {
    "envl": {
        "threshold_db": -10,   # raw RMS below this → 0
        "gain_db":      0,    # after smoothing
        "attack":    0.005,  # seconds
        "release":   0.100,  # seconds
        "mode":      "up"    # "up", "down", or "updown"
    },
    "envh": {
        "threshold_db": -10,
        "gain_db":      0,
        "attack":    0.005,
        "release":   0.100,
        "mode":      "up"
    }
}

# ─── PRECOMPUTE FFT BINS ────────────────────────────────────────────────────
freqs     = np.fft.rfftfreq(BLOCKSIZE, d=1.0/SAMPLERATE)
low_bins  = np.where((freqs >= LOW_BAND[0]) & (freqs <= LOW_BAND[1]))[0]
high_bins = np.where((freqs >= HIGH_BAND[0]) & (freqs <= HIGH_BAND[1]))[0]
# audible range: 20 Hz … Nyquist
fmin, fmax = 20.0, SAMPLERATE/2
# create 25 log-spaced edges
edges = np.logspace(np.log10(fmin), np.log10(fmax), N_BANDS+1)
band_bins = [
    np.where((freqs >= edges[i]) & (freqs < edges[i+1]))[0]
    for i in range(N_BANDS)
]

# ─── INTERNAL STATE ─────────────────────────────────────────────────────────
_raw_l        = 0.0
_raw_h        = 0.0
_sm_l         = 0.0
_sm_h         = 0.0
_prev_above_l = False
_prev_above_h = False
_state_l      = True   # for updown toggle
_state_h      = True
_raw_bands = [0.0]*N_BANDS

# ─── AUDIO CALLBACK ─────────────────────────────────────────────────────────

def _audio_cb(indata, frames, time, status):
    """Read `frames` samples into the FFT buffer, then compute 2-band RMS plus N-band RMS."""
    global _raw_l, _raw_h, _raw_bands, _fft_buffer

    # 0) Push the raw samples into our rolling buffer for the FFT bands
    samples = indata[:,0]  # mono
    _fft_buffer.extend(samples)

    # 1) window & FFT (this is still used for raw_l/raw_h)
    mono = samples * np.hanning(frames)
    spec = np.fft.rfft(mono, n=FFT_SIZE)
    mag2 = np.abs(spec)**2

    # 2) legacy low/high bands
    _raw_l = LOW_GAIN * math.sqrt(np.mean(mag2[low_bins])) if low_bins.size else 0.0
    _raw_h = HIGH_GAIN * math.sqrt(np.mean(mag2[high_bins])) if high_bins.size else 0.0

    # 3) multi-band RMS for VU-meter or other patterns
    for idx, bins in enumerate(band_bins):
        if bins.size:
            _raw_bands[idx] = math.sqrt(np.mean(mag2[bins]))
        else:
            _raw_bands[idx] = 0.0

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
        thr_db    = cfg["threshold_db"]
        gain_db   = cfg["gain_db"]
        atk_tc = cfg["attack"]
        rel_tc = cfg["release"]
        mode   = cfg["mode"]

        # compute alphas
        dt     = BLOCKSIZE / SAMPLERATE
        alpha_a = math.exp(-dt/atk_tc)
        alpha_r = math.exp(-dt/rel_tc)

        thr_lin  = 10 ** (thr_db  / 20.0)
        gain_lin = 10 ** (gain_db / 20.0)
        # print(
        #     f"{name}: threshold {thr_db:+.1f} dB → {thr_lin:.4f} lin, "
        #     f"gain {gain_db:+.1f} dB → {gain_lin:.4f} lin"
        # )


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
        val = max(0.0, raw - thr_lin)

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
        sig *= gain_lin

        # store back
        if name=="envl":
            _sm_l, _prev_above_l, _state_l = sm, above, state
        else:
            _sm_h, _prev_above_h, _state_h = sm, above, state

        out[name] = sig

    return out


# choose your FFT size and sample rate
FFT_SIZE   = 2048

# rolling input buffer (mono)
_fft_buffer = deque(maxlen=FFT_SIZE)




import math
import numpy as np

def evaluate_fft_bands(n_bands=24):
    """
    Returns a list of length `n_bands`, each ∈ [0.0 .. 1.0], by:
      • grabbing FFT_SIZE samples from _fft_buffer
      • windowing + rfft → magnitude spectrum
      • splitting into log-spaced bands 0 Hz … Nyquist
      • converting to dB (floor at –30 dB Power) and normalizing
      • falling back to the nearest bin if a band has no FFT bins
    """
    # 1) pull & pad the rolling buffer
    data = np.array(_fft_buffer, dtype=float)
    if data.size < FFT_SIZE:
        data = np.pad(data, (FFT_SIZE - data.size, 0), 'constant')

    # 2) window + FFT → magnitude spectrum (0…1)
    window = np.hanning(FFT_SIZE)
    spec   = np.abs(np.fft.rfft(data * window))
    spec  /= (spec.max() + 1e-12)

    # 3) build a log-spaced edge array of length n_bands+1
    freqs  = np.fft.rfftfreq(FFT_SIZE, 1.0 / SAMPLERATE)
    fmax   = SAMPLERATE / 2.0
    # smallest non-zero FFT bin
    fmin_nz = freqs[1] if freqs.size>1 else 0.0

    # first edge at 0, last at Nyquist
    # middle edges log‐spaced between fmin_nz and fmax
    log_edges = np.logspace(math.log10(fmin_nz), math.log10(fmax), n_bands-1)
    edges     = np.concatenate(([0.0], log_edges, [fmax]))  # shape (n_bands+1,)

    out = []
    db_floor = -30.0

    for i in range(n_bands):
        low_e, high_e = edges[i], edges[i+1]
        mask = (freqs >= low_e) & (freqs < high_e)

        if mask.any():
            m = float(spec[mask].mean())
        else:
            # fallback: pick nearest single FFT bin to the band-center
            center_f = (low_e + high_e) / 2.0
            idx = int(np.argmin(np.abs(freqs - center_f)))
            m = float(spec[idx])

        # 4) convert to dB Power and normalize
        m_db   = 10.0 * math.log10(m + 1e-12)
        m_db   = max(db_floor, m_db)
        m_norm = (m_db - db_floor) / (-db_floor)
        out.append(m_norm)

    return out