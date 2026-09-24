import os
import re
import json
import uuid
import logging
import asyncio
import threading
from typing import Annotated

from dotenv import load_dotenv
import aiohttp
import torch
from livekit import agents, rtc
from livekit.agents import AgentSession, Agent, room_io, llm, stt, tts, StopResponse, TurnHandlingOptions
from livekit.plugins import noise_cancellation, silero, deepgram, openai, cartesia

from vtube_controller import VTUBE
from avatar_bridge import BRIDGE
from aura_tts import AuraTTS

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.normpath(os.path.join(BASE_DIR, "..", ".env"))

if not os.path.exists(ENV_PATH):
    ENV_PATH = os.path.join(BASE_DIR, ".env")

load_dotenv(ENV_PATH)

# Setup Logger
logging.basicConfig(level=logging.INFO)
logging.getLogger("hpack").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("torio").setLevel(logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.WARNING)
logger = logging.getLogger("aura-agent")
logger.info(f"Loaded .env from: {ENV_PATH}")

# Configuration
DEEPGRAM_KEY   = os.getenv("DEEPGRAM_API_KEY")
CARTESIA_KEY   = os.getenv("CARTESIA_API_KEY")
AI_SERVICE_URL = os.getenv("AI_SERVICE_URL", "http://127.0.0.1:8001/api/v1/chat/voice")
_parsed        = AI_SERVICE_URL.split("/api/v1")[0]
BACKEND_URL    = _parsed  # e.g. http://127.0.0.1:8001
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "aura-internal-secret")

if not DEEPGRAM_KEY:
    logger.error("DEEPGRAM_API_KEY is missing!")


tts_type = os.getenv("TTS_TYPE", "qwen").lower()

if tts_type == "qwen":
    ref_prompt_path = os.path.join(BASE_DIR, 'resources', 'voice', 'aura_voice_xvec.pt')
    TTS_PLUGIN = AuraTTS(
        model_name="Qwen/Qwen3-TTS-12Hz-0.6B-Base",
        ref_audio=ref_prompt_path,
        ref_text="",
        language="English",
        dtype=torch.bfloat16,
        max_seq_len=512,
    )
    logger.info("Local Qwen3 TTS singleton created.")
elif tts_type == "cartesia":
    logger.info("Using Cartesia Cloud TTS (Sonic-3)")
    TTS_PLUGIN = cartesia.TTS(
        model="sonic-3",
        voice="f786b574-daa5-4673-aa0c-cbe3e8534c02",
        api_key=CARTESIA_KEY,
    )
else:
    logger.info("Using OpenAI Cloud TTS")
    TTS_PLUGIN = openai.TTS()

_tts_ready_event = threading.Event()

def _do_tts_warmup():
    logger.info("Background TTS warmup started...")
    try:
        if hasattr(TTS_PLUGIN, 'warmup'):
            TTS_PLUGIN.warmup()
        logger.info("Background TTS warmup complete.")
    except Exception as e:
        logger.error(f"Background TTS warmup failed: {e}")
    finally:
        _tts_ready_event.set()

def prewarm(proc: agents.JobProcess):
    logger.info("Prewarming worker process (scheduling background TTS warmup)...")
    try:
        threading.Thread(target=_do_tts_warmup, daemon=True).start()
    except Exception as e:
        logger.error(f"Could not start background prewarm: {e}")
        _tts_ready_event.set()


class AiServiceLLMStream(llm.LLMStream):
    def __init__(self, llm_instance: llm.LLM, chat_ctx: llm.ChatContext, tools: list[llm.Tool], conn_options: agents.APIConnectOptions, endpoint: str, auth_token: str, identity: str, conversation_id: str):
        super().__init__(llm_instance, chat_ctx=chat_ctx, tools=tools, conn_options=conn_options)
        self._endpoint = endpoint
        self._auth_token = auth_token
        self._identity = identity
        self._conversation_id = conversation_id
        self._session: aiohttp.ClientSession | None = None
        self._resp: aiohttp.ClientResponse | None = None
        self._closed = False

    async def _run(self) -> None:
        try:
            last_msg = None
            messages = list(self.chat_ctx.messages())
            for i in range(len(messages) - 1, -1, -1):
                m = messages[i]
                if m.role == "user" and m.text_content:
                    last_msg = m.text_content
                    break

            if not last_msg:
                last_msg = "Hello"

            headers = {
                "X-Internal-API-Key": self._auth_token,
                "Authorization": f"Bearer {self._auth_token}",
                "Content-Type": "application/json",
            }
            
            payload = {
                "message": str(last_msg),
                "stream": True,
                "identity": self._identity,
                "conversation_id": self._conversation_id
            }

            self._session = aiohttp.ClientSession()
            async with self._session.post(self._endpoint, headers=headers, json=payload) as resp:
                self._resp = resp
                resp.raise_for_status()
                async for line in resp.content:
                    line = line.decode('utf-8').strip()
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            text = data.get("text", "")
                            emotion = data.get("emotion", "neutral")
                            
                            # KEMBALIKAN TAG EMOSI AGAR DIBACA OLEH AURA_TTS.PY
                            if emotion and emotion != "neutral":
                                text = f"[{emotion}] {text}"

                            if text:
                                delta = llm.ChoiceDelta(role="assistant", content=text)
                                chunk = llm.ChatChunk(id=str(uuid.uuid4()), delta=delta)
                                self._event_ch.send_nowait(chunk)
                        except Exception:
                            pass
        except asyncio.CancelledError:
            logger.info("AiServiceLLMStream task was cancelled. Aborting HTTP stream.")
            raise
        except Exception as e:
            if self._closed:
                return
            logger.error(f"AiServiceLLMStream unexpected error: {e}")
            delta = llm.ChoiceDelta(role="assistant", content=f" [sad] Network error: {e}")
            self._event_ch.send_nowait(llm.ChatChunk(id=str(uuid.uuid4()), delta=delta))
        finally:
            if self._session:
                await self._session.close()
                self._session = None
            self._resp = None

    async def aclose(self) -> None:
        self._closed = True
        if self._resp:
            try:
                self._resp.close()
            except Exception:
                pass
        if self._session:
            try:
                await self._session.close()
            except Exception:
                pass
        await super().aclose()

class AiServiceLLM(llm.LLM):
    def __init__(self, endpoint: str, auth_token: str, identity: str, conversation_id: str):
        super().__init__()
        self._endpoint = endpoint
        self._auth_token = auth_token
        self._identity = identity
        self._conversation_id = conversation_id

    def chat(self, *, chat_ctx: llm.ChatContext, tools: list[llm.Tool] | None = None, conn_options: agents.APIConnectOptions | None = None, **kwargs) -> llm.LLMStream:
        return AiServiceLLMStream(
            llm_instance=self,
            chat_ctx=chat_ctx,
            tools=tools or [],
            conn_options=conn_options or agents.APIConnectOptions(),
            endpoint=self._endpoint,
            auth_token=self._auth_token,
            identity=self._identity,
            conversation_id=self._conversation_id
        )

class AURAAssistant(Agent):
    def __init__(
        self,
        *,
        conversation_id=None,
        user_identity: str = "aura-user",
        initial_chat_ctx: "llm.ChatContext | None" = None,
        llm: llm.LLM,
        tts: tts.TTS,
    ) -> None:
        super().__init__(instructions="", chat_ctx=initial_chat_ctx, llm=llm, tts=tts)
        
        self._conversation_id      = conversation_id
        self._user_identity        = user_identity
        self._vtube_connected      = False
        self._last_user_text       = ""
        self._last_activity_time   = asyncio.get_event_loop().time()
        self._last_aura_spoke_time = asyncio.get_event_loop().time()

    def reset_activity(self):
        self._last_activity_time = asyncio.get_event_loop().time()

    async def on_enter(self):
        self._vtube_connected = await VTUBE.connect()

    async def on_exit(self):
        await VTUBE.disconnect()
        BRIDGE.set_room(None)

    async def on_user_turn_started(self) -> None:
        self.reset_activity()

    async def on_user_turn_completed(self, turn_ctx: llm.ChatContext, new_message: llm.ChatMessage) -> None:
        self.reset_activity()
        text = (new_message.text_content or "").strip()
        
        if not text or not re.search(r'[a-zA-Z0-9\u3040-\u309f\u30a0-\u30ff\u4e00-\u9faf]', text):
            logger.info("Ignoring empty user turn / false VAD trigger.")
            raise StopResponse()
            
        self._last_user_text = text
        await super().on_user_turn_completed(turn_ctx, new_message)

    async def llm_chat(self, chat_ctx, **kwargs):
        self.reset_activity()
        await VTUBE.start_turn()
        async for chunk in super().llm_chat(chat_ctx, **kwargs):
            yield chunk

    async def on_agent_speech_committed(self, msg: llm.ChatMessage) -> None:
        self.reset_activity()
        self._last_aura_spoke_time = asyncio.get_event_loop().time()
        self._last_user_text = ""

async def voice_session(ctx: agents.JobContext):
    logger.info(f"Voice session starting (Job assigned) for room: {ctx.room.name}")

    if not _tts_ready_event.is_set():
        logger.info("Waiting for background TTS warmup to finish before connecting...")
        loop = asyncio.get_event_loop()
        ready = await loop.run_in_executor(None, lambda: _tts_ready_event.wait(60.0))
        if not ready:
            logger.warning("TTS warmup timed out after 60s, proceeding anyway...")
        else:
            logger.info("TTS warmup finished, proceeding to connect.")

    await ctx.connect()
    logger.info(f"User connected: {ctx.room.name}")

    vtube_connected = await VTUBE.connect()
    if vtube_connected:
        logger.info("VTube Studio connected")

    user_identity = "aura-user"  
    conversation_id_str = None

    found_identity = False
    for i in range(300):
        if ctx.job and getattr(ctx.job, 'participant', None):
            if ctx.job.participant.identity:
                user_identity = ctx.job.participant.identity
                found_identity = True
                if ctx.job.participant.metadata:
                    try:
                        meta = json.loads(ctx.job.participant.metadata)
                        conversation_id_str = meta.get("conversation_id")
                    except: pass
        
        if not found_identity:
            participants = [p for p in ctx.room.remote_participants.values() if not p.identity.startswith("agent-")]
            if participants:
                p = participants[0]
                user_identity = p.identity
                found_identity = True
                if p.metadata:
                    try:
                        meta = json.loads(p.metadata)
                        conversation_id_str = meta.get("conversation_id")
                    except: pass

        if found_identity:
            if conversation_id_str:
                break
            if i > 10: 
                break
        
        if i % 20 == 0:
            logger.info("Waiting for participant to join room and reveal identity...")
        await asyncio.sleep(0.1)

    logger.info(f"Resolved identity: '{user_identity}', conversation: '{conversation_id_str}'")

    session_endpoint = f"{BACKEND_URL}/api/v1/memory/session"
    conversation_id = None
    facts = ""

    try:
        headers = {
            "Authorization": f"Bearer {INTERNAL_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "identity": user_identity,
            "title": f"Voice Session: {user_identity}"
        }
        async with aiohttp.ClientSession() as http_sess:
            async with http_sess.post(session_endpoint, headers=headers, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    conversation_id = data.get("conversation_id")
                    facts = data.get("long_term_memory", "")
                    logger.info(f"Centralized session established: conv={conversation_id}")
                else:
                    body = await resp.text()
                    logger.error(f"Failed to establish centralized session: {resp.status}. Body: {body}")
    except Exception as e:
        logger.error(f"Error calling centralized session endpoint: {e}")

    is_returning_user = bool(facts.strip())
    
    initial_chat_ctx = llm.ChatContext()
    BRIDGE.set_room(ctx.room)

    connector = aiohttp.TCPConnector(use_dns_cache=True, keepalive_timeout=120)
    stt_session = aiohttp.ClientSession(connector=connector)
    
    stt_plugin = deepgram.STT(
        model="nova-3",
        language="multi",
        detect_language=False,
        smart_format=True,
        interim_results=True,
        api_key=DEEPGRAM_KEY,
        http_session=stt_session,
        keyterm=["moshi", "desu", "konnichiwa", "nihongo", "arigato", "sugoi", "hello", "hey", "AURA"]
    )

    llm_plugin = AiServiceLLM(
        endpoint=AI_SERVICE_URL,
        auth_token=INTERNAL_API_KEY,
        identity=user_identity,
        conversation_id=str(conversation_id) if conversation_id else ""
    )

    agent_instance = AURAAssistant(
        conversation_id=conversation_id,
        user_identity=user_identity,
        initial_chat_ctx=initial_chat_ctx,
        llm=llm_plugin,
        tts=TTS_PLUGIN,
    )

    session = AgentSession(
        stt=stt_plugin,
        tts=TTS_PLUGIN,
        vad=silero.VAD.load(
            min_silence_duration=1.2,
            min_speech_duration=0.1
        ),
        preemptive_generation=False,
        turn_handling=TurnHandlingOptions(
            interruption={
                "enabled": True,
                "mode": "vad",
                "min_words": 3,
                "min_duration": 0.8,
            }
        ),
    )

    await session.start(
        room=ctx.room,
        agent=agent_instance,
    )

    if vtube_connected:
        await VTUBE.set_expression("happy")

    instruction = (
        "Greet the user warmly as someone you already know. "
        "Briefly acknowledge you remember them. Keep it to 1-2 sentences."
        if is_returning_user else
        "Greet the user with a polite and helpful AURA introduction. "
        "Example: 'Hello! I'm AURA, your personal AI assistant. How can I help you today?'"
    )

    if ctx.room.remote_participants:
        logger.info("TTS ready, generating greeting via LLM")
        try:
            await session.generate_reply(instructions=instruction, allow_interruptions=False)
        except Exception as e:
            logger.warning(f"Could not deliver dynamic greeting: {e}")

    try:
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        logger.info("Voice session cancelled by user/room.")
    finally:
        logger.info(f"Cleaning up session for {user_identity}...")
        await stt_session.close()
        
        if vtube_connected:
            await VTUBE.reset_to_neutral()


if __name__ == "__main__":
    agents.cli.run_app(
        agents.WorkerOptions(
            entrypoint_fnc=voice_session,
            prewarm_fnc=prewarm,
        )
    )