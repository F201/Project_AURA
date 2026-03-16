"""
Phase 0 tests — AURA TTS HTTP Service
All GPU calls are mocked so these run in CI without CUDA.

Run:
    cd voice-agent
    pytest tests/test_tts_server.py -v
"""
import sys
import os
import types
import numpy as np
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# ── Stub out heavy imports before tts_server is imported ────────────────────
# We need to stub faster_qwen3_tts so the module-level import succeeds in CI.

def _make_stubs():
    # faster_qwen3_tts package
    fqt_pkg = types.ModuleType("faster_qwen3_tts")
    fqt_model = types.ModuleType("faster_qwen3_tts.model")

    class _FakeTTS:
        @classmethod
        def from_pretrained(cls, *a, **kw):
            return cls()
        def generate_voice_clone(self, *a, **kw):
            # Returns (audio_array, sample_rate) — 0.1s of silence
            audio = np.zeros(2400, dtype=np.float32)
            return audio, 24000
        def _warmup(self, *a, **kw):
            pass

    fqt_model.FasterQwen3TTS = _FakeTTS
    fqt_pkg.model = fqt_model
    sys.modules.setdefault("faster_qwen3_tts", fqt_pkg)
    sys.modules.setdefault("faster_qwen3_tts.model", fqt_model)

    # torch (only if not already installed in the test env)
    if "torch" not in sys.modules:
        torch_mod = types.ModuleType("torch")
        torch_mod.bfloat16 = "bfloat16"
        torch_mod.cuda = MagicMock(is_available=MagicMock(return_value=False))
        backends = MagicMock()
        backends.mps.is_available.return_value = False
        torch_mod.backends = backends
        sys.modules["torch"] = torch_mod

_make_stubs()

# ── Now import the app ────────────────────────────────────────────────────────
# Patch _load_model so it never touches the filesystem / GPU during tests.
import tts_server  # noqa: E402  (must come after stubs)

_DUMMY_PCM = np.zeros(2400, dtype=np.float32)


def _fake_model():
    m = MagicMock()
    # Returns (list_of_arrays, sample_rate) matching real model output
    m.generate_voice_clone.return_value = ([_DUMMY_PCM], 24000)
    return m


@pytest.fixture(autouse=True)
def patch_model(monkeypatch):
    """Replace the GPU model with a lightweight mock for every test."""
    monkeypatch.setattr(tts_server, "_model", _fake_model())
    monkeypatch.setattr(tts_server, "REF_AUDIO", "/dev/null")
    # Also replace asyncio.to_thread so tests don't need a real thread pool
    import asyncio

    async def fake_to_thread(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    monkeypatch.setattr(asyncio, "to_thread", fake_to_thread)


# ── Test client ───────────────────────────────────────────────────────────────
from httpx import AsyncClient, ASGITransport  # noqa: E402


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=tts_server.app), base_url="http://test"
    ) as c:
        yield c


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health_returns_ok(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "model" in body


@pytest.mark.asyncio
async def test_health_includes_model_name(client):
    resp = await client.get("/health")
    assert resp.json()["model"] == tts_server.MODEL_NAME


@pytest.mark.asyncio
async def test_synthesize_returns_200(client):
    resp = await client.post("/synthesize", json={"text": "Hello AURA", "language": "English"})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_synthesize_content_type_is_pcm(client):
    resp = await client.post("/synthesize", json={"text": "Hello AURA"})
    assert "audio/pcm" in resp.headers["content-type"]


@pytest.mark.asyncio
async def test_synthesize_returns_bytes(client):
    resp = await client.post("/synthesize", json={"text": "Hello AURA"})
    assert len(resp.content) > 0


@pytest.mark.asyncio
async def test_synthesize_japanese(client):
    resp = await client.post("/synthesize", json={"text": "こんにちは", "language": "Japanese"})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_synthesize_missing_language_defaults_english(client):
    """Omitting language should not cause a 422 — defaults to English."""
    resp = await client.post("/synthesize", json={"text": "Hello"})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_synthesize_empty_text_returns_400(client):
    resp = await client.post("/synthesize", json={"text": "", "language": "English"})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_synthesize_whitespace_only_returns_400(client):
    resp = await client.post("/synthesize", json={"text": "   "})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_synthesize_strips_emotion_tags(client):
    """Text that is ONLY an emotion tag after stripping → 400."""
    resp = await client.post("/synthesize", json={"text": "[smile]"})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_synthesize_emotion_tag_prefix_is_cleaned(client):
    """[smile] Hello → calls model with 'Hello', not '[smile] Hello'."""
    resp = await client.post("/synthesize", json={"text": "[smile] Hello there"})
    assert resp.status_code == 200
    # Verify generate_voice_clone was called with clean text
    kwargs = tts_server._model.generate_voice_clone.call_args[1]
    call_text = kwargs.get("text") or tts_server._model.generate_voice_clone.call_args[0][0]
    assert "[smile]" not in call_text
    assert "Hello there" in call_text


@pytest.mark.asyncio
async def test_synthesize_wav_returns_200(client):
    resp = await client.post("/synthesize.wav", json={"text": "Hello AURA"})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_synthesize_wav_content_type(client):
    resp = await client.post("/synthesize.wav", json={"text": "Hello AURA"})
    assert "audio/wav" in resp.headers["content-type"]


@pytest.mark.asyncio
async def test_synthesize_wav_has_riff_header(client):
    resp = await client.post("/synthesize.wav", json={"text": "Hello AURA"})
    assert resp.content[:4] == b"RIFF"
    assert resp.content[8:12] == b"WAVE"


@pytest.mark.asyncio
async def test_synthesize_wav_empty_text_returns_400(client):
    resp = await client.post("/synthesize.wav", json={"text": ""})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_synthesize_unknown_language_falls_back_to_english(client):
    """An unrecognised language value should not crash — defaults to English."""
    resp = await client.post("/synthesize", json={"text": "Hello", "language": "Klingon"})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_synthesize_passes_language_to_model(client):
    resp = await client.post("/synthesize", json={"text": "こんにちは", "language": "Japanese"})
    assert resp.status_code == 200
    kwargs = tts_server._model.generate_voice_clone.call_args[1]
    assert kwargs.get("language") == "Japanese"


@pytest.mark.asyncio
async def test_synthesize_headers_contain_sample_rate(client):
    resp = await client.post("/synthesize", json={"text": "Hello"})
    assert resp.headers.get("x-sample-rate") == "24000"


@pytest.mark.asyncio
async def test_synthesize_headers_contain_bit_depth(client):
    resp = await client.post("/synthesize", json={"text": "Hello"})
    assert resp.headers.get("x-bit-depth") == "16"
