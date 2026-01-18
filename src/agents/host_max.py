import os
from dotenv import load_dotenv
from livekit import agents
from livekit.agents import AgentSession, Agent, RoomInputOptions
from livekit.plugins import openai, elevenlabs, silero
from .agent_config import HOST_MAX

load_dotenv()

async def entrypoint(ctx: agents.JobContext):
    await ctx.connect()
    
    # Create session with ElevenLabs TTS
    session = AgentSession(
        llm=openai.LLM(model="gpt-4o"),
        tts=elevenlabs.TTS(
            voice_id=HOST_MAX.voice_id,
            model="eleven_flash_v2_5",  # Lowest latency for streaming
            voice_settings=elevenlabs.VoiceSettings(
                stability=0.4,          # Lower = more expressive
                similarity_boost=0.8,
                style=0.3,              # Add some style variation
            ),
        ),
        vad=silero.VAD.load(),  # Voice activity detection
    )
    
    await session.start(
        room=ctx.room,
        agent=Agent(instructions=HOST_MAX.system_prompt),
        room_input_options=RoomInputOptions(
            text_enabled=True,  # Receive text input from orchestrator
        ),
    )

if __name__ == "__main__":
    agents.cli.run_app(
        agents.WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name="host-max",
        )
    )