from app.core.config import settings
import requests

class LLMService:
    def generate(self, message: str, context: dict):
        # A placeholder LLM call (you can replace with OpenAI or local LLM)
        return {
            "text": f"Echo: {message}",
            "emotion": "neutral"
        }
