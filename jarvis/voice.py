"""Voice I/O: speech-to-text (microphone) and natural neural text-to-speech.

Speech output uses Microsoft Edge neural voices via `edge-tts` (very human-sounding, free,
needs internet) played through pygame. If that's unavailable (offline / error), it falls back
to the offline SAPI voice so JARVIS always has a voice.

Listening is tuned for real conversation: it calibrates to room noise, keeps adapting, waits
for natural pauses, and ignores silence/background disturbances instead of misfiring.

These imports are optional — only needed with --voice — so they're imported lazily.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import threading
import time

# Keep pygame quiet on import (no "Hello from the pygame community" banner).
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

DEFAULT_VOICE = "en-IN-PrabhatNeural"


class Voice:
    def __init__(
        self,
        tts_voice: str = DEFAULT_VOICE,
        tts_rate: str = "+18%",
        engine: str = "edge",
        clone_url: str = "http://127.0.0.1:5111",
        barge_in: bool = True,
    ) -> None:
        import speech_recognition as sr

        self._sr = sr
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        self.tts_voice = tts_voice or DEFAULT_VOICE
        # edge-tts rate, e.g. "+18%" (faster) or "-10%" (slower).
        self.tts_rate = tts_rate or "+0%"
        # "clone" routes speech to the local XTTS server (your voice); else edge neural voice.
        self.engine = engine
        self.clone_url = clone_url.rstrip("/")
        # Listen for the owner talking over JARVIS (needs headphones to avoid hearing itself).
        self.barge_in = barge_in

        # --- Listening: silence / noise tuning -------------------------------------
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = 0.9       # silence that means "done talking"
        self.recognizer.non_speaking_duration = 0.4
        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=1.0)
        self.recognizer.energy_threshold = max(self.recognizer.energy_threshold, 300)

        # --- Speaking: pygame plays audio; edge-tts/clone produce it; pyttsx3 is offline ---
        self._pygame = self._init_pygame()
        self._edge_tts = self._init_edge()
        self._engine = None  # lazy offline engine

    # ------------------------------------------------------------------ engines ---
    def _init_pygame(self):
        try:
            import pygame

            pygame.mixer.init()
            return pygame
        except Exception:  # noqa: BLE001
            return None

    def _init_edge(self):
        try:
            import edge_tts

            return edge_tts
        except Exception:  # noqa: BLE001
            return None

    def _offline_engine(self):
        if self._engine is None:
            import pyttsx3

            self._engine = pyttsx3.init()
            self._engine.setProperty("rate", 210)
        return self._engine

    # ------------------------------------------------------------------ listening ---
    def listen(self) -> str:
        """Capture one spoken utterance and transcribe it.

        Returns '' when nothing intelligible was heard (silence, timeout, or noise), so the
        caller can simply keep listening without error spam.
        """
        with self.microphone as source:
            try:
                audio = self.recognizer.listen(source, timeout=8, phrase_time_limit=15)
            except self._sr.WaitTimeoutError:
                return ""
        try:
            return self.recognizer.recognize_google(audio).strip()
        except self._sr.UnknownValueError:
            return ""
        except self._sr.RequestError as exc:
            return f"[speech recognition unavailable: {exc}]"

    # ------------------------------------------------------------------- speaking ---
    def speak(self, text: str, interrupt: bool = False):
        """Speak text aloud (blocking). Returns None normally, or your next command (string)
        if you interrupted it.

        When interrupt=True you can cut JARVIS off:
          - Press any key (always works), then just say your new request.
          - Or say something like "stop" / "wait" / "jarvis" (needs barge-in on; best with
            headphones so it doesn't hear its own voice — an echo filter helps either way).
        Falls back clone -> edge -> offline so there's always a voice.
        """
        if not text or not text.strip():
            return None

        path = self._make_audio(text)
        if path is None:
            time.sleep(0.3)
            return None  # spoken via offline engine (can't be interrupted)
        try:
            if interrupt and self._pygame is not None:
                command = self._play_interruptible(path, text)
                time.sleep(0.2)
                return command
            self._play_file(path)
        finally:
            try:
                os.remove(path)
            except OSError:
                pass
        time.sleep(0.3)
        return None

    @staticmethod
    def _looks_like_echo(heard: str, spoken: str) -> bool:
        """True if `heard` is probably JARVIS hearing its own voice, not the owner."""
        h, s = heard.lower().strip(), spoken.lower()
        if not h:
            return True
        if h in s:
            return True
        htoks = set(h.split())
        return bool(htoks) and len(htoks & set(s.split())) / len(htoks) >= 0.6

    @staticmethod
    def _key_pressed() -> bool:
        """True if a key is waiting; drains the keyboard buffer. Windows only."""
        try:
            import msvcrt
        except ImportError:
            return False
        if not msvcrt.kbhit():
            return False
        while msvcrt.kbhit():
            msvcrt.getch()
        return True

    def _heard_interrupt(self, source, spoken_text: str):
        """Listen briefly during playback; return the owner's words if they spoke (not echo)."""
        try:
            audio = self.recognizer.listen(source, timeout=0.3, phrase_time_limit=6)
        except self._sr.WaitTimeoutError:
            return None
        try:
            heard = self.recognizer.recognize_google(audio).strip()
        except Exception:  # noqa: BLE001
            return None
        if heard and not self._looks_like_echo(heard, spoken_text):
            return heard
        return None

    def _play_interruptible(self, path: str, spoken_text: str):
        """Play audio while watching for an interrupt (keypress or the owner talking).

        Returns the owner's next command (string) if interrupted, else None.
        """
        mixer = self._pygame.mixer
        mixer.music.load(path)
        mixer.music.play()

        old_threshold = self.recognizer.energy_threshold
        old_dynamic = self.recognizer.dynamic_energy_threshold
        source = None
        result = None
        try:
            if self.barge_in:
                self.recognizer.dynamic_energy_threshold = False
                self.recognizer.energy_threshold = old_threshold * 2.2
                source = self.microphone.__enter__()

            while mixer.music.get_busy():
                if self._key_pressed():
                    mixer.music.stop()
                    result = self.listen()  # capture what they want to say
                    break
                if source is not None:
                    result = self._heard_interrupt(source, spoken_text)
                    if result:
                        mixer.music.stop()
                        break
                else:
                    self._pygame.time.Clock().tick(15)
        finally:
            if source is not None:
                self.microphone.__exit__(None, None, None)
                self.recognizer.energy_threshold = old_threshold
                self.recognizer.dynamic_energy_threshold = old_dynamic
            mixer.music.unload()
        return result or None

    def _make_audio(self, text: str):
        """Produce an audio file for `text`. Returns its path, or None if it fell back to the
        offline engine (which speaks immediately and isn't a file we can replay)."""
        order = ["clone", "edge"] if self.engine == "clone" else ["edge"]
        for eng in order:
            try:
                path = self._gen_clone(text) if eng == "clone" else self._gen_edge(text)
                if path:
                    return path
            except Exception:  # noqa: BLE001 — try the next engine
                continue
        self._speak_offline(text)
        return None

    def _gen_clone(self, text: str):
        import requests

        resp = requests.post(f"{self.clone_url}/tts", json={"text": text}, timeout=120)
        resp.raise_for_status()
        fd, path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        with open(path, "wb") as f:
            f.write(resp.content)
        return path

    def _gen_edge(self, text: str):
        if self._edge_tts is None:
            return None
        fd, path = tempfile.mkstemp(suffix=".mp3")
        os.close(fd)

        # Run in a dedicated thread with its own event loop so we never collide with any other
        # async state in the process (e.g. left over from browser automation).
        err: list = []

        def _worker() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                comm = self._edge_tts.Communicate(text, self.tts_voice, rate=self.tts_rate)
                loop.run_until_complete(comm.save(path))
            except Exception as exc:  # noqa: BLE001
                err.append(exc)
            finally:
                loop.close()

        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        t.join()
        if err:
            raise err[0]
        return path

    def _play_file(self, path: str) -> bool:
        """Play an audio file (mp3/wav) through pygame, blocking until done."""
        if self._pygame is None:
            return False
        mixer = self._pygame.mixer
        mixer.music.load(path)
        mixer.music.play()
        while mixer.music.get_busy():
            self._pygame.time.Clock().tick(15)
        mixer.music.unload()  # release the file so Windows lets us delete it
        return True

    def _speak_offline(self, text: str) -> bool:
        try:
            engine = self._offline_engine()
            engine.say(text)
            engine.runAndWait()
            return True
        except Exception:  # noqa: BLE001 — never let speech crash the assistant
            return False
