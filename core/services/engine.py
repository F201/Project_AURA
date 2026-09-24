import asyncio
import logging
from uuid import UUID

from core.services.memory import memory_service
from core.services.prompter import prompter
from core.services.llm import llm_service

logger = logging.getLogger(__name__)

class MemoryEngine:
    async def extract_and_save_facts(self, conversation_id: UUID, identity: str = "anonymous"):
        if not conversation_id:
            return

        try:
            history = await memory_service.get_history(conversation_id, n=20)
            if not history:
                return

            chat_text = ""
            for m in history:
                role = "User" if m["role"] == "user" else "AURA"
                chat_text += f"{role}: {m['content']}\n"

            messages = prompter.build_extraction_prompt(chat_text)

            response = await asyncio.to_thread(llm_service.generate, messages)
            facts = response.get("text", "").strip()

            if not facts or facts == "NO_FACTS":
                logger.info(f"Memory Engine: No new facts extracted for session {conversation_id}")
                return

            await memory_service.save_long_term_memory(
                identity=identity,
                facts=facts,
                conversation_id=str(conversation_id)
            )
            logger.info(f"Memory Engine: Successfully updated long-term memory for '{identity}'")

        except Exception as e:
            logger.error(f"Memory Engine Error during extraction: {e}", exc_info=True)

memory_engine = MemoryEngine()