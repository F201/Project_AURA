# Usage Guide

Once you have successfully launched AURA and opened **[http://localhost:5173](http://localhost:5173)**, you will be greeted by the Dashboard.

## 1. Connecting to the Agent
- Ensure your microphone is functional and not blocked by the browser.
- Click **"Connect"** or the microphone icon on the Dashboard.
- Say a greeting like "Hello, AURA." The LiveKit indicator should show that your user stream is transmitting, and AURA will reply natively.

## 2. Using the Knowledge Base (RAG)
One of AURA's core features is the semantic memory provided by the AI-Service and Supabase.

### Uploading Documents
- Locate the document upload section on the dashboard UI.
- You can upload `.txt`, `.pdf`, or `.pptx` files.
- Once uploaded, the `AI Service` automatically unzips, chunks, embeds the texts, and stores them in your Supabase `pgvector` store.

### Asking Contextual Questions
- Simply ask AURA via voice about the document.
- Example: *"AURA, based on the PDF I just uploaded, what is the main objective of the Q3 project?"*
- AURA will process the prompt, fetch relevant vector matches from Supabase, and synthesize a response that is then piped out through the local TTS.

## 3. Bilingual Mode
Because Deepgram Nova-3 and the local Qwen3-TTS engine support multilingual capabilities across English and Japanese, you can transparently change languages mid-sentence, and AURA's LLM will match the primary language in its contextual response.

## Troubleshooting Common Issues

### Avatar isn't moving its mouth
- Ensure the `AnalyserNode` logic in the Dashboard component is receiving an audio stream. Check your browser console via `F12` to ensure `livekit-client` successfully connected to the WebRTC server.
- The lip sync relies entirely on RMS audio amplitude mapped to `ParamMouthOpenY`.

### "Agent Offline" or Disconnected
- Make sure all microservices are running. If `start_aura.bat` was killed, or Docker containers crashed, the Voice Agent Python app might not be polling LiveKit.
- Check the console logs of the `Voice Agent` window.
