# AURA: Advanced Universal Responsive Avatar

AURA is a local-first AI companion with real-time voice interaction, a browser-rendered Live2D avatar, semantic document memory (RAG), and expressive emotion animation.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | React 19, Vite, TailwindCSS |
| **Avatar** | pixi-live2d-display 0.4, pixi.js 6, Cubism 4 (Hu Tao model) |
| **Voice** | LiveKit Agents, Deepgram Nova-3 (STT) |
| **TTS** | Faster-Qwen3-TTS (local GPU, 12 Hz codec) |
| **LLM** | DeepSeek-V3 / GPT-4o via OpenRouter |
| **Memory** | FastAPI + Supabase (pgvector RAG) |
| **Lip sync** | Web Audio API — RMS amplitude from LiveKit audio track |

## Key Capabilities

- **Low-latency voice** — sub-500 ms response pipeline
- **Browser Live2D avatar** — idle animations, blinking, eye saccades, breathing, lip sync, and parameter-driven expressions with no external avatar software required
- **Smart memory** — upload PDFs, PPTX, or text; AURA cites them in conversation
- **Emotion engine** — per-sentence expressions driven by LLM output tags
- **Bilingual** — seamless English / Japanese switching
- **Local-first TTS** — Qwen3-TTS runs entirely on your GPU

---

## Quick Start (Windows)

### 1. Install prerequisites

| Tool | Version | Link |
|------|---------|------|
| Python | 3.10 – 3.12 (3.13+ not supported) | [python.org](https://www.python.org/downloads/release/python-3128/) |
| Node.js | LTS | [nodejs.org](https://nodejs.org/) |
| Miniconda | Latest | [anaconda.com](https://docs.anaconda.com/miniconda/) |
| Git | Latest | [git-scm.com](https://git-scm.com/downloads) |

### 2. Clone the repository

```bash
git clone https://github.com/ASE-Lab/project-aura.git
cd project-aura
```

### 3. Configure environment variables

Copy `.env.example` to `.env` and fill in:

```env
DEEPGRAM_API_KEY=...
OPENROUTER_API_KEY=...
LIVEKIT_URL=...
LIVEKIT_API_KEY=...
LIVEKIT_API_SECRET=...
SUPABASE_URL=...
SUPABASE_KEY=...

# Optional — set to "true" only if using VTube Studio instead of the browser avatar
VTUBE_ENABLED=false
```

### 4. Start AURA

```powershell
./start_aura.bat
```

First run downloads AI models (~2 GB) and takes 5–10 minutes. Subsequent starts are fast.

Open **http://localhost:5173**. The Live2D avatar loads automatically in the browser — no additional software needed.

### 5. Docker (optional, NVIDIA GPU required)

```bash
docker compose up --build
```

Requires [Docker Desktop](https://www.docker.com/products/docker-desktop/) and the [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html).

---

## Avatar System

AURA's avatar renders directly in the browser using **pixi-live2d-display** with the Cubism 4 runtime. No external software is required.

- **Model**: Hu Tao (Cubism 4 `.model3.json`)
- **Idle animation**: head sway, breathing, eye blink FSM, eye saccades — all driven by `coreModel.setParameterValueById`
- **Lip sync**: `AnalyserNode` on the LiveKit audio track; RMS amplitude maps to `ParamMouthOpenY`
- **Expressions**: `.exp3.json` files triggered by emotion tags parsed from LLM output

To use a different model, copy a Cubism 4 model folder to `dashboard/public/models/<name>/` and update `MODEL_URL` in `src/components/AvatarRenderer.jsx`.

### VTube Studio (optional, legacy)

Set `VTUBE_ENABLED=true` in `.env` and ensure VTube Studio's WebSocket API is running on port 8001. See [voice-agent/README.md](./voice-agent/README.md) for hotkey configuration.

---

## Project Structure

```
project-aura/
├── dashboard/              # React frontend + Live2D avatar renderer
├── voice-agent/            # LiveKit Python agent (STT → LLM → TTS)
├── ai-service/             # FastAPI RAG + memory service
├── Hu_Tao__model_for_PC_/  # Cubism 4 model source files
├── docs/                   # Architecture and backend documentation
├── start_aura.bat          # Windows one-click launcher
├── start_aura.sh           # Unix one-click launcher
└── docker-compose.yml      # Docker orchestration
```

Component READMEs:
- [Dashboard](./dashboard/README.md)
- [Voice Agent](./voice-agent/README.md)
- [AI Service](./ai-service/README.md)
- [Architecture](./docs/architecture/ARCHITECTURE.md)

---

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md) for branch naming and PR format.

## License

MIT — see [LICENSE](./LICENSE).
