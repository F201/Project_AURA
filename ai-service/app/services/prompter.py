from datetime import datetime
from app.services.persona import persona_engine
from app.services.settings_service import settings_service


class Prompter:
    def build(self, message: str, context: dict = None) -> list:
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Pull live settings — custom system_prompt overrides the hardcoded persona
        db_settings = settings_service.get_settings()
        custom_prompt = (db_settings.get("system_prompt") or "").strip()
        persona = custom_prompt if custom_prompt else persona_engine.get_persona()

        formatted_system = (
            f"You are AURA (Advanced Universal Responsive Avatar), the spirited AI steward of the ASE Lab.\n\n"
            f"{persona}\n\n"
            f"**Context:**\n- Current Time: {current_time}"
        )

        messages = [{"role": "system", "content": formatted_system}]

        if context and "history" in context:
            messages.extend(context["history"])

        messages.append({"role": "user", "content": message})
        return messages


prompter = Prompter()
