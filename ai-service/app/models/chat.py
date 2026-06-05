from pydantic import BaseModel
from typing import Optional

class ChatMessageModel(BaseModel):
    role: str
    content: str
    emotion: str = "neutral"

class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None 
    identity: Optional[str] = None
    stream: bool = False
    history: Optional[list[ChatMessageModel]] = None

class ChatResponse(BaseModel):
    text: str
    emotion: str = "neutral"
    conversation_id: Optional[str] = None
    tools_used: list[dict] | None = None

class SessionRequest(BaseModel):
    identity: str
    title: Optional[str] = "Voice Session"

class SessionResponse(BaseModel):
    conversation_id: str
    is_returning_user: bool
    long_term_memory: str

class MemoryExtractionRequest(BaseModel):
    conversation_id: str
    identity: str
    chat_text: Optional[str] = None

class PersistRequest(BaseModel):
    conversation_id: str
    identity: Optional[str] = None
    messages: list[ChatMessageModel]

