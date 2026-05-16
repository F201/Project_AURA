from pydantic_settings import BaseSettings
from dotenv import load_dotenv
import os
import logging
from pathlib import Path

logger = logging.getLogger("uvicorn")


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
    ANTHROPIC_API_KEY: str | None = None
    GROQ_API_KEY: str | None = None
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    # Default Models
    DEFAULT_LLM_MODEL: str = "deepseek/deepseek-v3.2"
    DEFAULT_OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    DEFAULT_OPENROUTER_EMBEDDING_MODEL: str = "openai/text-embedding-3-small"
    DEFAULT_OLLAMA_EMBEDDING_MODEL: str = "nomic-embed-text"

    SUPABASE_URL: str | None = None
    SUPABASE_SERVICE_KEY: str | None = None
    INTERNAL_API_KEY: str | None = None

    model_config = {
        "env_file": str(ENV_PATH),
        "env_file_encoding": "utf-8",
        "extra": "ignore"
    }

settings = Settings()

if settings.SUPABASE_URL:
    logger.info(f"Supabase URL loaded: {settings.SUPABASE_URL}")
else:
    logger.error("Supabase URL NOT loaded")
