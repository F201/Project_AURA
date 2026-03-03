# AURA: Advanced Universal Responsive Avatar

*AURA* is a state-of-the-art 3D/2.5D AI Companion designed for real-time interaction. It combines low-latency voice communication, semantic document memory (RAG), and expressive emotional animation via VTube Studio.

---

## 🏗️ Tech Stack
- **Frontend**: React, Vite, TailwindCSS (Modern, reactive dashboard)
- **Voice Edge**: LiveKit Agents, Deepgram (Nova-3 STT), Cartesia/Qwen3 (TTS)
- **Brain**: DeepSeek-V3 / GPT-4o via OpenRouter, FastAPI, Qdrant/pgvector
- **Live Interaction**: VTube Studio (WebSockets), Lip-sync, per-sentence emotions.

## 📋 Key Capabilities
- **🎤 Low Latency Voice**: Human-like conversation with <500ms response times.
- **📚 Smart Memory**: Upload PDFs, PPTX, or text files; AURA will remember and cite them.
- **🎭 Visual Emotions**: Synchronized facial expressions that match the context of every sentence.
- **🇯🇵 Bilingual Support**: Seamlessly switches between English and Japanese.
- **💻 Local-First**: Capable of running the TTS engine entirely on your local GPU.

---

## ⚡ Quick Start Guide
*Follow these steps if you have nothing installed on your computer yet.*

### Step 1: Install Mandatory Tools
Download and install these three tools (use default settings for all):
1. **Node.js**: [Download here](https://nodejs.org/). (Choose "LTS" version). This runs the Dashboard.
2. **Miniconda**: [Download here](https://docs.anaconda.com/miniconda/). This manages the AI models.
3. **Git**: [Download here](https://git-scm.com/downloads). This downloads the project code.
4. **VTube Studio (Optional)**: Available for free on Steam.

### Step 2: Get the Code
Open your **Terminal** (Search for "PowerShell" on Windows) and type:
```bash
git clone https://github.com/ASE-Lab/project-aura.git
cd project-aura
```

### Step 3: Set Up Your Secrets
1. Create a file named `.env` in the root folder (copy `.env.example`).
2. Open it with Notebook and add your API keys:
   - **Deepgram API Key**: For listening.
   - **OpenRouter API Key**: For thinking.
   - **LiveKit Keys**: For the voice connection.
   - **Supabase Keys**: For the database connection.

### Step 4: One-Click Start (Windows)
We've made a dedicated launcher to handle everything for you. Simply run:
```powershell
./start_aura.bat
```
*The first run will take 5-10 minutes as it downloads the AI models (~2GB). Subsequent starts will be nearly instant.*

### Step 5: Docker Setup
If you prefer using Docker and have an NVIDIA GPU, you can run AURA as containers. 

**Prerequisites:**
- **Docker Desktop**: [Download here](https://www.docker.com/products/docker-desktop/)
- **NVIDIA Container Toolkit**: [Install here](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html) (Required for GPU support).

**Run AURA with Docker:**
```bash
docker compose up --build
```
*Wait for all services to initialize. The Dashboard will be available at http://localhost:5173.*

## 📚 Component Deep Dives
For developers or those wanting to customize AURA:
- [**Dashboard** (Frontend)](./dashboard/README.md): React interface.
- [**Voice Agent** (The "Soul")](./voice-agent/README.md): LiveKit logic, TTS, and VTube emotions.
- [**AI Service** (The "Brain")](./ai-service/README.md): RAG, search, and knowledge ingestion.

## 🎭 Configuring Emotions (VTube Studio)
To enable AURA's expressions:
1. Open VTube Studio and ensure the API is enabled in settings (Port 8001).
2. Set `VTUBE_ENABLED=true` in your `.env`.
3. When AURA starts, click **Allow** in VTube Studio.
4. Detailed emotion recipes can be found in the [Voice Agent README](./voice-agent/README.md).

## 🤝 Contribution
Built with ❤️ by the ASE Lab Members. We welcome all contributions!
1. Fork it.
2. Create your feature branch.
3. Commit & Push.
4. Open a Pull Request.

## 📜 License
Distributed under the MIT License. See `LICENSE` for more information.
