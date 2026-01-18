"""
Web-based voting server for Polymarket AI Stream.
Replaces Twitch chat voting with WebSocket-based voting from the website.
"""

import asyncio
import json
import os
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Set
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn


class ShowPhase(str, Enum):
    STARTING = "starting"
    DISCUSSION = "discussion"
    VOTING = "voting"
    TRANSITION = "transition"


@dataclass
class MarketInfo:
    """Market information for display"""
    id: str
    question: str
    odds: Dict[str, str]
    volume: str = ""
    
    def to_dict(self):
        return asdict(self)


@dataclass
class ShowState:
    """Current state of the show"""
    phase: ShowPhase = ShowPhase.STARTING
    current_market: Optional[MarketInfo] = None
    candidate_markets: List[MarketInfo] = field(default_factory=list)
    vote_tally: Dict[int, int] = field(default_factory=lambda: {1: 0, 2: 0})
    voting_ends_at: Optional[float] = None  # Unix timestamp
    current_speaker: Optional[str] = None  # "max" or "ben"
    markets_discussed: int = 0
    total_votes: int = 0
    
    def to_dict(self):
        return {
            "phase": self.phase.value,
            "current_market": self.current_market.to_dict() if self.current_market else None,
            "candidate_markets": [m.to_dict() for m in self.candidate_markets],
            "vote_tally": self.vote_tally,
            "voting_ends_at": self.voting_ends_at,
            "current_speaker": self.current_speaker,
            "markets_discussed": self.markets_discussed,
            "total_votes": self.total_votes,
        }


class WebVotingServer:
    """
    WebSocket-based voting server for the streaming website.
    Handles real-time state broadcasting and vote collection.
    """
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8080):
        self.host = host
        self.port = port
        self.state = ShowState()
        self.votes: Dict[str, int] = {}  # ip/session -> vote option
        self.connected_clients: Set[WebSocket] = set()
        self.voting_open = False
        self.candidates: List[str] = []
        self._server_task: Optional[asyncio.Task] = None
        self._app: Optional[FastAPI] = None
        
    def _create_app(self) -> FastAPI:
        """Create FastAPI application"""
        
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            print(f"✅ Web voting server starting on http://{self.host}:{self.port}")
            yield
            print("⏹️ Web voting server shutting down")
        
        app = FastAPI(
            title="Polymarket AI Stream - Voting Server",
            lifespan=lifespan
        )
        
        # CORS for website access
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # TODO: Restrict in production
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        @app.get("/state")
        async def get_state():
            """Get current show state"""
            return self.state.to_dict()
        
        @app.post("/vote")
        async def cast_vote(request: Request):
            """Cast a vote via HTTP POST"""
            if not self.voting_open:
                return {"success": False, "error": "Voting is not open"}
            
            try:
                body = await request.json()
                option = body.get("option")
                
                if option not in [1, 2]:
                    return {"success": False, "error": "Invalid option. Use 1 or 2."}
                
                # Use IP for vote deduplication
                client_ip = request.client.host if request.client else "unknown"
                
                # Record vote (overwrites previous)
                self.votes[client_ip] = option
                
                # Update tally
                self._update_tally()
                
                # Broadcast update
                await self._broadcast_state()
                
                return {
                    "success": True,
                    "option": option,
                    "tally": self.state.vote_tally,
                    "total": len(self.votes)
                }
                
            except Exception as e:
                return {"success": False, "error": str(e)}
        
        @app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket connection for real-time updates"""
            await websocket.accept()
            self.connected_clients.add(websocket)
            
            try:
                # Send current state immediately
                await websocket.send_json({
                    "type": "state",
                    "data": self.state.to_dict()
                })
                
                # Keep connection alive and handle incoming votes
                while True:
                    try:
                        data = await asyncio.wait_for(
                            websocket.receive_json(),
                            timeout=30.0
                        )
                        
                        if data.get("type") == "vote" and self.voting_open:
                            option = data.get("option")
                            if option in [1, 2]:
                                # Use websocket id for dedup
                                client_id = str(id(websocket))
                                self.votes[client_id] = option
                                self._update_tally()
                                await self._broadcast_state()
                                
                        elif data.get("type") == "ping":
                            await websocket.send_json({"type": "pong"})
                            
                    except asyncio.TimeoutError:
                        # Send ping to keep connection alive
                        await websocket.send_json({"type": "ping"})
                        
            except WebSocketDisconnect:
                pass
            except Exception as e:
                print(f"WebSocket error: {e}")
            finally:
                self.connected_clients.discard(websocket)
        
        return app
    
    def _update_tally(self):
        """Update vote tally from votes dict"""
        tally = {1: 0, 2: 0}
        for vote in self.votes.values():
            tally[vote] = tally.get(vote, 0) + 1
        self.state.vote_tally = tally
    
    async def _broadcast_state(self):
        """Broadcast current state to all connected clients"""
        if not self.connected_clients:
            return
            
        message = json.dumps({
            "type": "state",
            "data": self.state.to_dict()
        })
        
        disconnected = set()
        for ws in self.connected_clients:
            try:
                await ws.send_text(message)
            except Exception:
                disconnected.add(ws)
        
        # Remove disconnected clients
        self.connected_clients -= disconnected
    
    async def start(self):
        """Start the voting server in background"""
        self._app = self._create_app()
        
        config = uvicorn.Config(
            self._app,
            host=self.host,
            port=self.port,
            log_level="warning"
        )
        server = uvicorn.Server(config)
        self._server_task = asyncio.create_task(server.serve())
        
        # Wait a moment for server to start
        await asyncio.sleep(0.5)
        print(f"✅ Voting server running at http://{self.host}:{self.port}")
    
    async def stop(self):
        """Stop the voting server"""
        if self._server_task:
            self._server_task.cancel()
            try:
                await self._server_task
            except asyncio.CancelledError:
                pass
    
    # --- VotingBot-compatible interface ---
    
    def get_current_tally(self) -> Dict[int, int]:
        """Get current vote counts"""
        return dict(self.state.vote_tally)
    
    async def open_voting(self, candidates: List[str]):
        """Start a voting round with 2 candidate markets"""
        self.votes.clear()
        self.candidates = candidates
        self.voting_open = True
        self.state.vote_tally = {1: 0, 2: 0}
        self.state.phase = ShowPhase.VOTING
        self.state.voting_ends_at = asyncio.get_event_loop().time() + 60  # 60 seconds
        
        print(f"🗳️ Voting opened: 1) {candidates[0][:40]}... | 2) {candidates[1][:40]}...")
        
        await self._broadcast_state()
    
    async def close_voting(self) -> dict:
        """End voting and return results"""
        self.voting_open = False
        self.state.phase = ShowPhase.TRANSITION
        self.state.voting_ends_at = None
        
        tally = self.get_current_tally()
        total = len(self.votes)
        
        # Default to option 1 if no votes or tie
        if not tally or tally.get(1, 0) == tally.get(2, 0):
            winner = 1
        else:
            winner = max(tally.items(), key=lambda x: x[1])[0]
        
        self.state.total_votes += total
        
        result = {
            "winner": winner,
            "winner_market": self.candidates[winner - 1] if self.candidates else None,
            "tally": tally,
            "total_votes": total
        }
        
        print(f"🏆 Voting closed! Winner: Option {winner} ({tally.get(winner, 0)} votes). Total: {total}")
        
        await self._broadcast_state()
        
        return result
    
    # --- State update methods ---
    
    async def update_current_market(self, market_id: str, question: str, odds: Dict[str, str], volume: str = ""):
        """Update the current market being discussed"""
        self.state.current_market = MarketInfo(
            id=market_id,
            question=question,
            odds=odds,
            volume=volume
        )
        self.state.phase = ShowPhase.DISCUSSION
        await self._broadcast_state()
    
    async def update_candidates(self, candidates: List[dict]):
        """Update candidate markets for voting"""
        self.state.candidate_markets = [
            MarketInfo(
                id=c.get("id", ""),
                question=c.get("question", ""),
                odds=c.get("odds", {}),
                volume=c.get("volume", "")
            )
            for c in candidates
        ]
        await self._broadcast_state()
    
    async def update_speaker(self, speaker: str):
        """Update which host is currently speaking"""
        self.state.current_speaker = speaker
        await self._broadcast_state()
    
    async def increment_markets_discussed(self):
        """Increment the count of markets discussed"""
        self.state.markets_discussed += 1
        await self._broadcast_state()


# For standalone testing
if __name__ == "__main__":
    async def main():
        server = WebVotingServer(port=8080)
        await server.start()
        
        # Keep running
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            await server.stop()
    
    asyncio.run(main())
