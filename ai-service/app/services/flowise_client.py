import requests
from app.core.config import settings

class FlowiseClient:
    def query_rag(self, prompt: str):
        url = f"{settings.FLOWISE_URL}/prediction/{settings.FLOWISE_RAG_WORKFLOW_ID}"
        response = requests.post(url, json={"question": prompt})
        return response.json()
