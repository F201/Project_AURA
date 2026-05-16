"""
Memory service using Supabase pgvector for semantic search.
Replaces the previous Qdrant-based implementation — zero Docker containers needed.
"""
from __future__ import annotations
from typing import List
import urllib.request
from supabase import create_client

from app.core.config import settings
from uuid import UUID
from datetime import datetime


from app.models.database import (Conversation, CreateConversation, Message, CreateMessage, Memory, CreateMemory)

import logging

logger = logging.getLogger(__name__)


def _ollama_is_running(base_url: str) -> bool:
    """Return True if an Ollama server is reachable at base_url."""
    try:
        urllib.request.urlopen(f"{base_url}/api/tags", timeout=2)
        return True
    except Exception:
        return False

from app.services.embeddings import get_embeddings

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

        # Initialize embeddings using centralized factory
        self.embeddings = get_embeddings()
        if not self.embeddings:
            logger.warning("Memory store/search disabled due to lack of embeddings.")

    async def _run(self, fn):
        import asyncio
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, fn)

    async def create_conversation(self, title: str = "New Conversation") -> UUID | None:
        if not self.client:
            return None
        
        try:
            result = await self._run(lambda: self.client.table("conversations").insert(
                CreateConversation(title=title).model_dump()
            ).execute())

            if result.data:
                return UUID(result.data[0]["id"])
            else:
                return None
        
        except Exception as error:
            logger.error(f"Memory Service Create Conversation Error: {error}")
            return None

    async def get_or_create_conversation(self, identity: str, title: str = "Voice Session") -> UUID | None:
        if not self.client:
            return None
        try:
            result = await self._run(
                lambda: self.client.table("memories")
                    .select("content, created_at")
                    .eq("metadata->>type", "session_pointer")
                    .eq("metadata->>identity", identity)
                    .order("created_at", desc=True)
                    .limit(1)
                    .execute()
            )

            if result.data:
                conversation_id = UUID(result.data[0]["content"])
                check = await self._run(
                    lambda: self.client.table("conversations")
                        .select("id")
                        .eq("id", str(conversation_id))
                        .limit(1)
                        .execute()
                )

                if check.data:
                    logger.info(f"Memory: Resuming conversation {conversation_id} for {identity}")
                    return conversation_id
                
                logger.warning(f"Memory: Conversation {conversation_id} missing, creating new one.")

            new_id = await self.create_conversation(title=f"{title}: {identity}")
            if not new_id:
                return None

            await self._run(
                lambda: self.client.table("memories").insert(
                    CreateMemory(
                        content=str(new_id),
                        metadata={"type": "session_pointer", "identity": identity}
                    ).model_dump()
                ).execute()
            )

            logger.info(f"Memory: New conversation {new_id} created for {identity}")
            return new_id

        except Exception as error:
            logger.error(f"Memory Service Get or Create Conversation Error: {error}")
        return None
    
    async def get_conversation(self, conversation_id: UUID) -> Conversation | None:
        if not self.client:
            return None
        
        try:
            result = await self._run(lambda: self.client.table("conversations") \
                .select("*") \
                .eq("id", str(conversation_id)) \
                .single() \
                .execute())
            
            if result.data:
                return Conversation(**result.data)
            else:
                return None
        
        except Exception as error:
            logger.error(f"Memory Service Get Conversation Error: {error}")
            return None
    
    async def add_interaction(self, conversation_id: UUID, user_text: str, assistant_text: str | None, user_emotion: str = "neutral", assistant_emotion: str = "neutral") -> None:
        if not self.client:
            return None

        try:
            msgs = []
            if user_text:
                msgs.append(CreateMessage(
                    conversation_id=conversation_id,
                    role="user",
                    content=user_text,
                    emotion=user_emotion,
                ).model_dump(mode="json"))

            if assistant_text:
                msgs.append(CreateMessage(
                    conversation_id=conversation_id,
                    role="aura",
                    content=assistant_text,
                    emotion=assistant_emotion
                ).model_dump(mode="json"))
            
            if msgs:
                await self._run(lambda: self.client.table("messages").insert(msgs).execute())

            await self._run(lambda: self.client.table("conversations") \
                .update({"updated_at": "now()"}) \
                .eq("id", str(conversation_id)) \
                .execute())

        except Exception as error:
            logger.error(f"Memory Service Add Interaction Error: {error}")

    async def batch_add_messages(self, conversation_id: UUID, messages: list[dict]) -> None:
        """
        messages list format: [{"role": "user"|"aura", "content": str, "emotion": str}]
        """
        if not self.client or not messages:
            return

        try:
            to_insert = []
            for m in messages:
                role = m["role"]
                if role == "assistant":
                    role = "aura"
                
                to_insert.append(CreateMessage(
                    conversation_id=conversation_id,
                    role=role,
                    content=m["content"],
                    emotion=m.get("emotion", "neutral")
                ).model_dump(mode="json"))

            if to_insert:
                await self._run(lambda: self.client.table("messages").insert(to_insert).execute())

            await self._run(lambda: self.client.table("conversations") \
                .update({"updated_at": "now()"}) \
                .eq("id", str(conversation_id)) \
                .execute())

            logger.info(f"Persisted {len(to_insert)} messages for conversation {conversation_id}")

        except Exception as error:
            logger.error(f"Memory Service Batch Add Messages Error: {error}")

    async def get_history(self, conversation_id: UUID, n: int = 30) -> List[dict]:
        if not self.client or n <= 0:
            return []     
        
        try:
            result = await self._run(lambda: self.client.table("messages") \
                        .select("role, content, emotion, created_at") \
                        .eq("conversation_id", str(conversation_id)) \
                        .order("created_at", desc=True) \
                        .limit(n) \
                        .execute())
            
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
            result = await self._run(lambda: self.client.table("messages") \
                .select("id, role, content, emotion, created_at") \
                .eq("conversation_id", str(conversation_id)) \
                .order("created_at", desc=True) \
                .limit(n) \
                .execute())

            rows = result.data or []
            rows.reverse()
            return [Message(**row) for row in rows]
        
        except Exception as error:
            logger.error(f"Memory Service Get Last N Message Error: {error}")
            return []

    async def get_summary(self, conversation_id: UUID, n: int = 20) -> List[Message]:
        return await self.get_last_n_message(conversation_id, n)

    async def clear_conversation(self, conversation_id: UUID) -> None:
        if not self.client:
            return []

        try:
            await self._run(lambda: self.client.table("messages") \
                .delete() \
                .eq("conversation_id", str(conversation_id)) \
                .execute())

            logger.info(f"Memory Service: Conversation {conversation_id} Cleared.")

        except Exception as error:
            logger.error(f"Memory Service Clear Conversation Error: {error}")           
            
    async def store(self, text: str, metadata: dict = None):
        """Embed and store a memory in Supabase pgvector."""
        if not self.client or not self.embeddings or not text.strip():
            return

        try:
            vector = await self.embeddings.aembed_query(text)

            await self._run(lambda: self.client.table("memories").insert({
                "content": text,
                "embedding": vector,
                "metadata": metadata or {},
            }).execute())

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
            result = await self._run(lambda: self.client.rpc("match_memories", {
                "query_embedding": vector,
                "match_count": limit,
            }).execute())

            return [row["content"] for row in (result.data or [])]
        except Exception as e:
            logger.error(f"Memory search error: {e}")
            return []


    async def get_long_term_memories(self, identity: str, limit: int = 10) -> str:
        """Retrieve the last N non-embedded 'user_facts' memories for this identity."""
        if not self.client:
            return ""

        try:
            result = await self._run(lambda: self.client.table("memories") \
                .select("content, created_at") \
                .eq("metadata->>type", "user_facts") \
                .eq("metadata->>identity", identity) \
                .order("created_at", desc=True) \
                .limit(limit) \
                .execute())

            rows = result.data or []
            if not rows:
                return ""

            # Reverse to get chronological order in the prompt
            facts_list = [row["content"] for row in reversed(rows)]
            return "\n---\n".join(facts_list)

        except Exception as e:
            logger.error(f"Memory Service Get Long Term Memories error: {e}")
            return ""

    async def save_long_term_memory(self, identity: str, facts: str, conversation_id: str | None = None) -> None:
        """Save a new user_facts entry for the identity."""
        if not self.client or not facts.strip():
            return
        
        try:
            metadata = {"type": "user_facts", "identity": identity}
            if conversation_id:
                metadata["conversation_id"] = str(conversation_id)

            await self._run(lambda: self.client.table("memories").insert(
                CreateMemory(
                    content=facts.strip(),
                    metadata=metadata
                ).model_dump()
            ).execute())
            logger.info(f"Long-term memory saved for '{identity}'")
        except Exception as error:
            logger.error(f"Memory Service Save Long Term Memory Error: {error}")



memory_service = MemoryService()