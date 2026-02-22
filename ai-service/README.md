# AURA AI Service

This service acts as the brain for AURA, managing long-term memory, personality orchestration, and API routing.

## Features
- **LangGraph Orchestration**: Processes input through a graph-based state machine for complex decision making.
- **Supabase (PGVector) Memory**: Handles semantic search and long-term conversation storage.
- **FastAPI Backend**: Provides high-performance endpoints for the dashboard and external integrations.

## Folder Structure
- `app/api/`: Versioned API endpoints.
- `app/core/`: Configuration, logging, and security.
- `app/models/`: Pydantic schemas and database models.
- `app/services/`: Core logic (LLM, Persona, Memory, VAD).
- `app/system/`: Lower-level orchestration (Audio pipeline, Emotion mapper).

## Development
To run this service independently (requires `.env`):
```bash
docker compose up ai-service
```
API Documentation: [http://localhost:8000/docs](http://localhost:8000/docs)
