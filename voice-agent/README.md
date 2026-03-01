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

## TTS Configuration
You can switch between local and cloud TTS providers in the root `.env` file:
```bash
# Options: 'qwen' (local, high-perf), 'cartesia' (cloud), 'openai' (cloud)
TTS_TYPE=qwen
```

### 1. Local TTS Engine (Qwen3)
**Best for**: Latency and privacy. Requires a GPU (6GB+ VRAM recommended).
- **Environment**: Use the `aura` Conda environment.
- **Setup**: `conda env create -f environment.yml`

### 2. Cloud TTS (Cartesia / OpenAI)
**Best for**: Low local resource usage.
- **Environment**: Use the standard `venv` or the `aura` environment.
- **Requirements**: Valid `CARTESIA_API_KEY` or `OPENAI_API_KEY` in `.env`.

## Running
Depending on your `TTS_TYPE`, ensure you activate the correct environment:

### Using local Qwen3 TTS:
```bash
conda activate aura
python agent.py dev
```

### Using Cloud TTS:
```bash
# Standard venv is sufficient for cloud-only
call venv\Scripts\activate
python agent.py dev
```
