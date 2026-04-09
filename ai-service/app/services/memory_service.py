"""
Memory service using Supabase pgvector for semantic search.
Replaces the previous Qdrant-based implementation — zero Docker containers needed.
"""
from __future__ import annotations
from typing import List
import urllib.request
from supabase import create_client
from langchain_openai import OpenAIEmbeddings
from app.core.config import settings
from uuid import UUID


from app.models.database import (Conversation, CreateConversation, Message, CreateMesssage, Memory, CreateMemory)

import logging

logger = logging.getLogger(__name__)


def _ollama_is_running(base_url: str) -> bool:
    """Return True if an Ollama server is reachable at base_url."""
    try:
        urllib.request.urlopen(f"{base_url}/api/tags", timeout=2)
        return True
    except Exception:
        return False

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

        # Initialize embeddings — try providers in order of preference
        if settings.OPENAI_API_KEY:
            self.embeddings = OpenAIEmbeddings(
                api_key=settings.OPENAI_API_KEY,
                model="text-embedding-3-small",
            )
            logger.info("Embeddings: using OpenAI directly.")
        elif settings.OPENROUTER_API_KEY:
            self.embeddings = OpenAIEmbeddings(
                api_key=settings.OPENROUTER_API_KEY,
                model="openai/text-embedding-3-small",
                base_url="https://openrouter.ai/api/v1",
            )
            logger.info("Embeddings: using OpenRouter.")
        elif _ollama_is_running(settings.OLLAMA_BASE_URL):
            self.embeddings = OpenAIEmbeddings(
                api_key="ollama",
                model="nomic-embed-text",
                base_url=f"{settings.OLLAMA_BASE_URL}/v1",
            )
            logger.info("Embeddings: using local Ollama (nomic-embed-text).")
        else:
            logger.warning(
                "No embedding provider available "
                "(OPENAI_API_KEY / OPENROUTER_API_KEY not set; Ollama not reachable). "
                "Memory store/search disabled."
            )

    async def create_conversation(self, title: str = "New Conversation") -> UUID | None:
        if not self.client:
            return None
        
        try:
            result = self.client.table("conversations").insert(
                CreateConversation(title=title).model_dump()
            ).execute()

            if result.data:
                return UUID(result.data[0]["id"])
            else:
                return None
        
        except Exception as error:
            logger.error(f"Memory Service Create Conversation Error: {error}")
            return None
    
    async def get_conversation(self, conversation_id: UUID) -> Conversation | None:
        if not self.client:
            return None
        
        try:
            result = self.client.table("conversations") \
                .select("*") \
                .eq("id", str(conversation_id)) \
                .single() \
                .execute()
            
            if result.data:
                return Conversation(**result.data)
            else:
                return None
        
        except Exception as error:
            logger.error(f"Memory Service Get Conversation Error: {error}")
            return None
    
    async def add_interaction(self, conversation_id: UUID, user_text: str, assistant_text: str, user_emotion: str = "neutral", assistant_emotion: str = "neutral") -> None:
        if not self.client:
            return None

        try:
            self.client.table("messages").insert([
                CreateMesssage(
                    conversation_id=conversation_id,
                    role="user",
                    content=user_text,
                    emotion=user_emotion,
                ).model_dump(mode="json"),

                CreateMesssage(
                    conversation_id=conversation_id,
                    role="aura",
                    content=assistant_text,
                    emotion=assistant_emotion
                ).model_dump(mode="json")
            ]).execute() 

            self.client.table("conversations") \
                .update({"updated_at": "now()"}) \
                .eq("id", str(conversation_id)) \
                .execute()

        except Exception as error:
            logger.error(f"Memory Service Add Interaction Error: {error}")

    async def get_history(self, conversation_id: UUID, n: int = 30) -> List[Message]:
        if not self.client or n <= 0:
            return []     
        
        try:
            result = self.client.table("messages") \
                        .select("role, content, emotion, created_at") \
                        .eq("conversation_id", str(conversation_id)) \
                        .order("created_at", desc=True) \
                        .limit(n) \
                        .execute()
            
            rows = result.data or []
            rows.reverse()
            
            return [{"role": "assistant" if row["role"] == "aura" else row["role"], "content": row["content"]} for row in rows]
        
        except Exception as error:
            logger.error(f"Memory Service Get History Error : {error}")
            return []
    
    async def get_last_n_message(self, conversation_id: UUID, n: int) -> List[Message]:
        if not self.client or n <= 0:
            return []     
        
        try:
            result = self.client.table("messages") \
                .select("id, role, content, emotion, created_at") \
                .eq("conversation_id", str(conversation_id)) \
                .order("created_at", desc=True) \
                .limit(n) \
                .execute()

            rows = result.data or []
            rows.reverse()
            return rows
        
        except Exception as error:
            logger.error(f"Memory Service Get Last N Message Error: {error}")
            return []

    async def get_summary(self, conversation_id: UUID, n: int = 20) -> List[Message]:
        return await self.get_last_n_message(conversation_id, n)

    async def clear_conversation(self, conversation_id: UUID) -> None:
        if not self.client:
            return []

        try:
            self.client.table("messages") \
                .delete() \
                .eq("conversation_id", str(conversation_id)) \
                .execute()

            logger.info(f"Memory Service: Conversation {conversation_id} Cleared.")

        except Exception as error:
            logger.error(f"Memory Service Clear Conversation Error: {error}")           
            
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