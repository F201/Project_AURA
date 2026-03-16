"""
AvatarBridge — Phase 1
Broadcasts expression events over the LiveKit data channel so any connected
client (browser dashboard or Electron desktop app) can animate the avatar in
sync with AURA's speech.

The bridge is intentionally fire-and-forget: failures are swallowed so they
never block the TTS pipeline.

Usage:
    from avatar_bridge import BRIDGE

    # On session start (agent.py voice_session):
    BRIDGE.set_room(ctx.room)

    # On session end:
    BRIDGE.set_room(None)

    # In aura_tts.py _sync_expression (alongside VTUBE calls):
    await BRIDGE.send_expression(["smile", "shadow"], duration=2.3)
    await BRIDGE.send_neutral()
"""

import json
import logging
import os

from livekit import rtc

logger = logging.getLogger("avatar-bridge")

_TOPIC = "avatar"


class AvatarBridge:
    """Publishes avatar expression events to LiveKit data channel."""

    def __init__(self):
        self._room: rtc.Room | None = None
        self.enabled: bool = os.getenv("AVATAR_BRIDGE_ENABLED", "true").lower() == "true"

    def set_room(self, room: rtc.Room | None) -> None:
        self._room = room
        if room is not None:
            logger.info("[BRIDGE] attached to room: %s", room.name)
        else:
            logger.info("[BRIDGE] detached from room")

    async def send_expression(self, names: list[str], duration: float = 2.0) -> None:
        """
        Publish an expression event.

        Args:
            names:    List of expression tag strings, e.g. ["smile", "shadow"].
                      Empty list means 'reset to neutral'.
            duration: How long (seconds) the expression should last before
                      the client auto-resets.  Matches the audio segment duration
                      so the avatar stays expressive exactly as long as that line plays.
        """
        if not self.enabled or self._room is None:
            return

        payload = json.dumps(
            {
                "type": "expression",
                "expressions": names,
                "duration": duration,
            }
        ).encode()

        try:
            await self._room.local_participant.publish_data(
                payload,
                reliable=True,
                topic=_TOPIC,
            )
            logger.debug("[BRIDGE] sent: %s (%.1fs)", names, duration)
        except Exception as exc:
            # Never propagate — a LiveKit hiccup must not silence AURA's voice
            logger.debug("[BRIDGE] publish failed (non-fatal): %s", exc)

    async def send_neutral(self) -> None:
        """Reset the avatar to its default idle expression."""
        await self.send_expression([], duration=0)


# Module-level singleton — imported by agent.py and aura_tts.py
BRIDGE = AvatarBridge()
