"""
AuraTTS — Custom LiveKit TTS plugin wrapping faster-qwen3-tts.
Runs the 0.6B Qwen3-TTS model locally with CUDA graph acceleration.
"""
import asyncio
import logging
import threading
import uuid
import time
from dataclasses import dataclass
from typing import Optional
import numpy as np
from vtube_controller import VTUBE
from avatar_bridge import BRIDGE

from livekit import rtc
from livekit.agents import tts, tokenize

# Import the community fork module
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


def _trim_silence(audio: np.ndarray, threshold: float = 0.004,
                  sample_rate: int = SAMPLE_RATE, tail_ms: int = 120) -> np.ndarray:
    """Trim trailing silence from generated audio. Scans in 25 ms windows."""
    window = sample_rate // 40
    tail   = int(tail_ms * sample_rate / 1000)
    n_win  = len(audio) // window
    if n_win == 0:
        return audio

    rms = np.array([
        np.sqrt(np.mean(audio[i * window:(i + 1) * window] ** 2))
        for i in range(n_win)
    ])
    above = np.where(rms > threshold)[0]
    if len(above) == 0:
        return audio[:window]

    end = min(int(above[-1]) * window + tail, len(audio))
    return audio[:end]


@dataclass
class _TTSOptions:
    model_name: str
    ref_audio: str
    ref_text: str
    language: str
    dtype: torch.dtype
    max_seq_len: int


def _split_text(text: str, max_chars: int = 85) -> list[str]:
    """Recursively split text into chunks smaller than max_chars, preferably at punctuation or spaces."""
    if len(text) <= max_chars:
        return [text]

    # Try splitting at logical points: . ! ? 。 ！ ？
    split_points = ".!?。！？"
    best_idx = -1
    for i, char in enumerate(text[:max_chars]):
        if char in split_points:
            best_idx = i

    # If no punctuation, try space
    if best_idx == -1:
        for i in range(max_chars, 0, -1):
            if text[i] == ' ':
                best_idx = i
                break

    # If still no luck, hard cut (fallback)
    if best_idx == -1:
        best_idx = max_chars

    chunk = text[:best_idx + 1].strip()
    rest = text[best_idx + 1:].strip()

    if not rest:
        return [chunk]

    return [chunk] + _split_text(rest, max_chars)


class AuraTTS(tts.TTS):
    """
    Custom LiveKit TTS plugin wrapping the faster-qwen3-tts local model.
    Conforms to livekit-agents v1.4.3 TTS base class.
    """

    def __init__(
        self,
        *,
        model_name: str = "Qwen/Qwen3-TTS-12Hz-0.6B-Base",
        ref_audio: str,
        ref_text: str = "",
        language: str = "English",
        dtype: torch.dtype = torch.bfloat16,
        max_seq_len: int = 512,  # Bumped from 384 for better headroom
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
            max_seq_len=max_seq_len,
        )
        self._model: Optional[FasterQwen3TTS] = None
        self._model_lock = threading.Lock()
        self._gen_lock = threading.Lock()  # Serialize GPU inference

    def _ensure_model(self):
        """Lazy-load the model on first use (thread-safe, loads only once)."""
        if self._model is not None:
            return
        with self._model_lock:
            if self._model is not None:
                return
            import gc
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            logger.info(f"Loading FasterQwen3TTS: {self._opts.model_name} (max_seq_len={self._opts.max_seq_len})")
            self._model = FasterQwen3TTS.from_pretrained(
                self._opts.model_name,
                dtype=self._opts.dtype,
                max_seq_len=self._opts.max_seq_len,
            )
            # Warmup is handled inside ensure_model to ensure graphs are ready
            self._model._warmup(64)
            logger.info("FasterQwen3TTS loaded and ready!")

    def warmup(self):
        """Run a real generation to prime CUDA graphs AND the attention mask cache.

        _model._warmup() captures the CUDA graph using attention_mask=None (mask_key=None).
        The first real generation produces attention_mask=all-ones (mask_key=(0,)), which
        triggers TalkerGraph._build_attention_masks() — a 512-iteration loop taking 30-40s.
        Running a real generation here pays that cost once at startup instead of mid-session.
        """
        self._ensure_model()
        try:
            logger.info("Priming attention mask cache via real generation...")
            self._generate_audio_with_lang("Hello.", "English")
            logger.info("TTS warmup complete — CUDA graphs and mask cache ready!")
        except Exception as e:
            logger.warning(f"TTS mask cache priming failed ({e}); first real call may be slow.")
            logger.info("TTS warmup complete — CUDA graphs ready!")

    def _generate_audio(self, text: str) -> bytes:
        """Call internal generation with the default language."""
        return self._generate_audio_with_lang(text, self._opts.language)

    def _generate_audio_with_lang(self, text: str, language: str) -> bytes:
        """Generate audio for the given text and return raw PCM int16 bytes.
        Thread-safe: serialized via _gen_lock to prevent concurrent GPU usage.
        NOTE: text should already be cleaned by format_for_tts before calling this."""
        if not text or not text.strip():
            return b""

        # Budget: Japanese ≈ 4 chars/s, English ≈ 12 chars/s. 2.5× safety.
        # Ensure max_new_tokens is at least 1s (12 tokens) and doesn't hit context wall
        chars_per_sec = 4.0 if language == "Japanese" else 12.0
        max_new_tokens = int(len(text) / chars_per_sec * 2.5 * 12)
        max_new_tokens = max(12, min(max_new_tokens, self._opts.max_seq_len - 100))

        with self._gen_lock:
            try:
                audio_np, sample_rate = self._model.generate_voice_clone(
                    text=text,
                    ref_audio=self._opts.ref_audio,
                    ref_text=self._opts.ref_text,
                    language=language,
                    max_new_tokens=max_new_tokens,
                    append_silence=False,
                    repetition_penalty=1.2,
                )
                audio_data = _trim_silence(audio_np[0])

                audio_int16 = (audio_data * 32767).clip(-32768, 32767).astype(np.int16)
                return audio_int16.tobytes()
            except Exception as e:
                logger.error(f"TTS generation failed: {e}")
                return b""

    async def _generate_audio_stream_with_lang_async(self, text: str, language: str):
        """Generate audio in streaming chunks using an async generator."""
        if not text or not text.strip():
            return

        chars_per_sec = 4.0 if language == "Japanese" else 12.0
        max_new_tokens = int(len(text) / chars_per_sec * 2.5 * 12)
        max_new_tokens = max(12, min(max_new_tokens, self._opts.max_seq_len - 100))

        loop = asyncio.get_event_loop()
        q = asyncio.Queue()

        def _worker():
            try:
                with self._gen_lock:
                    gen = self._model.generate_voice_clone_streaming(
                        text=text,
                        language=language,
                        ref_audio=self._opts.ref_audio,
                        ref_text=self._opts.ref_text,
                        max_new_tokens=max_new_tokens,
                        chunk_size=8,
                        append_silence=False,
                        repetition_penalty=1.2,
                    )
                    for audio_np, sr, timing in gen:
                        audio_int16 = (audio_np * 32767).clip(-32768, 32767).astype(np.int16)
                        loop.call_soon_threadsafe(q.put_nowait, audio_int16.tobytes())
                loop.call_soon_threadsafe(q.put_nowait, None)
            except Exception as e:
                logger.error(f"TTS stream generation failed: {e}")
                loop.call_soon_threadsafe(q.put_nowait, None)

        threading.Thread(target=_worker, daemon=True).start()

        while True:
            chunk = await q.get()
            if chunk is None:
                break
            yield chunk

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

        # Non-streaming mode: auto-starts a single segment
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
    """Streaming: buffers LLM text into sentences, synthesizes each as one continuous audio stream."""

    def __init__(self, tts_instance: AuraTTS, opts: _TTSOptions, conn_options):
        super().__init__(tts=tts_instance, conn_options=conn_options or tts.APIConnectOptions())
        self._tts_instance = tts_instance
        self._opts = opts

    async def _run(self, output_emitter):
        self._tts_instance._ensure_model()

        # Use non-streaming mode (single auto-segment) to avoid segment count mismatch
        output_emitter.initialize(
            request_id=str(uuid.uuid4()),
            sample_rate=SAMPLE_RATE,
            num_channels=NUM_CHANNELS,
            mime_type="audio/pcm",
            stream=False,
        )

        tokenizer = tokenize.basic.SentenceTokenizer(min_sentence_len=3)
        token_stream = tokenizer.stream()
        expr_tasks = set()
        # Shared emotion buffer: _process_input writes latest emotions, _synthesize consumes
        emotion_buffer: list = []

        import re as _re

        async def _process_input():
            """Feed LLM tokens to the sentence tokenizer with expression tags stripped out.

            Tags are detected statelessly across chunk boundaries (e.g. '[ang' + 'ry, sad]')
            for emotion_buffer, but are NEVER passed to the tokenizer. This prevents
            SentenceTokenizer from splitting mid-tag on punctuation inside brackets
            (e.g. '[smile, sad, show up!]' would produce a false sentence boundary at '!')."""
            first_text = True
            tag_acc = ""
            in_tag = False

            async for data in self._input_ch:
                if isinstance(data, self._FlushSentinel):
                    token_stream.flush()
                else:
                    if first_text and data.strip():
                        first_text = False
                        start_t = getattr(self._tts_instance, "_agent_turn_start", None)
                        if start_t:
                            llm_ttft = time.time() - start_t
                            logger.info(f"[Metrics] LLM Time-to-First-Token: {llm_ttft:.3f}s")

                    # Single pass: detect emotions AND build clean text for the tokenizer.
                    # Characters inside [...] go to tag_acc only — never to clean_text.
                    clean_text = ""
                    for ch in data:
                        if ch == '[' and not in_tag:
                            in_tag = True
                            tag_acc = ch
                        elif in_tag:
                            tag_acc += ch
                            if ch == ']':
                                in_tag = False
                                detected = VTUBE.detect_emotion(tag_acc)
                                if detected:
                                    emotion_buffer[:] = detected
                                tag_acc = ""
                        else:
                            clean_text += ch

                    clean_text = clean_text.replace('。', '. ').replace('！', '! ').replace('？', '? ')
                    if clean_text.strip():
                        token_stream.push_text(clean_text)

            token_stream.end_input()

        async def _synthesize():
            """Read sentences from the tokenizer and synthesize each, streaming audio chunks
            to the emitter as they arrive (~440ms per chunk) to prevent buffer underruns.

            Streaming via generate_voice_clone_streaming delivers the first audio chunk after
            ~8 codec steps (~440ms), keeping the LiveKit audio queue fed without waiting for a
            full sentence to complete. This eliminates 'flush audio emitter due to slow audio
            generation' flushes that occurred when short sentences played out before the next
            full-sentence generation finished.

            Expression timing uses a text-length estimate before streaming starts so that
            VTUBE/BRIDGE fire when the audio actually reaches the speaker, then the playhead
            is corrected with the real duration once all chunks are collected.
            """
            # Approximate latency until the first streaming chunk is ready:
            # 8 codec steps x ~55 ms/step = ~440 ms.
            FIRST_CHUNK_DELAY = 0.44

            try:
                async for ev in token_stream:
                    raw_sentence = ev.token
                    logger.debug(f"[Tokenizer] raw: {repr(raw_sentence[:120])}")

                    # BREAK LONG SENTENCES INTO PIECES to avoid TTS glitches and hit max context
                    text_chunks = _split_text(raw_sentence, max_chars=85)

                    for chunk in text_chunks:
                        # Detect if the chunk is primarily Japanese
                        has_japanese = any(
                            '぀' <= char <= 'ヿ' or '一' <= char <= '鿿'
                            for char in chunk
                        )
                        lang = "Japanese" if has_japanese else "English"

                        # Clean sentence for TTS
                        sentence = VTUBE.format_for_tts(chunk).rstrip('-~～').strip()

                        # _process_input() converts ？！ → ?! for the sentence tokenizer.
                        # Restore fullwidth punctuation for Japanese so TTS treats them as
                        # sentence-ending markers (intonation) rather than reading them aloud.
                        if lang == "Japanese":
                            sentence = sentence.replace('?', '？').replace('!', '！')

                        # Skip if sentence contains NO alphanumeric characters (stripped tag remnants)
                        if not any(c.isalnum() for c in sentence):
                            continue

                        try:
                            emotions = list(emotion_buffer) if emotion_buffer else []
                            start_gen_time = time.time()

                            # Estimate duration from text length so expression tasks can be
                            # scheduled before streaming audio arrives.
                            chars_per_sec = 4.0 if lang == "Japanese" else 12.0
                            estimated_duration = max(0.5, len(sentence) / chars_per_sec)

                            now = time.time()
                            if not hasattr(self, '_playhead') or self._playhead < now + FIRST_CHUNK_DELAY:
                                self._playhead = now + FIRST_CHUNK_DELAY

                            # delay_until_play accounts for first-chunk streaming latency so
                            # the expression fires when audio actually reaches the speaker.
                            delay_until_play = max(0.0, self._playhead - now)
                            self._reset_token = getattr(self, '_reset_token', 0) + 1
                            current_token = self._reset_token

                            async def _fire_expression(em_list, delay_start, est_dur):
                                try:
                                    if delay_start > 0:
                                        await asyncio.sleep(delay_start)
                                    if em_list:
                                        await asyncio.gather(
                                            VTUBE.set_expression(em_list),
                                            BRIDGE.send_expression(em_list, est_dur),
                                        )
                                except Exception as e:
                                    logger.debug(f"Expression trigger error: {e}")

                            t_expr = asyncio.create_task(
                                _fire_expression(emotions, delay_until_play, estimated_duration)
                            )
                            expr_tasks.add(t_expr)
                            t_expr.add_done_callback(expr_tasks.discard)

                            # Advance playhead by estimated duration so back-to-back sentences
                            # schedule their expressions correctly before actual duration is known.
                            self._playhead += estimated_duration

                            # Streaming: push audio chunks as they arrive (~440ms each).
                            # This keeps the emitter queue fed without waiting for a full sentence,
                            # eliminating "flush audio emitter due to slow audio generation" events.
                            pcm_chunks = []
                            async for audio_chunk in self._tts_instance._generate_audio_stream_with_lang_async(sentence, lang):
                                output_emitter.push(audio_chunk)
                                pcm_chunks.append(audio_chunk)

                            if not pcm_chunks:
                                continue

                            pcm_bytes = b''.join(pcm_chunks)
                            actual_duration = len(pcm_bytes) / (SAMPLE_RATE * NUM_CHANNELS * 2)
                            logger.info(
                                f"[Metrics] TTS gen {time.time() - start_gen_time:.3f}s "
                                f"({actual_duration:.2f}s audio): '{sentence[:50]}'"
                            )

                            # Correct the playhead for actual vs estimated duration so the next
                            # sentence's expression timing stays accurate.
                            self._playhead += actual_duration - estimated_duration

                            self._reset_token = getattr(self, '_reset_token', 0) + 1
                            current_token = self._reset_token

                            async def _reset_expression(delay_to_end, token):
                                try:
                                    if delay_to_end > 0:
                                        await asyncio.sleep(delay_to_end + 0.3)
                                    if getattr(self, '_reset_token', -1) == token:
                                        await asyncio.gather(
                                            VTUBE.reset_to_neutral(),
                                            BRIDGE.send_neutral(),
                                        )
                                except asyncio.CancelledError:
                                    await asyncio.gather(VTUBE.reset_to_neutral(), BRIDGE.send_neutral())
                                except Exception:
                                    pass

                            reset_delay = self._playhead - time.time()
                            t_reset = asyncio.create_task(_reset_expression(reset_delay, current_token))
                            expr_tasks.add(t_reset)
                            t_reset.add_done_callback(expr_tasks.discard)

                        except Exception as e:
                            logger.error(f"TTS chunk generation failed: {e}")
                            if torch.cuda.is_available():
                                torch.cuda.empty_cache()
            finally:
                now = time.time()
                playhead = getattr(self, '_playhead', now)
                delay = max(0.0, playhead - now)

                async def _final_reset():
                    if delay > 0:
                        await asyncio.sleep(delay + 0.3)

                    # FINAL RESET: Cancel pending expression tasks and return to neutral
                    for t in list(expr_tasks):
                        t.cancel()
                    if expr_tasks:
                        await asyncio.gather(*expr_tasks, return_exceptions=True)

                    try:
                        await asyncio.gather(
                            VTUBE.reset_to_neutral(),
                            BRIDGE.send_neutral(),
                        )
                        logger.debug("Final safety reset triggered.")
                    except: pass

                asyncio.get_event_loop().create_task(_final_reset())

        await asyncio.gather(_process_input(), _synthesize())
