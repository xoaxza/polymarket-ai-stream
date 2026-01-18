import asyncio
from typing import Optional, Callable, Awaitable
from .voting import VotingBot
from ..utils.logging import get_logger

logger = get_logger(__name__)


class TwitchChatBot:
    """High-level wrapper for Twitch chat integration"""
    
    def __init__(self):
        self.voting_bot = VotingBot()
        self._task: Optional[asyncio.Task] = None
        self._running = False
    
    async def start(self) -> None:
        """Start the Twitch bot in the background"""
        if self._running:
            logger.warning("Bot is already running")
            return
        
        self._running = True
        self._task = asyncio.create_task(self._run_bot())
        
        # Wait for bot to be ready
        await self.voting_bot.wait_until_ready()
        logger.info("Twitch chat bot started and ready")
    
    async def _run_bot(self) -> None:
        """Run the bot (internal)"""
        try:
            await self.voting_bot.start()
        except Exception as e:
            logger.error(f"Bot error: {e}")
            self._running = False
    
    async def stop(self) -> None:
        """Stop the Twitch bot"""
        if not self._running:
            return
        
        self._running = False
        await self.voting_bot.close()
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        logger.info("Twitch chat bot stopped")
    
    async def run_voting_round(
        self,
        candidate_1: str,
        candidate_2: str,
        duration_seconds: int = 60,
        on_progress: Optional[Callable[[dict], Awaitable[None]]] = None
    ) -> dict:  # FIXED: Changed from VoteResult to dict
        """Run a complete voting round"""
        # Open voting
        await self.voting_bot.open_voting([candidate_1, candidate_2])
        
        # Wait for voting duration, optionally sending progress updates
        elapsed = 0
        update_interval = 15  # Send update every 15 seconds
        
        while elapsed < duration_seconds:
            wait_time = min(update_interval, duration_seconds - elapsed)
            await asyncio.sleep(wait_time)
            elapsed += wait_time
            
            if on_progress and elapsed < duration_seconds:
                tally = self.voting_bot.get_current_tally()
                await on_progress({
                    "elapsed": elapsed,
                    "remaining": duration_seconds - elapsed,
                    "tally": tally,
                    "total_votes": sum(tally.values())
                })
        
        # Close voting and get results
        result = await self.voting_bot.close_voting()
        return result
    
    async def send_message(self, message: str) -> None:
        """Send a message to chat"""
        await self.voting_bot.send_announcement(message)
    
    async def announce_market(self, market_question: str, odds: dict) -> None:
        """Announce the current market being discussed"""
        odds_str = " | ".join([f"{k}: {v}" for k, v in odds.items()])
        await self.send_message(
            f"📈 NOW DISCUSSING: {market_question} | {odds_str}"
        )
    
    async def countdown(self, seconds: int = 10) -> None:
        """Send a countdown in chat"""
        for i in range(seconds, 0, -1):
            if i <= 5 or i == 10:
                await self.send_message(f"⏰ {i}...")
            await asyncio.sleep(1)