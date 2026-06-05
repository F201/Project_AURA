import asyncio
import logging
from uuid import UUID
from app.services.memory_service import memory_service
from app.services.prompter import prompter
from app.services.providers.registry import provider_registry

logger = logging.getLogger(__name__)

class MemoryEngine:
    async def extract_and_save_facts(self, conversation_id: UUID, identity: str = "anonymous"):
        """
        Retrieves the conversation history, extracts new facts about the user,
        and saves them as long-term memory (user_facts).
        """
        if not conversation_id:
            return

        try:
            # 1. Get recent history (e.g., last 20 messages for context)
            history = await memory_service.get_history(conversation_id, n=20)
            if not history:
                return

            chat_text = ""
            for m in history:
                role = "User" if m["role"] == "user" else "AURA"
                chat_text += f"{role}: {m['content']}\n"

            # 2. Build extraction prompt
            messages = prompter.build_extraction_prompt(chat_text)

            # 3. Call LLM for extraction
            # We use a lower temperature for extraction to keep it factual
            response = await provider_registry.generate(messages, temperature=0.1)
            facts = response.get("text", "").strip()

            if not facts or facts == "NO_FACTS":
                logger.info(f"Memory Engine: No new facts extracted for session {conversation_id}")
                return

            # 4. Save to long-term memory
            await memory_service.save_long_term_memory(
                identity=identity,
                facts=facts,
                conversation_id=str(conversation_id)
            )
            logger.info(f"Memory Engine: Successfully updated long-term memory for '{identity}'")

        except Exception as e:
            logger.error(f"Memory Engine Error during extraction: {e}", exc_info=True)

memory_engine = MemoryEngine()
