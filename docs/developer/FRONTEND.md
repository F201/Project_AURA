# Frontend Hacking Guide

The AURA Dashboard handles LiveKit WebRTC state management and directly renders the Pixi.js avatar on an HTML5 Canvas.

## Tech Stack
- **Framework:** React 19 + Vite
- **Styling:** Tailwind CSS V4
- **WebGL Rendering:** Pixi.js v6 + `pixi-live2d-display`

## Running the Development Server
Since UI changes require instant visual feedback, you should run the Vite dev server manually instead of relying on the overarching containerized solution.

1. Keep your AI Service and Voice Agent running in the background.
2. In a new terminal tab, navigate to the dashboard map.
   ```bash
   cd dashboard
   npm install --no-fund
   npm run dev
   ```
3. Open `http://localhost:5173`. Any changes to React `.jsx` components will instantly Hot-Module-Reload (HMR) without needing a page refresh.

## Modifying the Avatar

### Dependency Warning
> [!WARNING]
> Do **not** upgrade `pixi.js` via NPM. The currently locked mechanism uses `pixi.js` v6 because `pixi-live2d-display` is deeply broken on Pixi versions 7 and 8 due to Cubism WASM breaking changes.

### Adding New Idle Animations
If you wish to make the character blink differently or sway faster, locate `src/components/AvatarRenderer.jsx` and inspect the injected `coreModel.update()` patch.
This block intercepts the Live2D GPU memory pipeline. You can inject native JS `Math.sin()` loops to map custom procedural animations before the frame is rendered!
