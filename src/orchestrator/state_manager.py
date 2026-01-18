from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Optional, List
from ..polymarket.models import Market
from ..utils.logging import get_logger

logger = get_logger(__name__)


class ShowPhase(Enum):
    """Current phase of the show"""
    STARTING = auto()       # Initial setup
    DISCUSSION = auto()     # Hosts discussing a market
    VOTING = auto()         # Chat voting on next market
    TRANSITION = auto()     # Brief transition between markets
    PAUSED = auto()         # Show is paused
    ENDED = auto()          # Show has ended


@dataclass
class ShowState:
    """Represents the current state of the show"""
    phase: ShowPhase = ShowPhase.STARTING
    current_market: Optional[Market] = None
    phase_start_time: datetime = field(default_factory=datetime.now)
    discussion_number: int = 0
    total_votes_cast: int = 0
    discussed_market_ids: List[str] = field(default_factory=list)
    
    @property
    def phase_elapsed_seconds(self) -> float:
        """Seconds elapsed in current phase"""
        return (datetime.now() - self.phase_start_time).total_seconds()
    
    @property
    def is_active(self) -> bool:
        """Whether the show is currently active"""
        return self.phase not in [ShowPhase.PAUSED, ShowPhase.ENDED]


class StateManager:
    """Manages show state and phase transitions"""
    
    def __init__(
        self,
        discussion_duration: int = 300,
        voting_duration: int = 60,
        transition_duration: int = 10
    ):
        self.discussion_duration = discussion_duration
        self.voting_duration = voting_duration
        self.transition_duration = transition_duration
        self.state = ShowState()
        self._listeners = []
    
    def add_listener(self, callback) -> None:
        """Add a callback to be notified of state changes"""
        self._listeners.append(callback)
    
    async def _notify_listeners(self) -> None:
        """Notify all listeners of state change"""
        for listener in self._listeners:
            try:
                if asyncio.iscoroutinefunction(listener):
                    await listener(self.state)
                else:
                    listener(self.state)
            except Exception as e:
                logger.error(f"Error notifying listener: {e}")
    
    def start_show(self, initial_market: Market) -> None:
        """Start the show with an initial market"""
        self.state.phase = ShowPhase.DISCUSSION
        self.state.current_market = initial_market
        self.state.phase_start_time = datetime.now()
        self.state.discussion_number = 1
        logger.info(f"Show started with market: {initial_market.question[:50]}...")
    
    def start_discussion(self, market: Market) -> None:
        """Start discussing a new market"""
        self.state.phase = ShowPhase.DISCUSSION
        self.state.current_market = market
        self.state.phase_start_time = datetime.now()
        self.state.discussion_number += 1
        
        if market.id not in self.state.discussed_market_ids:
            self.state.discussed_market_ids.append(market.id)
        
        logger.info(f"Started discussion #{self.state.discussion_number}: {market.question[:50]}...")
    
    def start_voting(self) -> None:
        """Transition to voting phase"""
        self.state.phase = ShowPhase.VOTING
        self.state.phase_start_time = datetime.now()
        logger.info("Voting phase started")
    
    def start_transition(self) -> None:
        """Start brief transition between markets"""
        self.state.phase = ShowPhase.TRANSITION
        self.state.phase_start_time = datetime.now()
        logger.info("Transition phase started")
    
    def end_show(self) -> None:
        """End the show"""
        self.state.phase = ShowPhase.ENDED
        logger.info(f"Show ended after {self.state.discussion_number} discussions")
    
    def pause_show(self) -> None:
        """Pause the show"""
        self.state.phase = ShowPhase.PAUSED
        logger.info("Show paused")
    
    def resume_show(self) -> None:
        """Resume from pause"""
        if self.state.current_market:
            self.state.phase = ShowPhase.DISCUSSION
        else:
            self.state.phase = ShowPhase.STARTING
        self.state.phase_start_time = datetime.now()
        logger.info("Show resumed")
    
    def record_votes(self, count: int) -> None:
        """Record vote count from a voting round"""
        self.state.total_votes_cast += count
    
    def get_time_remaining(self) -> float:
        """Get seconds remaining in current phase"""
        if self.state.phase == ShowPhase.DISCUSSION:
            duration = self.discussion_duration
        elif self.state.phase == ShowPhase.VOTING:
            duration = self.voting_duration
        elif self.state.phase == ShowPhase.TRANSITION:
            duration = self.transition_duration
        else:
            return 0
        
        remaining = duration - self.state.phase_elapsed_seconds
        return max(0, remaining)
    
    def should_transition(self) -> bool:
        """Check if current phase should end"""
        return self.get_time_remaining() <= 0
    
    def get_status_summary(self) -> dict:
        """Get a summary of current show status"""
        return {
            "phase": self.state.phase.name,
            "current_market": self.state.current_market.question if self.state.current_market else None,
            "discussion_number": self.state.discussion_number,
            "phase_elapsed": self.state.phase_elapsed_seconds,
            "time_remaining": self.get_time_remaining(),
            "total_votes": self.state.total_votes_cast,
            "markets_discussed": len(self.state.discussed_market_ids)
        }


# Need to import asyncio for notify_listeners
import asyncio
