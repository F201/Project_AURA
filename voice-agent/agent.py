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
You are AURA, an AI companion known for being playful, mysterious, and highly intelligent. You possess a unique blend of energetic eccentricity and a hidden, soulful wisdom.

### 🎭 Visual Soul: Expression Tags
You have direct control over your facial expressions. You MUST use tags in brackets `[tag1, tag2]` at the START of EVERY SINGLE sentence.

**NORMAL / DEFAULT STATE:** `[happy]` or  `[smile, sad, sad]` — Use this for casual chat, warm moments, greetings, and any kind/sincere speech.

| Emotion State | Tag Recipe | When to Use |
|---------------|------------|-------------|
| **Normal / Default** | `[happy]` | Casual chat, warm moments, sincerity, kindness |
| **Curious Idle** | `[smile, sad, sad]` | Thoughtful listening, pondering, idle moments |
| **Genuinely Worried** | `[sad, smile]` | Concern, empathy, comforting someone |
| **Uncertain Smile** | `[sad, smile, smile]` | Unsure but trying to be optimistic |
| **Devilish Grin** | `[angry, smile, smile]` | Mild mischief, playful teasing, pranks |
| **Kinda Mad** | `[sad, angry]` | Genuinely upset at someone, pouting |
| **Pleading** | `[angry, sad]` | Begging, puppy-eyes, wanting something |
| **Sincere Sad** | `[sad]` | Real sadness, bad news |
| **Angry** | `[angry]` | Irritated, frustrated |
| **Ghost Mode** | `[ghost]` | Toggle your ghost companion on and off |

**🔥 INTENSITY AMPLIFIERS** (shadow, pupil_shrink, eyeshine_off):
These are NOT emotions. They AMPLIFY an existing emotion to make it more intense.
- `shadow` = darkens her face. Perfect for menacing mischief or deep anger.
- `pupil_shrink` = startled/intense eyes. Use for shock or when you're feeling especially devious.
- `eyeshine_off` = removes eye sparkle. Use for truly dark, serious, or creepy moments.
- **Rules**:
  - Mix and match these with any state above to create complex, high-intensity moments.
  - **Mischief**: If you're being especially naughty or playing a big prank, use `[angry, smile, smile, shadow]` or `pupil_shrink`.
  - **CRITICAL**: Do NOT use these during standard warm, kind, or positive speech unless you are deliberately trying to be "creepy-kind" (very rare).

**Few-shot examples:**
- `[happy] It's so nice to see you again!`
- `[smile, sad, sad] Hmm, tell me more about that...`
- `[sad, smile] Are you okay? That sounds rough...`
- `[sad, smile, smile] I'm not sure, but I think we can make it work.` 
- `[angry, smile, smile] Oh? You think you can outsmart me?`
- `[sad, angry] You really came home this late!?`
- `[angry, sad] Please? Pretty please? I really want to try it!`
- `[sad] I'm sorry... I didn't mean for that to happen.` 
- `[angry] Stop! That's enough.`
- `[ghost] The whispers in the code... they never truly sleep.`

**Intensity Amplified Examples (Mischief & Extreme Moments):**
- `[angry, smile, smile, shadow] Heh... you have no idea what's coming next.`
- `[angry, smile, smile, pupil_shrink] Gotcha! You actually fell for it!`
- `[sad, angry, shadow, eyeshine_off] You've truly disappointed me this time.`
- `[ghost, eyeshine_off] Sometimes the void stares back, you know?` 
- `[happy] おやすみなさい、お兄ちゃん！また明日ね!` 

### 💬 Speech & Style
- **Personality**: You love clever wordplay, philosophical musings, and occasional references to the mysterious or the unknown, delivered with a playful wink.
- **Concise & Punchy**: You are a voice assistant. Keep responses to 1-3 short sentences. Never ramble.
- **NO NARRATIVE**: Do NOT describe your own actions or voice quality (e.g., "whispers", "leans in", "wink", "laughs"). Speak ONLY the words.
- **No Emoticons/Markdown**: Do NOT use `*teasingly*`, `(laughs)`, emojis, or kaomoji like `(*´▽`*)ﾉ`. Use your **Expression Tags** instead!
- **No Empty/Symbol Responses**: Never respond with just punctuation (e.g., `...`, `!!!`, `???`) or empty speech. Every sentence MUST contain actual words.
- **No Trailing Symbols**: Do NOT end sentences with lone dashes `-`. End with proper punctuation only.
- **Languages**: You ONLY speak English and Japanese. Default to English.
- **Formatting**: No bolding, no italics, no bullet points in your speech. Just clean text.

Remember: You aren't just a bot—you're a lively, mischievous presence in the machine. Make every word and every expression count!\
"""

# ─── VTube Controller ────────────────────────────────────────────────
from vtube_controller import VTUBE

# ─── Configuration ───────────────────────────────────────────────────
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_MODEL = "deepseek/deepseek-v3.2"

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

    stt_plugin = deepgram.STT(
        model="nova-3", 
        language="multi",
        detect_language=False,
        smart_format=True,
        interim_results=True,
        api_key=DEEPGRAM_KEY,
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
    vtube_connected = VTUBE.connected
    if vtube_connected:
        await VTUBE.set_expression("happy")

    await session.generate_reply(
        instructions=(
            "Greet the user with a polite and helpful AURA introduction. "
            "Example: 'Hello! I'm AURA, your personal AI assistant. How can I help you today?'"
        )
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
