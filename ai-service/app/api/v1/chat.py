import json
import logging
import asyncio
from uuid import UUID
from fastapi import APIRouter, HTTPException, Depends, Security
from fastapi.responses import StreamingResponse
from fastapi.security.api_key import APIKeyHeader

from app.core.config import settings
from app.models.chat import ChatRequest, ChatResponse, PersistRequest
from langchain_core.messages import HumanMessage

from core.brain.graph import brain
from core.services.memory import memory_service

router = APIRouter()
logger = logging.getLogger(__name__)

api_key_header = APIKeyHeader(name="Authorization", auto_error=False)

async def verify_internal_api_key(api_key_header: str = Security(api_key_header)):
    if not settings.INTERNAL_API_KEY:
        logger.error("INTERNAL_API_KEY is not configured in settings")
        raise HTTPException(status_code=500, detail="Internal API key not configured")
    
    token = api_key_header.replace("Bearer ", "") if api_key_header else None
    if token != settings.INTERNAL_API_KEY:
        raise HTTPException(status_code=403, detail="Could not validate credentials")
    return token

@router.options("")
async def chat_options():
    from fastapi import Response
    return Response(status_code=200)

@router.get("")
async def chat_get():
    return {"message": "AURA Chat endpoint active"}

@router.post("")
async def chat(request: ChatRequest):
    try:
        conversation_id = request.conversation_id
        
        if not conversation_id:
            new_id = await memory_service.create_conversation()
            conversation_id = str(new_id) if new_id else "default"
        
        initial_state = {
            "messages": [HumanMessage(content=request.message)],
            "emotion": "neutral",
            "conversation_id": conversation_id,
            "identity": request.identity or "anonymous",
            "stream": request.stream,
            "mode": "text", 
        }

        config = {"configurable": {"thread_id": conversation_id}}

        result = await brain.ainvoke(initial_state, config=config)

        last_msg = result["messages"][-1].content
        emotion = result.get("emotion", "neutral")

        if request.stream:
            async def event_generator():
                yield f"data: {json.dumps({'text': last_msg, 'emotion': emotion})}\n\n"
                yield "data: [DONE]\n\n"
            return StreamingResponse(event_generator(), media_type="text/event-stream")
        
        tools_used = []
        for msg in result["messages"]:
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    tools_used.append({
                        "name": tc.get("name"),
                        "args": tc.get("args", {})
                    })
                    
        return ChatResponse(
            text=last_msg,
            emotion=emotion,
            conversation_id=conversation_id,
            tools_used=tools_used if tools_used else None
        )
    
    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        if request.stream:
             return StreamingResponse(
                  iter([f"data: {json.dumps({'text': f'Brain Freeze: {str(e)}', 'emotion': 'confused'})}\n\n"]),
                  media_type="text/event-stream"
             )

        return ChatResponse(
            text=f"Brain Freeze: {str(e)}",
            emotion="confused",
            conversation_id=request.conversation_id or "default",
        )

@router.post("/persist")
async def persist_chat(request: PersistRequest):
    conv_id = UUID(request.conversation_id)
    if request.messages:
        await memory_service.batch_add_messages(conv_id, [
            {"role": m.role, "content": m.content, "emotion": m.emotion} 
            for m in request.messages
        ])

    return {
        "status": "success", 
        "messages_persisted": len(request.messages) if request.messages else 0,
        "extraction_triggered": True
    }

@router.post("/voice", dependencies=[Depends(verify_internal_api_key)])
async def chat_voice(request: ChatRequest):
    try:
        conversation_id = request.conversation_id
        if not conversation_id:
            new_id = await memory_service.create_conversation(title=f"Voice Session: {request.identity or 'anonymous'}")
            conversation_id = str(new_id) if new_id else "default"

        initial_state = {
            "messages": [HumanMessage(content=request.message)],
            "emotion": "neutral",
            "conversation_id": conversation_id,
            "identity": request.identity or "anonymous",
            "stream": True,
            "mode": "voice", 
        }
        
        config = {"configurable": {"thread_id": conversation_id}}

        result = await brain.ainvoke(initial_state, config=config)

        last_msg = result["messages"][-1].content
        emotion = result.get("emotion", "neutral")
        
        async def voice_event_generator():
            yield f"data: {json.dumps({'text': last_msg, 'emotion': emotion})}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(voice_event_generator(), media_type="text/event-stream")

    except Exception as e:
        logger.error(f"Voice Chat error: {e}", exc_info=True)
        return StreamingResponse(
            iter([f"data: {json.dumps({'text': f'[sad] Brain Freeze: {str(e)}', 'emotion': 'sad'})}\n\n"]),
            media_type="text/event-stream"
        )