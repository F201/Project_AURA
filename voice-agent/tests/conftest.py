"""Shared pytest fixtures and helpers for voice-agent tests."""
import asyncio


async def aiter(items):
    """Async generator that yields items — used to mock streaming methods."""
    for item in items:
        yield item
