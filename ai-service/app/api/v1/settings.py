from fastapi import APIRouter
from pydantic import BaseModel
from app.services.settings_service import settings_service

router = APIRouter()


class SettingsPatch(BaseModel):
    system_prompt: str | None = None
    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    empathy: int | None = None
    humor: int | None = None
    formality: int | None = None


class ApiKeysPatch(BaseModel):
    openrouter_api_key: str | None = None
    deepgram_api_key: str | None = None
    cartesia_api_key: str | None = None
    livekit_url: str | None = None
    livekit_api_key: str | None = None
    livekit_api_secret: str | None = None


@router.get("")
def get_settings():
    return settings_service.get_settings()


@router.put("")
def update_settings(patch: SettingsPatch):
    data = {k: v for k, v in patch.model_dump().items() if v is not None}
    return settings_service.update_settings(data)


@router.get("/keys")
def get_api_keys():
    keys = settings_service.get_api_keys()
    # Mask values in response — only reveal whether each key is set
    return {k: ("••••••••" if v else None) for k, v in keys.items() if k != "id"}


@router.put("/keys")
def update_api_keys(patch: ApiKeysPatch):
    data = {k: v for k, v in patch.model_dump().items() if v is not None}
    settings_service.update_api_keys(data)
    return {"status": "ok"}
