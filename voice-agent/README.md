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

## Docker
The `voice-agent` is optimized with a "Slim Image" strategy. It loads required models into a shared volume at runtime rather than pre-downloading them during build to save disk space and improve build times.
