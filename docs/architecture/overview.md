# AURA Architecture Overview

See [ARCHITECTURE.md](./ARCHITECTURE.md) for the full technical reference.

## Components

| Component | Path | Technology |
|-----------|------|-----------|
| Dashboard | `/dashboard` | React 19, Vite, pixi-live2d-display, livekit-client |
| Voice Agent | `/voice-agent` | Python, livekit-agents, Faster-Qwen3-TTS, Deepgram |
| AI Service | `/ai-service` | FastAPI, Supabase pgvector |
| Token Server | `/voice-agent` | Embedded in agent startup |

## Data Flow

```
User speaks
  → LiveKit (WebRTC)
  → Deepgram STT
  → OpenRouter LLM  → emotion tags → Avatar data channel → Live2D expressions
  → Qwen3 TTS
  → LiveKit audio → Dashboard → AnalyserNode RMS → lip sync
```

## Avatar

Browser-rendered Cubism 4 Live2D model (Hu Tao). No external software required. VTube Studio is available as an optional legacy integration via `VTUBE_ENABLED=true`.
