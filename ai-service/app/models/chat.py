from pydantic import BaseModel

class ChatRequest(BaseModel):
    message: str
    history: list[dict] | None = None

class ChatResponse(BaseModel):
    text: str
    emotion: str
