import inspect
import livekit.agents.voice.agent_activity

with open("agent_activity_sources.txt", "w", encoding="utf-8") as f:
    f.write("AgentActivity source code:\n")
    try:
        f.write(inspect.getsource(livekit.agents.voice.agent_activity.AgentActivity))
    except Exception as e:
        f.write(f"Error: {e}\n")
