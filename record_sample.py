"""Record a reference voice sample for voice cloning.

Run this in the MAIN environment (it has PyAudio):
    .venv\\Scripts\\python.exe record_sample.py

It records ~25 seconds of you reading a short paragraph and saves it to
voice_clone/reference.wav — the clip XTTS uses to clone your voice. Speak clearly in a quiet
room, at your normal pace and tone. Longer, cleaner samples clone better.
"""

from __future__ import annotations

import os
import time
import wave

import pyaudio

RATE = 22050
CHANNELS = 1
CHUNK = 1024
FORMAT = pyaudio.paInt16
SECONDS = 25
OUT_PATH = os.path.join("voice_clone", "reference.wav")

PROMPT = """Please read this aloud, naturally:

  "Hello, my name is Ayush. This is a recording of my voice so my assistant can learn how I
   speak. I enjoy building software, solving problems, and exploring new ideas. The weather
   today is pleasant, and I'm looking forward to getting a lot of work done. Thank you."
"""


def main() -> None:
    os.makedirs("voice_clone", exist_ok=True)
    print(PROMPT)
    input("Press ENTER when you're ready, then start reading...")

    pa = pyaudio.PyAudio()
    stream = pa.open(
        format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK
    )

    print(f"\n🔴 Recording for {SECONDS} seconds... speak now!\n")
    frames = []
    total_chunks = int(RATE / CHUNK * SECONDS)
    for i in range(total_chunks):
        frames.append(stream.read(CHUNK, exception_on_overflow=False))
        if i % int(RATE / CHUNK) == 0:  # roughly once per second
            remaining = SECONDS - i // int(RATE / CHUNK)
            print(f"  ...{remaining}s left", end="\r", flush=True)

    stream.stop_stream()
    stream.close()
    pa.terminate()

    with wave.open(OUT_PATH, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(pa.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b"".join(frames))

    print(f"\n\n✅ Saved your voice sample to {OUT_PATH}")
    print("You can now start JARVIS with the cloned voice.")
    time.sleep(0.2)


if __name__ == "__main__":
    main()
