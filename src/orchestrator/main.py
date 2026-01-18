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