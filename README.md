# Project AURA (Advanced Universal Responsive Avatar)

*AURA* is an open-source interactive AI Avatar project developed by the **Advanced Software Engineering (ASE) Laboratory**. Inspired by AI VTubers, AURA serves as a virtual assistant capable of answering questions, managing lab information, and providing conversational support via a web portal.

## 🚀 Features

### Conversational Core
- **Multi-modal Interaction**: Supports both text-based chat and low-latency voice interaction.
- **Local AI Edge**: Capable of running high-performance TTS (Qwen3) entirely locally on consumer GPUs.
- **Polyglot Intelligence**: Automatically detects and responds in English, Indonesian, and Japanese.
- **RAG Memory**: Integrated with Supabase (pgvector) to remember past conversations and lab-specific knowledge.
- **LiveKit Integration**: Uses LiveKit Agents for high-performance audio streaming and VAD (Voice Activity Detection).

### Dashboard
- Modern React-based dashboard for chat, personality management, and call modes.

## 🛠️ Tech Stack

- **Orchestration**: Python, FastAPI, LangGraph.
- **Voice Stack**: LiveKit, Deepgram (STT), Qwen3-TTS (Local) / Cartesia (Cloud).
- **LLM**: OpenRouter (Unified API for DeepSeek, GPT-4, etc.).
- **Database**: Supabase (PostgreSQL + pgvector).
- **Frontend**: React, Vite, TailwindCSS.
- **Deployment**: Windows Launcher (Native) & Docker / Docker Compose.

## ⚡ Quick Start

### Prerequisites
- Docker & Docker Compose

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/ASE-Lab/project-aura.git
   cd project-aura
   ```

2. **Configure Environment**:
   Copy the example environment file and fill in your API keys.
   ```bash
   cp .env.example .env
   ```
   *Note: Set `TTS_TYPE=qwen` for local or `cartesia` for cloud.*

3. **Run the Launcher (Windows Recommended)**:
   ```powershell
   ./start_aura.bat
   ```
   *This will handle environment checks and start all services (Dashboard, AI Service, Voice Agent, Token Server).*

### Alternative: Docker Setup
```bash
docker compose up --build -d
```

## 🌐 Accessing Services
- **User Dashboard**: [http://localhost:5173](http://localhost:5173)
- **AI Service Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Voice Agent**: Integrates automatically with the Dashbord.

## 🤝 Contribution

We follow a standard open-source contribution workflow!

1. Fork the repository.
2. Create a Branch for your feature (`git checkout -b feat/your-feature`).
3. Commit your changes.
4. Push to the branch.
5. Open a Pull Request.

## 📜 License
Distributed under the MIT License. See `LICENSE` for more information.

---
<p align="center">
Built with ❤️ by the ASE Lab Members
</p>
