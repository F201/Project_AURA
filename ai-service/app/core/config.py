from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    FLOWISE_URL: str = "http://flowise:3000/api/v1"
    FLOWISE_RAG_WORKFLOW_ID: str = "YOUR_WORKFLOW_ID"
    LLM_API_KEY: str = ""
    POSTGRES_HOST: str = "postgres"
    POSTGRES_USER: str = "aura"
    POSTGRES_PASSWORD: str = "password"
    POSTGRES_DB: str = "aura"

settings = Settings()
