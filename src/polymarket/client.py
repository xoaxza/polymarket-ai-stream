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