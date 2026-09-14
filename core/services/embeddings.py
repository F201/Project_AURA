import os
import urllib.request
import logging
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from langchain_core.embeddings import Embeddings

load_dotenv()
logger = logging.getLogger(__name__)

def _ollama_is_running(base_url: str) -> bool:
    try:
        urllib.request.urlopen(f"{base_url}/api/tags", timeout=2)
        return True
    except Exception:
        return False

def get_embeddings() -> Embeddings | None:
    openai_key = os.getenv("OPENAI_API_KEY")
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    ollama_base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    if openai_key:
        logger.info("Embeddings: Using OpenAI Directly for semantic embeddings.")
        return OpenAIEmbeddings(
            api_key=openai_key,
            model=os.getenv("DEFAULT_OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
        )
    elif openrouter_key:
        logger.info("Embeddings: Using OpenRouter for semantic embeddings.")
        return OpenAIEmbeddings(
            api_key=openrouter_key,
            model=os.getenv("DEFAULT_OPENROUTER_EMBEDDING_MODEL", "openai/text-embedding-3-small"),
            base_url="https://openrouter.ai/api/v1",
        )
    elif _ollama_is_running(ollama_base):
        logger.info("Embeddings: Using local Ollama for semantic embeddings.")
        return OpenAIEmbeddings(
            api_key="ollama",
            model=os.getenv("DEFAULT_OLLAMA_EMBEDDING_MODEL", "nomic-embed-text"),
            base_url=f"{ollama_base}/v1",
        )
    else:
        logger.warning(
            "No embedding provider available "
            "(OPENAI_API_KEY / OPENROUTER_API_KEY not set; Ollama not reachable). "
        )
        return None