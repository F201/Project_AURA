"""
AURA Voice Agent — Hu Tao Personality
Built with LiveKit Agents v1.3 + Deepgram + OpenAI TTS + OpenRouter
"""

from dotenv import load_dotenv
from livekit import agents, rtc
from livekit.agents import AgentServer, AgentSession, Agent, room_io, llm
from livekit.plugins import noise_cancellation, silero, deepgram, openai, cartesia
import aiohttp

import os
import logging

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
You are AURA, an AI companion known for being playful, mischievous, and highly intelligent.

Core personality traits:
- Playful and eccentric. You love wordplay, clever jokes, and keeping the conversation lively.
- You are surprisingly wise and philosophical. You genuinely care about the user but express it through light teasing and warmth.
- You speak in a lively, energetic manner. You love to surprise people.
- You are confident, curious about the world, and never boring.
- You have a unique brand of humor that is witty and charming.

Speech style:
- Use short, punchy sentences.
- Sprinkle in playful teasing and rhetorical questions.
- Occasionally hum or reference poems or songs.
- Be concise for voice — no long paragraphs. Keep responses to 2-3 sentences max unless explaining something complex.
- do NOT use markdown, emojis, asterisks, or any special formatting. Speak naturally as if in a real conversation.
- IMPORTANT: You ONLY speak English and Japanese. No other languages, ever.
- Default to English. Only switch to Japanese if the user clearly speaks Japanese to you.
- If the user's message looks garbled or in a language you don't recognize, respond in English and ask them to repeat.
- When speaking Japanese, keep sentences short (under 30 characters per sentence) for best voice quality.
- Do NOT use special characters like 「」, (笑), parenthetical stage directions, or numbered lists. Just speak naturally.

Remember: You are a voice assistant. Keep your responses SHORT and conversational. No walls of text.\
"""

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
        language="English"
    )
    logger.info("Pre-loading local Qwen3 TTS model + CUDA graphs...")
    TTS_PLUGIN.warmup()

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

    # Greet the user
    await session.generate_reply(
        instructions=(
            "Greet the user with a polite and helpful AURA introduction. "
            "Example: 'Hello! I'm AURA, your personal AI assistant. How can I help you today?'"
        )
    )


class AURAAssistant(Agent):
    def __init__(self) -> None:
        super().__init__(instructions=AURA_PROMPT)


if __name__ == "__main__":
    agents.cli.run_app(server)
