import pytest
import time
import json
import asyncio
import os
import httpx
from uuid import uuid4
from unittest.mock import MagicMock, AsyncMock

@pytest.mark.asyncio
async def test_voice_chat_latency_and_persistence(async_client, monkeypatch):
    """
    REPRODUCTION TEST:
    1. Measure time to first token in /api/v1/chat/voice
    2. Check if add_interaction is called (unwanted persistence)
    """
    from app.core.config import settings
    from app.services.providers.base import TextDelta
    from app.services.memory_service import memory_service
    
    # Mock dependencies to simulate network delay
    async def mock_get_history(*args, **kwargs): 
        await asyncio.sleep(0.1) # Simulate DB delay
        return []
        
    async def mock_get_ltm(*args, **kwargs): 
        await asyncio.sleep(0.1) # Simulate DB delay
        return "Fact"

    async def mock_get_settings(*args, **kwargs):
        return {"model": "mock-model", "provider": "mock-provider"}

    async def mock_get_api_keys(*args, **kwargs):
        return {"openrouter_api_key": "mock-key"}

    # Track calls to add_interaction
    add_interaction_called = False
    async def mock_add_interaction(*args, **kwargs):
        nonlocal add_interaction_called
        add_interaction_called = True
        return None

    async def mock_stream(messages, **kwargs):
        # Simulate LLM start delay
        await asyncio.sleep(0.2)
        yield TextDelta(text="Hello")
        yield TextDelta(text=" world")

    monkeypatch.setattr("app.services.memory_service.MemoryService.get_history", mock_get_history)
    monkeypatch.setattr("app.services.memory_service.MemoryService.get_long_term_memories", mock_get_ltm)
    monkeypatch.setattr("app.services.memory_service.MemoryService.add_interaction", mock_add_interaction)
    monkeypatch.setattr("app.services.providers.registry.provider_registry.stream", mock_stream)
    monkeypatch.setattr("app.services.settings_service.settings_service.get_settings", mock_get_settings)
    monkeypatch.setattr("app.services.settings_service.settings_service.get_api_keys", mock_get_api_keys)

    payload = {"message": "hi", "identity": "tdd-user"}
    headers = {"Authorization": f"Bearer {settings.INTERNAL_API_KEY}"}
    
    start_time = time.time()
    first_token_time = None
    
    async with async_client.stream("POST", "/api/v1/chat/voice", json=payload, headers=headers) as response:
        assert response.status_code == 200
        
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                if first_token_time is None:
                    first_token_time = time.time() - start_time
                    print(f"\nLatency to first token: {first_token_time:.4f}s")
                data_str = line.replace("data: ", "").strip()
                if data_str == "[DONE]":
                    break

    print(f"\nLatency to first token: {first_token_time:.4f}s")
    
    # Give background tasks time to run
    await asyncio.sleep(0.1)
    
    # Assertions
    # 1. We want to fix the unwanted persistence
    assert first_token_time < 1.0, f"Latency regression: {first_token_time}s"
    
    # Verify no interaction was added yet
    assert add_interaction_called == False, "Interaction should not be saved during stream"

@pytest.mark.asyncio
async def test_session_persistence():
    """
    Verify that the /persist endpoint correctly saves multiple messages.
    """
    from uuid import uuid4
    from app.services.memory_service import memory_service
    
    identity = f"test-user-{uuid4()}"
    conv_id = await memory_service.get_or_create_conversation(identity)
    
    persist_payload = {
        "conversation_id": str(conv_id),
        "messages": [
            {"role": "user", "content": "Hello, this is a test session persistence message.", "emotion": "neutral"},
            {"role": "assistant", "content": "I am acknowledging this test session.", "emotion": "happy"}
        ]
    }
    
    from app.main import app
    
    internal_key = os.getenv("INTERNAL_API_KEY", "aura-internal-secret")
    headers = {"Authorization": f"Bearer {internal_key}"}
    
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/chat/persist", json=persist_payload, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"
        assert resp.json()["messages_persisted"] == 2
        
    # Verify in DB
    history = await memory_service.get_history(conv_id)
    assert len(history) >= 2
    assert history[-2]["content"] == "Hello, this is a test session persistence message."
    assert history[-1]["content"] == "I am acknowledging this test session."
