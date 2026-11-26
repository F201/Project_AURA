"""
AURA Desktop Agent — True Streaming Voice Clone TTS Engine
Reuses Project AURA's bundled voice-agent/lib/faster-qwen3-tts and
voice-agent/resources/voice/aura_voice_xvec.pt with:
  - True chunked streaming (generate_voice_clone_streaming) -> ~300-550ms TTFA
  - Low-VRAM max_seq_len=256 + startup CUDA graph warmup
  - Local HuggingFace cache fast-load (local_files_only=True with fallback)
  - Instant mid-stream cancellation for VAD barge-in
  - Game Mode VRAM Saver (unloads Qwen3-TTS and switches to 0-VRAM Edge-TTS on demand)
"""
from __future__ import annotations

import asyncio
import gc
import io
import logging
import re
import sys
import threading
import time
from pathlib import Path
from typing import AsyncGenerator, List, Optional

import httpx
import numpy as np

from config import VOICE_AGENT_DIR, runtime, settings

logger = logging.getLogger("aura.tts")

_LIB_PATH = str(VOICE_AGENT_DIR / "lib" / "faster-qwen3-tts")
if _LIB_PATH not in sys.path:
    sys.path.insert(0, _LIB_PATH)

VOICE_DIR = VOICE_AGENT_DIR / "resources" / "voice"
SAMPLE_RATE = 24000

_TAG_RE = re.compile(r"\[[^\]]+\]")
_MD_RE = re.compile(r"[*_`#<>]+")
_EMOJI_RE = re.compile(r"[\U00010000-\U0010ffff]+", flags=re.UNICODE)


def clean_for_speech(text: str) -> str:
    text = _TAG_RE.sub("", text)
    text = _MD_RE.sub("", text)
    text = _EMOJI_RE.sub("", text)
    return re.sub(r"\s+", " ", text).strip()


def detect_language(text: str, preferred: str = "English") -> str:
    has_jp = any("\u3040" <= c <= "\u30ff" or "\u4e00" <= c <= "\u9fff" for c in text)
    if preferred in ("English", "Japanese"):
        return "Japanese" if has_jp else preferred
    return "Japanese" if has_jp else "English"


class StreamingTTSEngine:
    def __init__(self) -> None:
        self._model = None
        self._model_lock = threading.Lock()
        self._gen_lock = threading.Lock()
        self._sample_rate = SAMPLE_RATE

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    def list_voice_files(self) -> List[str]:
        VOICE_DIR.mkdir(parents=True, exist_ok=True)
        files = []
        for ext in ("*.pt", "*.wav", "*.mp3", "*.flac", "*.ogg"):
            files.extend([p.name for p in VOICE_DIR.glob(ext)])
        return sorted(set(files))

    def get_active_voice_path(self) -> str:
        candidate = VOICE_DIR / runtime.tts_voice_file
        if candidate.exists():
            return str(candidate)
        for fallback_name in ("aura_voice_xvec.pt", "ref_audio.wav"):
            fb = VOICE_DIR / fallback_name
            if fb.exists():
                return str(fb)
        return str(VOICE_DIR / "aura_voice_xvec.pt")

    def get_active_ref_text(self, voice_path: str) -> str:
        txt_path = Path(voice_path).with_suffix(".txt")
        if txt_path.exists():
            try:
                return txt_path.read_text(encoding="utf-8").strip()
            except Exception:
                return ""
        return ""

    def load_qwen(self, warmup: bool = True) -> bool:
        if runtime.game_mode:
            runtime.tts_backend = "edge"
            runtime.tts_ready = True
            return False

        if settings.remote_tts_url:
            try:
                httpx.get(f"{settings.remote_tts_url}/health", timeout=4.0, trust_env=False).raise_for_status()
            except httpx.HTTPError as exc:
                self._set_remote_error(exc)
                return False
            runtime.tts_backend = "remote"
            runtime.tts_error = ""
            runtime.tts_ready = True
            return True

        with self._model_lock:
            if self._model is not None:
                runtime.tts_backend = "qwen3"
                runtime.tts_ready = True
                return True

            runtime.tts_backend = "loading"
            runtime.tts_error = ""
            model = None
            try:
                import torch

                if not torch.cuda.is_available():
                    logger.warning("CUDA not available — use Game Mode for Edge-TTS.")
                    runtime.tts_backend = "edge"
                    runtime.tts_error = "No CUDA GPU detected"
                    runtime.tts_ready = True
                    return False

                free_bytes, total_bytes = torch.cuda.mem_get_info()
                logger.info(
                    f"GPU VRAM free before Qwen3 load: {free_bytes/(1024*1024):.0f} / {total_bytes/(1024*1024):.0f} MiB"
                )

                from faster_qwen3_tts.model import FasterQwen3TTS

                gc.collect()
                torch.cuda.empty_cache()

                logger.info(f"Loading FasterQwen3TTS ({settings.tts_model}) on GPU (max_seq_len=256)...")
                t0 = time.perf_counter()
                model_source = settings.tts_model
                try:
                    from huggingface_hub import snapshot_download

                    model_source = snapshot_download(settings.tts_model, local_files_only=True)
                    logger.info(f"Using cached local snapshot: {model_source}")
                except Exception:
                    pass

                model = FasterQwen3TTS.from_pretrained(
                    model_source,
                    device="cuda",
                    dtype=torch.bfloat16,
                    max_seq_len=256,
                )
                logger.info(f"FasterQwen3TTS loaded in {time.perf_counter() - t0:.2f}s")

                if warmup:
                    logger.info("Warming up CUDA graphs + streaming attention mask cache...")
                    tw = time.perf_counter()
                    ref_path = self.get_active_voice_path()
                    with self._gen_lock:
                        gen = model.generate_voice_clone_streaming(
                            text="Hello! AURA is ready!",
                            language="English",
                            ref_audio=ref_path,
                            ref_text="",
                            max_new_tokens=32,
                            chunk_size=max(3, runtime.tts_chunk_size),
                            append_silence=False,
                            repetition_penalty=1.15,
                        )
                        for audio_np, sr, _ in gen:
                            self._sample_rate = int(sr)
                    logger.info(f"TTS warmup complete in {time.perf_counter() - tw:.2f}s (sr={self._sample_rate})")

                self._model = model
                runtime.tts_backend = "qwen3"
                runtime.tts_error = ""
                runtime.tts_ready = True
                return True
            except Exception as e:
                err_str = str(e)
                logger.error(f"FasterQwen3TTS load failed ({err_str}) — freeing VRAM.")
                self._model = None
                try:
                    del model
                except Exception:
                    pass
                gc.collect()
                try:
                    import torch

                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                except Exception:
                    pass
                if "out of memory" in err_str.lower() or "oom" in err_str.lower():
                    runtime.tts_error = "Low GPU VRAM — free ~2GB VRAM & click Retry Qwen3 (or enable Game Mode)"
                else:
                    runtime.tts_error = f"Qwen3 load failed: {err_str[:80]}"
                runtime.tts_backend = "edge"
                runtime.tts_ready = True
                return False

    def unload_qwen(self) -> None:
        with self._model_lock:
            if self._model is not None:
                logger.info("Unloading Qwen3-TTS from GPU VRAM (Game Mode)...")
                self._model = None
                gc.collect()
                try:
                    import torch

                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                except Exception:
                    pass
            runtime.tts_backend = "edge"
            runtime.tts_ready = True

    async def stream_clause_pcm(
        self,
        text: str,
        abort_event: asyncio.Event,
    ) -> AsyncGenerator[tuple[bytes, int], None]:
        cleaned = clean_for_speech(text)
        if not cleaned or not any(c.isalnum() for c in cleaned):
            return
        if abort_event.is_set():
            return

        if settings.remote_tts_url and not runtime.game_mode:
            async for chunk in self._stream_remote_pcm(cleaned, abort_event):
                yield chunk
            return

        if self._model is None and runtime.tts_backend == "loading" and not runtime.game_mode:
            for _ in range(360):
                if abort_event.is_set() or self._model is not None or runtime.tts_backend != "loading":
                    break
                await asyncio.sleep(0.25)
            if abort_event.is_set():
                return

        if self._model is None and not runtime.game_mode:
            try:
                import torch

                if torch.cuda.is_available() and (torch.cuda.mem_get_info()[0] / (1024 * 1024)) >= 2400:
                    logger.info("VRAM available again — auto-reloading Faster-Qwen3-TTS...")
                    await asyncio.to_thread(self.load_qwen, True)
            except Exception:
                pass

        if self._model is not None and not runtime.game_mode:
            lang = detect_language(cleaned, runtime.tts_language)
            chars_per_sec = 4.0 if lang == "Japanese" else 12.0
            max_new_tokens = max(16, min(int(len(cleaned) / chars_per_sec * 2.4 * 12), 160))
            ref_path = self.get_active_voice_path()
            ref_text = self.get_active_ref_text(ref_path)
            ref_is_jp = any("\u3040" <= c <= "\u30ff" or "\u4e00" <= c <= "\u9fff" for c in ref_text)
            use_icl = bool(ref_text) and not ref_path.endswith(".pt") and (
                (lang == "Japanese" and ref_is_jp) or (lang == "English" and not ref_is_jp)
            )
            chunk_size = max(3, min(12, int(runtime.tts_chunk_size)))

            loop = asyncio.get_running_loop()
            q: asyncio.Queue[Optional[tuple[bytes, int]]] = asyncio.Queue()
            t_start = time.perf_counter()

            def _worker() -> None:
                first_logged = False
                try:
                    with self._gen_lock:
                        if self._model is None or abort_event.is_set():
                            return
                        gen = self._model.generate_voice_clone_streaming(
                            text=cleaned,
                            language=lang,
                            ref_audio=ref_path,
                            ref_text=ref_text if use_icl else "",
                            xvec_only=not use_icl,
                            max_new_tokens=max_new_tokens,
                            chunk_size=chunk_size,
                            append_silence=False,
                            repetition_penalty=1.18,
                        )
                        for audio_np, sr, _timing in gen:
                            if abort_event.is_set():
                                break
                            arr = np.asarray(audio_np, dtype=np.float32).flatten()
                            if arr.size == 0:
                                continue
                            if not first_logged:
                                first_logged = True
                                logger.info(
                                    f"[TTFA] First Qwen3 audio chunk in {(time.perf_counter() - t_start)*1000:.0f}ms "
                                    f"for '{cleaned[:45]}'"
                                )
                            pcm16 = (arr * 32767.0).clip(-32768, 32767).astype(np.int16).tobytes()
                            loop.call_soon_threadsafe(q.put_nowait, (pcm16, int(sr)))
                except Exception as e:
                    logger.error(f"Qwen3 streaming error: {e}")
                finally:
                    loop.call_soon_threadsafe(q.put_nowait, None)

            threading.Thread(target=_worker, daemon=True).start()

            while True:
                try:
                    item = await asyncio.wait_for(q.get(), timeout=12.0)
                except asyncio.TimeoutError:
                    logger.warning("Qwen3 TTS chunk timed out after 12s.")
                    break
                if item is None or abort_event.is_set():
                    break
                yield item
            return

        if runtime.game_mode:
            async for chunk in self._stream_edge_tts_pcm(cleaned, abort_event):
                yield chunk
        else:
            logger.warning("Skipping Edge-TTS fallback (Game Mode is OFF); Qwen3-TTS is not loaded.")

    def _set_remote_error(self, exc: Exception) -> None:
        logger.warning("Phone Qwen3-TTS failed: %s", exc)
        runtime.tts_backend = "off"
        runtime.tts_ready = False
        runtime.tts_error = "Phone Qwen3-TTS unavailable. Check the phone service and SSH tunnel."

    async def _stream_remote_pcm(
        self, text: str, abort_event: asyncio.Event,
    ) -> AsyncGenerator[tuple[bytes, int], None]:
        """Deliver a whole clause so slow phone inference cannot break up words."""
        language = "ja" if detect_language(text, runtime.tts_language) == "Japanese" else "en"
        headers = {"Content-Type": "text/plain; charset=utf-8", "X-TTS-Language": language}
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(45.0, connect=4.0), trust_env=False) as client:
                request = asyncio.create_task(client.post(
                    f"{settings.remote_tts_url}/speech", content=text.encode("utf-8"), headers=headers,
                ))
                interrupt = asyncio.create_task(abort_event.wait())
                try:
                    await asyncio.wait((request, interrupt), return_when=asyncio.FIRST_COMPLETED)
                    if abort_event.is_set():
                        return
                    response = request.result().raise_for_status()
                finally:
                    request.cancel()
                    interrupt.cancel()
                    await asyncio.gather(request, interrupt, return_exceptions=True)

            if response.headers.get("X-Sample-Rate") != str(SAMPLE_RATE):
                raise ValueError("Invalid phone TTS sample rate")
            pcm = response.content
            if not pcm or len(pcm) % 2:
                raise ValueError("Incomplete PCM from phone TTS")
            if abort_event.is_set():
                return
            runtime.tts_backend = "remote"
            runtime.tts_error = ""
            runtime.tts_ready = True
            yield pcm, SAMPLE_RATE
        except (httpx.HTTPError, ValueError) as exc:
            if not abort_event.is_set():
                self._set_remote_error(exc)

    async def _stream_edge_tts_pcm(
        self, text: str, abort_event: asyncio.Event
    ) -> AsyncGenerator[tuple[bytes, int], None]:
        """0-VRAM fallback via edge-tts + PyAV MP3 decode."""
        try:
            import av
            import edge_tts

            lang = detect_language(text, runtime.tts_language)
            voice = "ja-JP-NanamiNeural" if lang == "Japanese" else "en-US-AriaNeural"
            communicate = edge_tts.Communicate(text, voice=voice, rate="+5%", pitch="+3Hz")
            mp3_buf = bytearray()

            async def _collect():
                async for msg in communicate.stream():
                    if abort_event.is_set():
                        return
                    if msg["type"] == "audio":
                        mp3_buf.extend(msg["data"])

            await asyncio.wait_for(_collect(), timeout=10.0)
            if not mp3_buf or abort_event.is_set():
                return

            def _decode_mp3(raw: bytes) -> tuple[bytes, int]:
                container = av.open(io.BytesIO(raw), format="mp3")
                resampler = av.AudioResampler(format="s16", layout="mono", rate=24000)
                out_chunks = []
                for frame in container.decode(audio=0):
                    for rf in resampler.resample(frame):
                        out_chunks.append(rf.to_ndarray().tobytes())
                container.close()
                return b"".join(out_chunks), 24000

            pcm16, sr = await asyncio.to_thread(_decode_mp3, bytes(mp3_buf))
            if not pcm16:
                return
            slice_bytes = int(sr * 0.2) * 2
            for i in range(0, len(pcm16), slice_bytes):
                if abort_event.is_set():
                    return
                yield pcm16[i : i + slice_bytes], int(sr)
        except Exception as e:
            logger.warning(f"Edge-TTS fallback failed: {e}")


tts_engine = StreamingTTSEngine()
