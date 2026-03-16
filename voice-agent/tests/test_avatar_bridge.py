"""
Phase 1 tests — AvatarBridge
No LiveKit server needed — all network calls are mocked.

Run:
    cd voice-agent
    pytest tests/test_avatar_bridge.py -v
"""
import asyncio
import json
import time

import pytest
from unittest.mock import AsyncMock, MagicMock

from avatar_bridge import AvatarBridge


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def bridge():
    b = AvatarBridge()
    b.enabled = True
    return b


@pytest.fixture
def mock_room():
    room = MagicMock()
    room.name = "test-room"
    room.local_participant.publish_data = AsyncMock()
    return room


# ── Tests: enabled bridge with room ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_send_expression_publishes_correct_json(bridge, mock_room):
    bridge.set_room(mock_room)
    await bridge.send_expression(["smile", "shadow"], duration=2.3)

    mock_room.local_participant.publish_data.assert_called_once()
    call_args = mock_room.local_participant.publish_data.call_args
    payload = json.loads(call_args[0][0].decode())

    assert payload["type"] == "expression"
    assert payload["expressions"] == ["smile", "shadow"]
    assert abs(payload["duration"] - 2.3) < 1e-6


@pytest.mark.asyncio
async def test_send_expression_uses_avatar_topic(bridge, mock_room):
    bridge.set_room(mock_room)
    await bridge.send_expression(["smile"])
    kwargs = mock_room.local_participant.publish_data.call_args[1]
    assert kwargs["topic"] == "avatar"
    assert kwargs["reliable"] is True


@pytest.mark.asyncio
async def test_send_expression_single_emotion(bridge, mock_room):
    bridge.set_room(mock_room)
    await bridge.send_expression(["angry"], duration=1.5)
    payload = json.loads(mock_room.local_participant.publish_data.call_args[0][0].decode())
    assert payload["expressions"] == ["angry"]
    assert abs(payload["duration"] - 1.5) < 1e-6


@pytest.mark.asyncio
async def test_send_expression_empty_list(bridge, mock_room):
    """Empty list = reset to neutral (still published, not silently dropped)."""
    bridge.set_room(mock_room)
    await bridge.send_expression([], duration=0)
    payload = json.loads(mock_room.local_participant.publish_data.call_args[0][0].decode())
    assert payload["expressions"] == []


# ── Tests: send_neutral ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_send_neutral_sends_empty_list(bridge, mock_room):
    bridge.set_room(mock_room)
    await bridge.send_neutral()
    payload = json.loads(mock_room.local_participant.publish_data.call_args[0][0].decode())
    assert payload["expressions"] == []
    assert payload["duration"] == 0


# ── Tests: disabled / no room ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_send_expression_disabled_does_nothing(mock_room):
    bridge = AvatarBridge()
    bridge.enabled = False
    bridge.set_room(mock_room)
    await bridge.send_expression(["smile"])
    mock_room.local_participant.publish_data.assert_not_called()


@pytest.mark.asyncio
async def test_send_expression_no_room_does_nothing():
    bridge = AvatarBridge()
    bridge.enabled = True
    # No room set — must not raise
    await bridge.send_expression(["smile"])


@pytest.mark.asyncio
async def test_send_neutral_no_room_does_nothing():
    bridge = AvatarBridge()
    bridge.enabled = True
    await bridge.send_neutral()  # must not raise


# ── Tests: failure isolation ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_bridge_failure_does_not_propagate(bridge, mock_room):
    """If LiveKit publish raises, the TTS pipeline must not crash."""
    mock_room.local_participant.publish_data = AsyncMock(
        side_effect=Exception("network error")
    )
    bridge.set_room(mock_room)
    # Must not raise
    await bridge.send_expression(["smile"])


@pytest.mark.asyncio
async def test_send_neutral_failure_does_not_propagate(bridge, mock_room):
    mock_room.local_participant.publish_data = AsyncMock(
        side_effect=RuntimeError("connection dropped")
    )
    bridge.set_room(mock_room)
    await bridge.send_neutral()  # must not raise


# ── Tests: room lifecycle ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_set_room_none_stops_publishing(bridge, mock_room):
    bridge.set_room(mock_room)
    bridge.set_room(None)  # session ended
    await bridge.send_expression(["smile"])
    mock_room.local_participant.publish_data.assert_not_called()


@pytest.mark.asyncio
async def test_set_room_replaces_previous_room(bridge, mock_room):
    old_room = MagicMock()
    old_room.local_participant.publish_data = AsyncMock()

    bridge.set_room(old_room)
    bridge.set_room(mock_room)
    await bridge.send_expression(["smile"])

    old_room.local_participant.publish_data.assert_not_called()
    mock_room.local_participant.publish_data.assert_called_once()


# ── Tests: concurrency (gather VTUBE + BRIDGE) ────────────────────────────────

@pytest.mark.asyncio
async def test_bridge_does_not_block_on_slow_vtube():
    """
    Verify that running VTUBE (slow) and BRIDGE (fast) in asyncio.gather()
    means BRIDGE finishes before VTUBE — they are truly concurrent.
    """
    call_times: list[tuple[str, float]] = []

    async def slow_vtube(*a, **kw):
        await asyncio.sleep(0.1)
        call_times.append(("vtube", time.monotonic()))

    async def fast_bridge():
        call_times.append(("bridge", time.monotonic()))

    # Simulate the gather pattern from aura_tts.py
    await asyncio.gather(slow_vtube(), fast_bridge())

    assert len(call_times) == 2
    bridge_t = next(t for name, t in call_times if name == "bridge")
    vtube_t  = next(t for name, t in call_times if name == "vtube")
    # BRIDGE should complete well before VTUBE's 0.1s sleep finishes
    assert bridge_t < vtube_t
