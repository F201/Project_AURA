"""
Memory service using Supabase pgvector for semantic search.
Replaces the previous Qdrant-based implementation — zero Docker containers needed.
"""

from supabase import create_client
from langchain_openai import OpenAIEmbeddings
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


class MemoryService:
    def __init__(self):
        self.client = None
        self.embeddings = None

        # Initialize Supabase client
        if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_KEY:
            self.client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
            logger.info("Memory Service connected to Supabase")
        else:
            logger.warning("Supabase credentials not set. Memory service disabled.")

        # Initialize embeddings model via OpenRouter
        api_key = settings.OPENROUTER_API_KEY
        if api_key:
            self.embeddings = OpenAIEmbeddings(
                api_key=api_key,
                model="openai/text-embedding-3-small",
                base_url="https://openrouter.ai/api/v1"
            )
        else:
            logger.warning("OPENROUTER_API_KEY not set. Memory embedding disabled.")

    async def store(self, text: str, metadata: dict = None):
        """Embed and store a memory in Supabase pgvector."""
        if not self.client or not self.embeddings or not text.strip():
            return

        try:
            vector = await self.embeddings.aembed_query(text)

            self.client.table("memories").insert({
                "content": text,
                "embedding": vector,
                "metadata": metadata or {},
            }).execute()

            logger.info(f"Stored memory: {text[:40]}...")
        except Exception as e:
            logger.error(f"Memory store error: {e}")

    async def search(self, query: str, limit: int = 3) -> list[str]:
        """Retrieve relevant memories via cosine similarity."""
        if not self.client or not self.embeddings:
            return []

        try:
            vector = await self.embeddings.aembed_query(query)

            # Use Supabase RPC for pgvector similarity search
            result = self.client.rpc("match_memories", {
                "query_embedding": vector,
                "match_count": limit,
            }).execute()

            return [row["content"] for row in (result.data or [])]
        except Exception as e:
            logger.error(f"Memory search error: {e}")
            return []


memory_service = MemoryService()
