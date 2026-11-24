# AURA desktop and Samsung TTS handoff

The desktop overlay, FastAPI agent, and Whisper speech recognition run on Windows. The Samsung ARM64 service generates 24 kHz mono PCM with Qwen3-TTS 0.6B Base. It uses the checked-in AURA speaker embedding, the `Q4_K_M` talker, and the `Q8_0` codec. The service listens on loopback and Windows reaches it over an SSH port forward.

## Setup and operation

- Follow the [Android build, model, and SSH instructions](README.md#qwen3-tts-on-an-android-phone) to reproduce the phone service. The Samsung build used Android NDK 27.1 and the `armv8.2-a+dotprod+fp16+i8mm` profile. Choose CPU flags that the target device supports.
- On Windows, use Python 3.12 and install the agent requirements in `desktop-agent/.venv`. A phone-only installation can omit the `qwen-tts` Python package. Install the Electron dependencies with `npm install --legacy-peer-deps` in `desktop`.
- Set `DESKTOP_REMOTE_TTS_URL=http://127.0.0.1:17865` in the root `.env` for the phone backend. Set `OPENROUTER_API_KEY` there to enable conversation. With the key missing, typed requests show a silent setup message and automatic conversation turns are suppressed.
- Start the phone service and SSH tunnel, then run `start_aura_desktop.bat` on Windows. Check the phone endpoint at `http://127.0.0.1:17865/health` and the desktop agent at `http://127.0.0.1:8765/api/health`. The desktop should report `tts_backend=remote` and `tts_ready=true` after a successful connection.

## Playback and measured performance

The Android service emits two codec frames per chunk, which lets the stateful decoder reuse its previous audio context. The GGML worker-pool patch reduces the cost of starting CPU threads for individual graphs. Windows receives the streamed data and gives the desktop player a complete clause at a time. Interrupting a turn discards any unfinished clause.

| Samsung test | Time to first audio or playable clause | Generation time | Audio duration |
| --- | ---: | ---: | ---: |
| Deployed CPU service through the Windows client, raw streaming probe | 0.54 s | 5.18 s | 3.04 s |
| Deployed CPU service, buffered playback | 2.02 s | 2.02 s | 1.12 s |
| Experimental CPU overlap with four talker workers and three codec workers | 0.62 s | 5.83 s | 3.52 s |
| Experimental Vulkan vocoder | 0.79 s | 20.55 s | 3.52 s |

The deployed raw probe averaged 7.33 codec frames per second. Gapless playback with a sub-second start requires about 12.5 frames per second sustained and sufficient lead to cover bursty delivery. The phone did not meet that threshold in these trials. Whole-clause buffering keeps audio continuous within a clause, with possible pauses between clauses. Full in-context reference prompting was also tested and took substantially longer than speaker-embedding-only synthesis.

Any future streaming change should measure actual PCM delivery across short and long replies, confirm a warm first-audio time below one second, and check the playback queue for underruns. Keep the same model, codec, and speaker embedding when comparing quality. The worker-pool A/B test used a fixed seed and produced byte-identical WAVs.

## Verification

- Built the Android ARM64 service and verified synthesis on the Samsung through the Windows client.
- Verified whole-clause buffering and interruption with deliberately fragmented phone PCM. Verified the missing-key path leaves typed feedback and produces no automatic speech.
- `npm run build` and `tsc --noEmit` passed. The desktop test suite reported 50 passing tests and the pre-existing legacy wink assertion failure in `AvatarRenderer.test.tsx`.
