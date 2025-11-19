from fastapi import APIRouter
from app.models.stt import STTResponse

router = APIRouter(prefix="/stt")

@router.post("/", response_model=STTResponse)
def stt():
    return STTResponse(text="transcribed text")
