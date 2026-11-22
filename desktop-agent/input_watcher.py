"""
AURA Desktop Agent — Privacy-Guarded Typing Cadence & Ephemeral Context Watcher
Tracks typing speed, idle time, and a short-lived in-memory context snippet.
Never written to disk; immediately wiped on Blind Mode or sensitive apps.
"""
from __future__ import annotations

import collections
import logging
import threading
import time
from typing import Callable, Deque, Optional

from config import runtime

logger = logging.getLogger("aura.input")


class InputWatcher:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._key_times: Deque[float] = collections.deque(maxlen=120)
        self._buffer: str = ""
        self._last_key_at: float = 0.0
        self._last_mention_at: float = 0.0
        self._listener = None
        self._on_name_mentioned: Optional[Callable[[], None]] = None

    def set_name_mention_callback(self, cb: Callable[[], None]) -> None:
        self._on_name_mentioned = cb

    def start(self) -> None:
        if self._listener is not None:
            return
        try:
            from pynput import keyboard

            self._listener = keyboard.Listener(on_press=self._on_press)
            self._listener.daemon = True
            self._listener.start()
            logger.info("Typing watcher started (privacy-guarded, memory-only).")
        except Exception as e:
            logger.warning(f"Typing watcher unavailable: {e}")

    def stop(self) -> None:
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None
        self.clear()

    def clear(self) -> None:
        with self._lock:
            self._buffer = ""

    def _on_press(self, key) -> None:
        if runtime.blind_mode or not runtime.typing_watcher_enabled or runtime.privacy_paused:
            self.clear()
            return

        now = time.time()
        trigger_mention = False
        with self._lock:
            self._key_times.append(now)
            self._last_key_at = now

            try:
                ch = getattr(key, "char", None)
                if ch and ch.isprintable():
                    self._buffer = (self._buffer + ch)[-220:]
                else:
                    kname = str(key)
                    if "space" in kname:
                        self._buffer = (self._buffer + " ")[-220:]
                    elif "backspace" in kname:
                        self._buffer = self._buffer[:-1]
                    elif "enter" in kname:
                        self._buffer = (self._buffer + " | ")[-220:]
            except Exception:
                pass

            tail = self._buffer[-30:].lower()
            if "hey aura" in tail and (now - self._last_mention_at > 45.0):
                self._last_mention_at = now
                trigger_mention = True

        if trigger_mention and self._on_name_mentioned:
            try:
                self._on_name_mentioned()
            except Exception:
                pass

    def get_summary(self) -> dict:
        if runtime.blind_mode or not runtime.typing_watcher_enabled or runtime.privacy_paused:
            self.clear()
            return {"active": False, "wpm": 0, "idle_sec": 999, "recent_text": ""}

        now = time.time()
        with self._lock:
            idle_sec = round(now - self._last_key_at, 1) if self._last_key_at > 0 else 999.0
            if idle_sec > 90.0:
                self._buffer = ""
            recent_keys = [t for t in self._key_times if now - t <= 15.0]
            wpm = int(round((len(recent_keys) / 5.0) * 4.0))
            snippet = self._buffer.strip()[-160:]
        return {
            "active": idle_sec < 20.0,
            "wpm": wpm,
            "idle_sec": idle_sec,
            "recent_text": snippet,
        }


input_watcher = InputWatcher()
