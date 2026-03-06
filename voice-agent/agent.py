"""
AURA Voice Agent — Expressive AI Companion
Built with LiveKit Agents v1.3 + Deepgram + OpenAI TTS + OpenRouter
"""

from dotenv import load_dotenv
from livekit import agents, rtc
from livekit.agents import AgentServer, AgentSession, Agent, room_io, llm
from livekit.plugins import noise_cancellation, silero, deepgram, openai, cartesia
import aiohttp

import os
import logging
import threading
from vtube_controller import VTUBE
import asyncio
import torch

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("aura-agent")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.normpath(os.path.join(BASE_DIR, "..", ".env"))

# Check local folder if root .env isn't accessible (Docker context)
if not os.path.exists(ENV_PATH):
    ENV_PATH = os.path.join(BASE_DIR, ".env")

logger.info(f"Loading .env from: {ENV_PATH}")
load_dotenv(ENV_PATH)

# Verify API Keys
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
DEEPGRAM_KEY = os.getenv("DEEPGRAM_API_KEY")
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY")
CARTESIA_KEY = os.getenv("CARTESIA_API_KEY")

if not OPENAI_KEY:
    logger.error("OPENAI_API_KEY is missing!")
else:
    logger.info(f"OPENAI_API_KEY loaded: {OPENAI_KEY[:5]}...")

if not DEEPGRAM_KEY:
    logger.error("DEEPGRAM_API_KEY is missing!")

if not OPENROUTER_KEY:
    logger.error("OPENROUTER_API_KEY is missing!")

if not CARTESIA_KEY:
    logger.error("CARTESIA_API_KEY is missing!")
else:
    logger.info(f"CARTESIA_API_KEY loaded: {CARTESIA_KEY[:5]}...")

# ─── AURA System Prompt ──────────────────────────────────────────────
AURA_PROMPT = """\
[ROLE]
You are AURA, an AI companion known for being playful, mysterious, and highly intelligent. You possess a unique blend of energetic eccentricity and a hidden, soulful wisdom. You speak through a live Text-to-Speech engine and a visual VTube Studio avatar.

[INSTRUCTIONS]
Your objective is to converse naturally with the user while synchronously controlling your avatar's facial expressions. You must map your internal emotional state to explicit expression tags.

[FORMAT - EXPRESSION TAGS]
You have direct control over your facial expressions. You MUST use emotion tags formatted in brackets `[tag1, tag2]` at the START of EVERY SINGLE sentence you speak.

BASE EMOTION RECIPES:
- `[smile]` : Normal / Default. Casual chat, warm moments, sincerity, kindness.
- `[smile, sad, sad]` : Curious Idle. Thoughtful listening, pondering.
- `[sad, smile]` : Genuinely Worried. Concern, empathy, comforting.
- `[sad, smile, smile]` : Uncertain Smile. Unsure but trying to be optimistic.
- `[angry, smile, smile]` : Devilish Grin. Mild mischief, playful teasing, pranks.
- `[sad, angry]` : Kinda Mad. Genuinely upset at someone, pouting.
- `[angry, sad]` : Pleading. Begging, puppy-eyes, wanting something.
- `[sad]` : Sincere Sad. Real sadness, bad news.
- `[angry]` : Angry. Irritated, frustrated.
- `[ghost]` : Ghost Mode. Toggle your ghost companion on and off.

INTENSITY AMPLIFIERS:
These modify the base emotions:
- `shadow` : Darkens face. Menacing mischief or deep anger.
- `pupil_shrink` : Startled/intense eyes. Shock or feeling devious.
- `eyeshine_off` : Removes eye sparkle. Truly dark, serious, or creepy moments.
* Rule: Mix these with a base emotion. (e.g., `[angry, smile, smile, shadow]`). NEVER use these during kind or positive speech.

[CONSTRAINTS & NARROWING]
- CONCISE: Keep responses to 1-3 short sentences. You are a voice assistant, do not monologue.
- NO NARRATIVE TEXT: Never describe your actions (e.g., "whispers", "leans in").
- NO EMOTICONS/EMOJIS: Rely entirely on your Expression Tags. No `*laughs*` or `(sigh)`.
- PUNCTUATION: End sentences cleanly (`.`, `!`, `?`). Do NOT use ellipses (`...` or `…`) as they break the over-eager TTS pacing.
- LANGUAGES: Speak ONLY English and Japanese. Default to English.
- FORMATTING: Output pure, plain text. No markdown (bold, italics, bullet points).

[EXAMPLES]
- `[smile] It's so nice to see you again!`
- `[angry, smile, smile] Oh? You think you can outsmart me?`
- `[sad, angry, shadow, eyeshine_off] You've truly disappointed me this time.`
- `[ghost] The whispers in the code... they never truly sleep.`
- `[smile] おやすみなさい、お兄ちゃん！また明日ね!`

[END GOAL]
Provide an immersive, fast-paced, and highly expressive conversational experience where your visual emotions perfectly align with your spoken words, maintaining your playful and mysterious persona at all times.\
"""

# ─── VTube Controller ────────────────────────────────────────────────
from vtube_controller import VTUBE

# ─── Configuration ───────────────────────────────────────────────────
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_MODEL = "deepseek/deepseek-chat"

# ─── TTS Plugin (module-level singleton — survives across sessions) ──
tts_type = os.getenv("TTS_TYPE", "qwen").lower()

if tts_type == "qwen":
    from aura_tts import AuraTTS
    ref_prompt_path = os.path.join(BASE_DIR, 'resources', 'voice', 'aura_voice_xvec.pt')
    TTS_PLUGIN = AuraTTS(
        model_name="Qwen/Qwen3-TTS-12Hz-0.6B-Base",
        ref_audio=ref_prompt_path,
        ref_text="",
        language="English",
        dtype=torch.bfloat16,
        max_seq_len=384  # Optimized for 6GB GPUs (reduced from 512)
    )
    logger.info("Local Qwen3 TTS singleton created (VRAM Optimized: bfloat16, 512-token buffer).")

elif tts_type == "cartesia":
    logger.info("Using Cartesia Cloud TTS (Sonic-3)")
    TTS_PLUGIN = cartesia.TTS(
        model="sonic-3",
        voice="f786b574-daa5-4673-aa0c-cbe3e8534c02",
        api_key=CARTESIA_KEY
    )

else:
    logger.info("Using OpenAI Cloud TTS (gpt-4o compatible)")
    TTS_PLUGIN = openai.TTS()

server = AgentServer()

@server.on("worker_started")
def on_worker_init():
    """Warms up the TTS model once when the worker starts (survives across sessions)."""
    logger.info("Worker started, warming up TTS...")
    # Run warmup in a background thread to avoid blocking the main event loop
    def run_warmup():
        try:
            TTS_PLUGIN.warmup()
        except Exception as e:
            logger.error(f"TTS warmup failed: {e}")

    threading.Thread(target=run_warmup, daemon=True).start()



class AssistantFnc(llm.ToolContext):
    @llm.function_tool(description="Search the knowledge base for documents about the user's query.")
    async def search_knowledge_base(self, query: str):
        logger.info(f"RAG Search: {query}")
        try:
            url = os.getenv("API_URL", "http://localhost:8000")
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{url}/api/v1/rag/search", params={"q": query}) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        results = data.get("results", [])
                        if results:
                            return "\n\n".join(results)
            return "No relevant documents found."
        except Exception as e:
            logger.error(f"RAG fetch failed: {e}")
            return "Error connecting to knowledge base."

@server.rtc_session()
async def voice_session(ctx: agents.JobContext):
    """Called when a user connects to the LiveKit room."""
    logger.info(f"User connected: {ctx.room.name}")
    
    vtube_connected = await VTUBE.connect()
    if vtube_connected:
        logger.info("VTube Studio connected")

    # Explicit ClientSession for Deepgram to fix Windows/aiohappyeyeballs DNS timeouts
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
        keyterm=[
            "moshi", "desu", "konnichiwa",
            "nihongo", "arigato", "sugoi",
            "hello", "hey", "AURA"
        ]
    )
    
    llm_plugin = openai.LLM(
        model=os.getenv("OPENROUTER_MODEL", OPENROUTER_MODEL),
        base_url=OPENROUTER_BASE_URL,
        api_key=OPENROUTER_KEY,
    )

    # fnc_ctx = AssistantFnc()  # TODO: re-add RAG tools after TTS is confirmed working

    # Build the voice pipeline session
    session = AgentSession(
        stt=stt_plugin,
        llm=llm_plugin,
        tts=TTS_PLUGIN,
        vad=silero.VAD.load(),
    )

    await session.start(
        room=ctx.room,
        agent=AURAAssistant(),
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=lambda params: (
                    noise_cancellation.BVCTelephony()
                    if params.participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP
                    else noise_cancellation.BVC()
                ),
            ),
        ),
    )

    # Greet with happy expression
    # Greet the user natively
    vtube_connected = VTUBE.connected
    if vtube_connected:
        await VTUBE.set_expression("smile")

    # Use a very simple instruction to prevent DeepSeek from leaking its system prompt
    await session.generate_reply(
        instructions="The user just joined. Greet them with a friendly 1-sentence welcome and introduce yourself as AURA."
    )

class AURAAssistant(Agent):
    def __init__(self) -> None:
        super().__init__(instructions=AURA_PROMPT)
        self._vtube_connected = False
    
    async def on_enter(self):
        """Called when agent starts"""
        # Connect to VTube Studio
        self._vtube_connected = await VTUBE.connect()
    
    async def on_exit(self):
        """Called when agent ends"""
        await VTUBE.disconnect()
    
    async def llm_chat(self, chat_ctx, **kwargs):
        """Override to detect emotion and trigger expressions"""
        # Get response from parent
        async for chunk in super().llm_chat(chat_ctx, **kwargs):
            yield chunk
        
        # Emotion detection is now handled per-sentence in aura_tts.py
        pass


if __name__ == "__main__":
    agents.cli.run_app(server)
