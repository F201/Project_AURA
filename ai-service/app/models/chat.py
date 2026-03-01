from pydantic import BaseModel

class ChatRequest(BaseModel):
    message: str
    history: list[dict] | None = None
    session_id: str = "default"

class ChatResponse(BaseModel):
    text: str
    emotion: str
    tools_used: list[dict] | None = None
