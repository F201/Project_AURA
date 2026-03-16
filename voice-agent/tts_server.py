"""
AURA TTS HTTP Service — Phase 0
Exposes the local Qwen3-TTS voice clone as a standalone HTTP service.
Used by both the Electron desktop app and the browser dashboard.

Endpoints:
    POST /synthesize      → streaming raw PCM int16, actual sample rate, mono
                            (for Electron desktop app — fast, no header overhead)
    POST /synthesize.wav  → complete WAV file (for testing / browser <audio> tags)
    GET  /health          → {"status": "ok", "model": "...", "sample_rate": N}

Usage:
    python tts_server.py
    python tts_server.py --port 8765

M0 curl check (easy — plays in any media player):
    curl -X POST localhost:8765/synthesize.wav \\
         -H "Content-Type: application/json" \\
         -d '{"text":"Hello, I am AURA!"}' --output test.wav && start test.wav

Raw PCM check (needs ffplay):
    curl -X POST localhost:8765/synthesize \\
         -H "Content-Type: application/json" \\
         -d '{"text":"Hello, I am AURA!"}' --output test.pcm
    ffplay -f s16le -ar 24000 -ac 1 test.pcm
"""

import argparse
import asyncio
import gc
import io
import logging
import os
import re
import struct
import sys
import threading
from pathlib import Path

import numpy as np
import torch
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

# ── Path setup ──────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
_repo_path = str(BASE_DIR / "lib" / "faster-qwen3-tts")
if _repo_path not in sys.path:
    sys.path.insert(0, _repo_path)

from faster_qwen3_tts.model import FasterQwen3TTS  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tts-server")

# ── Config ───────────────────────────────────────────────────────────────────
MODEL_NAME   = os.getenv("TTS_MODEL", "Qwen/Qwen3-TTS-12Hz-0.6B-Base")
REF_AUDIO    = str(BASE_DIR / "resources" / "voice" / "aura_voice_xvec.pt")
NUM_CHANNELS = 1

_EMOTION_TAG_RE = re.compile(r"\[[^\]]+\]")

# ── Global state ─────────────────────────────────────────────────────────────
_model: FasterQwen3TTS | None = None
_model_lock = threading.Lock()   # guards lazy-load (called from thread pool)
_gen_lock   = asyncio.Lock()     # serialises GPU inference (one request at a time)


def _load_model() -> FasterQwen3TTS:
    """Lazy-load; thread-safe; loads only once."""
    global _model
    if _model is not None:
        return _model
    with _model_lock:
        if _model is not None:
            return _model
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        logger.info(f"Loading {MODEL_NAME}…")
        _model = FasterQwen3TTS.from_pretrained(
            MODEL_NAME,
            dtype=torch.bfloat16,
        )
        logger.info("TTS model loaded.")
    return _model


def _warmup():
    """Trigger CUDA graph capture with a short dummy generation at startup."""
    m = _load_model()
    logger.info("Warming up TTS (CUDA graph capture)…")
    m.generate_voice_clone(
        text="Hello.",
        ref_audio=REF_AUDIO,
        ref_text="",
        language="English",
    )
    logger.info("TTS warmup done.")


def _strip_tags(text: str) -> str:
    """Remove [emotion] brackets and normalise whitespace."""
    return _EMOTION_TAG_RE.sub("", text).strip()


def _synthesize(text: str, language: str) -> tuple[bytes, int]:
    """
    Run blocking GPU inference.
    Returns (pcm_int16_bytes, sample_rate).
    Concatenates all decoded audio arrays (matches demo server's _concat_audio).
    """
    m = _load_model()
    audio_arrays, sr = m.generate_voice_clone(
        text=text,
        ref_audio=REF_AUDIO,
        ref_text="",
        language=language,
    )
    # Concatenate all decoded chunks (batch_size=1 → usually one element, but safe)
    parts = []
    for a in audio_arrays:
        a = np.asarray(a, dtype=np.float32)
        if a.ndim > 1:
            a = a.squeeze()
        if a.size > 0:
            parts.append(a)
    audio = np.concatenate(parts) if parts else np.zeros(0, dtype=np.float32)
    audio_int16 = (audio * 32767).clip(-32768, 32767).astype(np.int16)
    return audio_int16.tobytes(), int(sr)


def _build_wav(pcm_bytes: bytes, sample_rate: int, num_channels: int = 1, bit_depth: int = 16) -> bytes:
    """Wrap raw PCM bytes in a RIFF/WAV header so any media player can play it."""
    data_size   = len(pcm_bytes)
    byte_rate   = sample_rate * num_channels * (bit_depth // 8)
    block_align = num_channels * (bit_depth // 8)
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + data_size,   # ChunkSize
        b"WAVE",
        b"fmt ",
        16,               # Subchunk1Size (PCM)
        1,                # AudioFormat (PCM = 1)
        num_channels,
        sample_rate,
        byte_rate,
        block_align,
        bit_depth,
        b"data",
        data_size,
    )
    return header + pcm_bytes


# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(title="AURA TTS Service")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


class SynthesizeRequest(BaseModel):
    text: str
    language: str = "English"  # "English" | "Japanese"


@app.get("/health")
async def health():
    return {"status": "ok", "model": MODEL_NAME}


@app.post("/synthesize")
async def synthesize(req: SynthesizeRequest):
    """
    Returns streaming raw PCM int16 at the model's native sample rate.
    Intended for the Electron desktop app's playPCMStream() which handles
    the raw format directly.  Sample rate is reported in X-Sample-Rate header.
    """
    text = _strip_tags(req.text).strip()
    if not text:
        raise HTTPException(status_code=400, detail="text must not be empty after cleaning")

    language = req.language if req.language in ("English", "Japanese") else "English"

    async with _gen_lock:
        pcm_bytes, sample_rate = await asyncio.to_thread(_synthesize, text, language)

    async def _stream():
        chunk = 8192
        for i in range(0, len(pcm_bytes), chunk):
            yield pcm_bytes[i : i + chunk]

    return StreamingResponse(
        _stream(),
        media_type="audio/pcm",
        headers={
            "X-Sample-Rate":  str(sample_rate),
            "X-Num-Channels": str(NUM_CHANNELS),
            "X-Bit-Depth":    "16",
        },
    )


@app.post("/synthesize.wav")
async def synthesize_wav(req: SynthesizeRequest):
    """
    Returns a complete WAV file. Plays in any media player — use this for the
    M0 curl verification test and for browser <audio> tags.
    """
    text = _strip_tags(req.text).strip()
    if not text:
        raise HTTPException(status_code=400, detail="text must not be empty after cleaning")

    language = req.language if req.language in ("English", "Japanese") else "English"

    async with _gen_lock:
        pcm_bytes, sample_rate = await asyncio.to_thread(_synthesize, text, language)

    wav_bytes = _build_wav(pcm_bytes, sample_rate, NUM_CHANNELS)
    return Response(content=wav_bytes, media_type="audio/wav")


# ── Entry point ───────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="AURA TTS HTTP Service")
    parser.add_argument("--host",       default="127.0.0.1")
    parser.add_argument("--port", "-p", type=int, default=8765)
    parser.add_argument("--no-warmup",  action="store_true",
                        help="Skip CUDA graph warmup on startup (faster boot, slower first request)")
    args = parser.parse_args()

    if not args.no_warmup:
        # Warmup must run before the event loop starts (it's blocking)
        _warmup()

    logger.info(f"TTS service ready at http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
