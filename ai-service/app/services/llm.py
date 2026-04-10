"""
LLMService — thin facade over the Provider Abstraction Layer.

All routing logic lives in providers/registry.py.
This class exists so existing callers (brain nodes, etc.) don't need to change.
"""
import logging
import asyncio
from app.services.providers.registry import provider_registry

logger = logging.getLogger(__name__)


class LLMService:
    async def generate(
        self,
        messages: list,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict:
        return await provider_registry.generate(
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def stream(self, *args, **kwargs):
        return provider_registry.stream(*args, **kwargs)


llm_service = LLMService()
