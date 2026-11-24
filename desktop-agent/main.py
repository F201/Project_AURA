"""
AURA Desktop Agent — FastAPI + WebSocket Companion Hub (:8765)
Direct local-first streaming pipeline for AURA Desktop:
  CPU faster-whisper STT / Text / Touch / Proactive
    -> Streaming OpenRouter Multimodal LLM (function-calling Live2D expressions + desktop tools)
    -> Streaming Faster-Qwen3-TTS (CUDA graphs, chunk_size=6)
    -> WebSocket binary PCM audio + Live2D/3D expression & subtitle events
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
# Preload PyTorch cuDNN DLLs BEFORE ctranslate2/onnxruntime (faster-whisper) on Windows
try:
    import torch  # noqa: F401
except Exception:
    pass

import uvicorn
from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from brain import brain
from config import PROJECT_ROOT, runtime, settings
from input_watcher import input_watcher
from memory_store import memory_store
from proactive_loop import proactive_loop
from stt_engine import stt_engine
from tts_engine import VOICE_DIR, tts_engine
from vision_watcher import vision_watcher

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("aura.desktop")


class CompanionHub:
    def __init__(self) -> None:
        self.clients: Set[WebSocket] = set()
        self._turn_lock = asyncio.Lock()
        self._abort_event = asyncio.Event()
        self._turn_seq = 0
        self._greeted = False

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.clients.add(ws)
        logger.info(f"AURA Desktop overlay connected ({len(self.clients)} client(s))")
        await self.send_json(
            ws,
            {
                "type": "init",
                "state": runtime.to_dict(),
                "profile": memory_store.get_profile(),
                "memories": memory_store.list_memories(limit=30),
                "reminders": memory_store.list_pending_reminders(),
                "history": memory_store.get_recent_messages(limit=20),
                "voices": tts_engine.list_voice_files(),
            },
        )
        if settings.openrouter_api_key and not self._greeted:
            self._greeted = True
            asyncio.create_task(self._startup_greeting())

    async def _startup_greeting(self) -> None:
        for _ in range(180):
            if runtime.tts_ready and runtime.tts_backend != "loading":
                break
            await asyncio.sleep(0.5)
        if not self.clients or runtime.is_speaking or runtime.is_thinking:
            return
        await self.handle_turn(
            "[STARTUP GREETING] You just appeared on the user's desktop! "
            "Greet them in ONE lively, friendly AURA sentence (under 14 words).",
            source="proactive",
            include_vision=not runtime.blind_mode,
            persist_user=False,
        )

    def disconnect(self, ws: WebSocket) -> None:
        self.clients.discard(ws)

    async def send_json(self, ws: WebSocket, payload: Dict[str, Any]) -> None:
        try:
            await asyncio.wait_for(ws.send_text(json.dumps(payload)), timeout=2.5)
        except Exception:
            self.clients.discard(ws)

    async def broadcast_json(self, payload: Dict[str, Any]) -> None:
        if not self.clients:
            return
        raw = json.dumps(payload)
        dead: List[WebSocket] = []
        for ws in list(self.clients):
            try:
                await asyncio.wait_for(ws.send_text(raw), timeout=2.5)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.clients.discard(ws)

    async def broadcast_bytes(self, data: bytes) -> None:
        if not self.clients:
            return
        dead: List[WebSocket] = []
        for ws in list(self.clients):
            try:
                await asyncio.wait_for(ws.send_bytes(data), timeout=2.5)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.clients.discard(ws)

    async def broadcast_state(self) -> None:
        await self.broadcast_json({"type": "state", "state": runtime.to_dict()})

    async def interrupt(self) -> None:
        self._abort_event.set()
        runtime.is_speaking = False
        runtime.client_playing = False
        runtime.is_thinking = False
        await self.broadcast_json({"type": "audio_stop"})
        await self.broadcast_state()

    async def handle_turn(
        self,
        user_text: str,
        source: str = "voice",
        include_vision: bool = True,
        extra_context: Optional[str] = None,
        persist_user: bool = True,
    ) -> None:
        if not settings.openrouter_api_key and source != "text":
            return
        self._abort_event.set()
        async with self._turn_lock:
            self._turn_seq += 1
            turn_id = self._turn_seq
            abort = asyncio.Event()
            self._abort_event = abort

            if source in ("voice", "text", "touch"):
                proactive_loop.mark_user_interaction()

            if persist_user:
                memory_store.add_message("user", user_text, source=source)
                await self.broadcast_json(
                    {
                        "type": "user_message",
                        "text": user_text,
                        "source": source,
                        "turn_id": turn_id,
                    }
                )

            runtime.is_thinking = True
            await self.broadcast_state()
            await self.broadcast_json({"type": "assistant_start", "turn_id": turn_id, "source": source})

            clause_queue: asyncio.Queue[Optional[tuple[str, List[str]]]] = asyncio.Queue()

            async def _tts_consumer() -> None:
                audio_started = False
                try:
                    while True:
                        item = await clause_queue.get()
                        if item is None or abort.is_set():
                            break
                        clause_text, emotions = item
                        if emotions:
                            await self.broadcast_json(
                                {
                                    "type": "expression",
                                    "expressions": emotions,
                                    "duration": max(2.2, len(clause_text) / 14.0),
                                }
                            )
                        async for pcm_bytes, sr in tts_engine.stream_clause_pcm(clause_text, abort):
                            if abort.is_set():
                                break
                            if not audio_started:
                                audio_started = True
                                runtime.is_speaking = True
                                runtime.is_thinking = False
                                await self.broadcast_state()
                                await self.broadcast_json(
                                    {
                                        "type": "audio_start",
                                        "turn_id": turn_id,
                                        "sample_rate": sr,
                                        "channels": 1,
                                    }
                                )
                            await self.broadcast_bytes(pcm_bytes)
                finally:
                    if audio_started:
                        await self.broadcast_json({"type": "audio_end", "turn_id": turn_id})
                    runtime.is_speaking = False
                    await self.broadcast_state()

            tts_task = asyncio.create_task(_tts_consumer())
            full_text = ""
            primary_emotion = "SmileLock"

            try:
                async for ev in brain.stream_response(
                    user_text=user_text,
                    abort_event=abort,
                    include_vision=include_vision,
                    extra_context=extra_context,
                    allow_tools=(source in ("voice", "text")),
                ):
                    if abort.is_set():
                        break
                    etype = ev["type"]
                    if etype == "expression":
                        await self.broadcast_json(
                            {
                                "type": "expression",
                                "expressions": ev["expressions"],
                                "duration": ev.get("duration", 5.5),
                            }
                        )
                    elif etype == "token":
                        await self.broadcast_json(
                            {"type": "assistant_token", "text": ev["text"], "turn_id": turn_id}
                        )
                    elif etype == "clause":
                        await clause_queue.put((ev["text"], ev["emotions"]))
                    elif etype == "tool":
                        await self.broadcast_json(
                            {"type": "tool_event", "name": ev["name"], "result": ev["result"]}
                        )
                        if ev["name"] in ("remember_fact", "set_reminder"):
                            await self.broadcast_json(
                                {
                                    "type": "sync_data",
                                    "memories": memory_store.list_memories(limit=30),
                                    "reminders": memory_store.list_pending_reminders(),
                                }
                            )
                    elif etype == "done":
                        full_text = ev["full_text"]
                        primary_emotion = ev["primary_emotion"]
            finally:
                await clause_queue.put(None)
                try:
                    await asyncio.wait_for(tts_task, timeout=120.0 if settings.remote_tts_url else 22.0)
                except asyncio.TimeoutError:
                    abort.set()
                    tts_task.cancel()
                runtime.is_thinking = False
                runtime.is_speaking = False

            if full_text and not abort.is_set():
                memory_store.add_message("assistant", full_text, emotion=primary_emotion, source=source)
                xp_gain = 4 if source in ("voice", "text") else 1
                stat = "total_chats" if source in ("voice", "text") else None
                profile = memory_store.add_bond_xp(xp_gain, stat_key=stat)
                await self.broadcast_json(
                    {
                        "type": "assistant_done",
                        "turn_id": turn_id,
                        "text": full_text,
                        "emotion": primary_emotion,
                        "profile": profile,
                    }
                )
            else:
                await self.broadcast_json({"type": "assistant_done", "turn_id": turn_id, "text": ""})
            await self.broadcast_state()

    async def handle_touch(self, kind: str, intensity: float = 1.0) -> None:
        proactive_loop.mark_user_interaction()
        if kind == "headpat":
            profile = memory_store.add_bond_xp(5, stat_key="total_headpats")
            await self.broadcast_json({"type": "expression", "expressions": ["SmileLock", "blush"], "duration": 4.0})
            await self.broadcast_json({"type": "particles", "kind": "blossom"})
            await self.broadcast_json({"type": "profile_update", "profile": profile})
            if not runtime.is_speaking and not runtime.is_thinking:
                await self.handle_turn(
                    "[TOUCH INTERACTION] The user just gently patted your head on their desktop! "
                    "React warmly and playfully in 1 short sentence as AURA.",
                    source="touch",
                    include_vision=False,
                    persist_user=False,
                )
        elif kind == "poke":
            profile = memory_store.add_bond_xp(2, stat_key="total_pokes")
            await self.broadcast_json({"type": "expression", "expressions": ["pouting", "Ghost"], "duration": 3.5})
            await self.broadcast_json({"type": "particles", "kind": "ghost"})
            await self.broadcast_json({"type": "profile_update", "profile": profile})
            if not runtime.is_speaking and not runtime.is_thinking:
                await self.handle_turn(
                    "[TOUCH INTERACTION] The user just poked your cheek on their desktop! "
                    "React playfully in 1 short sentence as AURA.",
                    source="touch",
                    include_vision=False,
                    persist_user=False,
                )
        elif kind == "shake":
            await self.broadcast_json({"type": "expression", "expressions": ["PupilShrink", "GhostChange"], "duration": 3.5})
            await self.broadcast_json({"type": "particles", "kind": "ghost"})
            if not runtime.is_speaking and not runtime.is_thinking:
                await self.handle_turn(
                    "[TOUCH INTERACTION] The user just shook your overlay rapidly across the desktop! "
                    "React dramatically and playfully in 1 short sentence as AURA.",
                    source="touch",
                    include_vision=False,
                    persist_user=False,
                )


hub = CompanionHub()


@asynccontextmanager
async def lifespan(app: FastAPI):
    loop = asyncio.get_running_loop()

    def _boot_tts():
        tts_engine.load_qwen(warmup=settings.tts_warmup)
        asyncio.run_coroutine_threadsafe(hub.broadcast_state(), loop)

    threading.Thread(target=_boot_tts, daemon=True).start()

    stt_engine.start(
        loop=loop,
        on_transcript=lambda txt: hub.handle_turn(txt, source="voice", include_vision=True),
        on_barge_in=hub.interrupt,
        on_state_change=hub.broadcast_state,
    )

    input_watcher.start()

    proactive_loop.start(
        trigger_cb=lambda prompt, src, vis: hub.handle_turn(
            prompt, source=src, include_vision=vis, persist_user=False
        ),
        broadcast_state_cb=hub.broadcast_state,
    )

    logger.info(f"AURA Desktop Agent running on http://{settings.host}:{settings.port}")
    yield

    proactive_loop.stop()
    stt_engine.stop()
    input_watcher.stop()


app = FastAPI(title="AURA Desktop Companion Agent", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await hub.connect(ws)
    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            mtype = msg.get("type")

            if mtype == "chat":
                text = str(msg.get("text", "")).strip()
                if text:
                    asyncio.create_task(
                        hub.handle_turn(
                            text,
                            source="text",
                            include_vision=bool(msg.get("include_vision", True)),
                        )
                    )
            elif mtype == "touch":
                asyncio.create_task(
                    hub.handle_touch(str(msg.get("kind", "headpat")), float(msg.get("intensity", 1.0)))
                )
            elif mtype == "interrupt":
                await hub.interrupt()
            elif mtype == "playback_state":
                runtime.client_playing = bool(msg.get("playing", False))
            elif mtype == "set_state":
                await _apply_state_patch(msg.get("patch") or {})
            elif mtype == "look_now":
                asyncio.create_task(
                    hub.handle_turn(
                        "Take a look at my screen right now and tell me what you think!",
                        source="text",
                        include_vision=True,
                        persist_user=True,
                    )
                )
    except WebSocketDisconnect:
        hub.disconnect(ws)
    except Exception:
        hub.disconnect(ws)


async def _apply_state_patch(patch: Dict[str, Any]) -> Dict[str, Any]:
    prev_game_mode = runtime.game_mode

    for field_name in (
        "mic_muted",
        "mic_mode",
        "blind_mode",
        "game_mode",
        "proactive_enabled",
        "vision_enabled",
        "typing_watcher_enabled",
        "tts_language",
        "tts_voice_file",
    ):
        if field_name in patch:
            setattr(runtime, field_name, patch[field_name])

    if "tts_chunk_size" in patch:
        runtime.tts_chunk_size = max(3, min(12, int(patch["tts_chunk_size"])))
    if "proactive_cooldown_sec" in patch:
        runtime.proactive_cooldown_sec = max(15.0, float(patch["proactive_cooldown_sec"]))

    if runtime.blind_mode:
        input_watcher.clear()

    if runtime.game_mode != prev_game_mode:
        if runtime.game_mode:
            await asyncio.to_thread(tts_engine.unload_qwen)
        else:
            loop = asyncio.get_running_loop()

            def _reload():
                tts_engine.load_qwen(warmup=True)
                asyncio.run_coroutine_threadsafe(hub.broadcast_state(), loop)

            threading.Thread(target=_reload, daemon=True).start()

    await hub.broadcast_state()
    return runtime.to_dict()


@app.get("/api/health")
async def api_health():
    return {"status": "ok", "state": runtime.to_dict(), "profile": memory_store.get_profile()}


@app.post("/api/state")
async def api_patch_state(patch: Dict[str, Any]):
    return await _apply_state_patch(patch)


@app.post("/api/tts/reload")
async def api_reload_tts():
    runtime.game_mode = False
    loop = asyncio.get_running_loop()

    def _reload():
        tts_engine.unload_qwen()
        tts_engine.load_qwen(warmup=True)
        asyncio.run_coroutine_threadsafe(hub.broadcast_state(), loop)

    threading.Thread(target=_reload, daemon=True).start()
    return {"ok": True, "status": "reloading"}


@app.get("/api/vision/preview")
async def api_vision_preview():
    data_url = await asyncio.to_thread(vision_watcher.get_preview_data_url)
    return {
        "image": data_url,
        "window": runtime.active_window,
        "process": runtime.active_process,
        "game": runtime.detected_game,
        "privacy_paused": runtime.privacy_paused,
        "privacy_reason": runtime.privacy_reason,
    }


class ProfilePatch(BaseModel):
    user_name: Optional[str] = None


@app.post("/api/profile")
async def api_update_profile(body: ProfilePatch):
    if body.user_name:
        memory_store.set_profile_value("user_name", body.user_name.strip()[:40])
    prof = memory_store.get_profile()
    await hub.broadcast_json({"type": "profile_update", "profile": prof})
    return prof


class MemoryCreate(BaseModel):
    content: str
    category: str = "fact"


@app.post("/api/memories")
async def api_add_memory(body: MemoryCreate):
    mid = memory_store.add_memory(body.content, category=body.category, importance=7)
    mems = memory_store.list_memories(limit=30)
    await hub.broadcast_json(
        {"type": "sync_data", "memories": mems, "reminders": memory_store.list_pending_reminders()}
    )
    return {"id": mid, "memories": mems}


@app.delete("/api/memories/{memory_id}")
async def api_delete_memory(memory_id: int):
    memory_store.delete_memory(memory_id)
    mems = memory_store.list_memories(limit=30)
    await hub.broadcast_json(
        {"type": "sync_data", "memories": mems, "reminders": memory_store.list_pending_reminders()}
    )
    return {"ok": True}


@app.delete("/api/reminders/{reminder_id}")
async def api_delete_reminder(reminder_id: int):
    memory_store.delete_reminder(reminder_id)
    await hub.broadcast_json(
        {
            "type": "sync_data",
            "memories": memory_store.list_memories(limit=30),
            "reminders": memory_store.list_pending_reminders(),
        }
    )
    return {"ok": True}


@app.get("/api/voices")
async def api_list_voices():
    return {"active": runtime.tts_voice_file, "files": tts_engine.list_voice_files()}


@app.post("/api/voices/upload")
async def api_upload_voice(file: UploadFile = File(...)):
    fname = Path(file.filename or "custom_voice.wav").name
    if not fname.lower().endswith((".wav", ".pt", ".mp3", ".flac", ".ogg")):
        raise HTTPException(status_code=400, detail="Unsupported audio/embedding format")
    VOICE_DIR.mkdir(parents=True, exist_ok=True)
    dest = VOICE_DIR / fname
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    runtime.tts_voice_file = fname
    await hub.broadcast_state()
    return {"ok": True, "active": fname, "files": tts_engine.list_voice_files()}


@app.get("/api/models3d")
async def api_list_models_3d():
    models_dir = PROJECT_ROOT / "desktop" / "public" / "models" / "3d"
    models_dir.mkdir(parents=True, exist_ok=True)
    found: List[Dict[str, str]] = []
    for p in models_dir.rglob("*"):
        if p.is_file() and p.suffix.lower() in (".vrm", ".glb", ".gltf", ".pmx"):
            rel = p.relative_to(models_dir).as_posix()
            found.append({"name": p.name, "url": f"./models/3d/{rel}", "ext": p.suffix.lower()})
    return {"models": found}


if __name__ == "__main__":
    uvicorn.run(app, host=settings.host, port=settings.port, log_level="info")
