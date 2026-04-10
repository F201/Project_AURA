# Installation Guide

Project AURA can be installed primarily on **Windows** using the native launcher, or via **Docker** for containerized deployments.

## Prerequisites

Regardless of how you install AURA, you need:
- **API Keys**: See [Configuration](CONFIGURATION.md) for a list of necessary API keys.
- **Microphone and Speakers**: For voice interaction.

---

## 1. Native Installation (Windows / macOS)

This is the recommended installation method as it avoids Docker container abstraction, making it easier to debug the voice pipelines and GPU acceleration.

### System Requirements
- **Python**: `3.10` to `3.12` (Python `3.13+` is currently unsupported by some dependencies).
- **Node.js**: The latest LTS release.
- **Miniconda**: For streamlined Python virtual environment setup.
- **Git**: To clone the repository.
- **NVIDIA GPU** (Optional but recommended): Required to run the local `Faster-Qwen3-TTS` engine at lightning-fast speeds.

### Steps

1. **Clone the repository**
   ```bash
   git clone https://github.com/ASE-Lab/project-aura.git
   cd project-aura
   ```

2. **Configure `.env`**
   Copy `.env.example` to `.env` and fill in the required API keys. [View Configuration Details](CONFIGURATION.md).

3. **Start the Application**
   For Windows:
   ```powershell
   ./start_aura.bat
   ```
   For macOS / Unix:
   ```bash
   ./start_aura.sh
   ```

   _Note: The first run may take 5–10 minutes to download necessary machine-learning models (~2 GB total). Subsequent runs will be significantly faster._

4. **Access the Dashboard**
   Once all services confirm they are running, open **[http://localhost:5173](http://localhost:5173)** in your browser. The Live2D avatar will load automatically.

---

## 2. Docker Installation

For those who want a completely isolated deployment.

### System Requirements
- **Docker Desktop**
- **NVIDIA Container Toolkit**: If you're on Windows/Linux and want to expose your GPU to the container for TTS performance.

### Steps

1. **Clone & Configure**
   Same as Steps 1 & 2 above. Ensure your `.env` is fully populated.

2. **Run Docker Compose**
   ```bash
   docker compose up --build
   ```

3. **Access the Dashboard**
   Once Docker has spun up all containers (Dashboard, Voice Agent, AI Service, Token Server), open **[http://localhost:5173](http://localhost:5173)** in your browser.
