import asyncio
import logging

from uuid import UUID
from app.services.brain.state import BrainState
from app.services.providers.registry import provider_registry
from app.services.prompter import prompter
from app.services.memory_service import memory_service
from langchain_core.messages import AIMessage, HumanMessage

session_history_window = 50

async def generate_response(state: BrainState) -> dict:
    """Async wrapper for the generation node."""
    return await generate(state)


# Node to generate response based on persona, conversation history and detected emotion (convesation history not being tested yet)
async def generate(state: BrainState) -> dict:

    # BrainState contains conversation history and detected emotion
    messages = state["messages"]
    detected_emotion = state.get("emotion", "neutral")
    raw_id = state.get("conversation_id") or ""

    if not raw_id or raw_id == "default":
        raise ValueError("BrainState missing valid conversation_id")
    
    conversation_id = UUID(raw_id)
    
    # Reformat messages to LLM format
    current_message = []
    for msg in messages:
        if isinstance(msg, HumanMessage):
            current_message.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage):
            current_message.append({"role": "assistant", "content": msg.content})
        elif isinstance(msg, dict):
            current_message.append(msg)
    
    if current_message:
        user_message = current_message[-1]["content"]
    else:
        user_message = ""

    # Load History & Long-term memories
    history_model, facts = await asyncio.gather(
        memory_service.get_history(conversation_id, session_history_window),
        memory_service.get_long_term_memories(identity=state.get("identity", "anonymous"), limit=5),
    )

    history = history_model

    system_content = await prompter.build_system_prompt(
        mode="text",
        facts=facts,
        memories=[]
    )

    system_message = {"role": "system", "content": system_content}
    
    # Build payload
    messages_format = [system_message] + history + current_message



    # Generate response from LLM
    response = await provider_registry.generate(messages_format)
    text = response.get("text", "")
    emotion = response.get("emotion", "neutral")
    
    # Complete the interaction in DB
    await memory_service.add_interaction(
        conversation_id=conversation_id,
        user_text=user_message,
        assistant_text=text,
        user_emotion=detected_emotion,
        assistant_emotion=emotion
    )

    # Return response
    return {"messages": [AIMessage(content=text)], "emotion": emotion}