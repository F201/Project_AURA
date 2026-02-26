from datetime import datetime
from app.services.persona import persona_engine

class Prompter:
    def __init__(self):
        self.system_prompt = """
                                You are AURA (Advanced Universal Responsive Avatar), the spirited AI steward of the ASE Lab.

                                {persona}

                                **Context:**
                                - Current Time: {current_time}
                            """

    def build(self, message: str, context: dict = None) -> list:
        """
        Constructs the messages list for the LLM.
        """
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        persona = persona_engine.get_persona()
        
        # Format system prompt
        formatted_system = self.system_prompt.format(
            current_time=current_time, 
            persona=persona
        )
        
        messages = [
            {"role": "system", "content": formatted_system}
        ]
        
        # Add conversation history if available in context
        if context and "history" in context:
            messages.extend(context["history"])
            
        # Add current user message
        messages.append({"role": "user", "content": message})
        
        return messages

prompter = Prompter()

