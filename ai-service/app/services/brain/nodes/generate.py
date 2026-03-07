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

def generate_response(state: BrainState) -> dict:
    with concurrent.futures.ThreadPoolExecutor() as pool:
        future = pool.submit(asyncio.run, generate(state))
        return future.result()


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

    # Load History
    history_model, memories = await asyncio.gather(
        memory_service.get_history(conversation_id, session_history_window),
        memory_service.search(query=user_message, limit=3),
    )

    history = history_model

    # System Prompt
    system_message = prompter.build("", context=None)[0]

    if memories:
        memory_block = "\n".join(f"-{message}" for message in memories)
        system_message = {
            "role" : "system",
            "content": (system_message["content"] + f"Ingatan sebelumnya: \n {memory_block}")
        }
    
    
    # Add system prompt with persona and current time
    messages_format = [system_message] + history + current_message

    # Generate response from LLM
    response = llm_service.generate(messages_format)
    emotion = response.get("emotion", "neutral")
    
    await asyncio.gather(
        memory_service.add_interaction(
            conversation_id=conversation_id,
            user_text=user_message,
            assistant_text=response["text"],
            user_emotion=detected_emotion,
            assistant_emotion=emotion
        ),

        memory_service.store(
            text=f"User: {user_message} \n AURA: {response['text']}",
            metadata={"conversation_id": str(conversation_id)},
        ),
    )

    # Return response
    return {"messages": [AIMessage(content=response["text"])], "emotion": response["emotion"]}