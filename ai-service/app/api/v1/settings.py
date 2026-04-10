from fastapi import APIRouter
from pydantic import BaseModel
from app.services.settings_service import settings_service

router = APIRouter()

PROVIDERS = ["openrouter", "openai", "anthropic", "groq", "ollama"]


class SettingsPatch(BaseModel):
    system_prompt: str | None = None
    model:         str | None = None
    provider:      str | None = None
    temperature:   float | None = None
    max_tokens:    int | None = None
    empathy:       int | None = None
    humor:         int | None = None
    formality:     int | None = None


class ApiKeysPatch(BaseModel):
    openrouter_api_key: str | None = None
    deepgram_api_key:   str | None = None
    cartesia_api_key:   str | None = None
    anthropic_api_key:  str | None = None
    groq_api_key:       str | None = None
    ollama_base_url:    str | None = None
    livekit_url:        str | None = None
    livekit_api_key:    str | None = None
    livekit_api_secret: str | None = None


@router.get("")
def get_settings():
    return settings_service.get_settings()


@router.put("")
def update_settings(patch: SettingsPatch):
    data = {k: v for k, v in patch.model_dump().items() if v is not None}
    return settings_service.update_settings(data)


@router.get("/providers")
def list_providers():
    """Return available provider names for the UI dropdown."""
    return {"providers": PROVIDERS}


@router.get("/keys")
def get_api_keys():
    keys = settings_service.get_api_keys()
    # Return masked values — just signals whether the key is configured
    return {k: ("set" if (v and str(v).strip()) else None)
            for k, v in keys.items() if k != "id"}


@router.put("/keys")
def update_api_keys(patch: ApiKeysPatch):
    data = {k: v for k, v in patch.model_dump().items() if v is not None}
    settings_service.update_api_keys(data)
    return {"status": "ok"}
