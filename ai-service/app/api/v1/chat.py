import json
import logging
import asyncio
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from app.services.memory_service import memory_service
from app.models.chat import ChatRequest, ChatResponse
from app.services.brain.graph import brain
from langchain_core.messages import HumanMessage, AIMessage

router = APIRouter()
logger = logging.getLogger(__name__)

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
                # 1. Start with emotion detection (sequential but fast)
                try:
                    from app.services.brain.nodes.emotion import detect_emotion
                    emotion_res = await detect_emotion(initial_state)
                    detected_emotion = emotion_res.get("emotion", "neutral")
                    yield f"data: {json.dumps({'emotion': detected_emotion})}\n\n"
                except Exception as ex:
                    logger.warning(f"Emotion detection failed: {ex}")
                    detected_emotion = "neutral"

                # 2. Setup the full context for generation
                from app.services.brain.nodes.generate import session_history_window
                from app.services.llm import llm_service
                from app.services.persona import persona_engine
                from app.services.settings_service import settings_service
                from datetime import datetime
                from uuid import UUID

                # Fetch context
                user_msg = request.message
                history_model, memories, facts = await asyncio.gather(
                    memory_service.get_history(UUID(conversation_id), session_history_window),
                    memory_service.search(query=user_msg, limit=3),
                    memory_service.get_long_term_memories(identity=request.identity or "anonymous", limit=5),
                )
                
                # Build Persona
                db_settings = settings_service.get_settings()
                custom_sys = (db_settings.get("system_prompt") or "").strip()
                persona = custom_sys if custom_sys else persona_engine.get_persona()
                time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                system_content = (
                    "You are AURA (Advanced Universal Responsive Avatar), steward of the ASE Lab.\n\n"
                    f"{persona}\n\n"
                    "IMPORTANT: Do NOT include bracketed emotions like [happy] or [sad] in your response content. "
                    "I have already detected your emotion separately.\n\n"
                    f"**Context:**\n- Current Time: {time_str}"
                )
                if facts: system_content += f"\nWhat I know about you:\n{facts}\n"
                if memories:
                    memory_block = "\n".join(f"- {m}" for m in memories)
                    system_content += f"\nRelevant past snippets:\n{memory_block}\n"

                messages_format = [{"role":"system", "content":system_content}] + history_model + [{"role":"user", "content":user_msg}]

                import re
                full_text = ""
                # 3. Stream from the registry directly
                from app.services.providers.base import TextDelta
                async for chunk in llm_service.stream(messages_format):
                    # Only yield incremental deltas to the dashboard
                    if isinstance(chunk, TextDelta):
                        txt = chunk.text
                        full_text += txt
                        yield f"data: {json.dumps({'text': txt})}\n\n"
                    # StreamDone is handled silently for background persistence below

                # 4. Final sync/persistence - SCRUBBED
                scrubbed_final = re.sub(r'\[.*?\]', '', full_text).strip()
                asyncio.create_task(memory_service.add_interaction(
                    conversation_id=UUID(conversation_id),
                    user_text=user_msg,
                    assistant_text=scrubbed_final,
                    user_emotion=detected_emotion,
                    assistant_emotion="neutral"
                ))
                asyncio.create_task(memory_service.store(
                    text=f"User: {user_msg} \n AURA: {scrubbed_final}",
                    metadata={"conversation_id": str(conversation_id)}
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
