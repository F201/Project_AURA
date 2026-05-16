from __future__ import annotations
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID
from typing import Optional

# Table Messages

class Message(BaseModel):
    id: UUID
    conversation_id: UUID
    role: str
    content: str
    emotion: str = "neutral"

class CreateMessage(BaseModel):
    conversation_id: UUID
    role: str
    content: str
    emotion: str = "neutral"

# Table Conversation

class Conversation(BaseModel):
    id: UUID
    title: Optional[str] = None
    created_at: datetime
    updated_at: datetime

class CreateConversation(BaseModel):
    title: Optional[str] = "New Conversation"

# Table Memories

class Memory(BaseModel):
    id: UUID
    content: str
    metadata: dict = Field(default_factory=dict)
    created_at: datetime

class CreateMemory(BaseModel):
    content: str
    metadata: dict = Field(default_factory=dict)

