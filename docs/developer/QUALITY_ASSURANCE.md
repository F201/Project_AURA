# Quality Assurance & Testing

To ensure Project AURA remains stable as we add new features, we follow a three-tier testing strategy.

## 1. Unit Testing
Unit tests focus on isolated logic without external dependencies (DBs, APIs).

### Voice Agent Logic
We test emotion parsing and text cleaning to ensure the avatar's face matches the speech.
- **Run**: `cd voice-agent && pytest tests/test_emotion_parsing.py`

### AI Service Logic
We test the brain's ability to inject memories and handle provider fallbacks.
- **Run**: `cd ai-service && pytest tests/unit/`

### Dashboard Components
We use Vitest to ensure UI components (like the Personality Tuner) respond correctly to user input.
- **Run**: `cd dashboard && npm test`

---

## 2. Integration Testing
Integration tests verify that two or more services work together correctly.

- **AI Service ↔ Supabase**: Verifying that RAG retrieval returns actual data.
- **Voice Agent ↔ AI Service**: Verifying that SSE streams are correctly consumed.
- **Run**: `cd ai-service && pytest tests/integration/`

---

## 3. End-to-End (E2E) Testing
E2E tests simulate a real user interaction in the browser.

- **Avatar Rendering**: Verifying that the Live2D model loads in PIXI.js.
- **Voice Loop**: (Planned) Using Playwright to trigger a microphone event and check for audio output.

---

## Stability Guidelines
1. **Never Break the SSE Stream**: The connection between the Voice Agent and AI Service must be robust. If the stream breaks, the avatar will stop moving.
2. **Handle API Rate Limits**: Always use the `RetryableError` pattern in the `ProviderRegistry` to avoid crashing on 429s.
3. **Unicode Safety**: On Windows, always ensure environment variables like `PYTHONIOENCODING=utf-8` are set.
