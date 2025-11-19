# Backend File Map (ai-service)

This document explains the purpose of each folder and module inside the ai-service.

## api/
Entry points exposed to the outside world via FastAPI.

- main.py — Main FastAPI application, router registration.
- v1/chat.py — Chat endpoint, communicates with persona, LLM, TTS, STT.
- v1/stt.py — Receives audio -> sends to STT service.
- v1/tts.py — Receives text -> returns synthesized audio.
- v1/avatar.py — For VTube Studio / Avatar control actions.
- v1/system.py — System introspection, status, diagnostics.
- v1/health.py — Health check for Docker / orchestration.

## core/
System-wide utilities and configuration.

- config.py — Environment variables, constants.
- logger.py — Logger configuration shared across all services.
- utils.py — General-purpose helper functions.

## models/
Request/response schemas (Pydantic models).

- chat.py — ChatRequest, ChatResponse.
- stt.py — Speech transcription response model.
- tts.py — Audio output model.
- avatar.py — Avatar trigger models.
- system.py — System status models.

## services/
Core logic modules. Each one represents a functional subsystem.

- persona.py — Persona voice, personality modeling.
- prompter.py — Builds prompts from message + context.
- llm.py — LLM wrapper (OpenAI, Anthropic, etc.)
- flowise_client.py — Queries Flowise for RAG context.
- stt_service.py — Handles speech-to-text.
- vad.py — Voice activity detection.
- tts_service.py — Converts text → audio.
- avatar_client.py — Sends commands to avatar (VTS or custom).

## system/
Complex subsystems or pipelines.

- audio_pipeline.py — Combined processing pipeline for audio.
- emotion_mapper.py — Maps LLM output to facial expression or animation.
