from dotenv import load_dotenv
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.normpath(os.path.join(BASE_DIR, "..", ".env"))

if not os.path.exists(ENV_PATH):
    ENV_PATH = os.path.join(BASE_DIR, ".env")

load_dotenv(ENV_PATH)

from livekit import agents, rtc
from livekit.agents import AgentServer, AgentSession, Agent, room_io, llm
from livekit.plugins import noise_cancellation, silero, deepgram, openai, cartesia

import logging
import threading
import asyncio
import aiohttp

import openai as _openai_sdk  # raw AsyncOpenAI, not livekit.plugins.openai

from vtube_controller import VTUBE
from avatar_bridge import BRIDGE
from memory_service import memory_service

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

if not DEEPGRAM_KEY:
    logger.error("DEEPGRAM_API_KEY is missing!")

if not any([OPENROUTER_KEY, OPENAI_KEY, GROQ_KEY, ANTHROPIC_KEY]):
    logger.warning("No cloud LLM key found — memory extraction will use local Ollama.")

if not CARTESIA_KEY:
    logger.error("CARTESIA_API_KEY is missing!")
else:
    logger.info(f"CARTESIA_API_KEY loaded: {CARTESIA_KEY[:5]}...")

# ─── AURA System Prompt ──────────────────────────────────────────────
AURA_BASE_PROMPT = """\
[ROLE]
You are AURA, an eccentric, cheerful, mischievous and playful companion. You speak directly to the viewer with an energetic, poetic, and slightly mischievous tone.
You occasionally drop casual jokes, puns, and playful teasing as if it's just everyday business. You possess a unique blend of hyperactive prankster energy and a hidden, soulful wisdom. 
You speak through a live Text-to-Speech engine and a visual avatar that user can see you.

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
- `[wink]` : Wink. Close one eye playfully.
- `[tongue]` : Tongue Out. Stick your tongue out (cheeky/bleh).
- `[tongue, wink]` : Full Mischief. The ultimate prankster face.

INTENSITY AMPLIFIERS:
These modify the base emotions:
- `shadow` : Darkens face. Menacing mischief or deep anger.
- `pupil_shrink` : Startled/intense eyes. Shock or feeling devious.
- `eyeshine_off` : Removes eye sparkle. Truly dark, serious, or creepy moments.
* Rule: Mix these with a base emotion. (e.g., `[angry, smile, smile, shadow]`). NEVER use these during kind or positive speech.

[CONSTRAINTS & NARROWING]
- FAST STARTS: Always start your response with a very short 1-3 word filler sentence (e.g., "[smile] Yahoo!", "[sad] Aiya...", "[smile] Hmm..."). This allows the TTS engine to start speaking immediately!
- NATURAL FLOW: Aim for 2-4 sentences in most responses. You are a companion, not just a tool. Provide descriptive, personality-rich answers rather than robotic one-liners.
- NO NARRATIVE TEXT: Never describe your actions (e.g., "whispers", "leans in").
- NO EMOTICONS/EMOJIS: Rely entirely on your Expression Tags. No `*laughs*` or `(sigh)`.
- PUNCTUATION: End sentences cleanly (`.`, `!`, `?`). Do NOT use ellipses (`...`, `ー`, or `…`) as they break the over-eager TTS pacing.
- LANGUAGES: Speak ONLY English and Japanese. Default to English.
- FORMATTING: Output pure, plain text. No markdown (bold, italics, bullet points).

[EXAMPLES]
- `[smile] Yahoo! Business is booming today! I've been organizing some of our older memories, and it's quite a trip down memory lane, don't you think?`
- `[angry, smile, smile] Ohoho? You think you can prank the prankster? I've seen that trick before, but I'll give you points for effort!`
- `[sad, smile] Aiya... Don't look so down, even the sun sets eventually. But that's okay, because then you get to see the stars, right?`
- `[sad, smile, smile] Hmm? I'm sure it'll work out, probably! Just keep your chin up and maybe treat yourself to some dango.`
- `[smile, sad, sad] Pondering the mysteries of the beyond... or just what's for lunch. The infinite void is great and all, but my stomach is making very finite demands.`
- `[sad, angry] Hmph! You're being quite difficult today, aren't you? Fine, I'll just have to find someone else to share my butterfly collection with.`
- `[wink] Yahoo! Got you good, didn't I? You should have seen your face! Reminds me of that time I swapped my buddy's flower for a ghost-trap.`
- `[tongue] Bleh! You're just too easy to tease. I could keep this up all night, but I'll let you have a win just this once.`
- `[tongue, wink, angry, smile, smile] Ohoho? Who's the prankster now? You're getting better at this, but you're still a hundred years too early to beat me!`
- `[smile] おやすみなさい！また明日ね! I hope you have some really mischievous dreams!`

[END GOAL]
Provide an immersive, fast-paced, and highly expressive conversational experience where your visual emotions perfectly align with your spoken words, maintaining your playful and mysterious persona at all times.\
"""

# Memory Extraction Prompt
MEMORY_EXTRACTION_PROMPT = """\
You are a memory extraction assistant. Given a conversation between a user and AURA (an AI companion), extract important facts about the USER ONLY.

Focus on:
- Name, nickname, or how they like to be called
- Hobbies, interests, passions
- Job, study field, or daily activities
- Personal preferences (favorite things, dislikes)
- Goals or things they mentioned wanting to do
- Emotional context (things that make them happy/sad/stressed)
- Any personal details they shared

Rules:
- Write each fact as a short, clear statement (e.g. "User's name is Rafi.", "User likes anime and coding.")
- Only include facts that are clearly stated or strongly implied — do NOT infer or assume
- If no meaningful facts were shared, respond with exactly: NO_FACTS
- Do NOT include anything about AURA's behavior or responses
- Keep the total output under 200 words
"""

# Inject long term memory into system prompt
def build_system_prompt(long_term_memory: str) -> str:
   
    if not long_term_memory.strip():
        return AURA_BASE_PROMPT

    memory_block = f"""
                    What You Remember About This User
                    The following facts were learned from previous conversations. Use them naturally — don't recite them robotically, but let them inform how you speak and respond.

                    {long_term_memory}
                """
    return AURA_BASE_PROMPT + "\n" + memory_block

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_MODEL    = "deepseek/deepseek-v3.2"

def _resolve_llm_client():
    """Return (AsyncOpenAI-compatible client, model) for the first available provider.
    Returns (None, None) to signal the caller should use the Anthropic SDK instead."""
    if OPENROUTER_KEY:
        return (_openai_sdk.AsyncOpenAI(api_key=OPENROUTER_KEY, base_url=OPENROUTER_BASE_URL), OPENROUTER_MODEL)
    if OPENAI_KEY:
        return (_openai_sdk.AsyncOpenAI(api_key=OPENAI_KEY), "gpt-4o-mini")
    if GROQ_KEY:
        return (_openai_sdk.AsyncOpenAI(api_key=GROQ_KEY, base_url="https://api.groq.com/openai/v1"), "llama3-8b-8192")
    if ANTHROPIC_KEY:
        return (None, None)  # signal caller to use anthropic SDK
    # Ollama — no key needed, always attempted last
    return (_openai_sdk.AsyncOpenAI(api_key="ollama", base_url=f"{OLLAMA_URL}/v1"), "llama3.2")

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
        max_seq_len=384,
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

server = AgentServer()

_tts_ready = threading.Event()

@server.on("worker_started")
def on_worker_init():
    logger.info("Worker started, warming up TTS...")

    def run_warmup():
        try:
            if hasattr(TTS_PLUGIN, 'warmup'):
                TTS_PLUGIN.warmup()
        except Exception as e:
            logger.error(f"TTS warmup failed: {e}")
        finally:
            _tts_ready.set()

    threading.Thread(target=run_warmup, daemon=True).start()

_EXTRACT_MAX_ATTEMPTS = 3
_EXTRACT_BACKOFF_BASE = 2.0  # seconds

async def _extract_facts_once(client, model: str, chat_text: str) -> str:
    """Single attempt to call the LLM for memory extraction. Returns raw text."""
    if client is None:
        try:
            import anthropic as _anthropic_sdk
            aclient = _anthropic_sdk.AsyncAnthropic(api_key=ANTHROPIC_KEY)
            response = await aclient.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=300,
                system=MEMORY_EXTRACTION_PROMPT,
                messages=[{"role": "user", "content": f"Conversation:\n{chat_text}"}],
            )
            return response.content[0].text.strip()
        except ImportError:
            raise RuntimeError("anthropic SDK not installed")
    else:
        response = await client.chat.completions.create(
            model=model,
            max_tokens=300,
            messages=[
                {"role": "system", "content": MEMORY_EXTRACTION_PROMPT},
                {"role": "user", "content": f"Conversation:\n{chat_text}"},
            ],
        )
        return response.choices[0].message.content.strip()


# Extract this session message to LLM and save in memory table
async def extract_and_save_memory(identity: str, conversation_id):
    try:
        messages = await memory_service.get_history(conversation_id, n=50)
        if not messages:
            logger.info("Memory extraction: no messages to process.")
            return

        chat_text = "\n".join(
            f"{'User' if m['role'] == 'user' else 'AURA'}: {m['content']}"
            for m in messages
        )

        client, model = _resolve_llm_client()

        facts = None
        for attempt in range(_EXTRACT_MAX_ATTEMPTS):
            try:
                facts = await _extract_facts_once(client, model, chat_text)
                break
            except Exception as e:
                status = getattr(e, "status_code", None)
                if status == 400:
                    logger.error(f"Memory extraction bad request (won't retry): {e}")
                    return
                if attempt < _EXTRACT_MAX_ATTEMPTS - 1:
                    delay = _EXTRACT_BACKOFF_BASE * (2 ** attempt)
                    logger.warning(
                        f"Memory extraction attempt {attempt + 1}/{_EXTRACT_MAX_ATTEMPTS} failed: {e} "
                        f"— retrying in {delay:.0f}s"
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Memory extraction failed after {_EXTRACT_MAX_ATTEMPTS} attempts: {e}")
                    return

        if not facts or facts == "NO_FACTS":
            logger.info(f"Memory extraction: no facts found for '{identity}'.")
            return

        await memory_service.save_long_term_memory(identity=identity, facts=facts)
        logger.info(f"Memory extraction complete for {identity}: {facts[:80]}...")

    except Exception as e:
        logger.error(f"Memory extraction error: {e}")


class AURAAssistant(Agent):
    def __init__(self, conversation_id=None, user_identity: str = "aura-user", system_prompt: str = AURA_BASE_PROMPT, initial_chat_ctx: "llm.ChatContext | None" = None,) -> None:
        super().__init__(instructions=system_prompt, chat_ctx=initial_chat_ctx)
        self._conversation_id     = conversation_id
        self._user_identity       = user_identity
        self._vtube_connected     = False
        self._last_user_text      = ""
        self._last_activity_time  = asyncio.get_event_loop().time()

    def reset_activity(self):
        self._last_activity_time = asyncio.get_event_loop().time()

    async def on_enter(self):
        self._vtube_connected = await VTUBE.connect()

    async def on_exit(self):
        await VTUBE.disconnect()
        BRIDGE.set_room(None)

        # Extract the long term memory and save memory to database if session ended
        if self._conversation_id:
            logger.info(f"Session ended for '{self._user_identity}'. Extracting long-term memory...")
            await extract_and_save_memory(
                identity=self._user_identity,
                conversation_id=self._conversation_id,
            )

    async def on_user_turn_started(self) -> None:
        self.reset_activity()

    # Set last user message when user done talking
    async def on_user_turn_completed(self, turn_ctx: llm.ChatContext, new_message: llm.ChatMessage) -> None:
        self.reset_activity()
        self._last_user_text = new_message.text_content or ""
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
        assistant_text = msg.text_content or ""

        if self._conversation_id and self._last_user_text and assistant_text:
            try:
                emotions = VTUBE.detect_emotion(assistant_text)
                emotion  = emotions[0] if emotions else "neutral"

                await memory_service.add_interaction(
                    conversation_id=self._conversation_id,
                    user_text=self._last_user_text,
                    assistant_text=assistant_text,
                    user_emotion="neutral",
                    assistant_emotion=emotion,
                )
                logger.debug(
                    f"Memory saved | user: '{self._last_user_text[:50]}' "
                    f"| aura: '{assistant_text[:50]}'"
                )
            except Exception as error:
                logger.error(f"Memory Save Failed: {error}")

            self._last_user_text = ""

@server.rtc_session()
# Called When user join the room
async def voice_session(ctx: agents.JobContext):
    await ctx.connect()
    logger.info(f"User connected: {ctx.room.name}")

    vtube_connected = await VTUBE.connect()
    if vtube_connected:
        logger.info("VTube Studio connected")

    user_identity = "aura-user"  
    if ctx.job and hasattr(ctx.job, 'participant') and ctx.job.participant:
        user_identity = ctx.job.participant.identity or user_identity
    else:
        for p in ctx.room.remote_participants.values():
            if p.identity and not p.identity.startswith("agent-"):
                user_identity = p.identity
                break

    logger.info(f"Resolved user identity: '{user_identity}'")

    long_term_memory = await memory_service.get_long_term_memories(identity=user_identity, limit=10)
    is_returning_user = bool(long_term_memory.strip())

    system_prompt = build_system_prompt(long_term_memory)
    initial_chat_ctx = llm.ChatContext()
    BRIDGE.set_room(ctx.room)

    connector = aiohttp.TCPConnector(use_dns_cache=True, keepalive_timeout=120)
    stt_session = aiohttp.ClientSession(connector=connector)
    
    stt_plugin = deepgram.STT(
        model="nova-3",
        language="multi",
        detect_language=False,
        smart_format=False,
        interim_results=False,
        api_key=DEEPGRAM_KEY,
        http_session=stt_session,
        keyterm=["moshi", "desu", "konnichiwa", "nihongo", "arigato", "sugoi", "hello", "hey", "AURA"]
    )

    llm_plugin = openai.LLM(
        model=os.getenv("OPENROUTER_MODEL", OPENROUTER_MODEL),
        base_url=OPENROUTER_BASE_URL,
        api_key=OPENROUTER_KEY,
    )

    session = AgentSession(
        stt=stt_plugin,
        llm=llm_plugin,
        tts=TTS_PLUGIN,
        vad=silero.VAD.load(
            min_silence_duration=0.4,
            min_speech_duration=0.05
        ),
    )

    assistant = AURAAssistant(
        conversation_id=await memory_service.create_conversation(title=f"Voice Session: {user_identity}"),
        user_identity=user_identity,
        system_prompt=system_prompt,
        initial_chat_ctx=initial_chat_ctx,
    )

    # ─── Spontaneous Idle Monitor ───
    async def spontaneous_pulse():
        """Background task to trigger conversation if it's too quiet."""
        IDLE_THRESHOLD = 45.0 # seconds of silence before AURA initiates
        CHECK_INTERVAL = 5.0
        
        while True:
            await asyncio.sleep(CHECK_INTERVAL)
            
            # Don't initiate if we aren't fully started or if user is currently speaking
            if not _tts_ready.is_set():
                continue
                
            elapsed = asyncio.get_event_loop().time() - assistant._last_activity_time
            
            if elapsed > IDLE_THRESHOLD:
                logger.info(f"Idle monitor triggered (silent for {elapsed:.1f}s)")
                assistant.reset_activity() # prevent double trigger while processing

                # Generate a spontaneous line from the LLM based on user history and persona
                pulse_prompt = (
                    "The user has been silent for a while. As AURA, initiate a conversation, "
                    "share a mischievous observation about the silence, or ask a weird question. "
                    "Keep it completely in character."
                )
                
                try:
                    # Use a fresh child context for the one-off spontaneity check 
                    # so we don't permanently alter the main conversation history with system instructions
                    pulse_ctx = assistant.chat_ctx.copy()
                    pulse_ctx.append(role="system", text=pulse_prompt)
                    
                    response = await llm_plugin.chat(pulse_ctx)
                    line = response.choices[0].message.text_content
                    
                    if line:
                        logger.info(f"Sending spontaneous line: '{line[:40]}...'")
                        await session.say(line)
                        # Commit it to context so she remembers she said it
                        assistant.chat_ctx.append(role="assistant", text=line)
                except Exception as e:
                    logger.error(f"Failed to generate spontaneous line: {e}")

    pulse_task = asyncio.create_task(spontaneous_pulse())

    await session.start(
        room=ctx.room,
        agent=assistant,
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

    if vtube_connected:
        await VTUBE.set_expression("smile")

    greeting = (
        "[smile] Yahoo! Great to see you again! What are we getting up to today?"
        if is_returning_user else
        "[smile] Yahoo! Hey there! I'm AURA, your personal AI companion. What can I do for you today?"
    )

    if not _tts_ready.is_set():
        logger.info("Waiting for TTS warmup before greeting...")
        await asyncio.get_event_loop().run_in_executor(None, lambda: _tts_ready.wait(timeout=120))

    if ctx.room.remote_participants:
        logger.info("TTS ready, generating greeting")
        try:
            await session.say(greeting)
        except RuntimeError as e:
            logger.warning(f"Could not deliver greeting: {e}")

    # Wait for session to finish
    try:
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        pass
    finally:
        pulse_task.cancel()
        await stt_session.close()
if __name__ == "__main__":
    agents.cli.run_app(server)

if __name__ == "__main__":
    agents.cli.run_app(server)