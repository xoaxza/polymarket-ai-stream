import os
from livekit import api
from livekit.protocol.egress import (
    RoomCompositeEgressRequest,
    StreamOutput,
    StreamProtocol,
    EncodingOptionsPreset,
)

class StreamController:
    def __init__(self):
        self.lkapi = api.LiveKitAPI()
        self.room_name = os.getenv("ROOM_NAME", "polymarket-ai-show")
        self.egress_id = None
        
    async def create_room(self):
        """Create the LiveKit room for the show"""
        room_info = await self.lkapi.room.create_room(
            api.CreateRoomRequest(
                name=self.room_name,
                empty_timeout=3600,  # 1 hour
                max_participants=10,
            )
        )
        print(f"✅ Room created: {room_info.name}")
        return room_info
    
    async def dispatch_agents(self):
        """Dispatch both AI host agents to the room"""
        await self.lkapi.agent.create_dispatch(self.room_name, "host-max")
        await self.lkapi.agent.create_dispatch(self.room_name, "host-ben")
        print("✅ AI hosts dispatched to room")
    
    async def start_twitch_stream(self):
        """Start RTMP egress to Twitch"""
        stream_key = os.getenv("TWITCH_STREAM_KEY")
        
        stream_output = StreamOutput(
            protocol=StreamProtocol.RTMP,
            urls=[f"rtmp://live.twitch.tv/app/{stream_key}"]
        )
        
        # Use custom overlay URL for visual template
        overlay_url = os.getenv("OVERLAY_URL", None)
        
        request = RoomCompositeEgressRequest(
            room_name=self.room_name,
            layout="speaker",  # Active speaker layout
            stream_outputs=[stream_output],
            preset=EncodingOptionsPreset.H264_1080P_30,
            # Optionally use custom visual template:
            # custom_base_url=overlay_url,
        )
        
        info = await self.lkapi.egress.start_room_composite_egress(request)
        self.egress_id = info.egress_id
        print(f"✅ Streaming to Twitch! Egress ID: {self.egress_id}")
        return info
    
    async def stop_stream(self):
        """Stop the Twitch stream"""
        if self.egress_id:
            await self.lkapi.egress.stop_egress(self.egress_id)
            print("⏹️ Stream stopped")
    
    async def cleanup(self):
        """Clean up resources"""
        await self.stop_stream()
        await self.lkapi.room.delete_room(
            api.DeleteRoomRequest(room=self.room_name)
        )
        await self.lkapi.aclose()