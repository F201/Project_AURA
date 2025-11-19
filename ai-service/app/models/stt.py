from pydantic import BaseModel

class STTResponse(BaseModel):
    text: str
