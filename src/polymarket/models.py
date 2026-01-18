from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class MarketOutcome(BaseModel):
    """Represents a single outcome in a prediction market"""
    name: str
    price: float  # Probability as decimal (0.65 = 65%)
    token_id: Optional[str] = None
    
    @property
    def percentage(self) -> str:
        """Return price as formatted percentage string"""
        return f"{self.price * 100:.1f}%"


class Market(BaseModel):
    """Represents a Polymarket prediction market"""
    id: str
    question: str
    slug: str
    description: str = ""
    outcomes: List[str] = Field(default_factory=list)
    outcome_prices: List[float] = Field(default_factory=list)
    volume_24h: float = 0.0
    liquidity: float = 0.0
    end_date: Optional[datetime] = None
    category: Optional[str] = None
    token_ids: List[str] = Field(default_factory=list)
    
    @property
    def formatted_odds(self) -> dict:
        """Return odds as percentage strings"""
        return {
            outcome: f"{price * 100:.1f}%"
            for outcome, price in zip(self.outcomes, self.outcome_prices)
        }
    
    @property
    def market_outcomes(self) -> List[MarketOutcome]:
        """Get list of MarketOutcome objects"""
        outcomes = []
        for i, (name, price) in enumerate(zip(self.outcomes, self.outcome_prices)):
            token_id = self.token_ids[i] if i < len(self.token_ids) else None
            outcomes.append(MarketOutcome(name=name, price=price, token_id=token_id))
        return outcomes
    
    @property
    def short_question(self) -> str:
        """Return truncated question for display"""
        if len(self.question) <= 50:
            return self.question
        return self.question[:47] + "..."
    
    @property
    def formatted_volume(self) -> str:
        """Return human-readable volume"""
        if self.volume_24h >= 1_000_000:
            return f"${self.volume_24h / 1_000_000:.1f}M"
        elif self.volume_24h >= 1_000:
            return f"${self.volume_24h / 1_000:.1f}K"
        return f"${self.volume_24h:.0f}"
    
    def get_summary(self) -> str:
        """Get a brief summary for display"""
        odds_str = " | ".join([f"{o}: {p}" for o, p in self.formatted_odds.items()])
        return f"{self.question}\n📊 {odds_str}\n💰 24h Volume: {self.formatted_volume}"


class VotingCandidate(BaseModel):
    """Represents a market as a voting candidate"""
    option_number: int  # 1 or 2
    market: Market
    display_name: str
    
    @classmethod
    def from_market(cls, market: Market, option_number: int) -> "VotingCandidate":
        return cls(
            option_number=option_number,
            market=market,
            display_name=market.short_question
        )
