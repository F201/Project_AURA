from fastapi import APIRouter

router = APIRouter(prefix="/health")

@router.get("/")
def health():
    return {"status": "ok"}
