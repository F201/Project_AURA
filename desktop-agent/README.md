# AURA Desktop Live Companion (`desktop-agent/` + `desktop/`)

A local-first, always-on-top live desktop companion runtime for **Project AURA** that connects the Electron Live2D / 3D overlay directly to a local FastAPI + WebSocket hub (`127.0.0.1:8765`) without requiring a LiveKit cloud room.

## Highlights
- **Local CPU Speech-to-Text + Barge-In (`stt_engine.py`)**: Runs `faster-whisper` on CPU (`0` GPU VRAM) with RMS VAD barge-in and toggleable **Always Listening** or **Wake Word ("AURA")** mode.
- **True Streaming Voice Clone (`tts_engine.py`)**: Reuses `voice-agent/lib/faster-qwen3-tts` and `voice-agent/resources/voice/aura_voice_xvec.pt` with CUDA graphs (`chunk_size=6`) plus a 0-VRAM **Game Mode** (`Edge-TTS`) toggle for heavy gaming sessions.
- **Multimodal Vision + Function-Calling Expressions (`brain.py`, `vision_watcher.py`)**: Sends screen context on demand / proactively (with automatic password/banking/incognito privacy pause) and drives the Live2D Cubism 4 expressions (`SmileLock`, `SadLock`, `Angry`, `Ghost`, `GhostChange`, `Shadow`, `PupilShrink`, `EyeshineOff`, `wink`, `tongue`, `blush`, `pouting`, `pleading`, `curious`) via OpenAI-style tool calling.
- **Desktop Tools & Persistent SQLite Memory (`desktop_tools.py`, `memory_store.py`)**: Local reminders, long-term memory facts, app/URL launching, media/volume control, and companion interaction stats.
- **Upgraded Electron Overlay (`desktop/`)**:
  - Windows 11 HRGN top-clip (`SetWindowRgn`) to eliminate unfocused DWM ghost titlebars.
  - 60Hz main-process silhouette click-through + 125Hz DPI-proof dragging + in-canvas scaling (Chibi / Full Body / Close-Up) + 30Hz global cursor eye/head tracking.
  - Priority-resolved Live2D `ParameterBus` (Idle + Tracking + Interaction + Expression) with inlined Cubism 4 expression descriptors and 60fps Web Audio RMS lip-sync.
  - Drop-in **Three.js VRM / GLB** 3D avatar mode (`desktop/public/models/3d/`).
  - Live OBS / Discord screen-share visibility toggle, audio output device (`setSinkId`) selector, and global hotkeys (`Ctrl+Shift+M` mute, `Ctrl+Shift+B` blind/privacy, `Ctrl+Shift+H` hide/show, `Ctrl+Shift+X` interrupt).

## Quick Start (Windows)

1. Copy `.env.example` to `.env` in the repository root and set `OPENROUTER_API_KEY`.
2. Create the Python environment for `desktop-agent/`:
   ```bash
   cd desktop-agent
   python -m venv .venv
   .venv\Scripts\pip install -r requirements.txt
   ```
   *(Install CUDA-enabled PyTorch if using local GPU Qwen3-TTS.)*
3. Install frontend dependencies in `desktop/`:
   ```bash
   cd desktop
   npm install --legacy-peer-deps
   ```
4. Launch both services together via `start_aura_desktop.bat` (or run `python main.py` in `desktop-agent/` and `npm run dev` in `desktop/`).
