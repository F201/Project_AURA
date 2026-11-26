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

## Qwen3-TTS on an Android phone

The companion can stream AURA's cloned voice from an ARM64 Android phone. This setup uses a quantized Qwen3-TTS 0.6B model through the Android CPU build of `qwen3-tts.cpp`. Windows runs the overlay, speech recognition, and conversation logic.

See the [desktop and Samsung handoff](HANDOFF.md) for verification, measured throughput, and remaining performance work.

1. Clone [qwen3-tts.cpp](https://github.com/Danmoreng/qwen3-tts.cpp) and check out `16bb5afcd06311031c72a8488f8d59660dc2fb46`. Run `git submodule update --init --recursive`. Remove `-march=native` from the release flags in its root `CMakeLists.txt` for the cross-build.
2. From the AURA root, build the service with the Android NDK, CMake, and Ninja. Set `$ndk` and `$qwenSource` to the NDK directory and the Qwen C++ source directory on the build machine. The CPU flags below target ARM64 phones that support both dot product and FP16 instructions.

   ```powershell
   git -C "$qwenSource/ggml" apply --unidiff-zero (Resolve-Path desktop-agent/android-tts/reuse-ggml-workers.patch)
   cmake -S desktop-agent/android-tts -B desktop-agent/data/android-build -G Ninja `
     "-DCMAKE_TOOLCHAIN_FILE=$ndk/build/cmake/android.toolchain.cmake" `
     "-DQWEN3_TTS_DIR=$qwenSource" -DANDROID_ABI=arm64-v8a -DANDROID_PLATFORM=android-28 `
     -DANDROID_STL=c++_static -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF `
     -DGGML_NATIVE=OFF -DGGML_OPENMP=OFF "-DGGML_CPU_ARM_ARCH:STRING=armv8.2-a+dotprod+fp16"
   cmake --build desktop-agent/data/android-build --target aura-phone-tts
   python desktop-agent/android-tts/export_voice.py voice-agent/resources/voice/aura_voice_xvec.pt desktop-agent/data/aura-speaker.json
   ```

   The patch lets the phone binary reuse GGML CPU workers across inference graphs. Voice export uses PyTorch on the build machine. The phone binary does not need PyTorch.

3. Copy the `aura-phone-tts` binary and `aura-speaker.json` to `~/aura-tts` in Termux. Download `qwen-talker-0.6b-base-Q4_K_M.gguf` and `qwen-tokenizer-12hz-Q8_0.gguf` from the [GGUF model repository](https://huggingface.co/Serveurperso/Qwen3-TTS-GGUF) into `~/aura-tts/models`. Start the service inside Termux.

   ```sh
   cd ~/aura-tts
   chmod +x aura-phone-tts
   ./aura-phone-tts models qwen-talker-0.6b-base-Q4_K_M.gguf models/qwen-tokenizer-12hz-Q8_0.gguf aura-speaker.json
   ```

4. Keep an SSH tunnel open from Windows, with `user@phone-ip` replaced by your Termux SSH account and host. Add `DESKTOP_REMOTE_TTS_URL=http://127.0.0.1:17865` to the AURA root `.env` and start or restart the desktop agent.

   ```powershell
   ssh -N -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -L 127.0.0.1:17865:127.0.0.1:17865 -p 8022 user@phone-ip
   ```

   The phone service uses the exported speaker embedding for every request. Replace the embedding on the phone and restart the service to change its voice. Game Mode switches the desktop agent to Edge TTS while enabled.

   The desktop queues each complete clause before playing phone audio. This can delay the start of speech and leave pauses between clauses when synthesis is slower than playback.
