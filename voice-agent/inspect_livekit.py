import inspect
import livekit.agents

print("livekit.agents path:", livekit.agents.__file__)
print("Members of livekit.agents:")
for name, obj in inspect.getmembers(livekit.agents):
    if name in ["Agent", "AgentSession", "VoicePipelineAgent", "VoiceAgent"]:
        print(f"  {name}: {obj} (from {inspect.getfile(obj) if inspect.isclass(obj) or inspect.ismodule(obj) or inspect.isfunction(obj) else 'unknown'})")
