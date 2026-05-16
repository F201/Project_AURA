import urllib.request
import logging
from langchain_openai import OpenAIEmbeddings
from langchain_core.embeddings import Embeddings
from app.core.config import settings

logger = logging.getLogger(__name__)

def _ollama_is_running(base_url: str) -> bool:
    """Return True if an Ollama server is reachable at base_url."""
    try:
        urllib.request.urlopen(f"{base_url}/api/tags", timeout=2)
        return True
    except Exception:
        return False

def get_embeddings() -> Embeddings | None:
    """
    Centralized factory for creating LangChain Embeddings.
    Tries providers in order of preference.
    """
    if settings.OPENAI_API_KEY:
        logger.info("Embeddings: Using OpenAI Directly for semantic embeddings.")
        return OpenAIEmbeddings(
            api_key=settings.OPENAI_API_KEY,
            model=settings.DEFAULT_OPENAI_EMBEDDING_MODEL,
        )
    elif settings.OPENROUTER_API_KEY:
        logger.info("Embeddings: Using OpenRouter for semantic embeddings.")
        return OpenAIEmbeddings(
            api_key=settings.OPENROUTER_API_KEY,
            model=settings.DEFAULT_OPENROUTER_EMBEDDING_MODEL,
            base_url="https://openrouter.ai/api/v1",
        )
    elif _ollama_is_running(settings.OLLAMA_BASE_URL):
        logger.info("Embeddings: Using local Ollama for semantic embeddings.")
        return OpenAIEmbeddings(
            api_key="ollama",
            model=settings.DEFAULT_OLLAMA_EMBEDDING_MODEL,
            base_url=f"{settings.OLLAMA_BASE_URL}/v1",
        )
    else:
        logger.warning(
            "No embedding provider available "
            "(OPENAI_API_KEY / OPENROUTER_API_KEY not set; Ollama not reachable). "
        )
        return None
