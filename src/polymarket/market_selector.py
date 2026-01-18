from typing import List, Optional, Tuple
from .client import PolymarketClient
from .models import Market, VotingCandidate
from ..utils.logging import get_logger
import random

logger = get_logger(__name__)


class MarketSelector:
    """Logic for selecting and managing candidate markets for voting"""
    
    def __init__(self, client: Optional[PolymarketClient] = None):
        self.client = client or PolymarketClient()
        self.discussed_market_ids: List[str] = []
        self.max_history = 20  # Keep track of last 20 discussed markets
    
    def mark_as_discussed(self, market_id: str) -> None:
        """Mark a market as discussed to avoid repeating it"""
        self.discussed_market_ids.append(market_id)
        # Keep only the most recent markets
        if len(self.discussed_market_ids) > self.max_history:
            self.discussed_market_ids = self.discussed_market_ids[-self.max_history:]
        logger.info(f"Marked market {market_id} as discussed")
    
    def clear_history(self) -> None:
        """Clear the discussion history"""
        self.discussed_market_ids.clear()
        logger.info("Cleared discussion history")
    
    def get_voting_candidates(self) -> Tuple[VotingCandidate, VotingCandidate]:
        """Get 2 candidate markets for voting, excluding recently discussed ones"""
        markets = self.client.get_trending_markets(limit=20)
        
        # Filter out recently discussed markets
        available_markets = [
            m for m in markets 
            if m.id not in self.discussed_market_ids
        ]
        
        # If we've discussed too many, reset and use all
        if len(available_markets) < 2:
            logger.warning("Running low on candidate markets, clearing history")
            self.clear_history()
            available_markets = markets
        
        # Return top 2 by volume as voting candidates
        candidates = available_markets[:2]
        
        return (
            VotingCandidate.from_market(candidates[0], 1),
            VotingCandidate.from_market(candidates[1], 2)
        )
    
    def get_diverse_candidates(self) -> Tuple[VotingCandidate, VotingCandidate]:
        """Get 2 candidate markets from different categories for variety"""
        markets = self.client.get_trending_markets(limit=30)
        
        # Filter out recently discussed
        available = [m for m in markets if m.id not in self.discussed_market_ids]
        
        if len(available) < 2:
            self.clear_history()
            available = markets
        
        # Try to get markets from different categories
        first = available[0]
        second = None
        
        for m in available[1:]:
            if m.category != first.category:
                second = m
                break
        
        # Fallback to just the second highest volume if no different category found
        if second is None:
            second = available[1]
        
        return (
            VotingCandidate.from_market(first, 1),
            VotingCandidate.from_market(second, 2)
        )
    
    def get_initial_market(self) -> Market:
        """Get the first market to start the show with"""
        markets = self.client.get_trending_markets(limit=5)
        
        if not markets:
            raise RuntimeError("Could not fetch any markets from Polymarket")
        
        # Return the highest volume market
        market = markets[0]
        logger.info(f"Selected initial market: {market.question}")
        return market
    
    def get_random_candidate(self) -> Market:
        """Get a random market from trending (for variety)"""
        markets = self.client.get_trending_markets(limit=20)
        available = [m for m in markets if m.id not in self.discussed_market_ids]
        
        if not available:
            self.clear_history()
            available = markets
        
        return random.choice(available[:10])  # Random from top 10
