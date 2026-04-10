# Component Directory

A high level map of the repository structure to help navigate where code lives.

```text
project-aura/
├── dashboard/               # React 19 frontend
│   ├── src/components/      # AvatarRenderer, CallOverlay (lip sync logic)
│   └── public/              # Served assets, Cubism WASM runtime, Live2D Models
│
├── voice-agent/             # Python LiveKit WebRTC Worker
│   ├── agent.py             # Main entry point for the process
│   ├── aura_tts.py          # Faster-Qwen3-TTS generation parameters
│   └── avatar_bridge.py     # Parses text tags into WebRTC data channel events
│
├── ai-service/              # FastAPI Memory & RAG provider
│   ├── app/main.py          # REST endpoints
│   └── app/services/        # Ingestion logic, Chunking, Embedding
│
├── docs/                    # The documentation you are reading now
├── start_aura.bat           # Desktop bootloader for Windows
└── docker-compose.yml       # Production docker bootloader
```
