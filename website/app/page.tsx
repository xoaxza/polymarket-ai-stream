"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { Room, RoomEvent, Track, RemoteTrack, RemoteTrackPublication } from "livekit-client";

// Types for show state
interface MarketInfo {
    id: string;
    question: string;
    odds: Record<string, string>;
    volume: string;
}

interface ShowState {
    phase: "starting" | "discussion" | "voting" | "transition";
    current_market: MarketInfo | null;
    candidate_markets: MarketInfo[];
    vote_tally: { 1: number; 2: number };
    voting_ends_at: number | null;
    current_speaker: "max" | "ben" | null;
    markets_discussed: number;
    total_votes: number;
}

// Environment configuration
const VOTING_SERVER_URL = process.env.VOTING_SERVER_URL || "http://localhost:8080";
const VOTING_WS_URL = VOTING_SERVER_URL.replace("http://", "ws://").replace("https://", "wss://") + "/ws";

export default function StreamPage() {
    // Show state
    const [state, setState] = useState<ShowState>({
        phase: "starting",
        current_market: null,
        candidate_markets: [],
        vote_tally: { 1: 0, 2: 0 },
        voting_ends_at: null,
        current_speaker: null,
        markets_discussed: 0,
        total_votes: 0,
    });

    // Voting
    const [selectedVote, setSelectedVote] = useState<1 | 2 | null>(null);
    const [hasVoted, setHasVoted] = useState(false);
    const [votingTimeLeft, setVotingTimeLeft] = useState<number>(0);

    // Audio
    const [volume, setVolume] = useState(80);
    const [isMuted, setIsMuted] = useState(false);
    const [audioEnabled, setAudioEnabled] = useState(false);
    const [trackCount, setTrackCount] = useState(0);
    const audioElementsRef = useRef<HTMLAudioElement[]>([]);
    const attachedTracksRef = useRef<Set<string>>(new Set());
    const roomRef = useRef<Room | null>(null);

    // WebSocket connection
    const wsRef = useRef<WebSocket | null>(null);
    const [isConnected, setIsConnected] = useState(false);
    const [isConnecting, setIsConnecting] = useState(true);

    // Connect to WebSocket for state updates
    useEffect(() => {
        const connectWebSocket = () => {
            try {
                const ws = new WebSocket(VOTING_WS_URL);

                ws.onopen = () => {
                    console.log("Connected to voting server");
                    setIsConnected(true);
                    setIsConnecting(false);
                };

                ws.onmessage = (event) => {
                    try {
                        const message = JSON.parse(event.data);
                        if (message.type === "state") {
                            setState(message.data);

                            // Reset vote when new voting round starts
                            if (message.data.phase === "voting" && state.phase !== "voting") {
                                setSelectedVote(null);
                                setHasVoted(false);
                            }
                        }
                    } catch (e) {
                        console.error("Error parsing WebSocket message:", e);
                    }
                };

                ws.onclose = () => {
                    console.log("Disconnected from voting server");
                    setIsConnected(false);
                    setTimeout(connectWebSocket, 3000);
                };

                ws.onerror = (error) => {
                    console.error("WebSocket error:", error);
                    setIsConnecting(false);
                };

                wsRef.current = ws;
            } catch (e) {
                console.error("Failed to connect to WebSocket:", e);
                setIsConnecting(false);
                setTimeout(connectWebSocket, 3000);
            }
        };

        connectWebSocket();

        return () => {
            if (wsRef.current) {
                wsRef.current.close();
            }
        };
    }, []);

    // Connect to LiveKit room for audio
    useEffect(() => {
        const connectToLiveKit = async () => {
            try {
                // Get token from our API
                const tokenResponse = await fetch("/api/livekit-token");
                if (!tokenResponse.ok) {
                    console.error("Failed to get LiveKit token");
                    return;
                }

                const { token, url } = await tokenResponse.json();
                console.log("Got LiveKit token, connecting to:", url);

                // Create room and connect
                const room = new Room({
                    adaptiveStream: true,
                    dynacast: true,
                });

                // Helper to attach audio track (only host tracks, no duplicates)
                const attachAudioTrack = (track: RemoteTrack, trackName: string) => {
                    // Skip if already attached
                    if (attachedTracksRef.current.has(track.sid)) {
                        console.log("Skipping duplicate track:", track.sid, trackName);
                        return;
                    }

                    // Only attach host-max-audio and host-ben-audio, skip centralized "podcast-audio" track
                    if (trackName === "podcast-audio") {
                        console.log("Skipping centralized track:", trackName);
                        return;
                    }

                    console.log("Attaching audio track:", track.sid, trackName);
                    attachedTracksRef.current.add(track.sid);

                    const audioElement = track.attach();
                    audioElement.volume = volume / 100;
                    audioElement.autoplay = true;
                    audioElement.style.display = "none";

                    audioElement.play().catch((e) => {
                        console.log("Autoplay blocked:", e.message);
                    });

                    audioElementsRef.current.push(audioElement);
                    document.body.appendChild(audioElement);
                    setTrackCount(prev => prev + 1);
                };

                // Handle track subscriptions
                room.on(RoomEvent.TrackSubscribed, (track: RemoteTrack, publication: RemoteTrackPublication) => {
                    if (track.kind === Track.Kind.Audio) {
                        attachAudioTrack(track, publication.trackName || "");
                    }
                });

                room.on(RoomEvent.TrackUnsubscribed, (track: RemoteTrack) => {
                    console.log("Unsubscribed from track:", track.sid);
                    attachedTracksRef.current.delete(track.sid);
                    const elements = track.detach();
                    elements.forEach((el) => el.remove());
                    setTrackCount(prev => Math.max(0, prev - 1));
                });

                room.on(RoomEvent.Connected, () => {
                    console.log("Connected to LiveKit room, participants:", room.remoteParticipants.size);

                    // Check for existing tracks
                    room.remoteParticipants.forEach((participant) => {
                        participant.audioTrackPublications.forEach((pub) => {
                            if (pub.track && pub.track.kind === Track.Kind.Audio) {
                                attachAudioTrack(pub.track as RemoteTrack, pub.trackName || "");
                            }
                        });
                    });
                });

                room.on(RoomEvent.Disconnected, () => {
                    console.log("Disconnected from LiveKit room");
                });

                room.on(RoomEvent.ParticipantConnected, (participant) => {
                    console.log("Participant connected:", participant.identity);
                });

                await room.connect(url, token);
                roomRef.current = room;
                console.log("LiveKit connection established");

            } catch (e) {
                console.error("Failed to connect to LiveKit:", e);
            }
        };

        connectToLiveKit();

        return () => {
            // Cleanup audio elements
            audioElementsRef.current.forEach((el) => {
                el.pause();
                el.remove();
            });
            audioElementsRef.current = [];
            attachedTracksRef.current.clear();

            if (roomRef.current) {
                roomRef.current.disconnect();
            }
        };
    }, []);

    // Enable audio on user interaction (for autoplay policy)
    const enableAudio = useCallback(() => {
        setAudioEnabled(true);
        audioElementsRef.current.forEach((el) => {
            el.muted = false;
            el.volume = volume / 100;
            el.play().catch((e) => console.log("Play failed:", e.message));
        });

        // Also try to resume audio context if needed
        if (roomRef.current) {
            roomRef.current.startAudio().catch(() => { });
        }
    }, [volume]);

    // Update audio volume
    useEffect(() => {
        audioElementsRef.current.forEach((el) => {
            el.volume = isMuted ? 0 : volume / 100;
        });
    }, [volume, isMuted]);

    // Voting timer countdown
    useEffect(() => {
        if (state.voting_ends_at && state.phase === "voting") {
            const updateTimer = () => {
                const now = Date.now() / 1000;
                const remaining = Math.max(0, Math.floor(state.voting_ends_at! - now));
                setVotingTimeLeft(remaining);
            };

            updateTimer();
            const interval = setInterval(updateTimer, 1000);
            return () => clearInterval(interval);
        } else {
            setVotingTimeLeft(0);
        }
    }, [state.voting_ends_at, state.phase]);

    // Cast vote
    const castVote = useCallback(async (option: 1 | 2) => {
        if (hasVoted) return;

        setSelectedVote(option);

        try {
            const response = await fetch(`${VOTING_SERVER_URL}/vote`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ option }),
            });

            if (response.ok) {
                setHasVoted(true);
            }

            if (wsRef.current?.readyState === WebSocket.OPEN) {
                wsRef.current.send(JSON.stringify({ type: "vote", option }));
            }
        } catch (e) {
            console.error("Failed to cast vote:", e);
        }
    }, [hasVoted]);

    // Calculate vote percentages
    const totalVotes = state.vote_tally[1] + state.vote_tally[2];
    const vote1Percent = totalVotes > 0 ? (state.vote_tally[1] / totalVotes) * 100 : 50;
    const vote2Percent = totalVotes > 0 ? (state.vote_tally[2] / totalVotes) * 100 : 50;

    // Format odds nicely
    const formatOdds = (odds: Record<string, string> | undefined) => {
        if (!odds) return { yes: "—", no: "—" };
        const entries = Object.entries(odds);
        if (entries.length >= 2) {
            return { yes: entries[0][1], no: entries[1][1] };
        }
        return { yes: entries[0]?.[1] || "—", no: "—" };
    };

    const currentOdds = formatOdds(state.current_market?.odds);

    return (
        <div className="main-container">
            {/* Header */}
            <header className="header">
                <div className="logo">
                    <span className="logo-icon">📈</span>
                    <span className="logo-text">POLYMARKET AI SHOW</span>
                </div>
                <div className="live-badge">
                    <span className="live-dot"></span>
                    LIVE
                </div>
            </header>

            {/* Connection warning */}
            {!isConnected && !isConnecting && (
                <div className="connection-banner">
                    <span className="connection-icon">⚠️</span>
                    <span className="connection-text">
                        Connecting to server... Make sure the voting server is running on port 8080.
                    </span>
                </div>
            )}

            {/* Main content */}
            <div className="content-grid">
                {/* Left side - Market info */}
                <div className="market-section">
                    {/* Current Market */}
                    <div className="market-card">
                        <div className="market-label">Currently Discussing</div>
                        <h1 className="market-question">
                            {state.current_market?.question || "Waiting for market..."}
                        </h1>
                        <div className="market-odds">
                            <div className="odds-item">
                                <div className="odds-label">Yes</div>
                                <div className="odds-value yes">{currentOdds.yes}</div>
                            </div>
                            <div className="odds-item">
                                <div className="odds-label">No</div>
                                <div className="odds-value no">{currentOdds.no}</div>
                            </div>
                        </div>
                    </div>

                    {/* Hosts */}
                    <div className="hosts-container">
                        <div className={`host-card max ${state.current_speaker === "max" ? "speaking" : ""}`}>
                            <div className="host-emoji">🐂</div>
                            <div className="host-name">MAD MONEY MAX</div>
                            <div className="host-style">Bullish • Energetic</div>
                        </div>
                        <div className={`host-card ben ${state.current_speaker === "ben" ? "speaking" : ""}`}>
                            <div className="host-emoji">🐻</div>
                            <div className="host-name">BULL BEAR BEN</div>
                            <div className="host-style">Skeptical • Analytical</div>
                        </div>
                    </div>

                    {/* Audio Player */}
                    <div className="audio-player">
                        <div className="audio-status">
                            <div className={`audio-indicator ${trackCount === 0 ? "disconnected" : ""}`}></div>
                            <span className="audio-label">
                                {trackCount > 0 ? `${trackCount} Audio Track${trackCount > 1 ? "s" : ""}` : "Connecting..."}
                            </span>
                        </div>

                        {/* Enable Audio Button */}
                        {!audioEnabled && trackCount > 0 && (
                            <button
                                onClick={enableAudio}
                                style={{
                                    background: "var(--gradient-primary)",
                                    border: "none",
                                    borderRadius: "8px",
                                    padding: "10px 20px",
                                    color: "white",
                                    fontWeight: "700",
                                    cursor: "pointer",
                                    fontSize: "14px",
                                    animation: "pulse 1.5s ease infinite",
                                }}
                            >
                                🔊 Click to Enable Audio
                            </button>
                        )}

                        {audioEnabled && (
                            <div className="volume-control">
                                <button
                                    className="mute-button"
                                    onClick={() => setIsMuted(!isMuted)}
                                >
                                    {isMuted ? "🔇" : "🔊"}
                                </button>
                                <input
                                    type="range"
                                    className="volume-slider"
                                    min="0"
                                    max="100"
                                    value={volume}
                                    onChange={(e) => setVolume(Number(e.target.value))}
                                />
                            </div>
                        )}
                    </div>
                </div>

                {/* Right side - Voting */}
                <div className="voting-sidebar">
                    {state.phase === "voting" && state.candidate_markets.length >= 2 ? (
                        <div className="voting-card">
                            <div className="voting-header">
                                <div className="voting-title">
                                    <span className="voting-icon">🗳️</span>
                                    <span className="voting-text">VOTE NOW!</span>
                                </div>
                                <div className={`voting-timer ${votingTimeLeft <= 10 ? "urgent" : ""}`}>
                                    {votingTimeLeft}s
                                </div>
                            </div>

                            <div className="vote-options">
                                <button
                                    className={`vote-button ${selectedVote === 1 ? "selected" : ""}`}
                                    onClick={() => castVote(1)}
                                    disabled={hasVoted && selectedVote !== 1}
                                >
                                    <div className="vote-button-header">
                                        <div className="vote-number">1</div>
                                        <div className="vote-question">
                                            {state.candidate_markets[0]?.question || "Option 1"}
                                        </div>
                                    </div>
                                    <div className="vote-progress">
                                        <div className="vote-progress-fill" style={{ width: `${vote1Percent}%` }}></div>
                                    </div>
                                    <div className="vote-count">
                                        {state.vote_tally[1]} votes ({vote1Percent.toFixed(0)}%)
                                    </div>
                                </button>

                                <button
                                    className={`vote-button ${selectedVote === 2 ? "selected" : ""}`}
                                    onClick={() => castVote(2)}
                                    disabled={hasVoted && selectedVote !== 2}
                                >
                                    <div className="vote-button-header">
                                        <div className="vote-number">2</div>
                                        <div className="vote-question">
                                            {state.candidate_markets[1]?.question || "Option 2"}
                                        </div>
                                    </div>
                                    <div className="vote-progress">
                                        <div className="vote-progress-fill" style={{ width: `${vote2Percent}%` }}></div>
                                    </div>
                                    <div className="vote-count">
                                        {state.vote_tally[2]} votes ({vote2Percent.toFixed(0)}%)
                                    </div>
                                </button>
                            </div>

                            {hasVoted && (
                                <div style={{ textAlign: "center", color: "var(--color-success)", fontSize: "14px" }}>
                                    ✓ Your vote has been recorded!
                                </div>
                            )}
                        </div>
                    ) : (
                        <div className="waiting-card">
                            <div className="waiting-icon">⏳</div>
                            <div className="waiting-title">
                                {state.phase === "starting"
                                    ? "Show Starting..."
                                    : state.phase === "transition"
                                        ? "Loading Next Market..."
                                        : "Discussion in Progress"}
                            </div>
                            <div className="waiting-subtitle">
                                Voting opens 1 minute before market change
                            </div>
                        </div>
                    )}

                    {/* Stats */}
                    <div className="stats-card">
                        <div className="stats-grid">
                            <div className="stat-item">
                                <div className="stat-label">Markets</div>
                                <div className="stat-value">{state.markets_discussed}</div>
                            </div>
                            <div className="stat-item">
                                <div className="stat-label">Total Votes</div>
                                <div className="stat-value">{state.total_votes}</div>
                            </div>
                            <div className="stat-item">
                                <div className="stat-label">Phase</div>
                                <div className="stat-value" style={{ fontSize: "14px", textTransform: "capitalize" }}>
                                    {state.phase}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
