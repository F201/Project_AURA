from pydantic import BaseModel

class TTSResponse(BaseModel):
    audio: bytes
