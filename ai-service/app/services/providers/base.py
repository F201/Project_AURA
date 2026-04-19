"""
Provider Abstraction Layer — base types and interface.

Every LLM provider normalizes its output into the same result dict
so the rest of the system never needs to know which model is running.

Normalized result:
  { text, emotion, raw, provider, model, tool_calls }

Tool calls are always normalized to:
  [{ "id": str, "name": str, "arguments": str (JSON) }]
  — regardless of whether the provider used OpenAI function_call deltas
    or Anthropic content_block tool_use blocks.

Stream events (for future streaming endpoints):
  TextDelta  — incremental text chunk
  StreamDone — final assembled result
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncGenerator


# ── Normalized event types ────────────────────────────────────────────────────

@dataclass
class TextDelta:
    """A chunk of text from a streaming response."""
    text: str


@dataclass
class StreamDone:
    """Final event — carries the fully assembled response."""
    text: str
    emotion: str
    raw: str
    provider: str
    model: str
    tool_calls: list | None = None


# ── Error types ───────────────────────────────────────────────────────────────

class RetryableError(Exception):
    """
    Rate limit (429), server error (5xx), or transient network issue.
    The registry will retry with exponential backoff, then try the next provider.
    """
    def __init__(self, msg: str, status_code: int | None = None):
        super().__init__(msg)
        self.status_code = status_code


class NonRetryableError(Exception):
    """
    Auth failure (401) or bad request (400).
    - 401: key is wrong for this provider → skip to next provider.
    - 400: our message is malformed → no provider will fix it; abort immediately.
    """
    def __init__(self, msg: str, status_code: int | None = None):
        super().__init__(msg)
        self.status_code = status_code


# ── Helpers ───────────────────────────────────────────────────────────────────

def parse_emotion(raw: str) -> tuple[str, str]:
    """
    Extract the leading [emotion, tag] from a raw LLM response.
    Returns (emotion_string, cleaned_text).
    """
    stripped = raw.strip()
    match = re.match(r'^\[(.*?)\]', stripped)
    if match:
        return match.group(1), stripped[match.end():].strip()
    return "neutral", stripped


def make_result(
    raw: str,
    provider: str,
    model: str,
    tool_calls: list | None = None,
) -> dict:
    """Build the normalized result dict that the rest of the system expects."""
    emotion, text = parse_emotion(raw)
    return {
        "text": text,
        "emotion": emotion,
        "raw": raw,
        "provider": provider,
        "model": model,
        "tool_calls": tool_calls or None,
    }


# ── Abstract base ─────────────────────────────────────────────────────────────

class LLMProvider(ABC):
    """
    All providers implement this interface.
    `generate` is the blocking path used by the brain pipeline.
    `stream`   is the async-generator path for future streaming endpoints.

    Tool definitions follow the OpenAI schema:
      [{ "type": "function", "function": { "name": ..., "description": ...,
                                           "parameters": {...} } }]
    Providers that use a different native schema (e.g. Anthropic) translate
    internally — callers always pass the OpenAI format.
    """

    name: str = "base"

    @abstractmethod
    def generate(
        self,
        messages: list[dict],
        *,
        model: str,
        temperature: float,
        max_tokens: int,
        tools: list[dict] | None = None,
    ) -> dict:
        """
        Blocking generation. Returns the normalized result dict:
          { text, emotion, raw, provider, model, tool_calls }
        """

    @abstractmethod
    async def stream(
        self,
        messages: list[dict],
        *,
        model: str,
        temperature: float,
        max_tokens: int,
        tools: list[dict] | None = None,
    ) -> AsyncGenerator[TextDelta | StreamDone, None]:
        """
        Streaming generation.
        Yields TextDelta chunks, ends with one StreamDone.
        """
        yield  # type: ignore
