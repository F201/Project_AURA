import inspect
import livekit.agents.voice.agent
import livekit.agents.voice.agent_session

with open("agent_sources.txt", "w", encoding="utf-8") as f:
    f.write("Agent source code:\n")
    try:
        f.write(inspect.getsource(livekit.agents.voice.agent.Agent))
    except Exception as e:
        f.write(f"Error: {e}\n")

    f.write("\n\nAgentSession source code:\n")
    try:
        f.write(inspect.getsource(livekit.agents.voice.agent_session.AgentSession))
    except Exception as e:
        f.write(f"Error: {e}\n")
