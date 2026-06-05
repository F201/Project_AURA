from langgraph.graph import StateGraph, END

from app.services.brain.state import BrainState
from app.services.brain.nodes.emotion import detect_emotion
from app.services.brain.nodes.generate import generate_response

# Build Brain Graph
workflow = StateGraph(BrainState)

# Add nodes
workflow.add_node("generate", generate_response)

# Add edges
workflow.set_entry_point("generate")
workflow.add_edge("generate", END)

# Compile graph
brain = workflow.compile()