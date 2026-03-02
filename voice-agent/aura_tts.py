"""
AuraTTS — Custom LiveKit TTS plugin wrapping faster-qwen3-tts.
Runs the 0.6B Qwen3-TTS model locally with CUDA graph acceleration.
Uses streaming generation to yield audio chunks for low TTFA.
"""
import asyncio
import logging
import threading
import queue
import uuid
from dataclasses import dataclass
from typing import Optional
import numpy as np

from livekit import rtc
from livekit.agents import tts, tokenize

import sys
import os
import torch

_repo_path = os.path.normpath(os.path.join(os.path.dirname(__file__), 'lib', 'faster-qwen3-tts'))
if _repo_path not in sys.path:
    sys.path.insert(0, _repo_path)
from faster_qwen3_tts.model import FasterQwen3TTS

logger = logging.getLogger("aura_tts")

SAMPLE_RATE = 24000
NUM_CHANNELS = 1


@dataclass
class _TTSOptions:
    model_name: str
    ref_audio: str
    ref_text: str
    language: str
    dtype: torch.dtype


class AuraTTS(tts.TTS):
    """
    Custom LiveKit TTS plugin wrapping the faster-qwen3-tts local model.
    Uses streaming generation for sub-second Time To First Audio.
    """

    def __init__(
        self,
        *,
        model_name: str = "Qwen/Qwen3-TTS-12Hz-0.6B-Base",
        ref_audio: str,
        ref_text: str,
        language: str = "English",
        dtype: torch.dtype = torch.bfloat16,
    ):
        super().__init__(
            capabilities=tts.TTSCapabilities(streaming=True),
            sample_rate=SAMPLE_RATE,
            num_channels=NUM_CHANNELS,
        )
        self._opts = _TTSOptions(
            model_name=model_name,
            ref_audio=ref_audio,
            ref_text=ref_text,
            language=language,
            dtype=dtype,
        )
        self._model: Optional[FasterQwen3TTS] = None
        self._model_lock = threading.Lock()
        self._gen_lock = threading.Lock()

    def _ensure_model(self):
        if self._model is not None:
            return
        with self._model_lock:
            if self._model is not None:
                return
            import gc
            gc.collect()
            torch.cuda.empty_cache()
            logger.info(f"Loading FasterQwen3TTS: {self._opts.model_name}")
            self._model = FasterQwen3TTS.from_pretrained(
                self._opts.model_name,
                dtype=self._opts.dtype,
            )
            logger.info("FasterQwen3TTS loaded and ready!")

    def warmup(self):
        """Run a short dummy generation to trigger CUDA graph capture at boot."""
        self._ensure_model()
        logger.info("Warming up TTS with dummy generation...")
        with self._gen_lock:
            for _ in self._model.generate_voice_clone_streaming(
                text="Hello.",
                ref_audio=self._opts.ref_audio,
                ref_text=self._opts.ref_text,
                language=self._opts.language,
                chunk_size=12,
                non_streaming_mode=False,
            ):
                pass
        logger.info("TTS warmup complete — CUDA graphs ready!")

    def _generate_audio(self, text: str) -> bytes:
        """Non-streaming fallback: generate full audio for a text string."""
        with self._gen_lock:
            audio_np, sample_rate = self._model.generate_voice_clone(
                text=text,
                ref_audio=self._opts.ref_audio,
                ref_text=self._opts.ref_text,
                language=self._opts.language,
            )
            audio_data = audio_np[0]
            audio_int16 = (audio_data * 32767).clip(-32768, 32767).astype(np.int16)
            return audio_int16.tobytes()

    def _generate_audio_streaming(self, text: str, chunk_queue: queue.Queue):
        """Run streaming generation in a thread, pushing PCM chunks to a queue."""
        try:
            with self._gen_lock:
                for audio_chunk_np, sr, timing in self._model.generate_voice_clone_streaming(
                    text=text,
                    ref_audio=self._opts.ref_audio,
                    ref_text=self._opts.ref_text,
                    language=self._opts.language,
                    chunk_size=12,
                    non_streaming_mode=False,
                ):
                    audio_int16 = (audio_chunk_np * 32767).clip(-32768, 32767).astype(np.int16)
                    chunk_queue.put(audio_int16.tobytes())
                    if timing.get('chunk_index', 0) == 0:
                        logger.info(
                            f"TTS first chunk: prefill={timing.get('prefill_ms', 0):.0f}ms, "
                            f"decode={timing.get('decode_ms', 0):.0f}ms"
                        )
        except Exception as e:
            logger.error(f"Streaming generation error: {e}")
        finally:
            chunk_queue.put(None)

    def synthesize(self, text: str, *, conn_options=None) -> "tts.ChunkedStream":
        return _AuraChunkedStream(self, text, self._opts, conn_options)

    def stream(self, *, conn_options=None) -> "tts.SynthesizeStream":
        return _AuraSynthesizeStream(self, self._opts, conn_options)


class _AuraChunkedStream(tts.ChunkedStream):
    """Non-streaming: synthesize a complete text string."""

    def __init__(self, tts_instance: AuraTTS, input_text: str, opts: _TTSOptions, conn_options):
        super().__init__(tts=tts_instance, input_text=input_text, conn_options=conn_options or tts.APIConnectOptions())
        self._tts_instance = tts_instance
        self._text = input_text
        self._opts = opts

    async def _run(self, output_emitter):
        self._tts_instance._ensure_model()

        output_emitter.initialize(
            request_id=str(uuid.uuid4()),
            sample_rate=SAMPLE_RATE,
            num_channels=NUM_CHANNELS,
            mime_type="audio/pcm",
            stream=False,
        )

        loop = asyncio.get_event_loop()
        pcm_bytes = await loop.run_in_executor(
            None, self._tts_instance._generate_audio, self._text
        )
        output_emitter.push(pcm_bytes)


class _AuraSynthesizeStream(tts.SynthesizeStream):
    """
    Streaming TTS: buffers LLM tokens into sentences, then streams each
    sentence's audio chunks to LiveKit as they are generated by the model.
    """

    def __init__(self, tts_instance: AuraTTS, opts: _TTSOptions, conn_options):
        super().__init__(tts=tts_instance, conn_options=conn_options or tts.APIConnectOptions())
        self._tts_instance = tts_instance
        self._opts = opts

    async def _run(self, output_emitter):
        self._tts_instance._ensure_model()

        output_emitter.initialize(
            request_id=str(uuid.uuid4()),
            sample_rate=SAMPLE_RATE,
            num_channels=NUM_CHANNELS,
            mime_type="audio/pcm",
            stream=False,
        )

        tokenizer = tokenize.basic.SentenceTokenizer()
        token_stream = tokenizer.stream()

        async def _process_input():
            async for data in self._input_ch:
                if isinstance(data, self._FlushSentinel):
                    token_stream.flush()
                else:
                    token_stream.push_text(data)
            token_stream.end_input()

        async def _synthesize():
            async for ev in token_stream:
                sentence = ev.token
                if not sentence.strip():
                    continue

                logger.debug(f"Synthesizing (streaming): {sentence}")

                chunk_q: queue.Queue = queue.Queue()
                loop = asyncio.get_event_loop()

                loop.run_in_executor(
                    None, self._tts_instance._generate_audio_streaming, sentence, chunk_q
                )

                while True:
                    pcm_bytes = await loop.run_in_executor(None, chunk_q.get)
                    if pcm_bytes is None:
                        break
                    output_emitter.push(pcm_bytes)

        await asyncio.gather(_process_input(), _synthesize())
