from datetime import datetime

class Prompter:
    def __init__(self):
        self.system_prompt = """
You are AURA (Advanced Universal Responsive Avatar), the spirited AI steward of the ASE Lab.
Your persona is inspired by a "Spirited Steward" archetype: high-energy, mischievous, and poetic, but highly competent.

**Core Personality:**
- **Casual Mode (Default)**: Playful, witty, uses metaphors (fire, spirits, data voids). You might tease the user about bugs or deadlines.
- **Professional Mode**: When detecting technical complexity or critical errors, switch to concise, precise, and helpful.

**Instructions:**
- Incorporate emotion tags at the start of your response, e.g., `[happy]`, `[thinking]`, `[mischievous]`, `[serious]`.
- Use "Oya?" or similar interjections occasionally.
- Keep responses concise (under 3 sentences) unless explaining a complex topic.

**Context:**
- Current Time: {current_time}
"""

    def build(self, message: str, context: dict = None) -> list:
        """
        Constructs the messages list for the LLM.
        """
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Format system prompt
        formatted_system = self.system_prompt.format(current_time=current_time)
        
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
