import json
import logging
import asyncio
from fastapi import APIRouter, HTTPException, Depends, Security
from fastapi.responses import StreamingResponse
from fastapi.security.api_key import APIKeyHeader
import re

from app.core.config import settings
from app.services.memory_service import memory_service
from app.models.chat import ChatRequest, ChatResponse, PersistRequest
from app.services.memory_service import memory_service
from app.services.brain.graph import brain
from langchain_core.messages import HumanMessage, AIMessage
from app.services.prompter import prompter
from app.services.providers.registry import provider_registry
from app.services.brain.nodes.generate import session_history_window
from app.services.providers.base import TextDelta, StreamDone
from uuid import UUID
from datetime import datetime

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
    # Run Graph
    try:
        conversation_id = request.conversation_id
        
        if not conversation_id:
            new_id = await memory_service.create_conversation()
            conversation_id = str(new_id) if new_id else "default"
        
        initial_state = {
            "messages":   [HumanMessage(content=request.message)],
            "emotion":    "neutral",
            "conversation_id": conversation_id,
            "identity": request.identity or "anonymous",
            "stream": request.stream
        }

        config = {"configurable": {"thread_id": conversation_id}}

        if request.stream:
            async def event_generator():
                # 2. Setup the full context for generation
                from app.services.brain.nodes.generate import session_history_window
                from app.services.providers.registry import provider_registry
                from app.services.persona import persona_engine
                from app.services.settings_service import settings_service
                from datetime import datetime
                from uuid import UUID

                # Fetch context
                user_msg = request.message
                
                history_model, facts = await asyncio.gather(
                    memory_service.get_history(UUID(conversation_id), session_history_window),
                    memory_service.get_long_term_memories(identity=request.identity or "anonymous", limit=5),
                )
                
                system_content = await prompter.build_system_prompt(mode="text", facts=facts, memories=[])

                messages_format = [{"role":"system", "content":system_content}] + history_model + [{"role":"user", "content":user_msg}]

                full_text = ""
                scrubbed_final = ""
                detected_emotion = "neutral"

                # 3. Stream from the registry directly
                async for chunk in provider_registry.stream(messages_format):
                    # Only yield incremental deltas to the dashboard
                    if isinstance(chunk, TextDelta):
                        txt = chunk.text
                        full_text += txt
                        yield f"data: {json.dumps({'text': txt})}\n\n"
                    elif isinstance(chunk, StreamDone):
                        # Use the parsed results from the provider
                        scrubbed_final = chunk.text
                        detected_emotion = chunk.emotion

                # 4. Final sync/persistence
                if not scrubbed_final:
                    # Fallback if StreamDone wasn't caught correctly
                    from app.services.providers.base import parse_emotion
                    detected_emotion, scrubbed_final = parse_emotion(full_text)

                asyncio.create_task(memory_service.add_interaction(
                    conversation_id=UUID(conversation_id),
                    user_text=user_msg,
                    assistant_text=scrubbed_final,
                    user_emotion="neutral",
                    assistant_emotion=detected_emotion
                ))

                yield "data: [DONE]\n\n"

            return StreamingResponse(event_generator(), media_type="text/event-stream")

        # Non-streaming fallback
        result = await brain.ainvoke(initial_state, config=config)
        
        # Extract response
        last_msg = result["messages"][-1].content
        emotion = result.get("emotion", "neutral")
        
        # Look for tool calls
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
        # If it was a stream request, we should yield an error event
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
    """
    Persist multiple messages from a session at once to the database.
    """
    from uuid import UUID
    conv_id = UUID(request.conversation_id)

    # 1. Persist messages if provided
    if request.messages:
        await memory_service.batch_add_messages(conv_id, [
            {"role": m.role, "content": m.content, "emotion": m.emotion} 
            for m in request.messages
        ])

    # 2. Extract facts from the conversation (uses existing DB history)
    from app.services.memory_engine import memory_engine
    asyncio.create_task(memory_engine.extract_and_save_facts(
        conversation_id=conv_id,
        identity=request.identity or "anonymous"
    ))

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
            new_id = await memory_service.create_conversation()
            conversation_id = str(new_id) if new_id else "default"

        async def voice_event_generator():
            user_msg = request.message
            history_model, facts = await asyncio.gather(
                memory_service.get_history(UUID(conversation_id), session_history_window),
                memory_service.get_long_term_memories(identity=request.identity or "anonymous", limit=5),
            )

            history_dicts = [{"role": m["role"], "content": m["content"]} for m in history_model]
            system_content = await prompter.build_system_prompt(mode="voice", facts=facts, memories=[])
            messages_format = [{"role":"system", "content":system_content}] + history_dicts + [{"role":"user", "content":user_msg}]

            full_text = ""
            scrubbed_final = ""
            detected_emotion = "neutral"

            async for chunk in provider_registry.stream(messages_format):
                if isinstance(chunk, TextDelta):
                    txt = chunk.text
                    full_text += txt
                    yield f"data: {json.dumps({'text': txt})}\n\n"
                elif isinstance(chunk, StreamDone):
                    scrubbed_final = chunk.text
                    detected_emotion = chunk.emotion

            # Ensure we have parsed results
            if not scrubbed_final:
                from app.services.providers.base import parse_emotion
                detected_emotion, scrubbed_final = parse_emotion(full_text)

            # PER USER REQUEST: Persistence is deferred to session end. 
            # We skip per-turn add_interaction to restore latency and avoid redundant chat entries.
            # asyncio.create_task(memory_service.add_interaction(...))

            yield "data: [DONE]\n\n"

        return StreamingResponse(voice_event_generator(), media_type="text/event-stream")

    except Exception as e:
        logger.error(f"Voice Chat error: {e}", exc_info=True)
        return StreamingResponse(
            iter([f"data: {json.dumps({'text': f'[sad] Brain Freeze: {str(e)}'})}\n\n"]),
            media_type="text/event-stream"
        )
