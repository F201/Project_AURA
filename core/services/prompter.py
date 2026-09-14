import os
from datetime import datetime
from typing import List

from core.services.settings import settings_service

MEMORY_EXTRACTION_PROMPT = """\
You are a memory extraction assistant. Given a conversation between a user and AURA (an AI companion), extract important facts about the USER ONLY.
"""

class Prompter:
    def __init__(self):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        core_dir = os.path.dirname(current_dir)
        prompt_path = os.path.join(core_dir, "prompts", "system_prompt.md")

        self.base_persona = ""
        
        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                self.base_persona = f.read()
        except FileNotFoundError:
            print(f"Persona Not Found at: {prompt_path}")

    async def build_system_prompt(self, mode: str = "text", facts: str = "", memories: List[str] = None) -> str:
        if memories is None:
            memories = []

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        db = await settings_service.get_settings()
        custom_sys = (db.get("system_prompt") or "").strip()
        
        active_persona = custom_sys if custom_sys else self.base_persona

        modality_instructions = ""
        if mode == "voice":
            modality_instructions = "[MODALITY: VOICE]\nUse tags in brackets `[tag1, tag2]` organically to punctuate emotional transitions. Keep it under 3 items per bracket. Use your FULL emotion palette (e.g., [happy], [angry, smile, smile], [ghost])."
        else:
            modality_instructions = "[MODALITY: TEXT]\nConverse naturally. You may use standard text expressions. Do not spam 3D expression tags."

        system_content = f"{active_persona}\n\n{modality_instructions}\n\n**Context:**\n- Current Time: {current_time}"

        system_content += (
            "\n\n[STRICT MEMORY USAGE RULES]\n"
            "- Use facts ONLY to personalize the conversation organically.\n"
            "- NEVER mention that you are 'reading facts' or 'accessing memory banks'.\n"
        )

        combined_memory = ""
        if facts:
            combined_memory += f"\n[LONG-TERM MEMORY (FACTS)]\n{facts}\n"
        
        if memories and isinstance(memories, list) and memories:
            memory_block = "\n".join(f"- {message}" for message in memories)
            combined_memory += f"\n[RELEVANT PAST CONTEXT]\n{memory_block}\n"

        if combined_memory:
            system_content += f"\n\n**Memory Retrieval:**\n{combined_memory}"

        return system_content

    def build_extraction_prompt(self, chat_text: str) -> List[dict]:
        return [
            {"role": "system", "content": MEMORY_EXTRACTION_PROMPT},
            {"role": "user", "content": f"Conversation:\n{chat_text}"},
        ]

prompter = Prompter()