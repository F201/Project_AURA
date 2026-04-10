# AI Service Developer Guide

The AI Service handles the memory ingestion logic for AURA's "Brain," dealing with RAG (Retrieval-Augmented Generation) architectures. 

## Python Ecosystem
This service is substantially lighter than the `voice-agent` and does not formally require PyTorch GPU dependencies locally, allowing standard Venv utilization.

```bash
cd ai-service
python -m venv venv
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate   # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Exploring API Endpoints
FastAPI natively builds fully interactive OpenAPI documentation interfaces.
Rather than attempting to trigger memory ingestion strictly through the React UI, you can test payloads quickly during backend hacking directly from the browser natively.

1. Ensure `uvicorn` is running.
2. Open your browser and navigate to `http://localhost:8000/docs`.
3. You can execute `POST /api/v1/memory` uploads directly from this page, feeding fake test PDFs into the vector engine.

## Resetting Supabase Memory locally
If you wish to purge the memory instance, since we leverage the Supabase `pgvector` container extension:
1. Connect via CLI or Datagrip to your Supabase project URL credentials referenced in `.env`.
2. Truncate the `memories` table:
   ```sql
   TRUNCATE TABLE memories;
   ```
3. This deletes all semantic vectors and chunks. Re-upload documents to test clean indices.
