import logging
import time
from supabase import create_client, Client
from app.core.config import settings as app_settings

logger = logging.getLogger(__name__)

_DEFAULTS = {
    "system_prompt": None,
    "model":         "deepseek/deepseek-v3.2",
    "provider":      "openrouter",
    "temperature":   0.8,
    "max_tokens":    300,
    "empathy":       50,
    "humor":         50,
    "formality":     50,
}

_KEY_DEFAULTS = {
    "openrouter_api_key": None,
    "deepgram_api_key":   None,
    "cartesia_api_key":   None,
    "anthropic_api_key":  None,
    "groq_api_key":       None,
    "ollama_base_url":    "http://localhost:11434",
    "livekit_url":        None,
    "livekit_api_key":    None,
    "livekit_api_secret": None,
}


class SettingsService:
    def __init__(self):
        self._client: Client | None = None
        if app_settings.SUPABASE_URL and app_settings.SUPABASE_SERVICE_KEY:
            self._client = create_client(app_settings.SUPABASE_URL, app_settings.SUPABASE_SERVICE_KEY)
        
        # Simple cache
        self._cache = {}
        self._cache_expiry = {
            "settings": 0,
            "keys": 0
        }
        self._TTL = 60 # seconds for settings
        self._KEY_TTL = 5 # seconds for keys (re-check faster)

    def get_settings(self) -> dict:
        if not self._client:
            return dict(_DEFAULTS)
        
        now = time.time()
        if "settings" in self._cache and now < self._cache_expiry["settings"]:
            return self._cache["settings"]

        try:
            result = self._client.table("personality_settings").select("*").eq("id", 1).single().execute()
            if result.data:
                settings = {**_DEFAULTS, **result.data}
                self._cache["settings"] = settings
                self._cache_expiry["settings"] = now + self._TTL
                return settings
        except Exception as e:
            logger.warning(f"SettingsService.get_settings failed: {e}")
        return self._cache.get("settings", dict(_DEFAULTS))

    def update_settings(self, patch: dict) -> dict:
        if not self._client:
            return dict(_DEFAULTS)
        try:
            result = self._client.table("personality_settings").update(patch).eq("id", 1).execute()
            # Invalidate cache
            if "settings" in self._cache:
                del self._cache["settings"]
            if result.data:
                return {**_DEFAULTS, **result.data[0]}
        except Exception as e:
            logger.error(f"SettingsService.update_settings failed: {e}")
        return dict(_DEFAULTS)

    def get_api_keys(self) -> dict:
        if not self._client:
            return dict(_KEY_DEFAULTS)

        now = time.time()
        if "keys" in self._cache and now < self._cache_expiry["keys"]:
            return self._cache["keys"]

        try:
            result = self._client.table("api_keys").select("*").eq("id", 1).single().execute()
            if result.data:
                keys = {**_KEY_DEFAULTS, **result.data}
                self._cache["keys"] = keys
                self._cache_expiry["keys"] = now + self._KEY_TTL
                return keys
        except Exception as e:
            logger.warning(f"SettingsService.get_api_keys failed: {e}")
        return self._cache.get("keys", dict(_KEY_DEFAULTS))

    def update_api_keys(self, patch: dict) -> dict:
        if not self._client:
            return dict(_KEY_DEFAULTS)
        try:
            result = self._client.table("api_keys").update(patch).eq("id", 1).execute()
            # Invalidate cache
            if "keys" in self._cache:
                del self._cache["keys"]
            if result.data:
                return {**_KEY_DEFAULTS, **result.data[0]}
        except Exception as e:
            logger.error(f"SettingsService.update_api_keys failed: {e}")
        return dict(_KEY_DEFAULTS)


settings_service = SettingsService()
