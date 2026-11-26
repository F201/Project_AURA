# AURA for Android

AURA runs as a standalone app on Android 12 and newer. It uses the project's Live2D avatar and generates the cloned voice on the phone using Qwen3-TTS 0.6B Base, the existing AURA speaker embedding, the Q4_K_M talker, and the Q8_0 codec. Chat and photo understanding use OpenRouter. Neither the desktop app nor Termux is required.

## Set up the phone

1. Install the APK. On a development device, run `adb install -r mobile/app/build/outputs/apk/debug/app-debug.apk`.
2. Open **Settings** in AURA and enter an OpenRouter API key. The default model is `google/gemini-2.5-flash`. When changing it, choose a model with image and tool support.
3. Choose **Download voice models** for a 920 MB download, or choose **Import voice ZIP or GGUF** and select the Samsung backup ZIP or each of the original files individually. Android needs room for a separate copy of the imported models. The app checks sizes and SHA-256 hashes before using them.
4. Choose **Test voice** to hear the local voice without an internet connection or API key.

Tap **Talk** once and speak normally. AURA sends your utterance after you pause, plays its reply through Android’s media output, and starts listening again. Subtitles follow the spoken phrases. **Interrupt** cuts off a reply and returns to listening. **End talk** closes the mic. **Type** opens the text composer and history.

**Auto-hide controls during Talk** is on by default. Double-tap the stage to show the buttons again. Subtitles and the active camera preview stay visible. Pinch the avatar to zoom its view, or pinch inside the camera preview to change camera zoom.

Tap **Camera** for a live preview. The button inside the preview switches between the rear and front lenses. While the preview is open, point at something and ask AURA about it. AURA sends the current frame with that turn. Frames are processed in memory and the app closes the camera and microphone when you leave it. Chat history stores text on the phone and can be cleared in Settings. AURA stores the API key with Android Keystore encryption.

Choose **Bahasa Indonesia** under **Settings → Mic language** to talk in Indonesian. AURA accepts Indonesian and answers in English or Japanese. The app prefers Android’s on-device recognizer and uses the standard speech service when the selected language is unavailable locally.

The chat model can call `set_avatar_expression` during its reply. AURA applies the chosen expression when the tool call arrives and repeats it when cloned speech starts.

## Saved memory

Ask AURA to remember a name, preference, or detail for future conversations. Its `remember_fact` tool writes the fact to an on-device SQLite database using desktop AURA’s `memories` schema. Saved facts can be recalled after the app closes and after older chats drop out of the prompt. **Settings → Saved memories** lists or clears the facts independently of chat history.

To bring over an existing desktop profile, use **Saved memories → Import desktop** and select a consistent SQLite backup of `desktop-agent/data/aura_memory.db`. AURA merges saved facts, skips duplicates, and imports the desktop name if the phone has no imported name. The import leaves chats and reminders out of the transfer.

## Build on Windows

Install JDK 17, Android SDK platform 35, NDK `27.1.12297006`, CMake `3.22.1`, Node.js 20.11 or newer, Python with Pillow and PyTorch, and Git. Set `ANDROID_HOME` to the SDK path.

    .\mobile\build-mobile.ps1

The script obtains the pinned native runtime, builds the mobile Live2D bundle, exports the speaker embedding, and creates a sideload APK. It produces a portable ARM64 and x86_64 build with optimized native code. For the Samsung previously benchmarked on the desktop branch, use its faster ARM instruction set.

    .\mobile\build-mobile.ps1 -Abis arm64-v8a -ArmArch 'armv8.2-a+dotprod+fp16+i8mm'

## Verify

    .\mobile\build-mobile.ps1 -DeviceTests

Import the models before testing native synthesis. Use `-e requireModels true` with the instrumentation runner to require the voice test.

    adb shell am instrument -w -e requireModels true com.aura.mobile.test/androidx.test.runner.AndroidJUnitRunner
    adb logcat -d -s AuraVoiceTest

After entering an OpenRouter key in the app, the live integration test sends a synthetic image and an Indonesian test prompt. It checks the English answer, the model's expression tool call, and the resulting Live2D parameters on the device.

    adb shell am instrument -w -e liveOpenRouter true -e class 'com.aura.mobile.MobileTest#liveOpenRouterToolCallAnimatesTheAvatar' com.aura.mobile.test/androidx.test.runner.AndroidJUnitRunner

The native test records model load time, first decoded audio, full synthesis time, and approximate codec frames per second. First decoded audio is an internal timing. The player buffers complete phrases to avoid mid-phrase starvation, so audible start also includes phrase generation. Longer answers can pause between phrases if generation falls behind. See the [Samsung benchmark handoff](../desktop-agent/HANDOFF.md) for the earlier hardware measurements and the 12.5 frames/s target.

### Galaxy A56 baseline before hands-free talk, November 25, 2026

Verified photo capture and preview, English and Indonesian dictation, the Live2D model, and offline cloned voice on the A56. With the app's OpenRouter key, the live model identified a synthetic blue square in English in response to an Indonesian prompt and called `set_avatar_expression` with `Angry`. The normal chat screen also rendered a live wink, then replayed it at speech onset. Stream fixtures verified smile, sadness, anger, ghost and shadow together, wink, and return to neutral.

The installed six-worker build generated a 3.28-second sample with 160 ms decoder chunks. On the final warm repeat, it decoded its first PCM at 0.64 seconds, completed synthesis at 10.66 seconds, and started Android playback at 10.68 seconds. It sustained 3.85 codec frames per second. Playback consumed all 78,720 samples with zero underruns. From the measured arrival times, an ideal streaming player would still have needed 7.46 seconds of lead to play that utterance continuously. The first run with the loaded model started playback in 15.74 seconds. In the earlier decoder comparison, the 640 ms variant took 29.99 seconds to synthesize the same duration.
