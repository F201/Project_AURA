from typing import TypedDict, List, Annotated
from langchain_core.messages import BaseMessage

import operator

# BrainState for conversation history and emotion tracking
class BrainState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    emotion: str