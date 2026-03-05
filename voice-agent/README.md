# AURA Voice Agent

The Voice Agent is the "body" and "voice" of AURA, providing real-time audio interaction, speech-to-text, and visual emotional expression.

## 🚀 Overview
The Voice Agent uses **LiveKit Agents** to manage low-latency voice streams. It features a custom local TTS engine based on Qwen3-TTS for expressive, high-speed speech without cloud costs.

## 🎭 Emotional Engine
AURA automatically detects emotions from her own speech using a context-aware system.

### Emotion Recipes
AURA uses specific tag combinations to achieve nuanced expressions. You can guide her by using these tags in the system prompt:

| Emotion State | Tag Recipe | When to Use |
|---------------|------------|-------------|
| **Normal / Default** | `[happy]` | Casual chat, warm moments, kindness |
| **Curious Idle** | `[smile, sad, sad]` | Thoughtful listening, pondering |
| **Genuinely Worried** | `[sad, smile]` | Concern, empathy, comforting |
| **Uncertain Smile** | `[sad, smile, smile]` | Unsure but optimistic |
| **Devilish Grin** | `[angry, smile, smile]` | Mild mischief, playful teasing |
| **Kinda Mad** | `[sad, angry]` | Upset, pouting |
| **Pleading** | `[angry, sad]` | Begging, puppy-eyes |
| **Sincere Sad** | `[sad]` | Real sadness |
| **Angry** | `[angry]` | Irritated, frustrated |
| **Ghost Mode** | `[ghost]` | Toggle ghost companion off/on |

### Intensity Amplifiers
These are added to the recipes above to increase intensity:
- `shadow`: Darkens the face (Menacing/Deep Anger).
- `pupil_shrink`: Startled or devious eyes (Shock/Deep Mischief).
- `eyeshine_off`: Removes eye sparkle (Dark/Serious/Creepy).

---

## 🎨 VTube Studio Integration Guide

This guide covers setting up AURA with the **Hu Tao** sample model (Official Live2D Model).

### 1. Download & Install Model
1.  **Download**: Get the sample model from [Live2D Sample Models](https://boom.pm/en/items/6845149).
2.  **Move Files**: Extract the folder into your VTube Studio models directory: 
    - `.../VTube Studio/VTube Studio_Data/StreamingAssets/Live2DModels/`
3.  **Load Model**: Open VTube Studio, click the "Person" icon, and select The **Hu Tao**.

### 2. Configure Expressions (Hotkeys)
AURA triggers expressions by looking for specific hotkey names. You **must** create these hotkeys in VTube Studio:

1.  Open **Settings** (Gear icon) -> **Hotkey Settings** (Clapperboard icon).
2.  Click **+** to add a new hotkey for each state below:
    - **Name**: `Smile` | **Action**: `Set/Unset Expression` | **Exp**: `SmileLock.exp3.json` | **Key**: `L CTRL + 4`
    - **Name**: `Sad` | **Action**: `Set/Unset Expression` | **Exp**: `SadLock.exp3.json` | **Key**: `L CTRL + 3`
    - **Name**: `Angry` | **Action**: `Set/Unset Expression` | **Exp**: `Angry.exp3.json` | **Key**: `L CTRL + 5`
    - **Name**: `Ghost Happy` | **Action**: `Set/Unset Expression` | **Exp**: `Ghost.exp3.json` | **Key**: `L CTRL + 1`
    - **Name**: `Ghost Nervous` | **Action**: `Set/Unset Expression` | **Exp**: `GhostChange.exp3.json` | **Key**: `L CTRL + 2`
    - **Name**: `Shadow` | **Action**: `Set/Unset Expression` | **Exp**: `Shadow.exp3.json` | **Key**: `L CTRL + 6`
    - **Name**: `Pupil Shrink` | **Action**: `Set/Unset Expression` | **Exp**: `PupilShrink.exp3.json` | **Key**: `L CTRL + 7`
    - **Name**: `Eyeshine Off` | **Action**: `Set/Unset Expression` | **Exp**: `EyeshineOff.exp3.json` | **Key**: `L CTRL + 8`

> [!IMPORTANT]
> The hotkey **Names** (e.g., `Smile`, `Shadow`) are what the AURA code looks for. The **Expression** (JSON file) and **Key Combination** are for VTube Studio to handle the visual change.

### 3. Connection & Authorization
1.  In AURA's `.env`, set `VTUBE_ENABLED=true`.
2.  Ensure **VTube Studio API** is enabled in VTube Studio Settings -> Plugins.
3.  Run the system: Use the root **`start_aura.bat`**.
4.  **Connect to AURA** via the Dashboard (usually `http://localhost:5173`).
5.  VTube Studio will show a **Plugin Permission Request** as soon as the Voice session starts. Click **Allow**.
6.  A `token.txt` will be generated in `voice-agent/` to remember the session.

> [!TIP]
> To re-test the authorization flow, simply delete `voice-agent/token.txt` and restart the agent.

---

## 🔊 Lip Sync & Virtual Audio Cable (VAC)

To ensure AURA's mouth movements perfectly match her TTS output without background noise interference, use a Virtual Audio Cable.

### 1. Mouth Open Parameter
Go to **Model Settings** (Person with Gear icon) -> **Parameter Settings**:
1.  Find the parameter **Mouth Open**.
2.  **Input**: Set to `VoiceVolume`.
3.  **Output**: Set to `ParamMouthOpenY`.
4.  **Smoothing**: Set to `10`.
5.  **Input Range (IN)**: Set Min `0` and Max `1`.
6.  **Output Range (OUT)**: Set Min `0` and Max **`0.7`** (This prevents the "jaw dropping" effect by capping how wide the mouth can open).

### 1. Install VB-CABLE
- Download and install [VB-CABLE Driver](https://vb-audio.com/Cable/), click on New Package.
- **Restart your computer** after installation.

### 2. Route AURA's Output
AURA (via LiveKit) needs to output her voice to the **CABLE Input**. You can set this in Windows:
1. Go to VTube Studio > Settings > Microphone Settings > Check toggle microphone > Set Microphone to CABLE Output (VB-Audio Virtual Cable)
2. Go to the browser that runs your Aura (e.g. Chrome, Edge), let aura speak for a second or play an audio in that browser.
3. Right click speaker icon in the bottom right tray icon > sound settings > In the Advanced tab, go to volume mixer > Set the output of the browser to CABLE Input (VB-Audio Virtual Cable)
4. Right now you can't hear anything from your browser so go back to the sound settings > in the advanced tab go to "More sound settings" > Recording > Cable Output > Properties > Listen > Check "Listen to this device" > Set "Play back through this device" to your speakers/headphones.
5. Done Aura should be able to lipsync with Vtube Studio!

---

## 👄 Calibrating Mouth Movement

To prevent AURA from constantly "dropping her jaw" or looking unnatural while speaking, fine-tune these parameters in VTS:

### 1. Sensitivity & Gain
- **Volume Gain**: Adjust so the volume bar reaches about 70-80% when she speaks at normal volume. Start around `2.0` and tweak.
- **Frequency Gain**: This controls how specific frequencies affect mouth shape. High frequency gain makes the mouth open wider for sharp sounds.

---

## 🛠 Tech Stack
- **Voice Pipeline**: LiveKit Agents
- **STT**: Deepgram (Nova-3)
- **LLM**: DeepSeek-V3 (via OpenRouter)
- **TTS**: Faster-Qwen3-TTS (Local)
- **VTube Interaction**: `pyvts` (WebSocket)

## 🏃 Running the System
1.  **Preparation**: Ensure VTube Studio is open and your Microphone setup (VB-CABLE) is ready.
2.  **Start Everything**: Run the launcher from the project root:
    ```powershell
    .\start_aura.bat
    ```
3.  **Interaction**: Open the Dashboard and start a voice session.

