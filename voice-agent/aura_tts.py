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
        ref_text: str,
        language: str = "English",
        dtype: torch.dtype = torch.bfloat16,
        max_seq_len: int = 384,  # Further reduced for 6GB GPUs (from 512)
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
        self._gen_lock = threading.Lock()  # Serialize GPU inference (CUDA graphs can't run concurrently)

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
            if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                torch.mps.empty_cache()
            logger.info(f"Loading FasterQwen3TTS: {self._opts.model_name} (max_seq_len={self._opts.max_seq_len})")
            self._model = FasterQwen3TTS.from_pretrained(
                self._opts.model_name,
                dtype=self._opts.dtype,
                max_seq_len=self._opts.max_seq_len,
            )
            logger.info("FasterQwen3TTS loaded and ready!")

    def warmup(self):
        """Run a short dummy generation to trigger CUDA graph capture at boot."""
        self._ensure_model()
        logger.info("Warming up TTS with dummy generation...")
        with self._gen_lock:
            self._model.generate_voice_clone(
                text="Hello.",
                ref_audio=self._opts.ref_audio,
                ref_text=self._opts.ref_text,
                language="English",
            )
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

        # Budget: Japanese ≈ 4 chars/s, English ≈ 12 chars/s. 3× safety, min 2 s.
        chars_per_sec = 4.0 if language == "Japanese" else 12.0
        max_new_tokens = max(24, int(len(text) / chars_per_sec * 3.0 * 12))

        with self._gen_lock:
            audio_np, sample_rate = self._model.generate_voice_clone(
                text=text,
                ref_audio=self._opts.ref_audio,
                ref_text=self._opts.ref_text,
                language=language,
                max_new_tokens=max_new_tokens,
                append_silence=False,
                repetition_penalty=1.15,
            )
            audio_data = _trim_silence(audio_np[0])

            # Convert float32 -> int16 PCM bytes
            audio_int16 = (audio_data * 32767).clip(-32768, 32767).astype(np.int16)
            return audio_int16.tobytes()

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

        # Buffer incoming text tokens into sentences
        # Use a custom bilingual sentence splitter that handles BOTH
        # English (.!?) AND Japanese (。！？) punctuation.
        tokenizer = tokenize.basic.SentenceTokenizer(
            min_sentence_len=3,
            # Custom delimiters: standard + Japanese full-width punctuation
        )
        token_stream = tokenizer.stream()
        
        # Track pending reset task so we can cancel it when a new sentence starts
        _pending_reset: Optional[asyncio.Task] = None

        async def _process_input():
            """Read text from the input channel and push to the tokenizer."""
            full_llm_response = ""
            async for data in self._input_ch:
                if isinstance(data, self._FlushSentinel):
                    token_stream.flush()
                else:
                    # Replace Japanese sentence-ending punctuation with ASCII equivalents
                    text = data
                    full_llm_response += text
                    text = text.replace('。', '. ')
                    text = text.replace('！', '! ')
                    text = text.replace('？', '? ')
                    token_stream.push_text(text)
            
            logger.info(f"\n====== FULL LLM RESPONSE ======\n{full_llm_response}\n===============================\n")
            token_stream.end_input()

        async def _synthesize():
            """Read complete sentences from the tokenizer and synthesize."""
            nonlocal _pending_reset
            
            async for ev in token_stream:
                raw_sentence = ev.token
                
                # Detect if the sentence is primarily Japanese
                has_japanese = any('\u3040' <= char <= '\u30ff' or '\u4e00' <= char <= '\u9fff' for char in raw_sentence)
                lang = "Japanese" if has_japanese else "English"

                # Clean sentence for TTS
                sentence = VTUBE.format_for_tts(raw_sentence)
                
                # Strip trailing dashes and tildes that TTS speaks as "minus"
                sentence = sentence.rstrip('-~～')
                sentence = sentence.strip()
                
                if not any(c.isalnum() for c in sentence):
                    continue

                _INSTRUCTION_STARTERS = (
                    'your mood ', 'your task ', 'your objective ', 'your goal ',
                    'use a ', 'use the ', 'use your ',
                    'be open', 'be cheerful', 'be warm', 'be friendly', 'be mischievous',
                    'ask them', 'ask what', 'ask how', 'ask if ', 'ask about',
                    'then ask', 'then, ask', 'then invite',
                    'you might ', 'you should ', 'you can also',
                    'start by ', 'start with ',
                    'remember to ', 'make sure ', 'keep in mind',
                    'greet them', 'introduce yourself',
                    'sprinkle in', 'hint that', 'suggest that',
                    'invite conversation', 'invite them',
                )
                if any(sentence.lower().startswith(s) for s in _INSTRUCTION_STARTERS):
                    logger.debug(f"Skipping instruction-like sentence: {sentence[:60]!r}")
                    continue

                # Generate audio and calculate duration
                # PCM 16-bit means 2 bytes per sample
                loop = asyncio.get_event_loop()
                try:
                    pcm_bytes = await loop.run_in_executor(
                        None, self._tts_instance._generate_audio_with_lang, sentence, lang
                    )
                    
                    if not pcm_bytes:
                        continue
                        
                    duration = len(pcm_bytes) / (SAMPLE_RATE * NUM_CHANNELS * 2)
                    
                    # SAFETY: Cap audio at 15 seconds per sentence to prevent TTS runaway
                    MAX_SENTENCE_DURATION = 15.0
                    if duration > MAX_SENTENCE_DURATION:
                        logger.warning(f"TTS generated {duration:.1f}s for '{sentence[:30]}' - truncating to {MAX_SENTENCE_DURATION}s")
                        max_bytes = int(MAX_SENTENCE_DURATION * SAMPLE_RATE * NUM_CHANNELS * 2)
                        pcm_bytes = pcm_bytes[:max_bytes]
                        duration = MAX_SENTENCE_DURATION

                    now = time.time()
                    if not hasattr(self, '_playhead') or self._playhead < now:
                        self._playhead = now
                        
                    self._reset_token = getattr(self, '_reset_token', 0) + 1
                    current_token = self._reset_token
                        
                    delay_until_play = self._playhead - now
                    self._playhead += duration
                    
                    emotions = VTUBE.detect_emotion(raw_sentence)
                    
                    async def _sync_expression(em_list, delay_start, dur, token):
                        try:
                            if delay_start > 0:
                                await asyncio.sleep(delay_start)

                            linger_time = 1.2  # let emotion linger for 1.2s after speech ends
                            total_dur = dur + linger_time

                            if em_list:
                                await asyncio.gather(
                                    VTUBE.set_expression(em_list),
                                    BRIDGE.send_expression(em_list, total_dur),
                                )

                            await asyncio.sleep(total_dur)  # wait for audio + linger duration

                            if getattr(self, '_reset_token', -1) == token:
                                await asyncio.gather(
                                    VTUBE.reset_to_neutral(),
                                    BRIDGE.send_neutral(),
                                )
                        except Exception as e:
                            logger.debug(f"VTS sync error (non-fatal): {e}")

                    asyncio.create_task(_sync_expression(emotions, delay_until_play, duration, current_token))

                    output_emitter.push(pcm_bytes)
                    logger.debug(f"Synthesized {duration:.2f}s audio for: {sentence} (Lang: {lang})")
                    
                except Exception as e:
                    logger.error(f"TTS generation failed for sentence '{sentence}': {e}")
                    import gc
                    gc.collect()
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                        torch.mps.empty_cache()


        # Run input processing and synthesis concurrently
        await asyncio.gather(_process_input(), _synthesize())
