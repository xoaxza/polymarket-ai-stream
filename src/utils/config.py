import os
from dataclasses import dataclass
from dotenv import load_dotenv
from typing import Optional

load_dotenv()


@dataclass
class LiveKitConfig:
    url: str
    api_key: str
    api_secret: str


@dataclass
class ElevenLabsConfig:
    api_key: str
    host_1_voice_id: str
    host_2_voice_id: str


@dataclass
class TwitchConfig:
    client_id: str
    client_secret: str
    oauth_token: str
    channel_name: str
    stream_key: str


@dataclass
class StreamConfig:
    discussion_duration: int
    voting_duration: int
    room_name: str


@dataclass
class Config:
    livekit: LiveKitConfig
    elevenlabs: ElevenLabsConfig
    twitch: TwitchConfig
    stream: StreamConfig
    openai_api_key: str
    
    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables"""
        return cls(
            livekit=LiveKitConfig(
                url=os.getenv("LIVEKIT_URL", ""),
                api_key=os.getenv("LIVEKIT_API_KEY", ""),
                api_secret=os.getenv("LIVEKIT_API_SECRET", ""),
            ),
            elevenlabs=ElevenLabsConfig(
                api_key=os.getenv("ELEVEN_API_KEY", ""),
                host_1_voice_id=os.getenv("HOST_1_VOICE_ID", "21m00Tcm4TlvDq8ikWAM"),
                host_2_voice_id=os.getenv("HOST_2_VOICE_ID", "AZnzlk1XvdvUeBnXmlld"),
            ),
            twitch=TwitchConfig(
                client_id=os.getenv("TWITCH_CLIENT_ID", ""),
                client_secret=os.getenv("TWITCH_CLIENT_SECRET", ""),
                oauth_token=os.getenv("TWITCH_OAUTH_TOKEN", ""),
                channel_name=os.getenv("TWITCH_CHANNEL_NAME", ""),
                stream_key=os.getenv("TWITCH_STREAM_KEY", ""),
            ),
            stream=StreamConfig(
                discussion_duration=int(os.getenv("DISCUSSION_DURATION_SECONDS", "300")),
                voting_duration=int(os.getenv("VOTING_DURATION_SECONDS", "60")),
                room_name=os.getenv("ROOM_NAME", "polymarket-ai-show"),
            ),
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        )
    
    def validate(self) -> list[str]:
        """Validate that all required config values are present"""
        errors = []
        
        if not self.livekit.url:
            errors.append("LIVEKIT_URL is required")
        if not self.livekit.api_key:
            errors.append("LIVEKIT_API_KEY is required")
        if not self.livekit.api_secret:
            errors.append("LIVEKIT_API_SECRET is required")
        if not self.elevenlabs.api_key:
            errors.append("ELEVEN_API_KEY is required")
        if not self.twitch.oauth_token:
            errors.append("TWITCH_OAUTH_TOKEN is required")
        if not self.twitch.channel_name:
            errors.append("TWITCH_CHANNEL_NAME is required")
        if not self.twitch.stream_key:
            errors.append("TWITCH_STREAM_KEY is required")
        if not self.openai_api_key:
            errors.append("OPENAI_API_KEY is required")
            
        return errors


_config: Optional[Config] = None


def get_config() -> Config:
    """Get or create the global config instance"""
    global _config
    if _config is None:
        _config = Config.from_env()
    return _config
