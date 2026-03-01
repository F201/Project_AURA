from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from app.services.brain.state import BrainState
from app.services.brain.nodes.emotion import detect_emotion
from app.services.brain.nodes.generate import generate_response

# Build Brain Graph
workflow = StateGraph(BrainState)

# Add nodes
workflow.add_node("detect_emotion", detect_emotion)
workflow.add_node("generate_response", generate_response)

# Add edges
workflow.set_entry_point("detect_emotion")
workflow.add_edge("detect_emotion", "generate_response")
workflow.add_edge("generate_response", END)

# Compile graph with memory saver
memory_saver = MemorySaver()
brain = workflow.compile(checkpointer=memory_saver)