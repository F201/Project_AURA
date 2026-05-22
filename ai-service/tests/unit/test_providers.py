import pytest
from app.services.providers.base import parse_emotion, RetryableError, NonRetryableError, make_result, LLMProvider
from app.services.providers.registry import infer_provider, ProviderRegistry

def test_infer_provider():
    assert infer_provider("claude-3-opus-20240229") == "anthropic"
    assert infer_provider("deepseek/deepseek-v3.2") == "openrouter"
    assert infer_provider("deepseek/deepseek-v4-flash") == "openrouter"
    assert infer_provider("gpt-4o") == "openai"
    assert infer_provider("llama3-8b-instruct") == "ollama"
    assert infer_provider("unknown-model") == "openrouter"

def test_parse_emotion():
    emotion, text = parse_emotion("[happy] Hello there!")
    assert emotion == "happy"
    assert text == "Hello there!"

    emotion, text = parse_emotion("No emotion tag here.")
    assert emotion == "neutral"
    assert text == "No emotion tag here."

    emotion, text = parse_emotion("[sad, crying] I am sad.")
    assert emotion == "sad, crying"
    assert text == "I am sad."

class MockProvider(LLMProvider):
    name = "mock"
    def __init__(self, raises=None, result=None):
        self.raises = raises
        self.result = result
        self.call_count = 0

    def generate(self, messages, *, model, temperature, max_tokens, tools=None):
        self.call_count += 1
        if self.raises:
            if isinstance(self.raises, list):
                err = self.raises.pop(0)
                if err:
                    raise err
            else:
                raise self.raises
        return self.result or make_result("test", self.name, model)

    async def stream(self, messages, *, model, temperature, max_tokens, tools=None):
        yield None

@pytest.mark.asyncio
async def test_provider_registry_fallback(monkeypatch):
    registry = ProviderRegistry()
    
    # Mock settings
    class MockSettings:
        async def get_settings(self):
            return {"provider": "auto", "model": "gpt-4", "temperature": 0.8, "max_tokens": 100}
        async def get_api_keys(self):
            return {"openai_api_key": "sk-123", "openrouter_api_key": "sk-or"}

    monkeypatch.setattr("app.services.settings_service.settings_service", MockSettings())

    # We want to trace which providers are requested
    requested_providers = []

    def mock_get_provider(provider_name, keys):
        requested_providers.append(provider_name)
        if provider_name == "openai":
            return MockProvider(raises=RetryableError("Timeout", 500))
        elif provider_name == "openrouter":
            return MockProvider(result=make_result("[happy] OpenRouter success", "openrouter", "gpt-4"))
        return MockProvider()

    monkeypatch.setattr(registry, "_get_provider", mock_get_provider)
    
    # Override backoff delay to make tests fast
    import app.services.providers.registry as reg_module
    monkeypatch.setattr(reg_module, "_BACKOFF_BASE", 0.0)
    monkeypatch.setattr(reg_module, "random", type("MockRandom", (), {"uniform": lambda a, b: 0.0}))

    res = await registry.generate([{"role": "user", "content": "hi"}])
    
    # Primary (openai) should fail with retryable error (3 times), then fallback to openrouter
    assert res["provider"] == "openrouter"
    assert res["emotion"] == "happy"
    assert res["text"] == "OpenRouter success"
    assert requested_providers == ["openai", "openrouter"]

@pytest.mark.asyncio
async def test_provider_registry_non_retryable(monkeypatch):
    registry = ProviderRegistry()
    
    class MockSettings:
        async def get_settings(self):
            return {"provider": "auto", "model": "claude-3"}
        async def get_api_keys(self):
            return {"anthropic_api_key": "sk-ant"}

    monkeypatch.setattr("app.services.settings_service.settings_service", MockSettings())

    def mock_get_provider(provider_name, keys):
        if provider_name == "anthropic":
            # 400 Bad Request immediately aborts
            return MockProvider(raises=NonRetryableError("Bad request", 400))
        return MockProvider(result=make_result("Fallback", provider_name, "claude-3"))

    monkeypatch.setattr(registry, "_get_provider", mock_get_provider)
    
    res = await registry.generate([{"role": "user", "content": "hi"}])
    
    # Since it's a 400 error, it should NOT fallback and return the default error response
    assert res["text"] == "I seem to be having trouble connecting right now. Please try again in a moment."
    assert res["emotion"] == "confused"
