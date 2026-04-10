from __future__ import annotations
from typing import List, Optional
from uuid import UUID
from supabase import create_client, Client
from database import (Conversation, CreateConversation, Message, CreateMesssage, Memory, CreateMemory)

import asyncio
import os
import logging

logger = logging.getLogger("aura")
logger.setLevel(logging.INFO)

# get database connection
def get_client() -> Client | None:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")

    if not url or not key:
        logger.warning("Memory Service URL or Service Key not found in environment")
        return None

    try:
        return create_client(url, key)
    except Exception as e:
        logger.error(f"Failed to create Supabase client: {e}")
        return None

class MemoryService:
    def __init__(self):
        self.client: Client = get_client()
        self.conversation_id: Optional[UUID] = None

    # run query asynchronously
    async def _run(self, fn):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, fn)

    # Create conversation in the database
    async def create_conversation(self, title: str = "New Conversation") -> UUID | None:
        if not self.client:
            return None
        try:
            result = await self._run(
                lambda: self.client.table("conversations").insert(
                    CreateConversation(title=title).model_dump()
                ).execute()
            )
            if result.data:
                return UUID(result.data[0]["id"])
            
        except Exception as error:
            logger.error(f"Memory Service Create Conversation Error: {error}")

        return None

    # Check the last conversation in memory table by user identity if not found, create new conversation
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
                    lambda cid=conversation_id: self.client.table("conversations")
                        .select("id")
                        .eq("id", str(cid))
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
                lambda nid=new_id: self.client.table("memories").insert(
                    CreateMemory(
                        content=str(nid),
                        metadata={"type": "session_pointer", "identity": identity}
                    ).model_dump()
                ).execute()
            )

            logger.info(f"Memory: New conversation {new_id} created for {identity}")
            return new_id

        except Exception as error:
            logger.error(f"Memory Service Get or Create Conversation Error: {error}")
        return None

    # Get conversation from the database
    async def get_conversation(self, conversation_id: UUID) -> Conversation | None:
        if not self.client:
            return None
        
        try:
            result = await self._run(
                lambda: self.client.table("conversations")
                    .select("*")
                    .eq("id", str(conversation_id))
                    .single()
                    .execute()
            )

            if result.data:
                return Conversation(**result.data)
            
        except Exception as error:
            logger.error(f"Memory Service Get Conversation Error: {error}")

        return None

    # Insert user and AI messages to the messages table
    async def add_interaction(self, conversation_id: UUID, user_text: str, assistant_text: str | None, user_emotion: str = "neutral", assistant_emotion: str = "neutral") -> None:
        if not self.client:
            return
        try:
            msgs = []
            if user_text:
                msgs.append(CreateMesssage(
                    conversation_id=conversation_id,
                    role="user",
                    content=user_text,
                    emotion=user_emotion,
                ).model_dump(mode="json"))

            if assistant_text:
                msgs.append(CreateMesssage(
                    conversation_id=conversation_id,
                    role="aura",
                    content=assistant_text,
                    emotion=assistant_emotion
                ).model_dump(mode="json"))
            
            if msgs:
                await self._run(
                    lambda: self.client.table("messages").insert(msgs).execute()
                )

            await self._run(
                lambda: self.client.table("conversations")
                    .update({"updated_at": "now()"})
                    .eq("id", str(conversation_id))
                    .execute()
            )

        except Exception as error:
            logger.error(f"Memory Service Add Interaction Error: {error}")

    # get conversation history from the table 
    async def get_history(self, conversation_id: UUID, n: int = 50) -> List[dict]:
        if not self.client or n <= 0:
            return []
        try:
            result = await self._run(
                lambda: self.client.table("messages")
                    .select("role, content, emotion, created_at")
                    .eq("conversation_id", str(conversation_id))
                    .order("created_at", desc=True)
                    .limit(n)
                    .execute()
            )

            rows = result.data or []
            rows.reverse()

            return [
                {
                    "role": "assistant" if row["role"] == "aura" else row["role"],
                    "content": row["content"],
                }
                for row in rows
            ]
        
        except Exception as error:
            logger.error(f"Memory Service Get History Error: {error}")

        return []

    # get last n message from the message table
    async def get_last_n_message(self, conversation_id: UUID, n: int) -> List[dict]:
        if not self.client or n <= 0:
            return []
        
        try:
            result = await self._run(
                lambda: self.client.table("messages")
                    .select("id, role, content, emotion, created_at")
                    .eq("conversation_id", str(conversation_id))
                    .order("created_at", desc=True)
                    .limit(n)
                    .execute()
            )

            rows = result.data or []
            rows.reverse()
            return rows
        
        except Exception as error:
            logger.error(f"Memory Service Get Last N Message Error: {error}")

        return []

    # Make summary for the last n message
    async def get_summary(self, conversation_id: UUID, n: int = 20) -> List[dict]:
        return await self.get_last_n_message(conversation_id, n)

    # Clear the conversation history
    async def clear_conversation(self, conversation_id: UUID) -> None:
        if not self.client:
            return
        
        try:
            await self._run(
                lambda: self.client.table("messages")
                    .delete()
                    .eq("conversation_id", str(conversation_id))
                    .execute()
            )
            logger.info(f"Memory Service: Conversation {conversation_id} Cleared.")

        except Exception as error:
            logger.error(f"Memory Service Clear Conversation Error: {error}")

    # Save LLM Extraction to memory table after session
    async def save_long_term_memory(self, identity: str, facts: str) -> None:
        if not self.client or not facts.strip():
            return
        
        try:
            await self._run(
                lambda: self.client.table("memories").insert(
                    CreateMemory(
                        content=facts.strip(),
                        metadata={"type": "user_facts", "identity": identity}
                    ).model_dump()
                ).execute()
            )
            logger.info(f"Long-term memory saved for '{identity}'")

        except Exception as error:
            logger.error(f"Memory Service Save Long Term Memory Error: {error}")

    # Get the LLM extraction from memory table
    async def get_long_term_memories(self, identity: str, limit: int = 10) -> str:
        if not self.client:
            return ""
        
        try:
            result = await self._run(
                lambda: self.client.table("memories")
                    .select("content, created_at")
                    .eq("metadata->>type", "user_facts")
                    .eq("metadata->>identity", identity)
                    .order("created_at", desc=True)
                    .limit(limit)
                    .execute()
            )

            rows = result.data or []
            if not rows:
                return ""

            facts_list = [row["content"] for row in reversed(rows)]
            return "\n---\n".join(facts_list)

        except Exception as error:
            logger.error(f"Memory Service Get Long Term Memories Error: {error}")
        return ""

    # Get the personality settings from the personality_settings table
    async def get_personality_settings(self) -> dict | None:
        if not self.client:
            return None
        try:
            result = await self._run(
                lambda: self.client.table("personality_settings")
                    .select("*")
                    .eq("id", 1)
                    .single()
                    .execute()
            )
            if result.data:
                return result.data
        except Exception as error:
            logger.error(f"Memory Service Get Personality Settings Error: {error}")
        return None

memory_service = MemoryService()