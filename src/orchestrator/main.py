import asyncio
import os
import numpy as np
from dotenv import load_dotenv
from datetime import datetime, timedelta
from livekit import api
from livekit.rtc import Room, RoomOptions, AudioSource, LocalAudioTrack, TrackPublishOptions, TrackSource, AudioFrame

from .stream_controller import StreamController
from .conversation import generate_conversation
from .voice_agent import VoiceAgent
from ..polymarket.client import PolymarketClient, Market
from ..twitch.voting import VotingBot
from ..agents.agent_config import HOST_MAX, HOST_BEN

load_dotenv()

class ShowOrchestrator:
    def __init__(self):
        self.stream_controller = StreamController()
        self.polymarket = PolymarketClient()
        self.twitch_bot = VotingBot()
        self.room: Room = None  # Realtime room connection
        self.audio_source: AudioSource = None  # Centralized audio source (for egress)
        self.audio_track: LocalAudioTrack = None  # Published audio track
        
        self.host_max: VoiceAgent = None
        self.host_ben: VoiceAgent = None
        
        # Updated: 2-minute market cycles (1 min per voice, voting during last minute)
        self.discussion_duration = int(os.getenv("DISCUSSION_DURATION_SECONDS", 120))  # 2 minutes
        self.voting_duration = int(os.getenv("VOTING_DURATION_SECONDS", 60))  # 1 minute
        self.voice_time_per_turn = 60  # 1 minute per voice
        
        self.current_market: Market = None
        self.discussed_market_ids = []
    
    async def _connect_as_participant(self):
        """Join room as a participant and create centralized audio track"""
        try:
            # Generate access token for orchestrator participant
            token = api.AccessToken() \
                .with_identity("orchestrator") \
                .with_name("Orchestrator") \
                .with_grants(api.VideoGrants(
                    room_join=True,
                    room=self.stream_controller.room_name,
                    can_publish=True,
                    can_subscribe=True,
                )) \
                .to_jwt()
            
            # Connect to room
            self.room = Room()
            livekit_url = os.getenv("LIVEKIT_URL")
            if not livekit_url:
                raise ValueError("LIVEKIT_URL environment variable not set")
            
            # Use the LiveKit URL as-is (wss:// for secure connections)
            # The RTC SDK handles the protocol correctly
            print(f"   Connecting to LiveKit at: {livekit_url}")
            await self.room.connect(livekit_url, token, options=RoomOptions())
            print("✅ Orchestrator connected to room as participant")
            
            # Create centralized audio source and publish immediately
            # This ensures egress sees a track right away (even if silent)
            await self._create_centralized_audio_track()
            
            self.host_max = VoiceAgent(
                name="host-max",
                voice_id=HOST_MAX.voice_id,
                room=self.room,
                participant=self.room.local_participant
            )
            self.host_ben = VoiceAgent(
                name="host-ben",
                voice_id=HOST_BEN.voice_id,
                room=self.room,
                participant=self.room.local_participant
            )
            print("✅ Voice agents initialized (in-process)")
            
        except Exception as e:
            print(f"⚠️ Could not connect orchestrator to room: {e}")
            print("   Will try using data messages instead (may not work reliably)")
            self.room = None
            import traceback
            traceback.print_exc()
    
    async def _create_centralized_audio_track(self):
        """Create and publish a centralized audio track immediately"""
        try:
            # Create audio source (48kHz, mono - standard for voice)
            SAMPLE_RATE = 48000
            NUM_CHANNELS = 1
            SAMPLES_PER_FRAME = 480  # ~10ms frames
            
            self.audio_source = AudioSource(SAMPLE_RATE, NUM_CHANNELS)
            self.audio_track = LocalAudioTrack.create_audio_track("podcast-audio", self.audio_source)
            
            # Publish the track immediately (even if silent)
            options = TrackPublishOptions(source=TrackSource.SOURCE_MICROPHONE)
            publication = await self.room.local_participant.publish_track(self.audio_track, options)
            print("✅ Centralized audio track published (egress can now start)")
            
            # Start feeding silence to keep the track alive
            # This ensures the track is always "active" even when agents aren't speaking
            asyncio.create_task(self._feed_silence_loop())
            
        except Exception as e:
            print(f"❌ Failed to create centralized audio track: {e}")
            import traceback
            traceback.print_exc()
    
    async def _feed_silence_loop(self):
        """Continuously feed silence frames to keep the audio track alive"""
        SAMPLE_RATE = 48000
        NUM_CHANNELS = 1
        SAMPLES_PER_FRAME = 480
        
        try:
            while self.audio_source:
                # Create silent audio frame
                frame = AudioFrame.create(SAMPLE_RATE, NUM_CHANNELS, SAMPLES_PER_FRAME)
                # Frame is already zero-initialized (silence)
                
                # Feed frame to source (this is non-blocking)
                await self.audio_source.capture_frame(frame)
                await asyncio.sleep(0.01)  # ~10ms per frame
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"⚠️ Error in silence feed loop: {e}")
        
    async def speak(self, agent_name: str, text: str):
        agent = self.host_max if agent_name == "host-max" else self.host_ben
        if agent:
            # This blocks until audio finishes playing (await pattern)
            await agent.speak(text)
        else:
            print(f"   ⚠️ Agent {agent_name} not initialized")
    
    async def send_to_agent(self, agent_name: str, text: str):
        """Send text to a specific agent for TTS synthesis (legacy method - use speak() instead)"""
        # For backward compatibility, redirect to speak()
        await self.speak(agent_name, text)
    
    async def wait_for_speech_completion(self, agent_name: str, timeout: int = 120):
        """Wait for agent to finish speaking (await pattern)"""
        self.pending_speech_agent = agent_name
        self.speech_completion_event.clear()
        
        try:
            # Wait for completion message with timeout
            await asyncio.wait_for(self.speech_completion_event.wait(), timeout=timeout)
            print(f"   ✅ {agent_name} finished speaking")
            return True
        except asyncio.TimeoutError:
            print(f"   ⚠️ Timeout waiting for {agent_name} to finish (may still be speaking)")
            return False
        finally:
            self.pending_speech_agent = None
    
    async def run_discussion(self, market: Market):
        """Run a 2-minute discussion about a market (1 min per voice, voting during last minute)"""
        print(f"\n🎙️ Starting discussion: {market.question}")
        
        # Generate conversation with 2 exchanges (1 min each = 2 min total)
        conversation_iter = generate_conversation(
            market_question=market.question,
            market_odds=market.formatted_odds,
            market_description=market.description,
            num_exchanges=2  # 2 exchanges: max (~60 sec) + ben (~60 sec) = 2 min total
        )
        
        # Start discussion timer (2 minutes total)
        discussion_start_time = asyncio.get_event_loop().time()
        
        # Get first exchange (max speaks first, ~1 minute)
        first_exchange = await conversation_iter.__anext__()
        current_speaker, current_dialogue = first_exchange
        current_agent_name = "host-max" if current_speaker == "max" else "host-ben"
        
        # Start first agent speaking (~1 minute)
        speak_task = asyncio.create_task(self.speak(current_agent_name, current_dialogue))
        
        # Pre-generate second response while first agent is speaking
        next_exchange_task = asyncio.create_task(conversation_iter.__anext__())
        
        # Wait for first agent to finish (~1 minute mark)
        await speak_task
        
        # At 1 minute mark, start voting for next market (concurrent with second voice)
        print(f"🗳️  Starting voting for next market (1 min before new market)...")
        voting_task = asyncio.create_task(self._run_voting_during_discussion())
        
        # Get second exchange and start speaking (ben speaks second, ~1 minute)
        # Voting runs concurrently during this time
        try:
            next_speaker, next_dialogue = await next_exchange_task
            next_agent_name = "host-max" if next_speaker == "max" else "host-ben"
            
            # Start second agent speaking (voting happens concurrently)
            await self.speak(next_agent_name, next_dialogue)
        except StopAsyncIteration:
            pass
        
        # Wait for voting to complete (should finish around 2 minute mark)
        next_market = await voting_task
        return next_market
    
    async def _run_voting_during_discussion(self) -> Market:
        """Run voting during the last minute of discussion"""
        # IMPORTANT: Exclude current market from candidates to ensure we get a NEW market
        # Also exclude already discussed markets
        exclude_ids = self.discussed_market_ids.copy()
        if self.current_market and self.current_market.id not in exclude_ids:
            exclude_ids.append(self.current_market.id)
        
        # Fetch candidate markets for voting (excluding current and discussed)
        candidates = self.polymarket.get_candidate_markets(exclude_ids=exclude_ids)
        
        if len(candidates) < 2:
            # If not enough candidates, clear history but still exclude current market
            self.discussed_market_ids.clear()
            exclude_ids = [self.current_market.id] if self.current_market else []
            candidates = self.polymarket.get_candidate_markets(exclude_ids=exclude_ids)
        
        # Ensure we have 2 candidates
        if len(candidates) < 2:
            # Last resort: fetch more markets
            all_markets = self.polymarket.get_trending_markets(limit=10)
            exclude_set = set(exclude_ids)
            candidates = [m for m in all_markets if m.id not in exclude_set][:2]
        
        if len(candidates) < 2:
            print("⚠️ WARNING: Could not get 2 unique candidates, using fallback")
            # Fallback: just get any 2 markets
            all_markets = self.polymarket.get_trending_markets(limit=10)
            candidates = all_markets[:2]
        
        print(f"   📊 Voting candidates: 1) {candidates[0].question[:50]}... | 2) {candidates[1].question[:50]}...")
        
        # Announce voting
        candidate_names = [c.question[:50] for c in candidates]
        await self.twitch_bot.open_voting(candidate_names)
        
        # Wait for voting duration (1 minute)
        await asyncio.sleep(self.voting_duration)
        
        # Close voting and get results
        results = await self.twitch_bot.close_voting()
        winner_idx = results["winner"] - 1
        
        selected_market = candidates[winner_idx]
        print(f"   ✅ Selected market: {selected_market.question[:50]}...")
        
        return selected_market
    
    async def run_voting_phase(self) -> Market:
        """Run voting phase and return winning market"""
        # Get 2 candidate markets
        candidates = self.polymarket.get_candidate_markets(
            exclude_ids=self.discussed_market_ids
        )
        
        if len(candidates) < 2:
            print("⚠️ Not enough candidate markets, refetching...")
            self.discussed_market_ids.clear()
            candidates = self.polymarket.get_candidate_markets()
        
        # Announce voting
        candidate_names = [c.question[:50] for c in candidates]
        await self.twitch_bot.open_voting(candidate_names)
        
        # Have hosts announce the options
        await self.send_to_agent(
            "host-max",
            f"Alright traders! Time to VOTE! Option 1: {candidates[0].question}"
        )
        await asyncio.sleep(5)
        await self.send_to_agent(
            "host-ben", 
            f"And Option 2: {candidates[1].question}. You have 60 seconds. Choose wisely."
        )
        
        # Wait for voting
        await asyncio.sleep(self.voting_duration)
        
        # Close voting and get results
        results = await self.twitch_bot.close_voting()
        winner_idx = results["winner"] - 1
        
        return candidates[winner_idx]
    
    async def run_show_loop(self):
        """Main show loop"""
        print("🚀 Starting Polymarket AI Show!")
        
        # Setup
        await self.stream_controller.create_room()
        # No need to dispatch agents - they're in-process classes now
        
        # Connect orchestrator as participant and create centralized audio track
        # This ensures egress sees a track immediately (solving chicken-and-egg problem)
        await self._connect_as_participant()
        await asyncio.sleep(1)  # Brief wait for track to be published
        
        # Trigger agents to speak so they publish audio tracks
        print("🎤 Triggering agents to speak (so they publish tracks)...")
        try:
            await self.speak("host-max", "Welcome to the Polymarket AI Show! Let's get started.")
            await self.speak("host-ben", "Ready to discuss some markets.")
        except Exception as e:
            print(f"⚠️ Could not trigger agents to speak: {e}")
            import traceback
            traceback.print_exc()
        
        # Now start egress (centralized track exists, agents may have tracks too)
        await self.stream_controller.start_twitch_stream()
        
        # Start Twitch bot
        asyncio.create_task(self.twitch_bot.start())
        await asyncio.sleep(3)  # Wait for bot to connect
        
        # Get initial market
        initial_markets = self.polymarket.get_trending_markets(limit=1)
        self.current_market = initial_markets[0]
        
        try:
            while True:
                # Phase 1: Discussion (2 minutes total: 1 min max + 1 min ben)
                # Voting happens during last minute of discussion
                old_market = self.current_market
                
                # Mark old market as discussed BEFORE starting discussion
                # This ensures it won't be selected in voting
                if old_market and old_market.id not in self.discussed_market_ids:
                    self.discussed_market_ids.append(old_market.id)
                    print(f"   📝 Marked market as discussed: {old_market.question[:50]}...")
                
                # Run discussion (voting happens during last minute)
                next_market = await self.run_discussion(self.current_market)
                
                # Verify we got a different market
                if next_market.id == old_market.id:
                    print(f"⚠️ WARNING: Voting returned same market! Fetching new market directly...")
                    # Fallback: just get a new trending market
                    exclude_ids = self.discussed_market_ids.copy()
                    if old_market.id not in exclude_ids:
                        exclude_ids.append(old_market.id)
                    new_markets = self.polymarket.get_trending_markets(limit=10)
                    exclude_set = set(exclude_ids)
                    available = [m for m in new_markets if m.id not in exclude_set]
                    if available:
                        next_market = available[0]
                    else:
                        # Last resort: use any market
                        next_market = new_markets[0] if new_markets else old_market
                
                # Update to next market
                self.current_market = next_market
                
                # Brief transition to new market
                await self.speak(
                    "host-max",
                    f"The people have spoken! Let's dive into: {self.current_market.question}!"
                )
                
        except KeyboardInterrupt:
            print("\n👋 Shutting down...")
        finally:
            # Disconnect orchestrator participant
            if self.room:
                try:
                    await self.room.disconnect()
                except:
                    pass
            await self.stream_controller.cleanup()

async def main():
    orchestrator = ShowOrchestrator()
    await orchestrator.run_show_loop()

if __name__ == "__main__":
    asyncio.run(main())