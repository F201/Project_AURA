# 🧠 Core - Project AURA (Central Brain)

The `core` folder serves as the **Single Source of Truth** for all artificial intelligence, memory, and personality of Project AURA. 

By centralizing all logic (LLM, RAG, Memory, and Prompting) within this folder, AURA maintains perfect consistency whether the user interacts via the text chat interface (`ai-service`) or interactive voice calls (`voice-agent`).

---

## 📂 Directory Structure

\`\`\`text
core/
├── brain/               # 🧠 AURA's thinking workflow logic
│   ├── graph.py         # LangGraph configuration (State Graph)
│   ├── state.py         # Global state definitions (messages, emotions, etc.)
│   └── nodes/           # Specific nodes (emotion processing, tool execution)
├── config/              # ⚙️ Default configurations
│   └── config.json      # LLM hyperparameter setup (temperature, max tokens)
├── models/              # 🗃️ Data Schemas
│   └── database.py      # Pydantic models for Supabase tables (Message, Memory)
├── prompts/             # 🎭 Personality & Instructions
│   └── system_prompt.md # AURA's base persona
└── services/            # 🛠️ Core Engines
    ├── embeddings.py    # Factory for vector embeddings (OpenAI/Ollama)
    ├── engine.py        # Background logic (Memory Engine)
    ├── llm.py           # OpenRouter/OpenAI integration + Regex Emotion Extraction
    ├── memory.py        # Supabase interactions (pgvector & conversations)
    ├── prompter.py      # Prompt formulation module (Voice vs Text Mode)
    ├── rag.py           # PDF/PPTX extraction & Document Indexing
    └── settings.py      # Global Supabase database settings
\`\`\`

---

## 🚀 Key Features

1. **Interface Agnostic (Separation of Concerns)**
   The `core` does not care whether the input comes from an HTTP API or WebRTC. It simply receives the raw state, processes it through the AI workflow graph, and returns the result (text & emotion) to be rendered by the respective client.
   
2. **Centralized Emotion & Expression Extraction (`llm.py` & `prompter.py`)**
   The system is instructed to use expression tags (e.g., `[happy]`, `[angry, smile]`). The LLM module in the `core` is responsible for intercepting these tags, sanitizing the text, and returning a structured JSON ready to drive VTube Studio facial expressions or UI indicators.

3. **Long-Term Memory & RAG (`memory.py` & `rag.py`)**
   Powered by Supabase `pgvector`, AURA can remember user facts from previous sessions and dynamically read documents (PDF/PPTX) without requiring a separate database server.

4. **LangGraph Thinking Engine (`brain/`)**
   Every user interaction enters a workflow graph that allows AURA to think, use tools (like internet search), and extract emotions before delivering the final response.

---

## 🔗 Relations with Other Services

*   **`ai-service` (FastAPI):** Acts as the API Layer. The HTTP routes in this service import `core.brain.graph.brain` directly to execute chats.
*   **`voice-agent` (LiveKit):** Acts as the "body and voice". This service hits the API in `ai-service` (which is connected to the `core`) to retrieve the processed text and emotion, then synthesizes it using Qwen3-TTS.

---

## ⚠️ Environment Prerequisites

Although the `core` is invoked by other services, it requires the following environment variables in the root project's `.env` file to function:

*   `OPENAI_API_KEY` or `OPENROUTER_API_KEY` (For the LLM engine)
*   `SUPABASE_URL` & `SUPABASE_SERVICE_KEY` (For memory and RAG)
*   `INTERNAL_API_KEY` (For inter-service security)