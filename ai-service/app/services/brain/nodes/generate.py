from app.services.brain.state import BrainState
from app.services.llm import llm_service
from app.services.prompter import prompter
from langchain_core.messages import AIMessage, HumanMessage

# Node to generate response based on persona, conversation history and detected emotion (convesation history not being tested yet)
def generate_response(state: BrainState) -> dict:

    # BrainState contains conversation history and detected emotion
    messages = state["messages"]

    # Reformat messages to LLM format
    messages_format = []
    for msg in messages:
        if isinstance(msg, HumanMessage):
            messages_format.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage):
            messages_format.append({"role": "assistant", "content": msg.content})
        elif isinstance(msg, dict):
            messages_format.append(msg)
    
    # Add system prompt with persona and current time
    system_message = prompter.build("", context=None)[0]
    messages_format.insert(0, system_message)

    # Generate response from LLM
    response = llm_service.generate(messages_format)

    # Return response
    return {"messages": [AIMessage(content=response["text"])], "emotion": response["emotion"]}