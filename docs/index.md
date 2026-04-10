# Welcome to Project AURA

AURA (Advanced Universal Responsive Avatar) is a seamless, local-first AI companion featuring a browser-rendered Live2D avatar, sub-500ms voice interactions, and semantic document memory (RAG).

## Key Features

1. **Ultra-Low Latency Voice Setup**
   AURA leverages LiveKit WebRTC and local Faster-Qwen3-TTS running on your GPU to achieve sub-500ms conversational latencies. 
2. **Browser-Native Live2D Avatar**
   The avatar is fully browser-based, making use of `pixi-live2d-display` and Cubism 4 WASM. No VTube Studio or external rendering engines are required (though conditionally supported based on your preference).
3. **Continuous Smart Memory**
   Using FastAPI, Sentence-Transformers, and Supabase pgvector, users can upload PDFs and text documents which AURA semantically recalls and leverages during conversations.
4. **Emotional Intelligence Engine**
   AURA is prompted to dynamically respond with emotion tags, which are immediately translated into real-time visual Live2D expression parameters.

## Where to go from here?

- Read the **[Installation Guide](getting-started/INSTALLATION.md)** to run AURA locally.
- Review **[Configuration](getting-started/CONFIGURATION.md)** to correctly set up your `.env` API keys.
- Dive into the **[Avatar Architecture](architecture/AVATAR_SYSTEM.md)** to understand how the browser-based Live2D renderer works.
