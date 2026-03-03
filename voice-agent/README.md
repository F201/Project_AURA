# AURA Voice Agent

The Voice Agent is the "body" and "voice" of AURA, providing real-time audio interaction, speech-to-text, and visual emotional expression.

## 🚀 Overview
The Voice Agent uses **LiveKit Agents** to manage low-latency voice streams. It features a custom local TTS engine based on Qwen3-TTS for expressive, high-speed speech without cloud costs.

## 🎭 Emotional Engine & VTube Studio
AURA can express her feelings visually through VTube Studio integration.

### Setup
1. **Enable Integration**: Set `VTUBE_ENABLED=true` in your `.env`.
2. **Authorize**: When AURA starts, VTube Studio will show a popup asking for permission. Click **Allow**. A `token.txt` will be saved locally (it is gitignored).
3. **Hotkeys**: For the best experience, name your VTube Studio expressions exactly as follows:
   - `Smile` (assigned to `happy`, `smile`)
   - `Sad` (assigned to `sad`)
   - `Angry` (assigned to `angry`)
   - `Ghost Happy` (assigned to `ghost`)
   - `Shadow`, `Pupil Shrink`, `Eyeshine Off` (assigned to specific effects)

### Emotion Recipes
AURA automatically detects emotions from her own speech. You can also force specific looks using tags like `[happy, shadow]` in the system prompt.
- **Pleading (Memelas)**: `[angry, sad]`
- **Shocked**: `[shadow, pupil_shrink, eyeshine_off]`
- **Furious**: `[shadow, pupil_shrink, eyeshine_off, angry]`
- **Restricted**: AURA is strictly forbidden from mixing positive emotions (`happy`) with scary effects (`shadow`) to maintain consistency.

## 🛠 Tech Stack
- **Voice Pipeline**: LiveKit Agents
- **STT**: Deepgram (Nova-3)
- **LLM**: DeepSeek-V3 (via OpenRouter)
- **TTS**: Faster-Qwen3-TTS (Local, 24kHz)
- **VTube Interaction**: `pyvts` (WebSocket)

## ⚙️ Configuration (.env)
- `VTUBE_ENABLED`: "true" or "false" (default: false)
- `DEEPGRAM_API_KEY`: Required for speech recognition.
- `OPENROUTER_API_KEY`: Required for the LLM.
- `LIVEKIT_URL / API_KEY / API_SECRET`: Connection to your LiveKit server.

## 🏃 Running the Agent
1. **Install Conda**: Ensure you have Miniconda or Anaconda installed.
2. **Create Environment**: `conda env create -f environment.yml`
3. **Activate**: `conda activate aura`
4. **Start**: `python agent.py dev`
