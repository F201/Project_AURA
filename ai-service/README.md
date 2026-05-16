# AURA AI Service (The Brain)

The centralized intelligence hub for AURA. It manages the LangGraph reasoning engine, Supabase memory (pgvector), and LLM provider orchestration.

## 🚀 Overview
The AI Service is the "Brain" of AURA. Unlike traditional agents where the logic is coupled to the transport (voice), AURA separates the **logic** (AI Service) from the **transport** (Voice Agent/Dashboard).

## 🛠 Tech Stack
- **Framework**: FastAPI (Python 3.10+)
- **Logic Engine**: LangGraph & Pydantic AI
- **Vector Database**: Supabase (PostgreSQL + `pgvector`)
- **Embeddings**: OpenAI / OpenRouter / Ollama
- **Storage**: Supabase Buckets (for document source files)

## 📋 Key Capabilities
- **Centralized Chat**: `POST /api/v1/chat` supports both standard JSON and Server-Sent Events (SSE) for real-time streaming.
- **Semantic Memory (RAG)**: Automatically retrieves relevant context from uploaded PDFs, PPTXs, and text files.
- **Long-Term Memory (LTM)**: Extracts user facts and preferences to persist across sessions.
- **Provider Registry**: Intelligent routing and automatic failover between Anthropic, OpenAI, Groq, and OpenRouter.

## ⚙️ Setup & Running

1. `cd ai-service`
2. `python -m venv venv`
3. `venv\Scripts\activate` (Windows)
4. `pip install -r requirements.txt`
5. `uvicorn app.main:app --reload --port 8001`

## 🧪 Testing
Unit and integration tests are located in `tests/`.
```powershell
pytest tests/unit/
pytest tests/integration/
```
