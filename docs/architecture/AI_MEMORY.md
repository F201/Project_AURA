# AI Service & Memory

The AI Service allows AURA to read, comprehend, and recall large chunks of data across different formats utilizing **Retrieval-Augmented Generation (RAG)**.

## Framework
The AI Service runs on Python `FastAPI`, providing standardized REST routes for knowledge processing.

## The Memory Pipeline

When a user uploads a document through the AURA Dashboard (e.g. `guide.pdf`):
1. **Ingestion**: The document is sent via `POST /api/v1/memory`.
2. **Chunking**: The document text is extracted (via PDF parser) and split into smaller, overlapping chunks (e.g. 500 characters per chunk).
3. **Embedding**: A local `Sentence-Transformers` model evaluates the context of the chunk and translates it into a dense mathematical vector.
4. **Storage**: The vector, alongside the original text and metadata, is saved in the **Supabase** instance using the `pgvector` extension.

> [!NOTE]  
> Historical iteration note: Older documentation and comments might reference *Qdrant* as a vector DB. The codebase currently exclusively utilizes Supabase `pgvector` for both Conversation standard memory and RAG embeddings to unify dependencies.

## Semantic Search During Conversation

When a user speaks:
1. The `voice-agent` retrieves the transcribed user text.
2. Submits the text query to `POST /api/v1/chat` inside the AI Service.
3. The AI Service runs semantic similarity search on Supabase, comparing the user's prompt against all saved document vectors.
4. Retrieves the top matching text chunks.
5. Injects the text chunks seamlessly into the System Prompt context before contacting the LLM.

As a result, AURA dynamically has context as if she "remembered" reading the document.
