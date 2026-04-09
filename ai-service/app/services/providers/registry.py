"""
Provider Registry — the single entry point for LLM calls.

Responsibilities:
  1. Read active model / provider / temperature / max_tokens from settings_service
  2. Read the matching API key from settings_service (DB) or fall back to env vars
  3. Instantiate the right LLMProvider
  4. Call provider.generate() and return the normalized result

Provider inference (when `provider` field is "auto" or missing):
  model starts with "claude-"        → anthropic
  model contains "/"                 → openrouter  (e.g. "deepseek/deepseek-v3.2")
  model starts with gpt-/o1-/o3-    → openai
  model starts with llama/mistral…   → ollama
  explicit groq_ prefix              → groq
  fallback                           → openrouter
"""
from __future__ import annotations

import logging
import os
import random
import time

from app.services.providers.base import LLMProvider, RetryableError, NonRetryableError

logger = logging.getLogger(__name__)

_MAX_ATTEMPTS  = 3        # attempts per provider before giving up on it
_BACKOFF_BASE  = 1.0      # seconds; delay = base * 2^attempt + jitter

# Ordered fallback chain — first provider with an available key wins
_FALLBACK_ORDER = ["openrouter", "openai", "groq", "ollama"]

# ── Provider inference ────────────────────────────────────────────────────────

_OPENAI_PREFIXES = ("gpt-", "o1-", "o3-", "text-davinci", "babbage", "ada")
_OLLAMA_PREFIXES = ("llama", "mistral", "gemma", "phi", "qwen", "codellama", "deepseek-r1")


def infer_provider(model: str) -> str:
    m = model.lower()
    if m.startswith("claude-"):
        return "anthropic"
    if "/" in m:
        return "openrouter"
    if any(m.startswith(p) for p in _OPENAI_PREFIXES):
        return "openai"
    if any(m.startswith(p) for p in _OLLAMA_PREFIXES):
        return "ollama"
    return "openrouter"


# ── Registry ──────────────────────────────────────────────────────────────────

class ProviderRegistry:
    """
    Resolves and calls the correct LLM provider on every request.
    Providers are constructed lazily and cached by (provider_name, key_hash).
    """

    def __init__(self):
        self._cache: dict[str, LLMProvider] = {}

    # ── Public API ────────────────────────────────────────────────────────────

    def generate(
        self,
        messages: list[dict],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        tools: list[dict] | None = None,
    ) -> dict:
        # Lazy import avoids circular imports at module load time
        from app.services.settings_service import settings_service

        db = settings_service.get_settings()
        keys = settings_service.get_api_keys()

        actual_model       = model or db.get("model") or "deepseek/deepseek-v3.2"
        actual_temp        = temperature if temperature is not None else float(db.get("temperature", 0.8))
        actual_max_tokens  = max_tokens or int(db.get("max_tokens", 300))

        configured_provider = (db.get("provider") or "auto").lower()
        primary = (
            configured_provider
            if configured_provider != "auto"
            else infer_provider(actual_model)
        )

        # Build candidate list: primary first, then any fallback with an available key
        candidates = [primary] + [
            p for p in _FALLBACK_ORDER
            if p != primary and (p == "ollama" or self._pick_key(p, keys))
        ]

        call_kwargs = dict(
            model=actual_model,
            temperature=actual_temp,
            max_tokens=actual_max_tokens,
            tools=tools,
        )

        last_error: Exception | None = None

        for provider_name in candidates:
            try:
                provider = self._get_provider(provider_name, keys)
            except (ValueError, RuntimeError) as e:
                # Missing key or missing package — skip silently
                logger.debug(f"[registry] skipping {provider_name}: {e}")
                last_error = e
                continue

            logger.info(f"[registry] trying {provider_name} / {actual_model}")
            try:
                result = self._call_with_retry(provider, messages, **call_kwargs)
                if provider_name != primary:
                    logger.warning(f"[registry] fell back to {provider_name} (primary={primary} failed)")
                return result

            except NonRetryableError as e:
                last_error = e
                if e.status_code == 400:
                    # Bad request — our message is wrong, no other provider will help
                    logger.error(f"[registry] bad request ({provider_name}): {e}")
                    break
                # 401 auth failure — key is bad for this provider, try next
                logger.warning(f"[registry] auth failed for {provider_name} (HTTP {e.status_code}), trying next")
                continue

            except RetryableError as e:
                # All retries for this provider exhausted — try next
                logger.warning(f"[registry] {provider_name} exhausted retries: {e}")
                last_error = e
                continue

        logger.error(f"[registry] all providers failed. Last: {last_error}")
        return {
            "text": "I seem to be having trouble connecting right now. Please try again in a moment.",
            "emotion": "confused",
            "raw": "",
            "provider": primary,
            "model": actual_model,
            "tool_calls": None,
        }

    def _call_with_retry(self, provider: LLMProvider, messages: list[dict], **kwargs) -> dict:
        """
        Call provider.generate() with exponential backoff on RetryableError.
        Raises RetryableError if all attempts fail.
        Raises NonRetryableError immediately (no retry).
        """
        for attempt in range(_MAX_ATTEMPTS):
            try:
                return provider.generate(messages, **kwargs)
            except NonRetryableError:
                raise  # propagate immediately
            except RetryableError as e:
                if attempt == _MAX_ATTEMPTS - 1:
                    raise  # all attempts exhausted
                delay = _BACKOFF_BASE * (2 ** attempt) + random.uniform(0.0, 0.5)
                logger.warning(
                    f"[{provider.name}] attempt {attempt + 1}/{_MAX_ATTEMPTS} failed "
                    f"(status={e.status_code}): {e} — retrying in {delay:.1f}s"
                )
                time.sleep(delay)

    # ── Provider instantiation ────────────────────────────────────────────────

    def _get_provider(self, provider_name: str, keys: dict) -> LLMProvider:
        # Cache key: provider name + first 8 chars of api key (detects key rotation)
        raw_key = self._pick_key(provider_name, keys)
        cache_key = f"{provider_name}:{(raw_key or '')[:8]}"

        if cache_key not in self._cache:
            self._cache[cache_key] = self._build(provider_name, keys)

        return self._cache[cache_key]

    def _build(self, provider_name: str, keys: dict) -> LLMProvider:
        from app.services.providers.openai_compat import (
            openrouter_provider, openai_provider, groq_provider, ollama_provider,
        )
        from app.services.providers.anthropic_provider import AnthropicProvider

        if provider_name == "anthropic":
            key = self._pick_key("anthropic", keys)
            if not key:
                raise ValueError("Anthropic API key not set. Add it via the dashboard or ANTHROPIC_API_KEY env var.")
            return AnthropicProvider(api_key=key)

        if provider_name == "groq":
            key = self._pick_key("groq", keys)
            if not key:
                raise ValueError("Groq API key not set. Add it via the dashboard or GROQ_API_KEY env var.")
            return groq_provider(api_key=key)

        if provider_name == "openai":
            key = self._pick_key("openai", keys)
            if not key:
                raise ValueError("OpenAI API key not set. Add it via the dashboard or OPENAI_API_KEY env var.")
            return openai_provider(api_key=key)

        if provider_name == "ollama":
            ollama_url = (
                (keys.get("ollama_base_url") or "").strip()
                or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
            )
            return ollama_provider(base_url=ollama_url)

        # Default: openrouter
        key = self._pick_key("openrouter", keys)
        if not key:
            raise ValueError("OpenRouter API key not set. Add it via the dashboard or OPENROUTER_API_KEY env var.")
        return openrouter_provider(api_key=key)

    @staticmethod
    def _pick_key(provider_name: str, keys: dict) -> str | None:
        """DB key takes precedence over env var."""
        env_map = {
            "openrouter": "OPENROUTER_API_KEY",
            "openai":     "OPENAI_API_KEY",
            "anthropic":  "ANTHROPIC_API_KEY",
            "groq":       "GROQ_API_KEY",
        }
        db_key_map = {
            "openrouter": "openrouter_api_key",
            "openai":     "openrouter_api_key",   # share the same field for now
            "anthropic":  "anthropic_api_key",
            "groq":       "groq_api_key",
        }

        db_field = db_key_map.get(provider_name)
        db_val = (keys.get(db_field) or "").strip() if db_field else ""
        if db_val:
            return db_val

        env_var = env_map.get(provider_name)
        return os.getenv(env_var, "") if env_var else ""


provider_registry = ProviderRegistry()
