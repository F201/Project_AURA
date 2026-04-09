"""
OpenAI-compatible provider.

Covers every backend that speaks the OpenAI chat-completions API:
  • OpenRouter  (base_url = https://openrouter.ai/api/v1)
  • OpenAI      (base_url = None  → default)
  • Groq        (base_url = https://api.groq.com/openai/v1)
  • Ollama      (base_url = http://localhost:11434/v1)

Tool call normalization:
  OpenAI sends tool_calls on the response message.
  Each tool call has: id, function.name, function.arguments (JSON string).
  We surface these as [{ "id", "name", "arguments" }] in the result dict.
"""
from __future__ import annotations

import logging
from typing import AsyncGenerator

import openai as _openai_lib
from openai import OpenAI, AsyncOpenAI

from app.services.providers.base import LLMProvider, TextDelta, StreamDone, make_result, RetryableError, NonRetryableError

logger = logging.getLogger(__name__)

_OPENROUTER_HEADERS = {
    "HTTP-Referer": "http://localhost:5173",
    "X-Title": "Project AURA",
}


def _extract_tool_calls(response_message) -> list | None:
    """Normalize OpenAI tool_calls to our common schema."""
    raw_calls = getattr(response_message, "tool_calls", None)
    if not raw_calls:
        return None
    return [
        {
            "id":        tc.id,
            "name":      tc.function.name,
            "arguments": tc.function.arguments,  # already a JSON string
        }
        for tc in raw_calls
    ]


class OpenAICompatProvider(LLMProvider):

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        extra_headers: dict | None = None,
        provider_name: str = "openai",
    ):
        self.name = provider_name
        self._extra_headers = extra_headers or {}
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._async_client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        logger.info(f"[{self.name}] provider ready (base_url={base_url or 'default'})")

    # ── Blocking ──────────────────────────────────────────────────────────────

    def generate(
        self,
        messages: list[dict],
        *,
        model: str,
        temperature: float,
        max_tokens: int,
        tools: list[dict] | None = None,
    ) -> dict:
        kwargs = dict(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            extra_headers=self._extra_headers,
        )
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        try:
            response = self._client.chat.completions.create(**kwargs)
            msg = response.choices[0].message
            raw = msg.content or ""
            tool_calls = _extract_tool_calls(msg)

            # When the model only returns a tool call (no text), give a placeholder
            # so make_result always has something to parse.
            if tool_calls and not raw:
                raw = f"[tool_call: {tool_calls[0]['name']}]"

            return make_result(raw, self.name, model, tool_calls=tool_calls)

        except _openai_lib.RateLimitError as e:
            raise RetryableError(str(e), status_code=429)
        except (_openai_lib.APIConnectionError, _openai_lib.APITimeoutError) as e:
            raise RetryableError(str(e))
        except _openai_lib.InternalServerError as e:
            raise RetryableError(str(e), status_code=getattr(e, "status_code", 500))
        except _openai_lib.AuthenticationError as e:
            raise NonRetryableError(str(e), status_code=401)
        except (_openai_lib.BadRequestError, _openai_lib.NotFoundError) as e:
            raise NonRetryableError(str(e), status_code=getattr(e, "status_code", 400))
        except Exception as e:
            # Unknown error — treat as retryable so the registry can decide
            raise RetryableError(str(e))

    # ── Streaming ─────────────────────────────────────────────────────────────

    async def stream(
        self,
        messages: list[dict],
        *,
        model: str,
        temperature: float,
        max_tokens: int,
        tools: list[dict] | None = None,
    ) -> AsyncGenerator[TextDelta | StreamDone, None]:
        assembled = ""
        kwargs = dict(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            extra_headers=self._extra_headers,
        )
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        try:
            async with self._async_client.chat.completions.stream(**kwargs) as stream:
                async for chunk in stream:
                    delta = chunk.choices[0].delta.content or ""
                    if delta:
                        assembled += delta
                        yield TextDelta(text=delta)
        except Exception as e:
            logger.error(f"[{self.name}] stream error: {e}")

        result = make_result(assembled, self.name, model)
        yield StreamDone(
            text=result["text"],
            emotion=result["emotion"],
            raw=assembled,
            provider=self.name,
            model=model,
        )


# ── Named constructors ────────────────────────────────────────────────────────

def openrouter_provider(api_key: str) -> OpenAICompatProvider:
    return OpenAICompatProvider(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
        extra_headers=_OPENROUTER_HEADERS,
        provider_name="openrouter",
    )


def openai_provider(api_key: str) -> OpenAICompatProvider:
    return OpenAICompatProvider(api_key=api_key, base_url=None, provider_name="openai")


def groq_provider(api_key: str) -> OpenAICompatProvider:
    return OpenAICompatProvider(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1",
        provider_name="groq",
    )


def ollama_provider(base_url: str = "http://localhost:11434") -> OpenAICompatProvider:
    return OpenAICompatProvider(
        api_key="ollama",
        base_url=f"{base_url.rstrip('/')}/v1",
        provider_name="ollama",
    )
