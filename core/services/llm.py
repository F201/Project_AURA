from openai import OpenAI
import logging
import re
import json
import os
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class LLMService:
    def __init__(self):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        core_dir = os.path.dirname(current_dir)
        config_path = os.path.join(core_dir, "config", "config.json")
        
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)["llm"]

        self.openrouter_key = os.getenv("OPENROUTER_API_KEY")
        self.api_key = self.openrouter_key or os.getenv("OPENAI_API_KEY")
        self.model = os.getenv("OPENAI_MODEL") or self.config["default_model"] 
        self.client = None

        self.base_url = "https://openrouter.ai/api/v1" if self.openrouter_key else None

        if self.api_key:
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )
            logger.info(f"LLM Service Initialized. Model: {self.model}")
        else:
            logger.warning("API Key not set. LLMService will fail.")

    def generate(self, messages: list) -> dict:
        if not self.client:
            return {
                "text": "Error: API Key is missing. I cannot think without it!",
                "emotion": "[dizzy]"
            }

        try:
            extra_headers = {}
            if self.openrouter_key:
                extra_headers = {
                    "HTTP-Referer": "http://localhost:5173", 
                    "X-Title": "Project AURA", 
                }

            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.config["temperature"],
                max_tokens=self.config["max_tokens"],
                extra_headers=extra_headers
            )
            
            content = response.choices[0].message.content

            # Emotion Tags
            emotion_match = re.search(r'\[([a-zA-Z_]+).*?\]', content)
            
            emotion = "neutral"
            text = content
            
            if emotion_match:
                emotion = emotion_match.group(1).lower()
                text = content[:emotion_match.start()] + content[emotion_match.end():]
                text = text.strip()
            
            return {
                "text": text,
                "emotion": emotion,
                "raw": content
            }
            
        except Exception as e:
            logger.error(f"LLM Generation Error: {e}")
            return {
                "text": f"I... I lost my train of thought. ({str(e)})",
                "emotion": "confused"
            }

llm_service = LLMService()