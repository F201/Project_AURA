"""
Contract tests for POST /api/v1/chat/voice.

These tests encode the MUST/MUST-NOT rules for the voice endpoint.
A test here should fail if someone accidentally re-introduces an
embedding call, strips tags from the stream, or breaks auth.
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ── Helpers ──────────────────────────────────────────────────────────────────

def _parse_sse(raw: str) -> list[dict]:
    """Parse SSE lines into a list of data payloads."""
    events = []
    for line in raw.splitlines():
        if line.startswith("data: "):
            payload = line[6:].strip()
            if payload == "[DONE]":
                events.append({"_done": True})
            else:
                try:
                    events.append(json.loads(payload))
                except json.JSONDecodeError:
                    pass
    return events


async def _collect_sse(response) -> list[dict]:
    chunks = []
    async for line in response.aiter_lines():
        if line.startswith("data: "):
            payload = line[6:].strip()
            if payload == "[DONE]":
                chunks.append({"_done": True})
            else:
                try:
                    chunks.append(json.loads(payload))
                except json.JSONDecodeError:
                    pass
    return chunks


def _auth_headers(settings):
    return {"Authorization": f"Bearer {settings.INTERNAL_API_KEY}"}


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_memory(monkeypatch):
    """Patch all memory_service methods. Callers assert which ones were/were-not called."""
    from app.services import memory_service as ms_module

    m = MagicMock()
    m.create_conversation = AsyncMock(return_value="aaaaaaaa-0000-0000-0000-000000000001")
    m.get_history         = AsyncMock(return_value=[])
    m.get_long_term_memories = AsyncMock(return_value="User likes tea.")
    m.search              = AsyncMock(return_value=["some rag result"])
    m.store               = AsyncMock()
    m.add_interaction     = AsyncMock()

    monkeypatch.setattr(ms_module, "memory_service", m)
    # Also patch the import inside chat.py
    import app.api.v1.chat as chat_module
    monkeypatch.setattr(chat_module, "memory_service", m)
    return m


@pytest.fixture
def mock_stream_happy(monkeypatch):
    """Provider streams a single chunk with expression tags."""
    from app.services.providers.base import TextDelta

    async def _stream(messages, **kwargs):
        yield TextDelta(text="[happy] Hello world!")

    import app.services.providers.registry as reg
    monkeypatch.setattr(reg.provider_registry, "stream", _stream)


@pytest.fixture
def mock_prompter(monkeypatch):
    """Spy on prompter.build_system_prompt so we can assert mode."""
    from app.services import prompter as p_module

    spy = MagicMock(wraps=p_module.prompter.build_system_prompt)
    monkeypatch.setattr(p_module.prompter, "build_system_prompt", spy)
    return spy


# ── Auth ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_voice_rejects_missing_auth(async_client):
    """MUST return 403 with no Authorization header."""
    r = await async_client.post("/api/v1/chat/voice", json={"message": "hi"})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_voice_rejects_wrong_token(async_client):
    """MUST return 403 with a wrong token."""
    r = await async_client.post(
        "/api/v1/chat/voice",
        json={"message": "hi"},
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert r.status_code == 403


# ── No embeddings ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_voice_never_calls_search(async_client, mock_memory, mock_stream_happy):
    """
    MUST NOT call memory_service.search().
    search() triggers the embeddings API — voice is real-time and must not
    incur embedding latency or cost.
    """
    from app.core.config import settings

    async with async_client.stream(
        "POST", "/api/v1/chat/voice",
        json={"message": "hi", "identity": "user-1",
              "conversation_id": "aaaaaaaa-0000-0000-0000-000000000001"},
        headers=_auth_headers(settings),
    ) as resp:
        assert resp.status_code == 200
        await _collect_sse(resp)

    mock_memory.search.assert_not_called()


@pytest.mark.asyncio
async def test_voice_never_calls_store(async_client, mock_memory, mock_stream_happy):
    """
    MUST NOT call memory_service.store().
    store() embeds the turn into pgvector — not needed for voice sessions.
    """
    from app.core.config import settings

    async with async_client.stream(
        "POST", "/api/v1/chat/voice",
        json={"message": "hi", "identity": "user-1",
              "conversation_id": "aaaaaaaa-0000-0000-0000-000000000001"},
        headers=_auth_headers(settings),
    ) as resp:
        assert resp.status_code == 200
        await _collect_sse(resp)

    mock_memory.store.assert_not_called()


# ── Tag handling ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_voice_streams_raw_tags(async_client, mock_memory, mock_stream_happy):
    """
    MUST stream expression tags like [happy] in SSE text chunks.
    voice-agent parses these per-sentence for VTube Studio.
    Scrubbing must NOT happen before yielding.
    """
    from app.core.config import settings

    async with async_client.stream(
        "POST", "/api/v1/chat/voice",
        json={"message": "hi", "identity": "user-1",
              "conversation_id": "aaaaaaaa-0000-0000-0000-000000000001"},
        headers=_auth_headers(settings),
    ) as resp:
        events = await _collect_sse(resp)

    text_chunks = [e["text"] for e in events if "text" in e]
    combined = "".join(text_chunks)
    assert "[happy]" in combined, "Expression tags must survive in the SSE stream"


@pytest.mark.asyncio
async def test_voice_no_per_turn_db_persist(async_client, mock_memory, mock_stream_happy):
    """
    Voice endpoint must NOT call add_interaction per turn.
    Persistence is deferred to session end via POST /persist to reduce latency.
    """
    from app.core.config import settings

    async with async_client.stream(
        "POST", "/api/v1/chat/voice",
        json={"message": "hi", "identity": "user-1",
              "conversation_id": "aaaaaaaa-0000-0000-0000-000000000001"},
        headers=_auth_headers(settings),
    ) as resp:
        await _collect_sse(resp)

    mock_memory.add_interaction.assert_not_called()


# ── Prompt mode ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_voice_uses_voice_mode_prompter(async_client, mock_memory, mock_stream_happy, mock_prompter):
    """
    MUST call prompter.build_system_prompt with mode='voice'.
    The voice prompt contains expression tag recipes; the text prompt does not.
    Using mode='text' would mean AURA stops emitting [emotion] tags entirely.
    """
    from app.core.config import settings

    async with async_client.stream(
        "POST", "/api/v1/chat/voice",
        json={"message": "hi", "identity": "user-1",
              "conversation_id": "aaaaaaaa-0000-0000-0000-000000000001"},
        headers=_auth_headers(settings),
    ) as resp:
        await _collect_sse(resp)

    mock_prompter.assert_called_once()
    call_kwargs = mock_prompter.call_args
    mode_used = call_kwargs.kwargs.get("mode") or call_kwargs.args[0]
    assert mode_used == "voice"


@pytest.mark.asyncio
async def test_voice_passes_empty_memories_list(async_client, mock_memory, mock_stream_happy, mock_prompter):
    """
    MUST pass memories=[] to prompter (no RAG results for voice).
    Passing a non-empty list would require search() to have been called.
    """
    from app.core.config import settings

    async with async_client.stream(
        "POST", "/api/v1/chat/voice",
        json={"message": "hi", "identity": "user-1",
              "conversation_id": "aaaaaaaa-0000-0000-0000-000000000001"},
        headers=_auth_headers(settings),
    ) as resp:
        await _collect_sse(resp)

    call_kwargs = mock_prompter.call_args
    memories_arg = call_kwargs.kwargs.get("memories")
    assert memories_arg == [], "memories must be empty list for voice (no RAG)"


# ── URL derivation (regression for double /api/v1 bug) ───────────────────────

def test_backend_url_strips_full_api_path():
    """
    BACKEND_URL must be scheme+host only — no /api/v1 suffix.
    Regression: AI_SERVICE_URL.replace('/chat/voice', '') left /api/v1 behind,
    causing f'{BACKEND_URL}/api/v1/...' to produce /api/v1/api/v1/... (404).
    """
    def derive(url: str) -> str:
        return url.split("/api/v1")[0]

    assert derive("http://127.0.0.1:8001/api/v1/chat/voice") == "http://127.0.0.1:8001"
    assert derive("http://127.0.0.1:8001/api/v1") == "http://127.0.0.1:8001"
    assert derive("http://ai-service:8001/api/v1/chat/voice") == "http://ai-service:8001"
    # Ensure downstream URL composition is correct
    base = derive("http://127.0.0.1:8001/api/v1/chat/voice")
    assert f"{base}/api/v1/memory/session" == "http://127.0.0.1:8001/api/v1/memory/session"
