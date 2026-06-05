import pytest
from unittest.mock import MagicMock, AsyncMock
from uuid import uuid4
from app.services.memory_service import MemoryService

@pytest.fixture
def memory_service(monkeypatch):
    monkeypatch.setattr("app.services.memory_service.settings", MagicMock(
        SUPABASE_URL="http://test",
        SUPABASE_SERVICE_KEY="test-key",
        OPENAI_API_KEY="test-key",
        OPENROUTER_API_KEY=None,
        OLLAMA_BASE_URL="http://test"
    ))
    
    mock_client = MagicMock()
    monkeypatch.setattr("app.services.memory_service.create_client", lambda url, key: mock_client)
    
    # Mock Embeddings
    mock_embeddings = MagicMock()
    mock_embeddings.aembed_query = AsyncMock(return_value=[0.1, 0.2, 0.3])
    monkeypatch.setattr("app.services.memory_service.get_embeddings", lambda: mock_embeddings)
    
    service = MemoryService()
    service.client = mock_client
    service.embeddings = mock_embeddings
    return service

@pytest.mark.asyncio
async def test_get_history(memory_service):
    conv_id = uuid4()
    
    # Setup mock response
    mock_response = MagicMock()
    mock_response.data = [
        {"role": "user", "content": "hi", "emotion": "neutral", "created_at": "1"},
        {"role": "aura", "content": "hello", "emotion": "happy", "created_at": "2"}
    ]
    
    # Mock supabase fluent api
    table_mock = MagicMock()
    memory_service.client.table.return_value = table_mock
    select_mock = MagicMock()
    table_mock.select.return_value = select_mock
    eq_mock = MagicMock()
    select_mock.eq.return_value = eq_mock
    order_mock = MagicMock()
    eq_mock.order.return_value = order_mock
    limit_mock = MagicMock()
    order_mock.limit.return_value = limit_mock
    limit_mock.execute.return_value = mock_response

    history = await memory_service.get_history(conv_id, n=2)
    
    # The get_history reverses the data
    assert len(history) == 2
    assert history[0]["role"] == "assistant"
    assert history[0]["content"] == "hello"
    assert history[1]["role"] == "user"
    assert history[1]["content"] == "hi"

@pytest.mark.asyncio
async def test_get_long_term_memories(memory_service):
    identity = "test-user"
    
    mock_response = MagicMock()
    mock_response.data = [
        {"content": "fact 2", "created_at": "2"},
        {"content": "fact 1", "created_at": "1"}
    ]
    
    table_mock = MagicMock()
    memory_service.client.table.return_value = table_mock
    select_mock = MagicMock()
    table_mock.select.return_value = select_mock
    eq_mock1 = MagicMock()
    select_mock.eq.return_value = eq_mock1
    eq_mock2 = MagicMock()
    eq_mock1.eq.return_value = eq_mock2
    order_mock = MagicMock()
    eq_mock2.order.return_value = order_mock
    limit_mock = MagicMock()
    order_mock.limit.return_value = limit_mock
    limit_mock.execute.return_value = mock_response

    facts = await memory_service.get_long_term_memories(identity)
    
    assert facts == "fact 1\n---\nfact 2"

@pytest.mark.asyncio
async def test_store_and_search(memory_service):
    # Store
    table_mock = MagicMock()
    memory_service.client.table.return_value = table_mock
    insert_mock = MagicMock()
    table_mock.insert.return_value = insert_mock
    
    await memory_service.store("test memory", {"type": "test"})
    
    memory_service.embeddings.aembed_query.assert_called_with("test memory")
    insert_mock.execute.assert_called_once()
    
    # Search
    mock_response = MagicMock()
    mock_response.data = [{"content": "found memory"}]
    
    rpc_mock = MagicMock()
    memory_service.client.rpc.return_value = rpc_mock
    rpc_mock.execute.return_value = mock_response
    
    results = await memory_service.search("query", limit=1)
    
    memory_service.embeddings.aembed_query.assert_called_with("query")
    assert results == ["found memory"]
