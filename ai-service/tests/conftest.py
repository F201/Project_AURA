"""
Shared pytest fixtures and env setup.
Loads the project .env so integration tests can use real API keys.
"""
import os
import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv

# ── Add ai-service root to sys.path so `app.*` imports resolve ───────────────
AI_SERVICE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AI_SERVICE_DIR))

# ── Load .env from project root ───────────────────────────────────────────────
PROJECT_ROOT = AI_SERVICE_DIR.parent
env_path = PROJECT_ROOT / ".env"
if not env_path.exists():
    env_path = AI_SERVICE_DIR / ".env"
load_dotenv(env_path)


# ── Reusable message lists ────────────────────────────────────────────────────

@pytest.fixture
def simple_messages():
    return [
        {"role": "system", "content": "You are a helpful assistant. Reply very briefly."},
        {"role": "user",   "content": "Say exactly: [smile] Hello!"},
    ]


@pytest.fixture
def tool_messages():
    return [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user",   "content": "What is the weather in Tokyo? Use the get_weather tool."},
    ]


@pytest.fixture
def sample_tools():
    return [
        {
            "type": "function",
            "function": {
                "name":        "get_weather",
                "description": "Get current weather for a city.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city": {"type": "string", "description": "City name"},
                    },
                    "required": ["city"],
                },
            },
        }
    ]


# ── Key availability helpers (used by integration marks) ─────────────────────

def has_openrouter_key():
    return bool(os.getenv("OPENROUTER_API_KEY", "").strip())

def has_openai_key():
    return bool(os.getenv("OPENAI_API_KEY", "").strip())

def has_anthropic_key():
    return bool(os.getenv("ANTHROPIC_API_KEY", "").strip())
