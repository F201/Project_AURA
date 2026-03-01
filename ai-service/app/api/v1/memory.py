from fastapi import APIRouter, UploadFile, File, HTTPException
from app.services.memory_service import memory_service
from langchain_text_splitters import RecursiveCharacterTextSplitter
import io
import logging
from pypdf import PdfReader

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/upload")
async def upload_memory(file: UploadFile = File(...)):
    """
    Ingest a file (PDF or TXT) into Aura's memory (Qdrant).
    """
    filename = file.filename
    content = await file.read()
    text = ""

    # 1. Extract Text
    if filename.endswith(".pdf"):
        try:
            pdf = PdfReader(io.BytesIO(content))
            for page in pdf.pages:
                text += page.extract_text() + "\n"
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid PDF: {str(e)}")
    else:
        # Assume text
        text = content.decode("utf-8")

    if not text.strip():
        return {"status": "skipped", "reason": "Empty text"}

    # 2. Chunk Text
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50
    )
    chunks = splitter.split_text(text)

    # 3. Store Vectors
    count = 0
    await memory_service.ensure_collection()
    
    for chunk in chunks:
        await memory_service.store(
            text=chunk,
            metadata={"source": filename, "type": "document"}
        )
        count += 1

    return {"status": "success", "file": filename, "chunks_ingested": count}

@router.get("/search")
async def search_memory(query: str, limit: int = 3):
    """
    Debug: Search Qdrant for context.
    """
    results = await memory_service.search(query, limit)
    return {"query": query, "results": results}
