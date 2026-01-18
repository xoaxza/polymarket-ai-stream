import os
import asyncio
from dotenv import load_dotenv
from livekit import agents
from livekit.agents import AgentSession, Agent, RoomInputOptions
from livekit.plugins import openai, elevenlabs, silero
from .agent_config import HOST_BEN

load_dotenv()


async def entrypoint(ctx: agents.JobContext):
    await ctx.connect()
    
    # Create session with ElevenLabs TTS
    session = AgentSession(
        llm=openai.LLM(model="gpt-4o"),
        tts=elevenlabs.TTS(
            voice_id=HOST_BEN.voice_id,
            model="eleven_flash_v2_5",  # Lowest latency for streaming
            voice_settings=elevenlabs.VoiceSettings(
                stability=0.6,          # Slightly more stable for analytical tone
                similarity_boost=0.8,
                style=0.2,              # Less style variation - more measured
            ),
        ),
        vad=silero.VAD.load(),  # Voice activity detection
    )
    
    await session.start(
        room=ctx.room,
        agent=Agent(instructions=HOST_BEN.system_prompt),
        room_input_options=RoomInputOptions(
            text_enabled=True,  # Receive text input from orchestrator
        ),
    )
    
    # Handle data messages from orchestrator (after session starts)
    @ctx.room.on("data_received")
    def on_data_received(packet):
        """Handle data messages from orchestrator and make agent speak"""
        async def handle_speech():
            try:
                # DataPacket has 'data' attribute (bytes), not 'payload'
                text = packet.data.decode("utf-8") if hasattr(packet, 'data') else packet.payload.decode("utf-8")
                print(f"[host-ben] Received message: {text[:50]}...")
                
                # Await speech completion - this blocks until TTS finishes
                await session.say(text, allow_interruptions=True)
                
                # Send completion message back to orchestrator via data message
                try:
                    await ctx.room.local_participant.publish_data(
                        b"SPEECH_COMPLETE",
                        reliable=True,
                        destination_identities=["orchestrator"],
                        topic="speech_complete"
                    )
                    print(f"[host-ben] Speech completed, notified orchestrator")
                except Exception as e:
                    print(f"[host-ben] Could not send completion message: {e}")
            except Exception as e:
                print(f"[host-ben] Error handling data message: {e}")
                import traceback
                traceback.print_exc()
        
        # Create task to handle speech asynchronously
        asyncio.create_task(handle_speech())


if __name__ == "__main__":
    # Allow port to be configured via environment variable, default to 8081
    http_port = int(os.getenv("AGENT_HTTP_PORT", "8081"))
    
    agents.cli.run_app(
        agents.WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name="host-ben",
            port=http_port,
        )
    )
