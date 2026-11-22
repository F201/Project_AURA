"""
AURA Desktop Agent — Proactive Companion Loop
Handles due voice reminders, one-time new-game reactions, typing mentions,
late-night check-ins, and Win32 overlay z-order maintenance.
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from typing import Awaitable, Callable

from config import runtime, settings
from input_watcher import input_watcher
from memory_store import memory_store
from vision_watcher import keep_overlay_topmost, vision_watcher

logger = logging.getLogger("aura.proactive")


class ProactiveLoop:
    def __init__(self) -> None:
        self._running = False
        self._task: asyncio.Task | None = None
        self._last_proactive_at: float = time.time()
        self._last_user_interaction_at: float = time.time()
        self._greeted_games: set[str] = set()
        self._late_night_warned_date: str = ""
        self._trigger_cb: Callable[[str, str, bool], Awaitable[None]] | None = None
        self._broadcast_state_cb: Callable[[], Awaitable[None]] | None = None

    def mark_user_interaction(self) -> None:
        self._last_user_interaction_at = time.time()

    def start(
        self,
        trigger_cb: Callable[[str, str, bool], Awaitable[None]],
        broadcast_state_cb: Callable[[], Awaitable[None]],
    ) -> None:
        if self._running:
            return
        self._trigger_cb = trigger_cb
        self._broadcast_state_cb = broadcast_state_cb
        self._running = True
        self._task = asyncio.create_task(self._loop())

        loop = asyncio.get_running_loop()

        def _on_mention() -> None:
            if not runtime.proactive_enabled or runtime.blind_mode or runtime.privacy_paused:
                return
            if runtime.is_speaking or runtime.is_thinking:
                return
            if time.time() - self._last_proactive_at < 30.0:
                return
            self._last_proactive_at = time.time()
            asyncio.run_coroutine_threadsafe(
                self._fire(
                    "The user just typed 'hey aura' on their keyboard! "
                    "Respond playfully in 1 short sentence.",
                    source="proactive",
                    with_vision=True,
                ),
                loop,
            )

        input_watcher.set_name_mention_callback(_on_mention)
        logger.info("AURA proactive companion loop started.")

    def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None

    async def _fire(self, prompt: str, source: str = "proactive", with_vision: bool = True) -> None:
        if self._trigger_cb:
            await self._trigger_cb(prompt, source, with_vision)

    async def _loop(self) -> None:
        try:
            _, _, init_game, _ = await asyncio.to_thread(vision_watcher.poll_window_only)
            if init_game:
                self._greeted_games.add(init_game)
        except Exception:
            pass

        tick = 0
        while self._running:
            try:
                await asyncio.sleep(2.0)
                tick += 1

                due = memory_store.pop_due_reminders()
                if due and not runtime.is_speaking:
                    texts = "; ".join(r["text"] for r in due)
                    self._last_proactive_at = time.time()
                    await self._fire(
                        f"[REMINDER TRIGGERED] Remind the user right now in 1-2 friendly AURA sentences about: {texts}",
                        source="reminder",
                        with_vision=False,
                    )
                    continue

                prev_privacy = runtime.privacy_paused
                prev_win = runtime.active_window
                title, proc, game, is_sensitive = await asyncio.to_thread(
                    vision_watcher.poll_window_only
                )
                await asyncio.to_thread(keep_overlay_topmost)
                if (prev_privacy != runtime.privacy_paused or prev_win != title) and self._broadcast_state_cb:
                    await self._broadcast_state_cb()

                if is_sensitive:
                    input_watcher.clear()

                if not runtime.proactive_enabled or runtime.is_speaking or runtime.is_thinking or runtime.is_listening:
                    continue

                now = time.time()
                cooldown = max(15.0, float(runtime.proactive_cooldown_sec))

                capture_every_ticks = max(2, int(settings.vision_interval_sec / 2.0))
                if tick % capture_every_ticks == 0 and not runtime.blind_mode and runtime.vision_enabled and not is_sensitive:
                    snap = await asyncio.to_thread(vision_watcher.capture_now)
                    recently_chatted = (now - self._last_user_interaction_at) < 60.0
                    if snap is not None and not recently_chatted and (now - self._last_proactive_at) >= cooldown:
                        if game and game not in self._greeted_games:
                            self._greeted_games.add(game)
                            self._last_proactive_at = now
                            await self._fire(
                                f"[OBSERVATION] The user just started playing {game}! "
                                "React playfully as AURA in ONE short sentence (under 14 words).",
                                source="proactive",
                                with_vision=True,
                            )
                            continue

                dt = datetime.now()
                today_key = dt.strftime("%Y-%m-%d")
                recently_chatted = (now - self._last_user_interaction_at) < 90.0
                if (
                    0 <= dt.hour <= 4
                    and (dt.hour > 0 or dt.minute >= 30)
                    and not recently_chatted
                    and self._late_night_warned_date != today_key
                    and (now - self._last_proactive_at) >= cooldown
                ):
                    self._late_night_warned_date = today_key
                    self._last_proactive_at = now
                    await self._fire(
                        f"[LATE NIGHT CARE] It is {dt.strftime('%H:%M')} and the user is still up at their PC. "
                        "Gently remind them to rest in 1-2 warm sentences as AURA.",
                        source="proactive",
                        with_vision=not runtime.blind_mode,
                    )
                    continue

                if (
                    (now - self._last_user_interaction_at) >= 720.0
                    and (now - self._last_proactive_at) >= max(cooldown * 3, 600.0)
                ):
                    self._last_proactive_at = now
                    await self._fire(
                        "[IDLE CHECK-IN] You've been sitting quietly on their desktop for a while. "
                        "Say a friendly 1-sentence check-in as AURA.",
                        source="proactive",
                        with_vision=not runtime.blind_mode,
                    )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Proactive loop error: {e}")


proactive_loop = ProactiveLoop()
