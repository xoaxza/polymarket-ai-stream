import asyncio
import os
import io
import numpy as np
from elevenlabs.client import ElevenLabs
from elevenlabs import stream
from livekit.rtc import AudioSource, LocalAudioTrack, TrackPublishOptions, TrackSource, AudioFrame

# Initialize ElevenLabs client
# Note: Environment variable is ELEVEN_API_KEY (not ELEVENLABS_API_KEY)
elevenlabs_api_key = os.getenv("ELEVEN_API_KEY")
if not elevenlabs_api_key:
    raise ValueError("ELEVEN_API_KEY environment variable not set")
elevenlabs_client = ElevenLabs(api_key=elevenlabs_api_key)

class VoiceAgent:
    """In-process voice agent that generates and plays audio directly"""
    
    def __init__(self, name: str, voice_id: str, room, participant):
        self.name = name
        self.voice_id = voice_id
        self.room = room
        self.participant = participant
        self.audio_source: AudioSource = None
        self.audio_track: LocalAudioTrack = None
        self.current_publication = None
        
        # Audio settings
        self.SAMPLE_RATE = 24000  # ElevenLabs default
        self.NUM_CHANNELS = 1
        self.FRAME_DURATION_MS = 20  # 20ms frames
        self.SAMPLES_PER_FRAME = int(self.SAMPLE_RATE * self.FRAME_DURATION_MS / 1000)
    
    async def _ensure_track_published(self):
        """Ensure audio track is published to room"""
        if self.audio_track is None or self.current_publication is None:
            # Create audio source and track
            self.audio_source = AudioSource(self.SAMPLE_RATE, self.NUM_CHANNELS)
            self.audio_track = LocalAudioTrack.create_audio_track(
                f"{self.name}-audio", 
                self.audio_source
            )
            
            # Publish track
            options = TrackPublishOptions(source=TrackSource.SOURCE_MICROPHONE)
            self.current_publication = await self.participant.publish_track(
                self.audio_track, 
                options
            )
            print(f"   ✅ {self.name} audio track published")
    
    async def speak(self, text: str) -> None:
        """Generate TTS audio and play it to the room. Blocks until playback completes."""
        print(f"   🎤 {self.name} speaking: {text[:50]}...")
        
        # Ensure track is published
        await self._ensure_track_published()
        
        try:
            # Generate audio from ElevenLabs (streaming, PCM format)
            audio_generator = elevenlabs_client.text_to_speech.stream(
                voice_id=self.voice_id,
                text=text,
                model_id="eleven_v3",
                output_format="pcm_24000",  # Raw PCM, 24kHz, 16-bit, mono
            )
            
            # Buffer to accumulate audio chunks
            audio_buffer = bytearray()
            bytes_per_frame = self.SAMPLES_PER_FRAME * 2  # 2 bytes per sample (16-bit)
            frame_interval = self.FRAME_DURATION_MS / 1000  # 20ms in seconds
            
            # Use a timer-based approach for smooth frame delivery
            last_frame_time = None
            
            # Stream audio chunks to LiveKit
            for audio_chunk in audio_generator:
                if not audio_chunk:
                    continue
                
                audio_buffer.extend(audio_chunk)
                
                # Process complete frames from buffer with proper timing
                while len(audio_buffer) >= bytes_per_frame:
                    # Extract one frame
                    frame_bytes = bytes(audio_buffer[:bytes_per_frame])
                    audio_buffer = audio_buffer[bytes_per_frame:]
                    
                    # Create AudioFrame
                    frame = AudioFrame.create(
                        self.SAMPLE_RATE,
                        self.NUM_CHANNELS,
                        self.SAMPLES_PER_FRAME
                    )
                    
                    # Copy PCM data into frame using numpy (proper way to handle memoryview)
                    audio_samples = np.frombuffer(frame_bytes, dtype=np.int16)
                    frame_samples = np.frombuffer(frame.data, dtype=np.int16)
                    np.copyto(frame_samples[:len(audio_samples)], audio_samples)
                    
                    # Feed to source immediately (LiveKit handles internal buffering)
                    await self.audio_source.capture_frame(frame)
                    
                    # Maintain frame rate timing based on actual elapsed time
                    if last_frame_time is not None:
                        current_time = asyncio.get_event_loop().time()
                        elapsed = current_time - last_frame_time
                        sleep_needed = frame_interval - elapsed
                        if sleep_needed > 0:
                            await asyncio.sleep(sleep_needed)
                    
                    last_frame_time = asyncio.get_event_loop().time()
            
            # Process remaining buffer (pad if needed)
            if len(audio_buffer) > 0:
                bytes_per_frame = self.SAMPLES_PER_FRAME * 2
                # Pad with zeros to complete frame
                padding_needed = bytes_per_frame - len(audio_buffer)
                audio_buffer.extend(b'\x00' * padding_needed)
                
                frame = AudioFrame.create(
                    self.SAMPLE_RATE,
                    self.NUM_CHANNELS,
                    self.SAMPLES_PER_FRAME
                )
                
                # Copy PCM data into frame using numpy (proper way to handle memoryview)
                audio_buffer_bytes = bytes(audio_buffer)
                audio_samples = np.frombuffer(audio_buffer_bytes, dtype=np.int16)
                frame_samples = np.frombuffer(frame.data, dtype=np.int16)
                np.copyto(frame_samples[:len(audio_samples)], audio_samples)
                
                await self.audio_source.capture_frame(frame)
            
            # Wait for all audio to finish playing
            await self.audio_source.wait_for_playout()
            print(f"   ✅ {self.name} finished speaking")
            
        except Exception as e:
            print(f"   ❌ Error in {self.name}.speak(): {e}")
            import traceback
            traceback.print_exc()
            raise
