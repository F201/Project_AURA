# Configuration

AURA relies on several cloud services and APIs to function, specifically for WebRTC (LiveKit), STT (Deepgram), LLMs (OpenRouter), and Memory (Supabase).

You must copy `.env.example` to `.env` in the root of the `project-aura` folder before launching the application.

## Core Services

### Voice and Video Signal (LiveKit)
LiveKit handles WebRTC streams, connecting the Dashboard to the Python Voice Agent.
- `LIVEKIT_URL`: Web Socket URL of your LiveKit instance (e.g., `wss://aura-xyz.livekit.cloud`).
- `LIVEKIT_API_KEY`: The API key from your LiveKit dashboard.
- `LIVEKIT_API_SECRET`: The API secret from your LiveKit dashboard.

### Speech-to-Text (Deepgram)
AURA uses Deepgram's Nova-3 model for incredibly fast, multilingual transcription.
- `DEEPGRAM_API_KEY`: Create an account at [Deepgram](https://deepgram.com/) and generate an API key.

### LLM Inference (OpenRouter)
OpenRouter provides unified access to LLMs. By default, AURA relies on `DeepSeek-V3` for conversational intelligence.
- `OPENROUTER_API_KEY`: Create an account at [OpenRouter](https://openrouter.ai/) to generate a key.

### Semantic Memory and History (Supabase)
Used by the AI Service to store vector embeddings for the RAG pipeline.
- `SUPABASE_URL`: The URL of your Supabase project (e.g., `https://xyz.supabase.co`).
- `SUPABASE_KEY`: The `anon` or `service_role` key from Supabase API settings.

---

## Optional Toggles

### Legacy VTube Studio Integration
- `VTUBE_ENABLED`: Set to `"true"` **only if** you intend to bypass the browser-based Live2D renderer and inject expressions directly into the standalone VTube Studio application.
  - *Default: `"false"`*

### Additional Settings
Depending on your LLM latency and network bandwidth, you may find additional performance flags in the `voice-agent`'s `.env`, though standard deployments generally only require the configuration mentioned above.
