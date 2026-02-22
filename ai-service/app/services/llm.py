from openai import OpenAI
from app.core.config import settings
import logging
import re

logger = logging.getLogger(__name__)

class LLMService:
    def __init__(self):
        self.api_key = settings.OPENROUTER_API_KEY or settings.OPENAI_API_KEY
        self.model = settings.OPENAI_MODEL or "openai/gpt-3.5-turbo"
        self.client = None
        
        # Determine Base URL (OpenRouter vs OpenAI)
        self.base_url = "https://openrouter.ai/api/v1" if settings.OPENROUTER_API_KEY else None

        if self.api_key:
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )
            logger.info(f"LLM Service Initialized. Model: {self.model}, Base: {self.base_url or 'Default'}")
        else:
            logger.warning("API Key not set. LLMService will fail.")

    def generate(self, messages: list) -> dict:
        """
        Generates a response from the LLM based on the list of messages.
        Expects messages to be formatted by Prompter.
        """
        if not self.client:
            return {
                "text": "Error: API Key is missing. I cannot think without it!",
                "emotion": "[dizzy]"
            }

        try:
            extra_headers = {}
            if settings.OPENROUTER_API_KEY:
                extra_headers = {
                    "HTTP-Referer": "http://localhost:5173", # Frontend URL
                    "X-Title": "Project AURA", 
                }

            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=250,
                extra_headers=extra_headers
            )
            
            content = response.choices[0].message.content
            
            # Robust parsing for emotion using Regex
            # Matches [emotion] at the start of the string
            emotion_match = re.match(r'^\[(.*?)\]', content)
            
            emotion = "neutral"
            text = content
            
            if emotion_match:
                emotion = emotion_match.group(1)
                # Remove the emotion tag from the text
                text = content[emotion_match.end():].strip()
            
            return {
                "text": text,
                "emotion": emotion,
                "raw": content
            }
            
        except Exception as e:
            logger.error(f"LLM Generation Error: {e}")
            return {
                "text": f"I... I lost my train of thought. ({str(e)})",
                "emotion": "[confused]"
            }

llm_service = LLMService()
