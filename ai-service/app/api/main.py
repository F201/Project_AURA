from fastapi import FastAPI
from app.api.v1 import chat, health, stt, tts, avatar, system

app = FastAPI(title="Project AURA API")

app.include_router(health.router)
app.include_router(chat.router)
app.include_router(stt.router)
app.include_router(tts.router)
app.include_router(avatar.router)
app.include_router(system.router)
