import pytest
from unittest.mock import AsyncMock, patch
from langchain_core.messages import HumanMessage
from app.services.brain.nodes.emotion import detect_emotion
from app.services.brain.nodes.generate import generate
from app.services.brain.state import BrainState

@pytest.mark.asyncio
async def test_detect_emotion():
    state = BrainState(messages=[HumanMessage(content="I am so happy!")])
    
    with patch("app.services.brain.nodes.emotion.provider_registry.generate", new_callable=AsyncMock) as mock_generate:
        mock_generate.return_value = {"emotion": "happy"}
        result = await detect_emotion(state)
        
        assert result["emotion"] == "happy"
        mock_generate.assert_called_once()

@pytest.mark.asyncio
async def test_generate():
    state = BrainState(
        messages=[HumanMessage(content="What's up?")],
        emotion="happy",
        conversation_id="12345678-1234-5678-1234-567812345678",
        identity="test-user",
        stream=False
    )

    with patch("app.services.brain.nodes.generate.memory_service") as mock_memory, \
         patch("app.services.brain.nodes.generate.provider_registry.generate", new_callable=AsyncMock) as mock_generate, \
         patch("app.services.settings_service.settings_service") as mock_settings, \
         patch("app.services.persona.persona_engine") as mock_persona:

        mock_memory.get_history = AsyncMock(return_value=[{"role": "assistant", "content": "hi"}])
        mock_memory.search = AsyncMock(return_value=["fact memory"])
        mock_memory.get_long_term_memories = AsyncMock(return_value="long term memory")
        mock_memory.add_interaction = AsyncMock()
        mock_memory.store = AsyncMock()
        
        mock_settings.get_settings.return_value = {"system_prompt": "test prompt"}
        mock_generate.return_value = {"text": "generated response", "emotion": "excited"}

        result = await generate(state)

        assert result["emotion"] == "excited"
        assert result["messages"][0].content == "generated response"
        
        mock_generate.assert_called_once()
        mock_memory.add_interaction.assert_called()
        mock_memory.store.assert_called()
