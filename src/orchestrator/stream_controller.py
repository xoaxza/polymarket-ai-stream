import os
import asyncio
from livekit import api
from livekit.protocol.egress import (
    RoomCompositeEgressRequest,
    StreamOutput,
    StreamProtocol,
    EncodingOptionsPreset,
)
from livekit.api.agent_dispatch_service import CreateAgentDispatchRequest

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
        await self.lkapi.agent_dispatch.create_dispatch(
            CreateAgentDispatchRequest(
                room=self.room_name,
                agent_name="host-max"
            )
        )
        await self.lkapi.agent_dispatch.create_dispatch(
            CreateAgentDispatchRequest(
                room=self.room_name,
                agent_name="host-ben"
            )
        )
        print("✅ AI hosts dispatched to room")
    
    async def check_room_participants(self) -> tuple[bool, int]:
        """Check if room has participants with tracks
        
        Returns:
            (has_participants, participant_count)
        """
        try:
            # Get detailed room info with participants
            try:
                room_detail = await self.lkapi.room.list_participants(
                    api.ListParticipantsRequest(room=self.room_name)
                )
                participant_count = len(room_detail.participants)
                print(f"📊 Room has {participant_count} participant(s)")
                
                # Check if participants have tracks
                has_tracks = False
                track_details = []
                for participant in room_detail.participants:
                    tracks = []
                    if hasattr(participant, 'tracks'):
                        tracks = participant.tracks if participant.tracks else []
                    elif hasattr(participant, 'published_tracks'):
                        tracks = participant.published_tracks if participant.published_tracks else []
                    
                    if tracks:
                        has_tracks = True
                        # Convert track source to string (it's an enum/int)
                        track_types = []
                        for t in tracks:
                            source = getattr(t, 'source', None)
                            if source is not None:
                                # Convert enum/int to string
                                track_types.append(str(source) if not isinstance(source, str) else source)
                            else:
                                track_types.append('unknown')
                        track_details.append(f"   ✅ {participant.identity}: {len(tracks)} track(s) - {', '.join(track_types)}")
                    else:
                        track_details.append(f"   ⚠️ {participant.identity}: No tracks published yet")
                
                for detail in track_details:
                    print(detail)
                
                return has_tracks, participant_count
            except Exception as e:
                print(f"⚠️ Could not list participants: {e}")
                import traceback
                traceback.print_exc()
                return False, 0
        except Exception as e:
            print(f"⚠️ Error checking room participants: {e}")
            import traceback
            traceback.print_exc()
            return False, 0
    
    async def start_twitch_stream(self):
        """Start RTMP egress to Twitch"""
        # Check if room has participants before starting egress
        print("🔍 Checking room for participants...")
        has_tracks, participant_count = await self.check_room_participants()
        
        # If no participants or no tracks, wait and retry
        max_retries = 6
        retry_count = 0
        while (participant_count == 0 or not has_tracks) and retry_count < max_retries:
            if participant_count == 0:
                print(f"⚠️ No participants in room yet. Waiting 5 seconds... (attempt {retry_count + 1}/{max_retries})")
            else:
                print(f"⚠️ Participants exist but no tracks published yet. Waiting 5 seconds... (attempt {retry_count + 1}/{max_retries})")
                print("   Note: Agents only publish tracks when they speak. They may need to receive a message first.")
            
            await asyncio.sleep(5)
            has_tracks, participant_count = await self.check_room_participants()
            retry_count += 1
        
        if not has_tracks:
            print("❌ WARNING: Starting egress without tracks. Egress will likely stay in STARTING state.")
            print("   Agents need to speak to publish audio tracks. Make sure agents are running and will receive messages.")
        
        stream_key = os.getenv("TWITCH_STREAM_KEY")
        if not stream_key:
            raise ValueError("TWITCH_STREAM_KEY environment variable not set")
        
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
        
        try:
            info = await self.lkapi.egress.start_room_composite_egress(request)
            self.egress_id = info.egress_id
            print(f"✅ Egress request accepted! Egress ID: {self.egress_id}")
            print(f"   Status: {getattr(info, 'status', 'UNKNOWN')}")
            
            # Wait and periodically check egress status
            print("   Monitoring egress status...")
            for i in range(5):
                await asyncio.sleep(3)
                try:
                    egress_info = await self.lkapi.egress.list_egress(
                        api.ListEgressRequest(room_name=self.room_name)
                    )
                    if egress_info.items:
                        for item in egress_info.items:
                            if item.egress_id == self.egress_id:
                                status = getattr(item, 'status', 'UNKNOWN')
                                print(f"   Status check {i+1}/5: {status}")
                                if status in ['EGRESS_ACTIVE', 'ACTIVE', 'RUNNING']:
                                    print("   ✅ Egress is ACTIVE! Stream should be live on Twitch.")
                                    return info
                                elif status in ['EGRESS_COMPLETE', 'COMPLETE', 'FINISHED']:
                                    print("   ⚠️ Egress completed (may have ended)")
                                    return info
                                elif status in ['EGRESS_FAILED', 'FAILED', 'ERROR']:
                                    error_msg = getattr(item, 'error', 'Unknown error')
                                    print(f"   ❌ Egress FAILED: {error_msg}")
                                    return info
                                elif hasattr(item, 'error') and item.error:
                                    print(f"   ⚠️ Error detected: {item.error}")
                except Exception as e:
                    print(f"   ⚠️ Could not check egress status: {e}")
            
            print("   ⚠️ Egress still in STARTING state. This may indicate:")
            print("      - No participants with tracks in the room")
            print("      - RTMP connection to Twitch is failing")
            print("      - Egress service is having issues")
            print("   Check the LiveKit console for more details.")
            
            return info
        except Exception as e:
            print(f"❌ Failed to start egress: {e}")
            print(f"   Error type: {type(e).__name__}")
            raise
    
    async def stop_stream(self):
        """Stop the Twitch stream"""
        if self.egress_id:
            await self.lkapi.egress.stop_egress(
                api.StopEgressRequest(egress_id=self.egress_id)
            )
            print("⏹️ Stream stopped")
    
    async def cleanup(self):
        """Clean up resources"""
        await self.stop_stream()
        await self.lkapi.room.delete_room(
            api.DeleteRoomRequest(room=self.room_name)
        )
        await self.lkapi.aclose()