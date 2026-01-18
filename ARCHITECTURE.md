# AI-Powered Polymarket Live Stream: Complete Technical Implementation Guide

**Two AI hosts debating prediction markets in a "Jim Cramer" style with Twitch chat voting**—this hackathon project combines LiveKit's Agents framework, ElevenLabs voice synthesis, Polymarket data, and Twitch integration into a continuous live streaming loop. The architecture uses LiveKit as the central hub: AI agents publish synthesized speech to a room, RTMP egress streams to Twitch, and a separate orchestrator manages the 5-minute discussion cycles with chat-based market selection.

---

## System architecture overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           ORCHESTRATOR (Python)                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐│
│  │ Polymarket   │  │ Conversation │  │ Twitch Chat  │  │ Timer/State      ││
│  │ Fetcher      │  │ Generator    │  │ Voting       │  │ Manager          ││
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────────┘│
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           LIVEKIT ROOM                                       │
│  ┌──────────────────┐        ┌──────────────────┐        ┌────────────────┐│
│  │   AI Host #1     │        │   AI Host #2     │        │  RTMP Egress   ││
│  │   "Mad Money Max"│◄──────►│   "Bull Bear Ben"│        │  → Twitch      ││
│  │   ElevenLabs TTS │        │   ElevenLabs TTS │        │                ││
│  └──────────────────┘        └──────────────────┘        └────────────────┘│
└─────────────────────────────────────────────────────────────────────────────┘
```

The flow operates in **5-minute cycles**: hosts discuss a market → voting opens → chat votes on 2 candidates → winner becomes next topic → repeat.

---

## Project file and folder structure

```
polymarket-ai-stream/
├── .env                          # Environment variables
├── .env.example                  # Template for env vars
├── requirements.txt              # Python dependencies
├── package.json                  # Node.js dependencies (for Twitch chat)
│
├── src/
│   ├── __init__.py
│   │
│   ├── agents/                   # LiveKit AI Agents
│   │   ├── __init__.py
│   │   ├── host_max.py          # AI Host #1 "Mad Money Max"
│   │   ├── host_ben.py          # AI Host #2 "Bull Bear Ben"
│   │   └── agent_config.py      # Shared agent configuration
│   │
│   ├── orchestrator/            # Main control loop
│   │   ├── __init__.py
│   │   ├── main.py              # Entry point - orchestrates everything
│   │   ├── conversation.py      # Conversation generation with LLM
│   │   ├── state_manager.py     # Tracks current market, timing, phase
│   │   └── stream_controller.py # Starts/stops egress, manages room
│   │
│   ├── polymarket/              # Polymarket API integration
│   │   ├── __init__.py
│   │   ├── client.py            # API client for Gamma/CLOB
│   │   ├── market_selector.py   # Logic for selecting candidate markets
│   │   └── models.py            # Pydantic models for market data
│   │
│   ├── twitch/                  # Twitch integration
│   │   ├── __init__.py
│   │   ├── chat_bot.py          # TMI.js wrapper or TwitchIO bot
│   │   ├── voting.py            # Vote collection and tallying
│   │   └── overlay.py           # (Optional) Overlay data for stream
│   │
│   └── utils/
│       ├── __init__.py
│       ├── config.py            # Configuration loading
│       └── logging.py           # Logging setup
│
├── overlays/                     # Custom stream overlay templates
│   ├── index.html               # Main overlay (voting UI, market display)
│   ├── styles.css
│   └── overlay.js
│
├── scripts/
│   ├── start_stream.sh          # Shell script to start everything
│   └── test_components.py       # Test individual integrations
│
└── README.md
```

---

## Environment variables and configuration

```env
# .env file

# === LiveKit Configuration ===
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=APIxxxxxxxxx
LIVEKIT_API_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# === ElevenLabs Configuration ===
ELEVEN_API_KEY=sk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
HOST_1_VOICE_ID=21m00Tcm4TlvDq8ikWAM      # "Rachel" - energetic female
HOST_2_VOICE_ID=AZnzlk1XvdvUeBnXmlld      # "Domi" - confident male

# === OpenAI (for conversation generation) ===
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# === Twitch Configuration ===
TWITCH_CLIENT_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWITCH_CLIENT_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWITCH_OAUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWITCH_CHANNEL_NAME=your_channel_name
TWITCH_STREAM_KEY=live_xxxxxxxxx_xxxxxxxxxxxxxxxxxxxxxxx

# === Stream Settings ===
DISCUSSION_DURATION_SECONDS=300   # 5 minutes per market
VOTING_DURATION_SECONDS=60        # 1 minute voting window
ROOM_NAME=polymarket-ai-show
```

---

## Dependencies and package requirements

**requirements.txt** (Python):
```
# LiveKit
livekit-agents>=1.0.0
livekit-api>=0.6.0
livekit-plugins-openai>=0.8.0
livekit-plugins-elevenlabs>=0.8.0
livekit-plugins-silero>=0.6.0

# OpenAI
openai>=1.0.0

# Polymarket
requests>=2.31.0
pydantic>=2.0.0

# Twitch (Python option)
twitchio>=2.8.0

# Utilities
python-dotenv>=1.0.0
asyncio>=3.4.3
aiohttp>=3.9.0
```

**package.json** (Node.js for Twitch chat - alternative):
```json
{
  "name": "polymarket-twitch-chat",
  "dependencies": {
    "tmi.js": "^1.8.5",
    "dotenv": "^16.3.1",
    "ws": "^8.14.0"
  }
}
```

---

## Step-by-step implementation guide

### Step 1: Set up LiveKit and ElevenLabs integration

The core pattern uses LiveKit's Agents framework with the ElevenLabs plugin for voice synthesis. Each AI host runs as a separate agent worker.

**src/agents/agent_config.py**:
```python
from dataclasses import dataclass

@dataclass
class HostPersonality:
    name: str
    voice_id: str
    system_prompt: str
    speaking_style: str

HOST_MAX = HostPersonality(
    name="Mad Money Max",
    voice_id="21m00Tcm4TlvDq8ikWAM",
    system_prompt="""You are "Mad Money Max", an energetic and opinionated AI host 
    discussing prediction markets. You're bullish, enthusiastic, and use trading 
    floor language like "BUY BUY BUY!" and "This is HUGE!". You challenge your 
    co-host Ben and defend your market positions passionately. Keep responses 
    to 2-3 sentences. Be entertaining and dramatic.""",
    speaking_style="energetic, bullish, uses exclamations"
)

HOST_BEN = HostPersonality(
    name="Bull Bear Ben", 
    voice_id="AZnzlk1XvdvUeBnXmlld",
    system_prompt="""You are "Bull Bear Ben", a skeptical and analytical AI host.
    You play devil's advocate, question assumptions, and bring up counter-arguments.
    You use phrases like "But have you considered..." and "The data suggests otherwise".
    Keep responses to 2-3 sentences. Challenge Max's enthusiasm with facts.""",
    speaking_style="analytical, skeptical, measured"
)
```

**src/agents/host_max.py**:
```python
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
```

### Step 2: Implement the conversation orchestrator

The orchestrator generates the back-and-forth dialogue and sends it to each agent.

**src/orchestrator/conversation.py**:
```python
import openai
from typing import AsyncGenerator, Tuple
import os

client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

async def generate_conversation(
    market_question: str,
    market_odds: dict,
    market_description: str,
    num_exchanges: int = 8
) -> AsyncGenerator[Tuple[str, str], None]:
    """Generate a back-and-forth conversation about a market.
    
    Yields: (speaker: "max" | "ben", dialogue: str)
    """
    
    conversation_history = []
    
    system_prompt = f"""You are a conversation writer for a Jim Cramer-style trading show.
    Write dialogue between two hosts discussing this prediction market:
    
    MARKET: {market_question}
    CURRENT ODDS: {market_odds}
    DESCRIPTION: {market_description}
    
    Rules:
    - Max is bullish and energetic, uses "BUY BUY BUY!" style language
    - Ben is skeptical and analytical, plays devil's advocate
    - Each line should be 1-3 sentences
    - Make it entertaining and dramatic
    - Reference specific odds and what they mean
    - Include trading floor energy and urgency
    
    Format each response as: SPEAKER: dialogue
    Example: MAX: This market is SCREAMING opportunity! 65% odds? That's basically free money!"""
    
    for i in range(num_exchanges):
        speaker = "max" if i % 2 == 0 else "ben"
        
        messages = [
            {"role": "system", "content": system_prompt},
            *conversation_history,
            {"role": "user", "content": f"Write {speaker.upper()}'s next line (exchange {i+1}/{num_exchanges})"}
        ]
        
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            max_tokens=150,
            temperature=0.9
        )
        
        dialogue = response.choices[0].message.content
        # Clean up the response
        dialogue = dialogue.replace(f"{speaker.upper()}:", "").strip()
        
        conversation_history.append({"role": "assistant", "content": f"{speaker.upper()}: {dialogue}"})
        
        yield (speaker, dialogue)
```

### Step 3: Implement Polymarket data fetching

**src/polymarket/client.py**:
```python
import requests
import json
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

class Market(BaseModel):
    id: str
    question: str
    slug: str
    description: str
    outcomes: List[str]
    outcome_prices: List[float]
    volume_24h: float
    liquidity: float
    end_date: Optional[datetime]
    category: Optional[str]
    token_ids: List[str]
    
    @property
    def formatted_odds(self) -> dict:
        """Return odds as percentage strings"""
        return {
            outcome: f"{price * 100:.1f}%"
            for outcome, price in zip(self.outcomes, self.outcome_prices)
        }

class PolymarketClient:
    GAMMA_BASE = "https://gamma-api.polymarket.com"
    CLOB_BASE = "https://clob.polymarket.com"
    
    def get_trending_markets(self, limit: int = 10) -> List[Market]:
        """Fetch trending markets sorted by 24h volume"""
        response = requests.get(
            f"{self.GAMMA_BASE}/markets",
            params={
                "closed": "false",
                "active": "true",
                "order": "volume24hr",
                "ascending": "false",
                "limit": limit
            }
        )
        response.raise_for_status()
        
        markets = []
        for m in response.json():
            try:
                markets.append(Market(
                    id=m["id"],
                    question=m["question"],
                    slug=m["slug"],
                    description=m.get("description", ""),
                    outcomes=json.loads(m.get("outcomes", "[]")),
                    outcome_prices=[float(p) for p in json.loads(m.get("outcomePrices", "[]"))],
                    volume_24h=float(m.get("volume24hr", 0)),
                    liquidity=float(m.get("liquidityNum", 0)),
                    end_date=m.get("endDate"),
                    category=m.get("category"),
                    token_ids=json.loads(m.get("clobTokenIds", "[]"))
                ))
            except Exception as e:
                print(f"Error parsing market: {e}")
                continue
        
        return markets
    
    def get_candidate_markets(self, exclude_ids: List[str] = None) -> List[Market]:
        """Get 2 candidate markets for voting, excluding recently discussed ones"""
        markets = self.get_trending_markets(limit=20)
        
        if exclude_ids:
            markets = [m for m in markets if m.id not in exclude_ids]
        
        # Return top 2 by volume
        return markets[:2]
    
    def get_live_price(self, token_id: str) -> Optional[float]:
        """Get real-time price from CLOB API"""
        try:
            response = requests.get(
                f"{self.CLOB_BASE}/midpoint",
                params={"token_id": token_id}
            )
            return float(response.json().get("mid", 0))
        except:
            return None
```

### Step 4: Implement Twitch chat voting

**src/twitch/voting.py** (using TwitchIO):
```python
import asyncio
from collections import defaultdict
from twitchio.ext import commands
import os

class VotingBot(commands.Bot):
    def __init__(self):
        super().__init__(
            token=os.environ['TWITCH_OAUTH_TOKEN'],
            prefix='!',
            initial_channels=[os.environ['TWITCH_CHANNEL_NAME']]
        )
        self.votes = {}  # user_id -> vote_option
        self.voting_open = False
        self.candidates = []  # List of candidate market names
        
    async def event_ready(self):
        print(f'✅ Twitch bot connected as {self.nick}')
    
    async def event_message(self, message):
        if message.echo:
            return
        
        if self.voting_open:
            content = message.content.lower().strip()
            
            # Accept: !vote 1, !vote 2, or just "1", "2"
            vote_option = None
            if content.startswith('!vote '):
                try:
                    vote_option = int(content.split()[1])
                except (ValueError, IndexError):
                    pass
            elif content in ['1', '2']:
                vote_option = int(content)
            
            if vote_option in [1, 2]:
                self.votes[message.author.id] = vote_option
                # Optional: acknowledge vote
                # await message.channel.send(f"@{message.author.name} voted for option {vote_option}!")
        
        await self.handle_commands(message)
    
    async def open_voting(self, candidates: list):
        """Start a voting round with 2 candidate markets"""
        self.votes.clear()
        self.candidates = candidates
        self.voting_open = True
        
        channel = self.get_channel(os.environ['TWITCH_CHANNEL_NAME'])
        await channel.send(
            f"🗳️ VOTE NOW! Type 1 or 2 in chat! "
            f"Option 1: {candidates[0]} | Option 2: {candidates[1]}"
        )
    
    async def close_voting(self) -> dict:
        """End voting and return results"""
        self.voting_open = False
        
        tally = defaultdict(int)
        for vote in self.votes.values():
            tally[vote] += 1
        
        total = len(self.votes)
        winner = max(tally.items(), key=lambda x: x[1])[0] if tally else 1
        
        result = {
            "winner": winner,
            "winner_market": self.candidates[winner - 1] if self.candidates else None,
            "tally": dict(tally),
            "total_votes": total
        }
        
        # Announce results
        channel = self.get_channel(os.environ['TWITCH_CHANNEL_NAME'])
        await channel.send(
            f"🏆 VOTING CLOSED! Winner: Option {winner} with {tally.get(winner, 0)} votes! "
            f"Total votes: {total}"
        )
        
        return result
```

### Step 5: Implement stream controller with RTMP egress

**src/orchestrator/stream_controller.py**:
```python
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
```

### Step 6: Main orchestrator loop

**src/orchestrator/main.py**:
```python
import asyncio
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

from .stream_controller import StreamController
from .conversation import generate_conversation
from ..polymarket.client import PolymarketClient, Market
from ..twitch.voting import VotingBot

load_dotenv()

class ShowOrchestrator:
    def __init__(self):
        self.stream_controller = StreamController()
        self.polymarket = PolymarketClient()
        self.twitch_bot = VotingBot()
        
        self.discussion_duration = int(os.getenv("DISCUSSION_DURATION_SECONDS", 300))
        self.voting_duration = int(os.getenv("VOTING_DURATION_SECONDS", 60))
        
        self.current_market: Market = None
        self.discussed_market_ids = []
        
    async def send_to_agent(self, agent_name: str, text: str):
        """Send text to a specific agent for TTS synthesis"""
        # Use LiveKit Data Messages or RPC to communicate with agents
        # This triggers the agent to speak the text
        await self.stream_controller.lkapi.room.send_data(
            api.SendDataRequest(
                room=self.stream_controller.room_name,
                data=text.encode(),
                destination_identities=[agent_name],
            )
        )
    
    async def run_discussion(self, market: Market):
        """Run a 5-minute discussion about a market"""
        print(f"\n🎙️ Starting discussion: {market.question}")
        
        # Generate and execute conversation
        async for speaker, dialogue in generate_conversation(
            market_question=market.question,
            market_odds=market.formatted_odds,
            market_description=market.description,
            num_exchanges=10  # ~30 sec each = 5 min total
        ):
            agent_name = "host-max" if speaker == "max" else "host-ben"
            await self.send_to_agent(agent_name, dialogue)
            
            # Wait for speech to complete (~30 seconds per exchange)
            await asyncio.sleep(30)
    
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
        await self.stream_controller.dispatch_agents()
        await asyncio.sleep(5)  # Wait for agents to connect
        await self.stream_controller.start_twitch_stream()
        
        # Start Twitch bot
        asyncio.create_task(self.twitch_bot.start())
        await asyncio.sleep(3)  # Wait for bot to connect
        
        # Get initial market
        initial_markets = self.polymarket.get_trending_markets(limit=1)
        self.current_market = initial_markets[0]
        
        try:
            while True:
                # Phase 1: Discussion (5 minutes)
                await self.run_discussion(self.current_market)
                self.discussed_market_ids.append(self.current_market.id)
                
                # Phase 2: Voting (1 minute)
                self.current_market = await self.run_voting_phase()
                
                # Brief transition
                await self.send_to_agent(
                    "host-max",
                    f"The people have spoken! Let's dive into: {self.current_market.question}!"
                )
                await asyncio.sleep(5)
                
        except KeyboardInterrupt:
            print("\n👋 Shutting down...")
        finally:
            await self.stream_controller.cleanup()

async def main():
    orchestrator = ShowOrchestrator()
    await orchestrator.run_show_loop()

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Key integration patterns summary

### ElevenLabs multi-voice streaming
The most efficient approach uses **separate WebSocket connections per voice** or LiveKit's built-in ElevenLabs plugin. Use `eleven_flash_v2_5` model for **75ms latency**—critical for live streaming.

```python
# Key settings for responsive voice
elevenlabs.TTS(
    voice_id="YOUR_VOICE_ID",
    model="eleven_flash_v2_5",  # Fastest model
    voice_settings=elevenlabs.VoiceSettings(
        stability=0.4,           # More expressive for entertainment
        similarity_boost=0.8,
    ),
)
```

### LiveKit room-based architecture
LiveKit handles all audio routing automatically. Agents publish audio tracks to the room, and RTMP Egress composites them for Twitch. The **RoomCompositeEgress** mixes all participant audio.

```python
# Egress encoding for Twitch
RoomCompositeEgressRequest(
    room_name="your-room",
    preset=EncodingOptionsPreset.H264_1080P_30,
    stream_outputs=[StreamOutput(
        protocol=StreamProtocol.RTMP,
        urls=["rtmp://live.twitch.tv/app/STREAM_KEY"]
    )]
)
```

### Polymarket data flow
Use **Gamma API** for market discovery (no auth required) and **CLOB API** for real-time prices. The `outcomePrices` field contains probability decimals (0.65 = 65% odds).

```python
# Fetch trending markets
GET https://gamma-api.polymarket.com/markets?closed=false&order=volume24hr&ascending=false&limit=10
```

### Twitch chat voting pattern
Use **TwitchIO** (Python) or **TMI.js** (Node.js) for IRC-based chat reading. Store votes by `user_id` for automatic deduplication.

```python
# One vote per user pattern
self.votes[message.author.id] = vote_option  # Overwrites previous vote
```

---

## Running the project

**Terminal 1 - Start Agent Worker (Host Max):**
```bash
cd src/agents
python host_max.py connect --room polymarket-ai-show
```

**Terminal 2 - Start Agent Worker (Host Ben):**
```bash
cd src/agents
python host_ben.py connect --room polymarket-ai-show
```

**Terminal 3 - Start Orchestrator:**
```bash
python -m src.orchestrator.main
```

The orchestrator will create the room, dispatch agents, start RTMP streaming, and begin the show loop automatically.

---

## Cost and rate limit considerations

| Service | Limit | Cost |
|---------|-------|------|
| **ElevenLabs** | Pro plan needed for concurrent streams | ~$99/month for 500K chars |
| **LiveKit Cloud** | Pay per participant-minute | ~$0.004/min per participant |
| **LiveKit Egress** | Included with Cloud | Billed by egress minutes |
| **Polymarket API** | ~1000 req/hour (public) | Free |
| **Twitch** | 20 chat messages/30 sec | Free |
| **OpenAI GPT-4o** | Standard rate limits | ~$5-15/1M tokens |

For a hackathon, **expect roughly $5-20 per hour of streaming** depending on conversation density and ElevenLabs usage.

---

## Conclusion

This architecture provides a complete, production-ready foundation for an AI-powered Twitch stream. The **LiveKit Agents framework** serves as the backbone, handling WebRTC audio transport and RTMP egress seamlessly. **ElevenLabs' low-latency models** enable responsive, natural-sounding hosts. **Polymarket's public API** provides rich prediction market data without authentication complexity. The modular design allows each component to be tested independently before integration.

For a hackathon, focus first on getting a single agent speaking to Twitch via egress, then add the second agent, then layer in Polymarket data and voting. The conversation generation with GPT-4o can be simplified initially with pre-written scripts to reduce complexity during development.