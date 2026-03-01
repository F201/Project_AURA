# AURA Voice Agent

This service handles low-latency voice interaction using LiveKit Agents, Deepgram (STT), and Cartesia (TTS).

## Components

### 1. Voice Agent (`agent.py`)
- **LiveKit Worker**: Connects to the LiveKit room as a participant.
- **Polyglot VAD**: Uses Silero and custom turn detection to handle English, Indonesian, and Japanese speech.
- **Dynamic Personality**: Implements the AURA persona with mischievous and wise traits.

### 2. Token Server (`token_server.py`)
- **Authentication**: Provides connection tokens (JWT) for the dashboard to join LiveKit rooms.
- **FastAPI Port**: Defaults to `:8082`.

## Running Locally
```bash
# Start the Token Server
python token_server.py

# Start the Agent Worker
python agent.py dev
```

## Local TTS Engine (Qwen3)
This service now defaults to a high-performance local TTS engine based on **Qwen3-TTS**.

### Setup (Conda - Recommended)
To run the local TTS with GPU acceleration:
```bash
# Create the environment from the provided file
conda env create -f environment.yml

# Activate the environment
conda activate aura
```

### Setup (Pip / Venv)
If you prefer standard venv:
```bash
python -m venv venv
call venv\Scripts\activate
pip install -r requirements.txt
# Note: You may need to manually install the matching torch+cu121 wheel for GPU support.
```

## Docker
The `voice-agent` uses a CUDA-enabled PyTorch runtime.
- **Base Image**: `pytorch/pytorch:2.2.1-cuda12.1-cudnn8-runtime`
- **GPU Support**: Ensure the [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html) is installed on your host.
- **Model Caching**: Models are downloaded to a shared `huggingface_cache` volume to avoid re-downloading on container restarts.

## Running
```bash
# Start the Token Server (Port 8082)
python token_server.py

# Start the Agent Worker
python agent.py dev
```
