import sounddevice as sd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

# Configuration
SAMPLERATE = 44100  # Hz
BLOCKSIZE = 256    # samples per audio block
BUFFER_SIZE = 200   # number of envelope points to display

# Shared buffer for envelope values
envelope_buffer = np.zeros(BUFFER_SIZE)

def audio_callback(indata, frames, time, status):
    """
    This callback is called for each audio block.
    We compute the RMS (root-mean-square) amplitude as the envelope value.
    """
    global envelope_buffer
    # Mono: take the first channel
    data = indata[:, 0]
    rms = np.sqrt(np.mean(data**2))
    # Shift buffer left and append new value
    envelope_buffer = np.roll(envelope_buffer, -1)
    envelope_buffer[-1] = rms

def main():
    # Set up matplotlib figure and line
    fig, ax = plt.subplots()
    x = np.arange(BUFFER_SIZE)
    line, = ax.plot(x, envelope_buffer, lw=2)
    ax.set_ylim(0, 0.5)            # Adjust max based on mic sensitivity
    ax.set_xlim(0, BUFFER_SIZE-1)
    ax.set_title("Microphone Envelope (RMS)")
    ax.set_xlabel("Time (frames)")
    ax.set_ylabel("Amplitude")

    # Animation update function
    def update(frame):
        line.set_ydata(envelope_buffer)
        return line,

    ani = FuncAnimation(fig, update, interval=30, blit=True)

    # Open the audio stream
    with sd.InputStream(channels=1,
                        samplerate=SAMPLERATE,
                        blocksize=BLOCKSIZE,
                        callback=audio_callback):
        plt.show()

if __name__ == "__main__":
    main()
