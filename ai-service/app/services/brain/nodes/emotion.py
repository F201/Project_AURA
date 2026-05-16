from app.services.brain.state import BrainState
from app.services.providers.registry import provider_registry

# Node to detect emotion 
async def detect_emotion(state: BrainState) -> dict:
    # Get last user message
    last_message = state["messages"][-1].content 
   
    # Prompt LLM to detect emotion
    prompt = f"""
            Analyze emotion in this message: "{last_message}"
            Respond with only the emotion in square brackets : [happy], [sad], [confused], [excited], [dizzy], [serious].
    """
    
    # Call LLM to detect emotion
    response = await provider_registry.generate([{"role": "system", "content": prompt}])

    # Return detected emotion
    return {"emotion": response.get("emotion", "neutral").strip().lower()}