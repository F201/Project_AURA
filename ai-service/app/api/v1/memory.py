from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from app.services.memory_service import memory_service
from langchain_text_splitters import RecursiveCharacterTextSplitter
import io
import logging
from pypdf import PdfReader
from app.models.chat import SessionRequest, SessionResponse, MemoryExtractionRequest
from app.services.providers.registry import provider_registry
from app.services.prompter import prompter
from app.api.v1.chat import verify_internal_api_key

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/upload")
async def upload_memory(file: UploadFile = File(...), _ = Depends(verify_internal_api_key)):
    """
    Ingest a file (PDF or TXT) into Aura's memory.
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
    for chunk in chunks:
        await memory_service.store(
            text=chunk,
            metadata={"source": filename, "type": "document"}
        )
        count += 1

    return {"status": "success", "file": filename, "chunks_ingested": count}

@router.get("/search")
async def search_memory(query: str, limit: int = 3, _ = Depends(verify_internal_api_key)):
    """
    Debug: Search memory for context.
    """
    results = await memory_service.search(query, limit)
    return {"query": query, "results": results}


@router.post("/session", response_model=SessionResponse)
async def get_voice_session(request: SessionRequest, _ = Depends(verify_internal_api_key)):
    """
    Get or create a conversation for a voice session and return relevant context.
    """
    import asyncio
    from app.services.settings_service import settings_service

    # 1. Get/Create Conversation
    conv_id = await memory_service.get_or_create_conversation(
        request.identity, 
        request.title
    )
    
    if not conv_id:
        raise HTTPException(status_code=500, detail="Failed to initialize session")

    # 2. Get Long-Term Memories (LTM)
    ltm = await memory_service.get_long_term_memories(request.identity)
    
    # 3. Pre-warm settings and api_keys caches in the background
    asyncio.create_task(settings_service.get_settings())
    asyncio.create_task(settings_service.get_api_keys())

    return SessionResponse(
        conversation_id=str(conv_id),
        is_returning_user=bool(ltm),
        long_term_memory=ltm
    )


@router.post("/extract")
async def extract_and_save(request: MemoryExtractionRequest, _ = Depends(verify_internal_api_key)):
    """
    Extract personal facts from a conversation and save them to Supabase.
    """
    text_to_process = request.chat_text
    
    # If text not provided, fetch from history
    if not text_to_process:
        from uuid import UUID
        history = await memory_service.get_history(UUID(request.conversation_id), n=50)
        text_to_process = "\n".join([f"{m.role}: {m.content}" for m in history])

    if not text_to_process.strip():
        return {"status": "skipped", "reason": "No text to extract"}

    # 1. Generate Extraction
    messages = prompter.build_extraction_prompt(text_to_process)
    
    # Use a strong model for extraction
    response = await provider_registry.generate(messages)
    extracted_text = response.get("text", "")

    if "NO_FACTS" in extracted_text or not extracted_text.strip():
        return {"status": "skipped", "reason": "No new facts found"}

    # 2. Save to Long-Term Memory (Supabase)
    await memory_service.save_long_term_memory(
        request.identity,
        extracted_text,
        request.conversation_id
    )

    return {"status": "success", "extracted": extracted_text}

@router.get("/history/{conversation_id}")
async def get_history(conversation_id: str, n: int = 50, _ = Depends(verify_internal_api_key)):
    """
    Get conversation history for a given conversation ID.
    """
    from uuid import UUID
    try:
        history = await memory_service.get_history(UUID(conversation_id), n)
        return {"history": history}
    except Exception as e:
        logger.error(f"Error fetching history for {conversation_id}: {e}")
        return {"history": []}
