from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from app.services.rag_service import rag_service, UPLOAD_DIR
import shutil
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

def process_document_background(filepath):
    try:
        logger.info(f"Starting background indexing for {filepath.name}...")
        rag_service.add_document(filepath)
    except Exception as e:
        logger.error(f"Background indexing failed for {filepath.name}: {e}")

@router.post("/upload")
async def upload_file(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    try:
        filepath = UPLOAD_DIR / file.filename
        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Dispatch processing to a background threadpool so the asyncio loop isn't blocked
        background_tasks.add_task(process_document_background, filepath)
        
        return {"status": "processing", "filename": file.filename, "message": "Document is being indexed in the background."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/search")
def search(q: str):
    # def instead of async def pushes it to a threadpool, preventing synchronous embed_query from blocking the loop
    results = rag_service.search(q)
    return {"results": results}
