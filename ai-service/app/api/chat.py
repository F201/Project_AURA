from fastapi import APIRouter
from app.services.flowise_client import FlowiseClient
from app.services.llm import LLMService
from app.models.chat import ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["chat"])

flowise = FlowiseClient()
llm = LLMService()

@router.post("/", response_model=ChatResponse)
def chat(req: ChatRequest):
    context = flowise.query_rag(req.message)
    output = llm.generate(req.message, context)
    return output
