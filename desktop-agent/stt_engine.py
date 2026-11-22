"""
AURA Desktop Agent — 100% Local CPU Speech-to-Text Engine
Runs faster-whisper (int8) on CPU so all GPU VRAM stays dedicated to Qwen3-TTS & games.
Features:
  - Responsive 550ms end-of-speech VAD
  - Parallel end-of-speech screen snapshot for zero-staleness visual grounding
  - Instant VAD barge-in synced with client audio playback state
  - Always Listening & Strict Wake-Word ("AURA") modes
"""
from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import Awaitable, Callable, Optional

import numpy as np

from config import runtime, settings

logger = logging.getLogger("aura.stt")

SAMPLE_RATE = 16000
BLOCK_MS = 30
BLOCK_SAMPLES = int(SAMPLE_RATE * BLOCK_MS / 1000)


class LocalSTTEngine:
    def __init__(self) -> None:
        self._whisper = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._on_transcript: Optional[Callable[[str], Awaitable[None]]] = None
        self._on_barge_in: Optional[Callable[[], Awaitable[None]]] = None
        self._on_state_change: Optional[Callable[[], Awaitable[None]]] = None
        self._audio_level: float = 0.0

    @property
    def audio_level(self) -> float:
        return self._audio_level

    def load_model(self) -> bool:
        try:
            from faster_whisper import WhisperModel

            logger.info(
                f"Loading faster-whisper '{settings.stt_model}' on {settings.stt_device} ({settings.stt_compute_type})..."
            )
            t0 = time.perf_counter()
            try:
                self._whisper = WhisperModel(
                    settings.stt_model,
                    device=settings.stt_device,
                    compute_type=settings.stt_compute_type,
                    cpu_threads=6,
                    local_files_only=True,
                )
            except Exception:
                self._whisper = WhisperModel(
                    settings.stt_model,
                    device=settings.stt_device,
                    compute_type=settings.stt_compute_type,
                    cpu_threads=6,
                )
            runtime.stt_ready = True
            logger.info(f"faster-whisper ready in {time.perf_counter() - t0:.2f}s (0 VRAM)")
            return True
        except Exception as e:
            logger.error(f"Failed to load faster-whisper: {e}")
            runtime.stt_ready = False
            return False

    def start(
        self,
        loop: asyncio.AbstractEventLoop,
        on_transcript: Callable[[str], Awaitable[None]],
        on_barge_in: Callable[[], Awaitable[None]],
        on_state_change: Callable[[], Awaitable[None]],
    ) -> None:
        if self._running:
            return
        self._loop = loop
        self._on_transcript = on_transcript
        self._on_barge_in = on_barge_in
        self._on_state_change = on_state_change
        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False

    def _notify_state(self) -> None:
        if self._loop and self._on_state_change:
            asyncio.run_coroutine_threadsafe(self._on_state_change(), self._loop)

    def _capture_loop(self) -> None:
        if self._whisper is None:
            self.load_model()
            self._notify_state()

        try:
            import sounddevice as sd
        except Exception as e:
            logger.error(f"sounddevice unavailable: {e}")
            return

        noise_floor = 0.008
        in_speech = False
        speech_frames: list[np.ndarray] = []
        pre_roll: list[np.ndarray] = []
        silence_blocks = 0
        speech_blocks = 0

        silence_limit_blocks = int(550 / BLOCK_MS)
        min_speech_blocks = int(210 / BLOCK_MS)
        max_speech_blocks = int(16000 / BLOCK_MS)

        def _process_utterance(frames: list[np.ndarray]) -> None:
            if not frames or self._whisper is None:
                return
            audio = np.concatenate(frames).astype(np.float32)
            if float(np.max(np.abs(audio))) < 0.025:
                return
            t0 = time.perf_counter()
            try:
                lang_arg = (
                    settings.stt_language
                    if settings.stt_language and settings.stt_language != "auto"
                    else None
                )
                segments, _ = self._whisper.transcribe(
                    audio,
                    language=lang_arg,
                    initial_prompt="AURA, ASE Lab.",
                    beam_size=1,
                    best_of=1,
                    vad_filter=True,
                    vad_parameters={"min_silence_duration_ms": 300},
                    condition_on_previous_text=False,
                )
                text = " ".join(seg.text.strip() for seg in segments).strip()
            except Exception as e:
                logger.error(f"Whisper transcribe failed: {e}")
                return

            low_clean = text.lower().strip()
            hallucinations = {
                "thank you",
                "thank you.",
                "thanks for watching",
                "thanks for watching.",
                "bye.",
                "you",
                ".",
                "...",
                "aura, ase lab.",
            }
            if not text or low_clean in hallucinations or "aura, ase lab" in low_clean or len(text) < 2:
                return

            if runtime.mic_mode == "wake":
                wake_hits = ("aura", "ora", "hey aura", "aurora")
                if not any(w in low_clean for w in wake_hits):
                    logger.info(f"[STT wake-mode ignored] '{text}'")
                    return

            logger.info(f"[STT] ({(time.perf_counter() - t0)*1000:.0f}ms): {text}")
            if self._loop and self._on_transcript:
                asyncio.run_coroutine_threadsafe(self._on_transcript(text), self._loop)

        try:
            with sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="float32",
                blocksize=BLOCK_SAMPLES,
            ) as stream:
                logger.info("Microphone listening (16kHz CPU VAD)...")
                while self._running:
                    data, _ = stream.read(BLOCK_SAMPLES)
                    chunk = data[:, 0].copy()

                    if runtime.mic_muted:
                        self._audio_level = 0.0
                        if in_speech:
                            in_speech = False
                            speech_frames.clear()
                            runtime.is_listening = False
                            self._notify_state()
                        continue

                    rms = float(np.sqrt(np.mean(chunk * chunk)))
                    self._audio_level = rms

                    aura_active = runtime.is_speaking or runtime.client_playing or runtime.is_thinking
                    multiplier = 3.1 if aura_active else 2.5
                    base_min = 0.018 if aura_active else 0.013
                    threshold = max(base_min, noise_floor * multiplier)

                    if not in_speech:
                        pre_roll.append(chunk)
                        if len(pre_roll) > 10:
                            pre_roll.pop(0)
                        if not aura_active:
                            noise_floor = noise_floor * 0.985 + min(rms, 0.025) * 0.015

                        if rms > threshold:
                            speech_blocks += 1
                            required_blocks = 5 if aura_active else 3
                            if speech_blocks >= required_blocks:
                                in_speech = True
                                silence_blocks = 0
                                speech_frames = list(pre_roll)
                                pre_roll.clear()
                                runtime.is_listening = True
                                self._notify_state()
                                if aura_active and runtime.mic_mode == "always" and self._loop and self._on_barge_in:
                                    logger.info(
                                        f"[VAD Barge-In] User started speaking (rms={rms:.3f} > {threshold:.3f}) — cancelling AURA!"
                                    )
                                    asyncio.run_coroutine_threadsafe(
                                        self._on_barge_in(), self._loop
                                    )
                        else:
                            speech_blocks = 0
                    else:
                        speech_frames.append(chunk)
                        if rms > threshold * 0.72:
                            silence_blocks = 0
                        else:
                            silence_blocks += 1

                        if silence_blocks >= silence_limit_blocks or len(speech_frames) >= max_speech_blocks:
                            captured = speech_frames
                            speech_frames = []
                            in_speech = False
                            speech_blocks = 0
                            silence_blocks = 0
                            runtime.is_listening = False
                            self._notify_state()
                            if len(captured) >= min_speech_blocks:
                                def _snap_and_transcribe(frames):
                                    try:
                                        from vision_watcher import vision_watcher

                                        vision_watcher.capture_now(force=True)
                                    except Exception:
                                        pass
                                    _process_utterance(frames)

                                threading.Thread(
                                    target=_snap_and_transcribe, args=(captured,), daemon=True
                                ).start()
        except Exception as e:
            logger.error(f"Microphone stream error: {e}")


stt_engine = LocalSTTEngine()
