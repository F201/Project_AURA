from openai import OpenAI
from app.core.config import settings
import logging
import re

logger = logging.getLogger(__name__)


class LLMService:
    def __init__(self):
        self._env_key = settings.OPENROUTER_API_KEY or settings.OPENAI_API_KEY
        self.base_url = "https://openrouter.ai/api/v1" if settings.OPENROUTER_API_KEY else None
        self.client = None

        if self._env_key:
            self.client = OpenAI(api_key=self._env_key, base_url=self.base_url)
            logger.info(f"LLM Service Initialized. Base: {self.base_url or 'Default'}")
        else:
            logger.warning("API Key not set. LLMService will fail.")

    def _get_client(self):
        """Return a client using the DB key if set, falling back to the env key."""
        from app.services.settings_service import settings_service
        db_key = settings_service.get_api_keys().get("openrouter_api_key")
        if db_key and db_key.strip():
            return OpenAI(api_key=db_key, base_url="https://openrouter.ai/api/v1")
        return self.client

    def generate(self, messages: list, model: str = None, temperature: float = None, max_tokens: int = None) -> dict:
        client = self._get_client()
        if not client:
            return {"text": "Error: API Key is missing.", "emotion": "[dizzy]"}

        # Import here to avoid circular imports at module load time
        from app.services.settings_service import settings_service
        db = settings_service.get_settings()

        actual_model = model or db.get("model") or "deepseek/deepseek-v3.2"
        actual_temp = temperature if temperature is not None else db.get("temperature", 0.8)
        actual_max_tokens = max_tokens or db.get("max_tokens") or 300

        try:
            extra_headers = {}
            if settings.OPENROUTER_API_KEY:
                extra_headers = {
                    "HTTP-Referer": "http://localhost:5173",
                    "X-Title": "Project AURA",
                }

            response = client.chat.completions.create(
                model=actual_model,
                messages=messages,
                temperature=actual_temp,
                max_tokens=actual_max_tokens,
                extra_headers=extra_headers,
            )

            content = response.choices[0].message.content
            emotion_match = re.match(r'^\[(.*?)\]', content)
            emotion = "neutral"
            text = content

            if emotion_match:
                emotion = emotion_match.group(1)
                text = content[emotion_match.end():].strip()

            return {"text": text, "emotion": emotion, "raw": content}

        except Exception as e:
            logger.error(f"LLM Generation Error: {e}")
            return {"text": f"I lost my train of thought. ({str(e)})", "emotion": "[confused]"}


llm_service = LLMService()
