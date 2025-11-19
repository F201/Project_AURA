from fastapi import APIRouter
from app.models.chat import ChatRequest, ChatResponse

router = APIRouter(prefix="/chat")

@router.post("/", response_model=ChatResponse)
def chat(req: ChatRequest):
    return ChatResponse(text="Hello from AURA", emotion="neutral")
