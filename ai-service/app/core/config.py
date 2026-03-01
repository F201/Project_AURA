from pydantic_settings import BaseSettings
from dotenv import load_dotenv
import os
import logging
from pathlib import Path

logger = logging.getLogger("uvicorn")

# Robust absolute path calculation
# Current file: .../ai-service/app/core/config.py
# .env is at:   .../Project_AURA/.env
# We need to go up 3 levels from 'app/core' to 'ai-service', then one more to root?
# No.
# __file__ = .../ai-service/app/core/config.py
# parent = .../ai-service/app/core
# parent.parent = .../ai-service/app
# parent.parent.parent = .../ai-service
# parent.parent.parent.parent = .../Project_AURA

CURRENT_FILE = Path(__file__).resolve()
AI_SERVICE_DIR = CURRENT_FILE.parent.parent.parent
PROJECT_ROOT = AI_SERVICE_DIR.parent

# Check for .env in root (Docker) or parent (Native)
ENV_PATH = PROJECT_ROOT / ".env"
if not ENV_PATH.exists():
    ENV_PATH = AI_SERVICE_DIR / ".env"

logger.info(f"Calculated ENV_PATH: {ENV_PATH}")

if ENV_PATH.exists():
    load_dotenv(ENV_PATH)
    logger.info(".env file found and loaded")
else:
    logger.warning(f".env file NOT found at {ENV_PATH}")

class Settings(BaseSettings):
    LLM_API_KEY: str | None = None
    OPENAI_API_KEY: str | None = None
    OPENROUTER_API_KEY: str | None = None
    OPENAI_MODEL: str = "gpt-3.5-turbo"

    # Supabase
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_KEY: str = ""
    VITE_SUPABASE_URL: str = ""
    VITE_SUPABASE_ANON_KEY: str = ""

    class Config:
        env_file = str(ENV_PATH)
        env_file_encoding = 'utf-8'
        extra = "ignore" # Ignore extra fields

settings = Settings()

if settings.SUPABASE_URL:
    logger.info(f"Supabase URL loaded: {settings.SUPABASE_URL}")
else:
    logger.error("Supabase URL NOT loaded")
