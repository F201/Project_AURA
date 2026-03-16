# AURA Dashboard

React frontend for AURA. Handles voice calls via LiveKit, renders the Live2D avatar, and provides the chat/settings UI.

## Tech Stack

| | |
|-|-|
| **Framework** | React 19 + Vite |
| **Styling** | TailwindCSS 4 |
| **Avatar** | pixi-live2d-display 0.4 + pixi.js 6 + Cubism 4 runtime |
| **Voice** | livekit-client SDK (WebRTC) |
| **Database** | @supabase/supabase-js (chat history, memory) |

> pixi.js must stay at v6. pixi-live2d-display 0.4 is incompatible with pixi.js v7+.

## Running Locally

```bash
cd dashboard
npm install
npm run dev
```

Dashboard available at **http://localhost:5173**.

## Build

```bash
npm run build
```

The production bundle is served via Nginx in the Docker container.

## Avatar Renderer

`src/components/AvatarRenderer.jsx` manages the PIXI application and Live2D model lifecycle:

- Loads `MODEL_URL` (default: `/models/hutao/Hu Tao.model3.json`) via `Live2DModel.from()`
- Injects idle animation parameters into `coreModel.update()` — head sway, breath, blink FSM, eye saccades
- Exposes `setMouthOpen(0–1)` for lip sync and `setExpression(names[])` for emotion triggers
- Requires `public/live2dcubismcore.min.js` (Cubism 4 WASM runtime) to be present and loaded before the ES module

To swap the model, copy a Cubism 4 model folder to `public/models/<name>/` and update `MODEL_URL`.

## Lip Sync

`src/components/CallOverlay.jsx` taps the LiveKit audio track via `createMediaStreamSource` → `AnalyserNode`. An RAF loop reads RMS amplitude and calls `avatarRef.current.setMouthOpen(value)` each frame.
