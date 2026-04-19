"""
Anthropic / Claude provider.

Key differences from OpenAI-compatible providers:

1. System message → separate `system` parameter (not in messages list).
2. Streaming: chunks are `content_block_delta` with type "text_delta"
   (vs GPT's `choices[0].delta.content`).
3. Tool calls: come as `content_block_start` with type "tool_use"
   (vs OpenAI's `message.tool_calls`).
4. Tool definitions: Anthropic uses a different schema than OpenAI.
   We accept the OpenAI schema and translate it internally.

Normalized output is always the same result dict as every other provider.
"""
from __future__ import annotations

import json
import logging
from typing import AsyncGenerator

from app.services.providers.base import LLMProvider, TextDelta, StreamDone, make_result, RetryableError, NonRetryableError

logger = logging.getLogger(__name__)


def _split_system(messages: list[dict]) -> tuple[str, list[dict]]:
    """Separate the system prompt from the rest of the message list."""
    system_parts = []
    rest = []
    for m in messages:
        if m.get("role") == "system":
            system_parts.append(m.get("content", ""))
        else:
            rest.append(m)
    return "\n\n".join(system_parts), rest


def _openai_tools_to_anthropic(tools: list[dict]) -> list[dict]:
    """
    Translate OpenAI tool schema to Anthropic's format.

    OpenAI:   { "type": "function", "function": { "name", "description", "parameters" } }
    Anthropic: { "name", "description", "input_schema" }
    """
    result = []
    for t in tools:
        fn = t.get("function", t)  # handle both wrapped and unwrapped
        result.append({
            "name":         fn["name"],
            "description":  fn.get("description", ""),
            "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
        })
    return result


def _extract_tool_calls(content_blocks) -> list | None:
    """Normalize Anthropic tool_use blocks to our common schema."""
    calls = [
        {
            "id":        block.id,
            "name":      block.name,
            "arguments": json.dumps(block.input),
        }
        for block in content_blocks
        if getattr(block, "type", None) == "tool_use"
    ]
    return calls or None


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, api_key: str):
        try:
            import anthropic as _anthropic
            self._anthropic = _anthropic
            self._client = _anthropic.Anthropic(api_key=api_key)
            self._async_client = _anthropic.AsyncAnthropic(api_key=api_key)
            logger.info("[anthropic] provider ready")
        except ImportError:
            raise RuntimeError(
                "The 'anthropic' package is required for the Anthropic provider. "
                "Run: pip install anthropic"
            )

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
        system, user_messages = _split_system(messages)
        kwargs = dict(
            model=model,
            system=system,
            messages=user_messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if tools:
            kwargs["tools"] = _openai_tools_to_anthropic(tools)

        _a = self._anthropic  # local ref so except clauses can reference it
        try:
            response = self._client.messages.create(**kwargs)

            # Text from text blocks
            raw = "".join(
                block.text for block in response.content
                if getattr(block, "type", None) == "text"
            )
            tool_calls = _extract_tool_calls(response.content)

            if tool_calls and not raw:
                raw = f"[tool_call: {tool_calls[0]['name']}]"

            return make_result(raw, self.name, model, tool_calls=tool_calls)

        except _a.RateLimitError as e:
            raise RetryableError(str(e), status_code=429)
        except (_a.APIConnectionError, _a.APITimeoutError) as e:
            raise RetryableError(str(e))
        except _a.InternalServerError as e:
            raise RetryableError(str(e), status_code=getattr(e, "status_code", 500))
        except _a.AuthenticationError as e:
            raise NonRetryableError(str(e), status_code=401)
        except _a.BadRequestError as e:
            raise NonRetryableError(str(e), status_code=400)
        except Exception as e:
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
        system, user_messages = _split_system(messages)
        assembled = ""
        kwargs = dict(
            model=model,
            system=system,
            messages=user_messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if tools:
            kwargs["tools"] = _openai_tools_to_anthropic(tools)

        try:
            async with self._async_client.messages.stream(**kwargs) as stream:
                async for event in stream:
                    if (
                        event.type == "content_block_delta"
                        and hasattr(event, "delta")
                        and getattr(event.delta, "type", None) == "text_delta"
                    ):
                        chunk = event.delta.text or ""
                        if chunk:
                            assembled += chunk
                            yield TextDelta(text=chunk)
        except Exception as e:
            logger.error(f"[anthropic] stream error: {e}")

        result = make_result(assembled, self.name, model)
        yield StreamDone(
            text=result["text"],
            emotion=result["emotion"],
            raw=assembled,
            provider=self.name,
            model=model,
        )
