from pydantic import BaseModel
from typing import Optional

class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None 
    identity: Optional[str] = None
    stream: bool = False

class ChatResponse(BaseModel):
    text: str
    emotion: str = "neutral"
    conversation_id: Optional[str] = None
    tools_used: list[dict] | None = None
