import sounddevice as sd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import math
import os

# ─── CONFIGURATION ─────────────────────────────────────────────────────────
SAMPLERATE    = 44100    # Hz
BLOCKSIZE     = 1024     # samples per block
BUFFER_SIZE   = 200      # number of points to display

LOW_CUTOFF    = 100.0    # Hz
HIGH_CUTOFF   = 1000.0   # Hz

ATTACK_TC     = 0.010    # 10 ms attack
RELEASE_TC    = 0.100    # 100 ms release
LOW_GAIN      = 0.025      # linear gain before dB
HIGH_GAIN     = 1.0

AGC_TARGET    = 0.05     # desired long-term RMS level
AGC_TC        = 5.0      # 5 s time constant

THRESHOLD_DB  = -10      # dBFS threshold for peak highlighting

EPS           = 1e-12    # to avoid log(0)

# ─── PRECOMPUTE FREQUENCY BINS ──────────────────────────────────────────────
freqs     = np.fft.rfftfreq(BLOCKSIZE, d=1.0/SAMPLERATE)
low_bins  = np.where(freqs <= LOW_CUTOFF)[0]
high_bins = np.where(freqs >= HIGH_CUTOFF)[0]

# ─── STATE BUFFERS ──────────────────────────────────────────────────────────
env_low     = np.zeros(BUFFER_SIZE) + EPS
env_high    = np.zeros(BUFFER_SIZE) + EPS
env_gain    = np.zeros(BUFFER_SIZE) + 1.0   # track AGC gain
sm_low      = 0.0
sm_high     = 0.0
agc_level   = EPS

# compute smoothing coefficients per block
dt         = BLOCKSIZE / SAMPLERATE
alpha_a    = math.exp(-dt / ATTACK_TC)
alpha_r    = math.exp(-dt / RELEASE_TC)
alpha_agc  = math.exp(-dt / AGC_TC)

def audio_callback(indata, frames, time, status):
    global env_low, env_high, env_gain, sm_low, sm_high, agc_level

    # 1) compute raw total RMS for AGC
    mono       = indata[:, 0]
    raw_total  = math.sqrt(np.mean(mono**2)) + EPS

    # 2) update long-term AGC level & compute gain
    agc_level  = alpha_agc * agc_level + (1 - alpha_agc) * raw_total
    gain       = AGC_TARGET / (agc_level + EPS)
    gain       = min(max(gain, 0.1), 10.0)

    # 3) FFT envelope detection
    windowed   = mono * np.hanning(frames)
    spectrum   = np.fft.rfft(windowed)
    mag2       = np.abs(spectrum) ** 2

    raw_low    = math.sqrt(np.mean(mag2[low_bins])) * gain
    raw_high   = math.sqrt(np.mean(mag2[high_bins])) * gain

    # 4) attack/release smoothing
    if raw_low > sm_low:
        sm_low = (1 - alpha_a) * raw_low + alpha_a * sm_low
    else:
        sm_low = (1 - alpha_r) * raw_low + alpha_r * sm_low
    out_low = sm_low * LOW_GAIN + EPS

    if raw_high > sm_high:
        sm_high = (1 - alpha_a) * raw_high + alpha_a * sm_high
    else:
        sm_high = (1 - alpha_r) * raw_high + alpha_r * sm_high
    out_high = sm_high * HIGH_GAIN + EPS

    # 5) update circular buffers
    env_low   = np.roll(env_low,  -1); env_low[-1]   = out_low
    env_high  = np.roll(env_high, -1); env_high[-1]  = out_high
    env_gain  = np.roll(env_gain, -1); env_gain[-1]  = gain

def main():
    # prepare plot
    fig, ax = plt.subplots()
    x = np.arange(BUFFER_SIZE)

    # initial dB data
    db_low_init   = 20 * np.log10(env_low)
    db_high_init  = 20 * np.log10(env_high)
    db_gain_init  = 20 * np.log10(env_gain + EPS)

    line_low,   = ax.plot(x, db_low_init,  color="tab:blue", label="Low <300 Hz")
    line_high,  = ax.plot(x, db_high_init, color="tab:red",  label="High >1 kHz")
    line_gain,  = ax.plot(x, db_gain_init, color="tab:green", label="AGC Gain (dB)")

    # threshold and peaks
    ax.axhline(THRESHOLD_DB, color="yellow", linestyle="--", label=f"Thresh {THRESHOLD_DB} dB")
    scatter_low  = ax.scatter([], [], s=20, color="yellow", label="_")
    scatter_high = ax.scatter([], [], s=20, color="orange", label="_")

    ax.set_xlim(0, BUFFER_SIZE-1)
    ax.set_ylim(-40, 20)  # extend to +20 dB for gain
    ax.set_title("Smoothed Mic Envelope (dBFS) + AGC Gain")
    ax.set_xlabel("Frame Index")
    ax.set_ylabel("Level (dBFS)")
    ax.legend(loc="upper right")
    ax.grid(True, which="both", ls=":", linewidth=0.5)

    def update(frame):
        db_low   = 20 * np.log10(env_low)
        db_high  = 20 * np.log10(env_high)
        db_gain  = 20 * np.log10(env_gain + EPS)

        line_low.set_ydata(db_low)
        line_high.set_ydata(db_high)
        line_gain.set_ydata(db_gain)

        # peak markers
        mask_l = db_low  > THRESHOLD_DB
        mask_h = db_high > THRESHOLD_DB
        scatter_low.set_offsets(np.column_stack((x[mask_l],  db_low[mask_l])))
        scatter_high.set_offsets(np.column_stack((x[mask_h], db_high[mask_h])))

        return line_low, line_high, line_gain, scatter_low, scatter_high

    ani = FuncAnimation(fig, update, interval=30, blit=True)

    # start audio
    with sd.InputStream(
        channels=1,
        samplerate=SAMPLERATE,
        blocksize=BLOCKSIZE,
        callback=audio_callback
    ):
        plt.show()

if __name__ == "__main__":
    main()
