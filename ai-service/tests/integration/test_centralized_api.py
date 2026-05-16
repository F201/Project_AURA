import pytest
from uuid import uuid4

@pytest.mark.asyncio
async def test_session_unauthorized(async_client):
    """RED: Verify session endpoint rejects requests without internal key."""
    response = await async_client.post("/api/v1/memory/session", json={"identity": "aura-user"})
    assert response.status_code == 403
    assert "credentials" in response.json()["detail"].lower()

@pytest.mark.asyncio
async def test_session_authorized(async_client, monkeypatch):
    """GREEN: Verify session endpoint works with internal key."""
    from app.core.config import settings
    
    # Mock MemoryService to avoid real DB calls
    mock_id = str(uuid4())
    
    async def mock_get_or_create(identity, title):
        return mock_id
    
    async def mock_get_ltm(identity):
        return "You like coffee."
    
    monkeypatch.setattr("app.api.v1.memory.memory_service.get_or_create_conversation", mock_get_or_create)
    monkeypatch.setattr("app.api.v1.memory.memory_service.get_long_term_memories", mock_get_ltm)

    response = await async_client.post(
        "/api/v1/memory/session",
        json={"identity": "aura-user"},
        headers={"Authorization": f"Bearer {settings.INTERNAL_API_KEY}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["conversation_id"] == mock_id
    assert data["long_term_memory"] == "You like coffee."

@pytest.mark.asyncio
async def test_extract_memory(async_client, monkeypatch):
    """Verify memory extraction endpoint."""
    from app.core.config import settings
    
    # Mock extract logic and provider
    async def mock_save_ltm(identity, facts, conversation_id=None):
        return None
    
    async def mock_generate(messages, provider=None):
        yield "Likes tea."
    
    monkeypatch.setattr("app.api.v1.memory.memory_service.save_long_term_memory", mock_save_ltm)
    monkeypatch.setattr("app.api.v1.memory.provider_registry.generate", mock_generate)
    
    response = await async_client.post(
        "/api/v1/memory/extract",
        json={"conversation_id": str(uuid4()), "identity": "aura-user", "chat_text": "I like tea."},
        headers={"Authorization": f"Bearer {settings.INTERNAL_API_KEY}"}
    )
    
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert "tea" in response.json()["extracted"].lower()

@pytest.mark.asyncio
async def test_voice_chat_stream(async_client, monkeypatch):
    """Verify voice chat streaming endpoint returns SSE events."""
    from app.core.config import settings
    from app.services.providers.base import TextDelta
    
    # Mock gather dependencies
    async def mock_get_history(*args, **kwargs): return []
    async def mock_search(*args, **kwargs): return []
    async def mock_get_ltm(*args, **kwargs): return "Memory"
    async def mock_add_interaction(*args, **kwargs): return None
    async def mock_store(*args, **kwargs): return None
    
    async def mock_stream(messages, provider=None):
        yield TextDelta(text="[happy] Hello world!")
    
    monkeypatch.setattr("app.services.memory_service.MemoryService.get_history", mock_get_history)
    monkeypatch.setattr("app.services.memory_service.MemoryService.search", mock_search)
    monkeypatch.setattr("app.services.memory_service.MemoryService.get_long_term_memories", mock_get_ltm)
    monkeypatch.setattr("app.services.memory_service.MemoryService.add_interaction", mock_add_interaction)
    monkeypatch.setattr("app.services.memory_service.MemoryService.store", mock_store)
    monkeypatch.setattr("app.services.providers.registry.provider_registry.stream", mock_stream)

    payload = {"message": "hi", "identity": "aura-user"}
    headers = {"Authorization": f"Bearer {settings.INTERNAL_API_KEY}"}
    
    async with async_client.stream("POST", "/api/v1/chat/voice", json=payload, headers=headers) as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        
        events = []
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                events.append(line.replace("data: ", "").strip())
        
        assert any("Hello world!" in e for e in events)
        assert events[-1] == "[DONE]"
