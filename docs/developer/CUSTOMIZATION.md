# Customization & Tweaking

AURA is highly modular, allowing developers to adapt its aesthetics, models, and personality.

## 1. Modifying the Live2D Avatar

The default model is Hu Tao mapping a `.model3.json` file. You can swap this with any valid Cubism 4 model.

1. Locate a Live2D Cubism 4 Model folder containing:
   - `<ModelName>.model3.json`
   - `.moc3` binary
   - Contains textures in `.png`
   - Physics `.json`
   - `.exp3.json` expression files
2. Create a folder inside the Dashboard public directory: `dashboard/public/models/<ModelName>`
3. Copy the files into the new directory.
4. Modify `MODEL_URL` inside `dashboard/src/components/AvatarRenderer.jsx` to point to the new JSON file:
   ```javascript
   const MODEL_URL = "/models/<ModelName>/<ModelName>.model3.json";
   ```

### Overriding Expressions
Different modellers use different IDs for expressions. By default, the `voice-agent` outputs names like `smile` and `shadow`. If your new character uses `Exp_Happy.exp3.json`, you must modify the `voice-agent/avatar_bridge.py` mapping dict so that python string outputs correctly bind to the new Model's `.exp3.json` file names.

## 2. Modifying Voice Characteristics
AURA's local GPU TTS is generated using Faster-Qwen3-TTS.

To change the generation parameters (Speed, Hallucination cut-offs):
- Open `voice-agent/aura_tts.py`
- Modify `repetition_penalty` (Increase if AURA keeps repeating words).
- Modify the multiplier for `max_new_tokens` depending on if you switch to a more loquacious LLM.

## 3. Adapting the Personality Prompt
The instructions fed to the OpenRouter LLM controlling AURA are defined in the backend codebase (and eventually via the `personality_settings` in Supabase). 
To make AURA speak differently, add specific instructions to the System Prompts ensuring she consistently returns `[emotion_tag]` pre-fixes, or the visual avatar will stall out while the voice speaks.
