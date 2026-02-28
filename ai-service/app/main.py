from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1 import chat, health, memory, rag
from app.core.config import settings
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

app = FastAPI(title="AURA AI Service")

# CORS Configuration
origins = [
    "http://localhost:5173",  # React Dev Server
    "http://localhost:3000",
    "*" # For dev flexibility
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Routers
app.include_router(health.router, prefix="/api/v1/health", tags=["Health"])
app.include_router(chat.router, prefix="/api/v1/chat", tags=["Chat"])
app.include_router(memory.router, prefix="/api/v1/memory", tags=["Memory"])
app.include_router(rag.router, prefix="/api/v1/rag", tags=["RAG"])

@app.get("/")
def read_root():
    return {"message": "AURA AI Service Operational"}
