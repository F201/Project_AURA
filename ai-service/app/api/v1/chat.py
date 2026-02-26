from fastapi import APIRouter
from app.models.chat import ChatRequest, ChatResponse
from app.services.brain.graph import brain
from langchain_core.messages import HumanMessage, AIMessage

router = APIRouter(prefix="/chat")

@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest):
    
    # Convert history dicts to LangChain messages
    history = []
    for msg in request.history or []:
        if msg['role'] == 'user':
            history.append(HumanMessage(content=msg['content']))
        else:
            history.append(AIMessage(content=msg['content']))
            
    # Add current message
    history.append(HumanMessage(content=request.message))
    
    # Run Graph
    try:
        initial_state = {"messages": history, "emotion": "neutral"}
        config = {"configurable": {"thread_id": request.session_id or "default"}}
        result = brain.invoke(initial_state, config=config)
        
        # Extract response
        last_msg = result["messages"][-1].content
        emotion = result.get("emotion", "neutral")
        
        # Clean tags
        text = last_msg
        if text.startswith("["):
             import re
             match = re.match(r'^\[(.*?)\]', text)
             if match:
                 text = text[match.end():].strip()

        # Return response
        return ChatResponse(
            text=text,
            emotion=emotion
        )
    
    except Exception as e:
        return ChatResponse(
             text=f"Brain Freeze: {str(e)}",
             emotion="dizzy"
        )

