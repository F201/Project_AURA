from fastapi import FastAPI
from app.api import chat

app = FastAPI()

app.include_router(chat.router)
