"""
AURA Desktop Agent — Live Screen & Active Window Watcher
Captures lightweight screen frames via mss, detects active window/process & games,
re-asserts Win32 HWND_TOPMOST cleanly, and auto-pauses on sensitive apps.
"""
from __future__ import annotations

import base64
import io
import logging
import os
import threading
import time
from dataclasses import dataclass
from typing import Optional, Tuple

import mss
import numpy as np
import psutil
from PIL import Image

from config import KNOWN_GAMES, runtime

logger = logging.getLogger("aura.vision")


def get_active_window_info() -> Tuple[str, str, str]:
    """Return (window_title, process_name, exe_path) on Windows."""
    if os.name != "nt":
        return ("", "", "")
    try:
        import win32gui
        import win32process

        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return ("", "", "")
        title = win32gui.GetWindowText(hwnd) or ""
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        proc_name = ""
        exe_path = ""
        if pid and pid > 0:
            try:
                p = psutil.Process(pid)
                proc_name = p.name()
                exe_path = p.exe()
            except Exception:
                proc_name = ""
        return (title.strip(), proc_name.strip(), exe_path.strip())
    except Exception:
        return ("", "", "")


def keep_overlay_topmost() -> None:
    """Re-assert native Win32 HWND_TOPMOST on AURA's Electron overlay without stealing focus."""
    if os.name != "nt":
        return
    try:
        import win32con
        import win32gui
        import win32process

        def _enum_cb(hwnd, _):
            if not win32gui.IsWindowVisible(hwnd):
                return
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            try:
                pname = psutil.Process(pid).name().lower()
            except Exception:
                return
            if pname != "electron.exe":
                return
            ex = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            if ex & win32con.WS_EX_LAYERED:
                win32gui.SetWindowPos(
                    hwnd,
                    win32con.HWND_TOPMOST,
                    0,
                    0,
                    0,
                    0,
                    win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE,
                )

        win32gui.EnumWindows(_enum_cb, None)
    except Exception:
        pass


def check_sensitive_window(title: str, process: str) -> Optional[str]:
    haystack = f"{title} {process}".lower()
    for kw in runtime.sensitive_keywords:
        if kw and kw.lower() in haystack:
            return kw
    return None


@dataclass
class ScreenSnapshot:
    jpeg_b64: str
    captured_at: float
    window_title: str
    process_name: str
    detected_game: str
    change_score: float


class VisionWatcher:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last_thumb: Optional[np.ndarray] = None
        self._last_snapshot: Optional[ScreenSnapshot] = None

    def poll_window_only(self) -> Tuple[str, str, str, bool]:
        title, proc, exe_path = get_active_window_info()

        low_title = title.lower()
        low_proc = proc.lower()
        is_self_window = (
            "aura desktop" in low_title
            or "aura backend" in low_title
            or (low_proc == "electron.exe" and ("aura" in low_title or not title))
        )
        if is_self_window:
            return (
                runtime.active_window,
                runtime.active_process,
                runtime.detected_game,
                runtime.privacy_paused,
            )

        game = KNOWN_GAMES.get(low_proc, "")
        if not game and exe_path:
            low_exe = exe_path.lower()
            if (
                "\\steamapps\\common\\" in low_exe
                or "\\epic games\\" in low_exe
                or "\\riot games\\" in low_exe
            ) and "wallpaper_engine" not in low_exe:
                game = title or proc.replace(".exe", "")

        sensitive_hit = check_sensitive_window(title, proc)
        runtime.active_window = title
        runtime.active_process = proc
        runtime.detected_game = game
        if sensitive_hit:
            runtime.privacy_paused = True
            runtime.privacy_reason = f"Auto-paused ({sensitive_hit})"
        else:
            runtime.privacy_paused = False
            runtime.privacy_reason = ""

        return title, proc, game, bool(sensitive_hit)

    def capture_now(
        self, force: bool = False, max_width: int = 1280, quality: int = 78
    ) -> Optional[ScreenSnapshot]:
        title, proc, game, is_sensitive = self.poll_window_only()

        if runtime.blind_mode or not runtime.vision_enabled or is_sensitive:
            return None

        try:
            with mss.mss() as sct:
                monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
                raw = sct.grab(monitor)
                img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
        except Exception as e:
            logger.debug(f"Screen capture failed: {e}")
            return None

        thumb = np.asarray(img.convert("L").resize((24, 24)), dtype=np.float32) / 255.0
        with self._lock:
            change_score = (
                float(np.mean(np.abs(thumb - self._last_thumb)))
                if self._last_thumb is not None
                else 1.0
            )
            self._last_thumb = thumb

        w, h = img.size
        if w > max_width:
            new_h = max(1, int(h * (max_width / w)))
            img = img.resize((max_width, new_h), Image.Resampling.BILINEAR)

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")

        snap = ScreenSnapshot(
            jpeg_b64=b64,
            captured_at=time.time(),
            window_title=title,
            process_name=proc,
            detected_game=game,
            change_score=change_score,
        )
        with self._lock:
            self._last_snapshot = snap
        return snap

    def get_latest_snapshot(self, max_age_sec: float = 15.0) -> Optional[ScreenSnapshot]:
        if runtime.blind_mode or not runtime.vision_enabled or runtime.privacy_paused:
            return None
        with self._lock:
            snap = self._last_snapshot
        if snap and (time.time() - snap.captured_at) <= max_age_sec:
            return snap
        return self.capture_now(force=True)

    def get_preview_data_url(self) -> Optional[str]:
        snap = self.get_latest_snapshot(max_age_sec=10.0)
        if not snap:
            return None
        return f"data:image/jpeg;base64,{snap.jpeg_b64}"


vision_watcher = VisionWatcher()
