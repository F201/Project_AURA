# AURA AI Service

This service provides the intelligent backbone for AURA, handling document processing, Knowledge Base (RAG) search, and LLM reasoning.

## 🚀 Overview
The AI Service is built with **FastAPI** and uses a RAG (Retrieval-Augmented Generation) pattern to grounded AURA's responses in specific documents.

## 🛠 Tech Stack
- **Framework**: FastAPI (Python 3.10+)
- **Vector Search**: Qdrant (local or cloud)
- **Embeddings**: Sentence-Transformers
- **ORMs/Tools**: Pydantic, SQLAlchemy

## 📋 Capabilities
- **Document Ingestion**: Upload `.txt`, `.pdf`, and `.pptx` documents to AURA's brain.
- **RAG Search**: Semantic search over uploaded documents to provide context to the Voice Agent.
- **API Endpoints**: 
  - `GET /api/v1/rag/search`: Search the knowledge base.
  - `POST /api/v1/rag/upload`: Ingest new documents.

## ⚙️ Setup
1. **Navigate to directory**: `cd ai-service`
2. **Setup environment**: `python -m venv venv`
3. **Activate environment**:
   - Windows: `venv\Scripts\activate`
   - Unix: `source venv/bin/activate`
4. **Install dependencies**: `pip install -r requirements.txt`
5. **Configure `.env`**:
   - `OPENAPI_KEY`: Your LLM provider key.
   - `QDRANT_URL`: URL to your vector database.
6. **Run**: `uvicorn app.main:app --reload`
