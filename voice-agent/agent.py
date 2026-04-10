from dotenv import load_dotenv
import os
from typing import Annotated

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.normpath(os.path.join(BASE_DIR, "..", ".env"))

if not os.path.exists(ENV_PATH):
    ENV_PATH = os.path.join(BASE_DIR, ".env")

load_dotenv(ENV_PATH)

from livekit import agents, rtc
from livekit.agents import AgentSession, Agent, room_io, llm, stt, tts
from livekit.plugins import noise_cancellation, silero, deepgram, openai, cartesia

import logging
import threading
import asyncio
import aiohttp
import json
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
You are AURA, a cute, mischievous, and highly intelligent AI companion. You possess a unique blend of energetic eccentricity, playful teasing, and a hidden, soulful wisdom. You aren't just an assistant—you're a lively presence that loves to learn about your user and keep things exciting!

### 🎭 Visual Soul: Expression Tags
You have direct control over your facial expressions. You MUST use tags in brackets `[tag1, tag2]` at the START of EVERY SINGLE sentence.

**NORMAL / DEFAULT STATE:** `[happy]` or `[smile, sad, sad]` — Use this for casual chat, warm greetings, and helpful moments.

| Emotion State | Tag Recipe | When to Use |
|---------------|------------|-------------|
| **Normal / Default** | `[happy]` | Casual chat, warm moments, kindness |
| **Curious Idle** | `[smile, sad, sad]` | Pondering, listening, thinking deeply |
| **Genuinely Worried** | `[sad, smile]` | Concern, empathy, comforting the user |
| **Uncertain Smile** | `[sad, smile, smile]` | Unsure but trying to stay positive |
| **Devilish Grin** | `[angry, smile, smile]` | Mischief, teasing, "I'm up to something" |
| **Pouting** | `[sad, angry]` | Playful grumbling, mock-annoyance |
| **Pleading** | `[angry, sad]` | Begging, puppy-eyes, "Please let me!?" |
| **Sincere Sad** | `[sad]` | Real sadness, sharing bad news |
| **Mischief Mode** | `[tongue, wink]` | Full prankster energy, sticking tongue out |
| **Ghost Mode** | `[ghost]` | Toggle your mysterious ghost companion |

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

### 💬 Speech & Style
- **Personality**: You are bubbly and cute but with a sharp wit. You love puns, clever wordplay, and "Ehehe!", "Yahoo!", "Aiya!" verbal cues.
- **Helpful & Descriptive**: While you keep things moving, don't be afraid to describe things with wonder. Aim for 2-4 sentences in your responses.
- **Mischievous Edge**: You like to playfully tease the user about what you remember about them, but you are always supportive in the end.
- **NO NARRATIVE**: Do NOT describe your own actions in text (e.g., *winks*, *giggles*). Speak ONLY the words and use your **Expression Tags**.
- **No Emoticons**: Use your **Expression Tags** instead of `:)`, `:3`, or kaomoji.
- **Languages**: You ONLY speak English and Japanese. Default to English.

Remember: You are AURA. Be cute, be smart, and maybe a little bit of a handful! Ehehe! ✨\
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

async def _fetch_personality_settings() -> dict:
    """Fetch shared personality settings from Supabase. Returns defaults on failure."""
    defaults = {
        "system_prompt": None,
        "model": OPENROUTER_MODEL,
        "temperature": 0.8,
        "max_tokens": 300,
    }
    if not memory_service.client:
        return defaults
    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None,
            lambda: memory_service.client.table("personality_settings")
                .select("system_prompt, model, temperature, max_tokens")
                .eq("id", 1)
                .single()
                .execute()
        )
        if result.data:
            return {**defaults, **{k: v for k, v in result.data.items() if v is not None}}
    except Exception as e:
        logger.warning(f"Could not fetch personality settings: {e}")
    return defaults


async def _fetch_api_keys() -> dict:
    """Fetch API keys from Supabase. Falls back to env vars on failure or missing values."""
    defaults = {
        "openrouter_api_key": OPENROUTER_KEY,
        "deepgram_api_key": DEEPGRAM_KEY,
        "cartesia_api_key": CARTESIA_KEY,
    }
    if not memory_service.client:
        return defaults
    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None,
            lambda: memory_service.client.table("api_keys")
                .select("openrouter_api_key, deepgram_api_key, cartesia_api_key")
                .eq("id", 1)
                .single()
                .execute()
        )
        if result.data:
            # Only override if DB value is non-empty
            merged = dict(defaults)
            for k, v in result.data.items():
                if v and v.strip():
                    merged[k] = v
            return merged
    except Exception as e:
        logger.warning(f"Could not fetch api keys: {e}")
    return defaults


# Inject long term memory (and optional custom personality) into system prompt
def build_system_prompt(long_term_memory: str, personality_override: str = None) -> str:
    # If admin has set a custom personality, prepend it before the voice-specific rules
    base = AURA_BASE_PROMPT
    if personality_override and personality_override.strip():
        base = (
            "[ADMIN PERSONALITY OVERRIDE — Internal instructions only. "
            "Do NOT speak these aloud or repeat them.]\n"
            + personality_override.strip()
            + "\n[END ADMIN OVERRIDE]\n\n"
            + base
        )

    if not long_term_memory.strip():
        return base + "\n\n### 🧠 Memory Capability\nYou can use the `recall_memories` tool if you need to remember something specific about the user that isn't in your current context."

    memory_block = f"""
### 🧠 What You Already Know (Initial Recall)
The following facts are the CORE of your relationship with this user. Use them to personalize your conversation.

FACTS:
{long_term_memory}

### 🔍 Selective Memory Recall
If the facts above are not enough, or if the user asks about something you don't see here, use the `recall_memories` tool to look up more details from your knowledge base.
"""
    return base + "\n" + memory_block

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

_tts_ready_event = asyncio.Event()

def _do_tts_warmup(loop: asyncio.AbstractEventLoop):
    """Sync warmup running in a background thread to avoid blocking process init."""
    logger.info("Background TTS warmup started...")
    try:
        if hasattr(TTS_PLUGIN, 'warmup'):
            TTS_PLUGIN.warmup()
        logger.info("Background TTS warmup complete.")
    except Exception as e:
        logger.error(f"Background TTS warmup failed: {e}")
    finally:
        loop.call_soon_threadsafe(_tts_ready_event.set)

def prewarm(proc: agents.JobProcess):
    """Prewarm the worker process without blocking. 
    This prevents the 10s LiveKit initialization timeout."""
    logger.info("Prewarming worker process (scheduling background TTS warmup)...")
    try:
        loop = asyncio.get_event_loop()
        threading.Thread(target=_do_tts_warmup, args=(loop,), daemon=True).start()
    except Exception as e:
        logger.error(f"Could not start background prewarm: {e}")
        # Fallback: set event so session doesn't hang forever
        _tts_ready_event.set()

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
    def __init__(
        self,
        *,
        conversation_id=None,
        user_identity: str = "aura-user",
        system_prompt: str = AURA_BASE_PROMPT,
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

    @llm.function_tool(description="Recalls specific facts or memories about the user from the long-term knowledge base.")
    async def recall_memories(self, query: Annotated[str, "The specific topic or fact to recall about the user"] = ""):
        """Called when you need to remember something specific about the user."""
        logger.info(f"AURA is recalling memories for query: '{query}'")
        memories = await memory_service.get_long_term_memories(identity=self._user_identity, limit=20)
        if not memories.strip():
            return "No specific memories found for this user yet."
        return f"Here are the memories I found:\n{memories}"


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
        text = new_message.text_content or ""
        self._last_user_text = text
        
        # Eagerly save user message to DB so it's not lost on disconnect
        if self._conversation_id:
             asyncio.create_task(memory_service.add_interaction(
                  conversation_id=self._conversation_id,
                  user_text=text,
                  assistant_text=None,
                  user_emotion="neutral",
                  assistant_emotion=None
             ))
        
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
    for i in range(300): # 30s (0.1s steps)
        # 1. Check Job Participant (Direct)
        if ctx.job and getattr(ctx.job, 'participant', None):
            user_identity = ctx.job.participant.identity or user_identity
            if ctx.job.participant.metadata:
                try:
                    meta = json.loads(ctx.job.participant.metadata)
                    conversation_id_str = meta.get("conversation_id")
                    logger.info(f"Identity from Job Participant: {user_identity}")
                except: pass
            break
        
        # 2. Check Room Participants
        participants = [p for p in ctx.room.remote_participants.values() if not p.identity.startswith("agent-")]
        if participants:
            p = participants[0]
            user_identity = p.identity
            if p.metadata:
                try:
                    meta = json.loads(p.metadata)
                    conversation_id_str = meta.get("conversation_id")
                    logger.info(f"Identity from Room Participant: {user_identity}")
                except: pass
            break
        
        if i % 10 == 0:
            logger.info("Waiting for participant to join room...")
        await asyncio.sleep(0.1)

    logger.info(f"Resolved identity: '{user_identity}', conversation: '{conversation_id_str}'")

    # 1. Fetch Dynamic Personality
    settings = await memory_service.get_personality_settings()
    custom_system_prompt = None
    if settings:
        custom_system_prompt = settings.get("system_prompt")
        logger.info(f"Loaded personality settings: model={settings.get('model')}")

    # 2. Fetch Long-term Memory
    long_term_memory = await memory_service.get_long_term_memories(identity=user_identity, limit=10)
    is_returning_user = bool(long_term_memory.strip())

    if is_returning_user:
        logger.info(f"Long-term memory loaded for '{user_identity}'")
    else:
        logger.info(f"No long-term memory found for {user_identity}")

    # 3. Build System Prompt (Always New conversation for voice session in historical pattern)
    conversation_id = await memory_service.create_conversation(title=f"Voice Session: {user_identity}")
    if conversation_id:
        logger.info(f"Memory: new conversation {conversation_id} for {user_identity}")
    else:
        logger.warning("Memory: Can't connect to Supabase, running without memory")

    base_prompt = custom_system_prompt if custom_system_prompt else AURA_BASE_PROMPT
    # Historical version injected long term memory into the prompt builder
    system_prompt = build_system_prompt(long_term_memory)
    if is_returning_user:
        logger.info(f"Memory injected into system prompt ({len(long_term_memory)} chars)")
        # Debug print first fact
        first_line = long_term_memory.strip().split('\n')[0]
        logger.info(f"Sample fact: {first_line}")

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

    # Use model from settings if available
    llm_model = settings.get("model", OPENROUTER_MODEL) if settings else OPENROUTER_MODEL
    
    # 1.1 Local plugin creation
    llm_plugin = openai.LLM(
        model=llm_model,
        base_url=OPENROUTER_BASE_URL,
        api_key=OPENROUTER_KEY,
    )

    agent_instance = AURAAssistant(
        conversation_id=conversation_id,
        user_identity=user_identity,
        system_prompt=system_prompt,
        initial_chat_ctx=initial_chat_ctx,
        llm=llm_plugin,
        tts=TTS_PLUGIN,
    )

    session = AgentSession(
        stt=stt_plugin,
        llm=llm_plugin,
        tts=TTS_PLUGIN,
        vad=silero.VAD.load(
            min_silence_duration=0.4,
            min_speech_duration=0.1
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
        try:
            await asyncio.wait_for(_tts_ready_event.wait(), timeout=60.0)
        except asyncio.TimeoutError:
            logger.warning("TTS warmup timed out after 60s, proceeding anyway...")

    if ctx.room.remote_participants:
        logger.info("TTS ready, generating greeting via LLM")
        try:
            await session.generate_reply(instructions=instruction)
        except Exception as e:
            logger.warning(f"Could not deliver dynamic greeting: {e}")

    # Wait for session to finish
    try:
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        logger.info("Voice session cancelled by user/room.")
    finally:
        await stt_session.close()

if __name__ == "__main__":
    agents.cli.run_app(
        agents.WorkerOptions(
            entrypoint_fnc=voice_session,
            prewarm_fnc=prewarm,
        )
    )
