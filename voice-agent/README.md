# AURA Voice Agent

LiveKit-based Python agent that handles the full voice pipeline: speech recognition, LLM inference, TTS synthesis, and avatar expression triggering.

## Pipeline

```
Microphone → LiveKit (WebRTC) → Deepgram STT → OpenRouter LLM → Qwen3-TTS → LiveKit → Browser
                                                      ↓
                                              Emotion tag parsing
                                                      ↓
                                        Avatar Bridge (data channel) → Live2D expressions
```

## Tech Stack

| | |
|-|-|
| **Voice framework** | livekit-agents v1.3+ |
| **STT** | Deepgram Nova-3 (multilingual) |
| **LLM** | DeepSeek-V3 via OpenRouter |
| **TTS** | Faster-Qwen3-TTS (local, 12 Hz codec, 24 kHz output) |
| **VAD** | Silero |

## TTS Notes

`aura_tts.py` wraps Faster-Qwen3-TTS with:

- **`max_new_tokens` budget** — computed from text length to prevent the model generating excess audio for short phrases (Japanese: ~4 chars/s, English: ~12 chars/s, 3× safety factor)
- **Trailing silence trim** — `_trim_silence()` scans in 25 ms windows and discards audio after the last active speech window
- **`repetition_penalty=1.15`** — reduces hallucination loops
- **Serialized GPU inference** — `_gen_lock` prevents concurrent CUDA calls

## Emotion Engine

The LLM is prompted to prefix sentences with emotion tags, e.g. `[happy] Great question!`. `avatar_bridge.py` parses these tags and forwards expression names to the dashboard via a LiveKit data channel.

Expression names and their Hu Tao model mappings:

| Tag | Expression file |
|-----|----------------|
| `smile` | `SmileLock.exp3.json` |
| `sad` | `SadLock.exp3.json` |
| `angry` | `Angry.exp3.json` |
| `ghost` | `Ghost.exp3.json` |
| `ghost_nervous` | `GhostChange.exp3.json` |
| `shadow` | `Shadow.exp3.json` |
| `pupil_shrink` | `PupilShrink.exp3.json` |
| `eyeshine_off` | `EyeshineOff.exp3.json` |

Combo recipes:
- **Shocked**: `[shadow, pupil_shrink, eyeshine_off]`
- **Furious**: `[shadow, pupil_shrink, eyeshine_off, angry]`
- **Pleading**: `[angry, sad]`

## Configuration (`.env`)

| Variable | Required | Description |
|----------|----------|-------------|
| `DEEPGRAM_API_KEY` | Yes | Speech recognition |
| `OPENROUTER_API_KEY` | Yes | LLM inference |
| `LIVEKIT_URL` | Yes | LiveKit server URL |
| `LIVEKIT_API_KEY` | Yes | LiveKit credentials |
| `LIVEKIT_API_SECRET` | Yes | LiveKit credentials |
| `VTUBE_ENABLED` | No | `"true"` to enable VTube Studio integration (default: `"false"`) |

## Running

```bash
conda env create -f environment.yml
conda activate aura
python agent.py dev
```

Or use `start_aura.bat` from the project root to start all services together.

## VTube Studio Integration (optional, disabled by default)

Set `VTUBE_ENABLED=true` in `.env`. Ensure the VTube Studio WebSocket API is enabled on port 8001. On first connect, click **Allow** in VTube Studio — a `token.txt` will be saved locally (gitignored).

For the best experience, name VTube Studio hotkeys to match the expression names in the table above.
