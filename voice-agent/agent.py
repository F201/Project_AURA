from dotenv import load_dotenv
import os
from typing import Annotated

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.normpath(os.path.join(BASE_DIR, "..", ".env"))

if not os.path.exists(ENV_PATH):
    ENV_PATH = os.path.join(BASE_DIR, ".env")

load_dotenv(ENV_PATH)

from livekit import agents, rtc
from livekit.agents import AgentSession, Agent, room_io, llm, stt, tts, StopResponse
from livekit.plugins import noise_cancellation, silero, deepgram, openai, cartesia

import logging
import threading
import asyncio
import aiohttp
import json
import uuid
import openai as _openai_sdk  # raw AsyncOpenAI, not livekit.plugins.openai

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
            for m in reversed(self.chat_ctx.messages()):
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
                            if "text" in data:
                                delta = llm.ChoiceDelta(role="assistant", content=data["text"])
                                chunk = llm.ChatChunk(id=str(uuid.uuid4()), delta=delta)
                                self._event_ch.send_nowait(chunk)
                        except Exception:
                            pass
        except asyncio.CancelledError:
            logger.info("AiServiceLLMStream task was cancelled. Aborting HTTP stream.")
            raise
        except aiohttp.ClientResponseError as e:
            if self._closed:
                logger.info("AiServiceLLMStream response aborted cleanly during close.")
                return
            body = ""
            if e.response:
                try:
                    body = await e.response.text()
                except Exception:
                    pass
            logger.error(f"AiServiceLLMStream HTTP error {e.status}: {e.message}. Body: {body}")
            delta = llm.ChoiceDelta(role="assistant", content=f" [sad] Network error: {e.status} {e.message}")
            self._event_ch.send_nowait(llm.ChatChunk(id=str(uuid.uuid4()), delta=delta))
        except Exception as e:
            if self._closed:
                logger.info("AiServiceLLMStream stream aborted cleanly during close.")
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

from vtube_controller import VTUBE
from avatar_bridge import BRIDGE

logging.basicConfig(level=logging.INFO)
logging.getLogger("hpack").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("torio").setLevel(logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.WARNING)
logger = logging.getLogger("aura-agent")
logger.info(f"Loaded .env from: {ENV_PATH}")

DEEPGRAM_KEY   = os.getenv("DEEPGRAM_API_KEY")
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY")
CARTESIA_KEY   = os.getenv("CARTESIA_API_KEY")
OPENAI_KEY     = os.getenv("OPENAI_API_KEY")
GROQ_KEY       = os.getenv("GROQ_API_KEY")
ANTHROPIC_KEY  = os.getenv("ANTHROPIC_API_KEY")
OLLAMA_URL     = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
AI_SERVICE_URL = os.getenv("AI_SERVICE_URL", "http://127.0.0.1:8001/api/v1/chat/voice")
_parsed        = AI_SERVICE_URL.split("/api/v1")[0]
BACKEND_URL    = _parsed  # e.g. http://127.0.0.1:8001
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "aura-internal-secret")

if not DEEPGRAM_KEY:
    logger.error("DEEPGRAM_API_KEY is missing!")

if not any([OPENROUTER_KEY, OPENAI_KEY, GROQ_KEY, ANTHROPIC_KEY]):
    logger.warning("No cloud LLM key found — memory extraction will use local Ollama.")

if not CARTESIA_KEY:
    logger.error("CARTESIA_API_KEY is missing!")
else:
    logger.info(f"CARTESIA_API_KEY loaded: {CARTESIA_KEY[:5]}...")


tts_type = os.getenv("TTS_TYPE", "qwen").lower()

if tts_type == "qwen":
    import torch
    from aura_tts import AuraTTS
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
# Active locks or trackers can go here if needed.

def _do_tts_warmup():
    """Sync warmup running in a background thread to avoid blocking process init."""
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
    """Prewarm the worker process without blocking.
    This prevents the 10s LiveKit initialization timeout."""
    logger.info("Prewarming worker process (scheduling background TTS warmup)...")
    try:
        threading.Thread(target=_do_tts_warmup, daemon=True).start()
    except Exception as e:
        logger.error(f"Could not start background prewarm: {e}")
        _tts_ready_event.set()

_EXTRACT_MAX_ATTEMPTS = 3
_EXTRACT_BACKOFF_BASE = 2.0  # seconds

async def extract_and_save_memory(identity: str, conversation_id: str, messages: list = None):
    """
    Delegates history persistence and memory extraction to the centralized AI service.
    """
    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {INTERNAL_API_KEY}",
                "X-Internal-API-Key": INTERNAL_API_KEY,
                "Content-Type": "application/json"
            }

            # 1. Persist the entire session history and trigger LTM extraction
            if not messages:
                logger.info(f"No messages to persist for {identity}. Skipping cleanup.")
                return

            persist_url = f"{BACKEND_URL}/api/v1/chat/persist"
            persist_payload = {
                "conversation_id": conversation_id,
                "identity": identity,
                "messages": messages
            }
            
            logger.info(f"Finalizing session: Persisting {len(messages)} messages and triggering LTM extraction...")
            async with session.post(persist_url, json=persist_payload, headers=headers) as resp:
                if resp.status == 200:
                    logger.info(f"Successfully finalized session for {identity}")
                else:
                    logger.warning(f"Failed to finalize session: {resp.status}")

    except Exception as e:
        logger.error(f"Error during session cleanup: {e}")


class AURAAssistant(Agent):
    def __init__(
        self,
        *,
        conversation_id=None,
        user_identity: str = "aura-user",
        system_prompt: str = "",
        initial_chat_ctx: "llm.ChatContext | None" = None,
        llm: llm.LLM,
        tts: tts.TTS,
    ) -> None:
        super().__init__(instructions=system_prompt, chat_ctx=initial_chat_ctx, llm=llm, tts=tts)
        self._conversation_id      = conversation_id
        self._user_identity        = user_identity
        self._vtube_connected      = False
        self._last_user_text       = ""
        self._last_activity_time   = asyncio.get_event_loop().time()
        self._last_aura_spoke_time = asyncio.get_event_loop().time()
        self._message_buffer       = []  # Buffer for session-end persistence

    def reset_activity(self):
        self._last_activity_time = asyncio.get_event_loop().time()

    async def on_enter(self):
        self._vtube_connected = await VTUBE.connect()

    async def on_exit(self):
        await VTUBE.disconnect()
        BRIDGE.set_room(None)

        if self._conversation_id and self._message_buffer:
            logger.info(f"[on_exit] Extracting memory for {self._user_identity} ({len(self._message_buffer)} messages)...")
            try:
                await asyncio.wait_for(
                    extract_and_save_memory(
                        self._user_identity,
                        str(self._conversation_id),
                        messages=self._message_buffer,
                    ),
                    timeout=30.0,
                )
            except asyncio.TimeoutError:
                logger.warning(f"[on_exit] Memory extraction timed out for {self._user_identity}")
            except Exception as e:
                logger.warning(f"[on_exit] Memory extraction failed: {e}")

    async def on_user_turn_started(self) -> None:
        self.reset_activity()

    # Set last user message when user done talking
    async def on_user_turn_completed(self, turn_ctx: llm.ChatContext, new_message: llm.ChatMessage) -> None:
        self.reset_activity()
        text = (new_message.text_content or "").strip()
        
        # If the transcribed text is completely empty or just punctuation, skip responding!
        # This prevents false interruptions from VAD feedback or microphone clicks.
        import re
        if not text or not re.search(r'[a-zA-Z0-9\u3040-\u309f\u30a0-\u30ff\u4e00-\u9faf]', text):
            logger.info("Ignoring empty user turn / false VAD trigger.")
            raise StopResponse()
            
        self._last_user_text = text
        
        # Buffer user message
        self._message_buffer.append({
            "role": "user",
            "content": text,
            "emotion": "neutral" # STT doesn't provide emotion yet
        })
        
        await super().on_user_turn_completed(turn_ctx, new_message)

    async def llm_chat(self, chat_ctx, **kwargs):
        """Override to detect emotion and trigger expressions"""
        self.reset_activity()
        # Start of turn: clear animation logs to allow fresh winks/tongues
        await VTUBE.start_turn()

        # Get response from parent
        async for chunk in super().llm_chat(chat_ctx, **kwargs):
            yield chunk
        
        # Emotion detection is now handled per-sentence in aura_tts.py
        pass

    # Set last assistant message when assistant done talking and add to database
    async def on_agent_speech_committed(self, msg: llm.ChatMessage) -> None:
        self.reset_activity()
        self._last_aura_spoke_time = asyncio.get_event_loop().time()
        
        # Buffer assistant message
        self._message_buffer.append({
            "role": "assistant",
            "content": msg.text_content or "",
            "emotion": getattr(msg, 'emotion', 'neutral')
        })
        
        self._last_user_text = ""


# Called When user join the room
async def voice_session(ctx: agents.JobContext):
    logger.info(f"Voice session starting (Job assigned) for room: {ctx.room.name}")
    await ctx.connect()
    logger.info(f"User connected: {ctx.room.name}")

    vtube_connected = await VTUBE.connect()
    if vtube_connected:
        logger.info("VTube Studio connected")

    user_identity = "aura-user"  
    conversation_id_str = None

    # Wait up to 30s for the participant to join so we get the correct identity
    # We loop every 0.1s to be snappy once they arrive.
    found_identity = False
    for i in range(300): # 30s (0.1s steps)
        # 1. Check Job Participant (Direct from Room Join events)
        if ctx.job and getattr(ctx.job, 'participant', None):
            if ctx.job.participant.identity:
                user_identity = ctx.job.participant.identity
                found_identity = True
                if ctx.job.participant.metadata:
                    try:
                        meta = json.loads(ctx.job.participant.metadata)
                        conversation_id_str = meta.get("conversation_id")
                    except: pass
                logger.info(f"Identity discovered from Job Participant: {user_identity}")
        
        # 2. Check Room Participants (Fallback)
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
                logger.info(f"Identity discovered from Room Participant: {user_identity}")

        if found_identity:
            # We found the identity, but let's wait a tiny bit for metadata to settle if it was missing
            if conversation_id_str:
                break
            # If we have identity but no conversation_id, wait a few more frames to see if metadata arrives
            if i > 10: # already waited at least 1s
                break
        
        if i % 20 == 0:
            logger.info("Waiting for participant to join room and reveal identity...")
        await asyncio.sleep(0.1)

    logger.info(f"Resolved identity: '{user_identity}', conversation: '{conversation_id_str}'")

    # 1. Fetch Dynamic Personality and Session from ai-service
    session_endpoint = f"{BACKEND_URL}/api/v1/memory/session"

    conversation_id = None
    session_id = None
    facts = ""

    try:
        headers = {
            "Authorization": f"Bearer {INTERNAL_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "identity": user_identity,
            "platform": "voice"
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
    if is_returning_user:
        logger.info(f"Long-term memory loaded from backend ({len(facts)} chars)")
    else:
        logger.info(f"No long-term memory found for {user_identity}")

    system_prompt = "" # Managed by ai-service internally

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


    
    # 1.1 AiServiceLLM creation
    llm_plugin = AiServiceLLM(
        endpoint=AI_SERVICE_URL,
        auth_token=INTERNAL_API_KEY,
        identity=user_identity,
        conversation_id=str(conversation_id) if conversation_id else ""
    )

    agent_instance = AURAAssistant(
        conversation_id=conversation_id,
        user_identity=user_identity,
        system_prompt=system_prompt,
        initial_chat_ctx=initial_chat_ctx,
        llm=llm_plugin,
        tts=TTS_PLUGIN,
    )

    from livekit.agents import TurnHandlingOptions

    session = AgentSession(
        stt=stt_plugin,
        tts=TTS_PLUGIN,
        vad=silero.VAD.load(
            min_silence_duration=1.2,  # 0.6s was triggering on natural speech pauses
            min_speech_duration=0.1
        ),
        # Local Qwen3 TTS takes ~2s per sentence; preemptive generation starts a
        # second TTS stream before the first finishes, causing audio interleaving
        # (word-soup) and LiveKit "speech not done in time" cancellation errors.
        preemptive_generation=False,
        turn_handling=TurnHandlingOptions(
            interruption={
                "enabled": True,
                "mode": "vad",
                "min_words": 3,   # was 1; require more words to count as real interruption
                "min_duration": 0.8,  # was 0.6
            }
        ),
    )

    async def spontaneous_pulse():
        """Occasionally speaks if the user is quiet too long."""
        while True:
            await asyncio.sleep(60) 
            # We skip pulse logic in this simple restoration to avoid overhead
            # The previous attempt had it but it was a bit complex
            break

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

    # Wait for the background TTS warmup to finish before speaking.
    # Awaiting the event allows the loop to stay responsive for STT/RTC heartbeats.
    if not _tts_ready_event.is_set():
        logger.info("Waiting for background TTS warmup to finish...")
        loop = asyncio.get_event_loop()
        ready = await loop.run_in_executor(None, lambda: _tts_ready_event.wait(60.0))
        if not ready:
            logger.warning("TTS warmup timed out after 60s, proceeding anyway...")

    if ctx.room.remote_participants:
        logger.info("TTS ready, generating greeting via LLM")
        try:
            await session.generate_reply(instructions=instruction, allow_interruptions=False)
        except Exception as e:
            logger.warning(f"Could not deliver dynamic greeting: {e}")

    # Wait for session to finish
    try:
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        logger.info("Voice session cancelled by user/room.")
    finally:
        logger.info(f"Cleaning up session for {user_identity}...")
        # Close STT session first to stop processing new audio
        await stt_session.close()
        
        # Memory extraction is handled in AURAAssistant.on_exit() which fires
        # while the event loop is still live (before session fully tears down).
        
        if vtube_connected:
            await VTUBE.reset_to_neutral()

if __name__ == "__main__":
    agents.cli.run_app(
        agents.WorkerOptions(
            entrypoint_fnc=voice_session,
            prewarm_fnc=prewarm,
        )
    )
