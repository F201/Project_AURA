# Avatar System Architecture

AURA renders its avatar purely in the browser, alleviating the need for users to configure external tools like VTube Studio. This reduces latency, lowers system overhead, and dramatically simplifies deployment.

## Core Technologies

- **[pixi.js v6](https://pixijs.com/)**: Serves as the core WebGL engine and canvas renderer.
- **[pixi-live2d-display (0.4)](https://github.com/guansss/pixi-live2d-display)**: A specialized PIXI.js extension that allows native ingestion and drawing of Cubism models.
- **Cubism 4 Web SDK (WASM)**: The underlying core runtime engine that interprets Live2D parametric models.

> [!WARNING]  
> AURA's frontend utilizes `pixi.js v6`, because `pixi-live2d-display v0.4` does not support `pixi.js v7+`. Upgrading `pixi.js` via NPM will break the Avatar renderer entirely. Ensure dependencies remain locked in the Dashboard's `package.json`.

## How it works: End-to-end Rendering

1. **Initialization**:  
   The React `AvatarRenderer.jsx` script creates a PIXI Application bound to a `<canvas>` element filling the screen.

2. **Model Loading**:  
   Via `Live2DModel.from(URL)`, the model loads all associated assets (masks, textures, `.exp3.json` expressions, physics files) directly using browser network requests.

3. **Injected Animation Loop**:  
   Rather than relying upon standard `.motion3.json` playback exclusively, AURA monkey-patches the `coreModel.update()` function from PIXI. Every frame, right before vertex data is committed to the GPU, AURA updates logic:
   - **Blink FSM (Finite State Machine)**: Evaluates random timers to trigger organic eye blinks.
   - **Eye Saccades**: Adds micro-randomization to `ParamEyeBallX` and `ParamEyeBallY`.
   - **Sway & Breath**: Uses `Math.sin()` multiplied by epoch time to calculate organic breathing cycles mapped to `ParamBreath` and `ParamBodyAngleZ`.

## Lip Sync Pipeline

Since the Voice Pipeline streams synthesized speech audio chunks over a LiveKit WebRTC channel, AURA captures this stream using the Web Audio API.

1. Takes the `MediaStreamTrack` from LiveKit.
2. Mounts an `AnalyserNode` to compute the Root Mean Square (RMS) amplitude of audio bytes.
3. In a `requestAnimationFrame` loop, RMS maps directly to the Cubism parameter `ParamMouthOpenY` (from 0 to 1). This delivers 100% synchronized, framerate-independent lip movements without complex phoneme extraction.

## Expression Triggering

The Voice Agent passes an "Emotion Tag" over a LiveKit data channel message (e.g., `["shadow", "pupil_shrink"]`).
The frontend maps these tags to corresponding Live2D Expression names, using the `setExpression` native calls to smoothly interpolate parameter changes visually.
