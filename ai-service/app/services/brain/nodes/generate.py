import asyncio
import concurrent.futures
import logging

from uuid import UUID
from app.services.brain.state import BrainState
from app.services.llm import llm_service
from app.services.prompter import prompter
from app.services.memory_service import memory_service
from langchain_core.messages import AIMessage, HumanMessage

session_history_window = 9999

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
    history_model, memories, facts = await asyncio.gather(
        memory_service.get_history(conversation_id, session_history_window),
        memory_service.search(query=user_message, limit=3),
        memory_service.get_long_term_memories(identity=state.get("identity", "anonymous"), limit=5),
    )

    history = history_model

    # Save User message IMMEDIATELY to DB so it persists even if AI fails or disconnects
    await memory_service.add_interaction(
        conversation_id=conversation_id,
        user_text=user_message,
        assistant_text=None, # Update later
        user_emotion=detected_emotion,
        assistant_emotion=None
    )

    # System Prompt (Pulling from DB via settings_service)
    from app.services.settings_service import settings_service
    db_settings = settings_service.get_settings()
    custom_sys = (db_settings.get("system_prompt") or "").strip()
    
    from app.services.persona import persona_engine
    persona = custom_sys if custom_sys else persona_engine.get_persona()
    
    from datetime import datetime
    time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    system_content = (
        "You are AURA (Advanced Universal Responsive Avatar), "
        "the spirited AI steward of the ASE Lab.\n\n"
        f"{persona}\n\n"
        f"**Context:**\n- Current Time: {time_str}"
    )

    # Combine RAG (memories) and LTS (facts)
    combined_memory = ""
    if facts:
        combined_memory += f"\nWhat I know about you:\n{facts}\n"
    if memories:
        memory_block = "\n".join(f"- {message}" for message in memories)
        combined_memory += f"\nRelevant past snippets:\n{memory_block}\n"

    if combined_memory:
        system_content += f"\n\n**Memory Retrieval:**{combined_memory}"

    system_message = {"role": "system", "content": system_content}
    
    # Build payload
    messages_format = [system_message] + history + current_message

    # Check for stream request
    is_stream = state.get("stream", False)

    if is_stream:
        # For streaming, we yield chunks. 
        # But this is a node, so we return the final state but can use callbacks?
        # Actually, chat.py will call brain.astream().
        # We handle the stream here if we want to return the stream object, 
        # but LangGraph nodes should return the update.
        # So we update chat.py to use a different strategy.
        pass

    # Generate response from LLM
    response = await llm_service.generate(messages_format)
    text = response.get("text", "")
    emotion = response.get("emotion", "neutral")
    
    await asyncio.gather(
        # Complete the interaction in DB
        memory_service.add_interaction(
            conversation_id=conversation_id,
            user_text=user_message,
            assistant_text=text,
            user_emotion=detected_emotion,
            assistant_emotion=emotion
        ),

        memory_service.store(
            text=f"User: {user_message} \n AURA: {text}",
            metadata={"conversation_id": str(conversation_id)},
        ),
    )

    # Return response
    return {"messages": [AIMessage(content=text)], "emotion": emotion}