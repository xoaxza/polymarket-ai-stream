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

export default function BloombergTerminal() {
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

    // Current time
    const [currentTime, setCurrentTime] = useState("");

    // Update time every second
    useEffect(() => {
        const updateTime = () => {
            const now = new Date();
            setCurrentTime(now.toLocaleTimeString('en-US', {
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit',
                hour12: true
            }).toUpperCase());
        };
        updateTime();
        const interval = setInterval(updateTime, 1000);
        return () => clearInterval(interval);
    }, []);

    // Connect to WebSocket for state updates
    useEffect(() => {
        const connectWebSocket = () => {
            try {
                const ws = new WebSocket(VOTING_WS_URL);

                ws.onopen = () => {
                    console.log("Connected to voting server");
                    setIsConnected(true);
                };

                ws.onmessage = (event) => {
                    try {
                        const message = JSON.parse(event.data);
                        if (message.type === "state") {
                            setState(message.data);
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
                    setIsConnected(false);
                    setTimeout(connectWebSocket, 3000);
                };

                ws.onerror = () => setIsConnected(false);
                wsRef.current = ws;
            } catch (e) {
                setTimeout(connectWebSocket, 3000);
            }
        };

        connectWebSocket();
        return () => { if (wsRef.current) wsRef.current.close(); };
    }, []);

    // Connect to LiveKit room for audio
    useEffect(() => {
        const connectToLiveKit = async () => {
            try {
                const tokenResponse = await fetch("/api/livekit-token");
                if (!tokenResponse.ok) return;

                const { token, url } = await tokenResponse.json();
                const room = new Room({ adaptiveStream: true, dynacast: true });

                const attachAudioTrack = (track: RemoteTrack, trackName: string) => {
                    if (attachedTracksRef.current.has(track.sid)) return;
                    if (trackName === "podcast-audio") return;

                    attachedTracksRef.current.add(track.sid);
                    const audioElement = track.attach();
                    audioElement.volume = volume / 100;
                    audioElement.autoplay = true;
                    audioElement.style.display = "none";
                    audioElement.play().catch(() => { });
                    audioElementsRef.current.push(audioElement);
                    document.body.appendChild(audioElement);
                    setTrackCount(prev => prev + 1);
                };

                room.on(RoomEvent.TrackSubscribed, (track: RemoteTrack, pub: RemoteTrackPublication) => {
                    if (track.kind === Track.Kind.Audio) attachAudioTrack(track, pub.trackName || "");
                });

                room.on(RoomEvent.TrackUnsubscribed, (track: RemoteTrack) => {
                    attachedTracksRef.current.delete(track.sid);
                    track.detach().forEach(el => el.remove());
                    setTrackCount(prev => Math.max(0, prev - 1));
                });

                room.on(RoomEvent.Connected, () => {
                    room.remoteParticipants.forEach(p => {
                        p.audioTrackPublications.forEach(pub => {
                            if (pub.track?.kind === Track.Kind.Audio) {
                                attachAudioTrack(pub.track as RemoteTrack, pub.trackName || "");
                            }
                        });
                    });
                });

                await room.connect(url, token);
                roomRef.current = room;
            } catch (e) {
                console.error("LiveKit error:", e);
            }
        };

        connectToLiveKit();
        return () => {
            audioElementsRef.current.forEach(el => { el.pause(); el.remove(); });
            audioElementsRef.current = [];
            attachedTracksRef.current.clear();
            roomRef.current?.disconnect();
        };
    }, []);

    // Enable audio
    const enableAudio = useCallback(() => {
        setAudioEnabled(true);
        audioElementsRef.current.forEach(el => {
            el.muted = false;
            el.volume = volume / 100;
            el.play().catch(() => { });
        });
        roomRef.current?.startAudio().catch(() => { });
    }, [volume]);

    // Update volume
    useEffect(() => {
        audioElementsRef.current.forEach(el => {
            el.volume = isMuted ? 0 : volume / 100;
        });
    }, [volume, isMuted]);

    // Voting timer
    useEffect(() => {
        if (state.voting_ends_at && state.phase === "voting") {
            const updateTimer = () => {
                const remaining = Math.max(0, Math.floor(state.voting_ends_at! - Date.now() / 1000));
                setVotingTimeLeft(remaining);
            };
            updateTimer();
            const interval = setInterval(updateTimer, 1000);
            return () => clearInterval(interval);
        }
        setVotingTimeLeft(0);
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
            if (response.ok) setHasVoted(true);
            wsRef.current?.send(JSON.stringify({ type: "vote", option }));
        } catch (e) {
            console.error("Vote failed:", e);
        }
    }, [hasVoted]);

    // Calculate vote percentages
    const totalVotes = state.vote_tally[1] + state.vote_tally[2];
    const vote1Pct = totalVotes > 0 ? (state.vote_tally[1] / totalVotes) * 100 : 50;
    const vote2Pct = totalVotes > 0 ? (state.vote_tally[2] / totalVotes) * 100 : 50;

    // Format odds
    const getOdds = (odds?: Record<string, string>) => {
        if (!odds) return { yes: "--", no: "--" };
        const entries = Object.entries(odds);
        return {
            yes: entries[0]?.[1] || "--",
            no: entries[1]?.[1] || "--"
        };
    };
    const odds = getOdds(state.current_market?.odds);

    // Ticker data (mock for now, would come from state)
    const tickerItems = state.candidate_markets.length > 0
        ? state.candidate_markets.map(m => ({
            symbol: m.question.substring(0, 30).toUpperCase(),
            value: Object.values(m.odds || {})[0] || "--"
        }))
        : [
            { symbol: "AWAITING MARKET DATA", value: "--" },
        ];

    return (
        <div className="crt-container">
            <div className="terminal">
                {/* Top Function Bar */}
                <div className="function-bar">
                    <div className="function-keys">
                        <button className="fn-key active">&lt;F1&gt; MARKET</button>
                        <button className="fn-key">&lt;F2&gt; VOTE</button>
                        <button className="fn-key">&lt;F3&gt; HOSTS</button>
                        <button className="fn-key">&lt;F4&gt; AUDIO</button>
                    </div>
                    <div className="ticker-container">
                        <div className="ticker">
                            {[...tickerItems, ...tickerItems].map((item, i) => (
                                <span key={i} className="ticker-item">
                                    <span className="symbol">{item.symbol}:</span>{" "}
                                    <span className="up">{item.value}</span>
                                </span>
                            ))}
                        </div>
                    </div>
                </div>

                {/* Main Grid */}
                <div className="main-grid">
                    {/* Left Panel - Max */}
                    <div className="panel host-panel">
                        <div className="panel-header">HOST TERMINAL 1</div>
                        <div className="host-label bull">
                            MAD MONEY MAX
                            <span className={`host-indicator ${state.current_speaker === "max" ? "host-speaking" : ""}`}>
                                {state.current_speaker === "max" ? "LIVE" : "BULL"}
                            </span>
                        </div>
                        <pre style={{ color: "#00AA2A", fontSize: "10px", marginBottom: "8px" }}>
                            {`    ^__^
    (oo)\\_______
    (__)\\       )\\/\\
        ||----w |
        ||     ||`}
                        </pre>
                        <div className="transcript-box">
                            <p>INITIATING BULLISH ANALYSIS PROTOCOL...</p>
                            <p>MARKET SENTIMENT: EXTREMELY BULLISH</p>
                            <p>RECOMMENDATION: BUY BUY BUY</p>
                            <span className="cursor-blink"></span>
                        </div>
                    </div>

                    {/* Center Panel - Market Quote */}
                    <div className="panel quote-panel">
                        <div className="panel-header">POLYMARKET QUOTE TERMINAL</div>

                        <div className="market-quote">
                            <div className="market-header">
                                <div className="market-question glow-amber">
                                    {state.current_market?.question || "AWAITING MARKET DATA..."}
                                </div>
                                <div className="market-last">
                                    <div className="market-last-label">LAST</div>
                                    <div className="glow">{odds.yes} / {odds.no}</div>
                                </div>
                            </div>

                            <div className="quote-grid">
                                <div className="quote-row">
                                    <span className="quote-label">YES</span>
                                    <span className="quote-yes glow">{odds.yes}</span>
                                    <span className="quote-change up">+0.0</span>
                                    <span className="quote-vol">VOL: {state.current_market?.volume || "--"}</span>
                                </div>
                                <div className="quote-row">
                                    <span className="quote-label">NO</span>
                                    <span className="quote-no">{odds.no}</span>
                                    <span className="quote-change down">-0.0</span>
                                    <span className="quote-vol">LIQ: HIGH</span>
                                </div>
                            </div>
                        </div>

                        {/* Stats */}
                        <div className="stats-grid">
                            <div className="stat-item">
                                <div className="stat-label">MARKETS</div>
                                <div className="stat-value glow">{state.markets_discussed}</div>
                            </div>
                            <div className="stat-item">
                                <div className="stat-label">TOTAL VOTES</div>
                                <div className="stat-value glow">{state.total_votes}</div>
                            </div>
                            <div className="stat-item">
                                <div className="stat-label">PHASE</div>
                                <div className="stat-value" style={{ color: state.phase === "voting" ? "#FFAA00" : "#00FF41" }}>
                                    {state.phase.toUpperCase()}
                                </div>
                            </div>
                        </div>

                        {/* Audio Panel */}
                        <div className="audio-panel" style={{ marginTop: "16px" }}>
                            <div className="panel-header">AUDIO FEED</div>
                            <div className="waveform">
                                {[...Array(16)].map((_, i) => (
                                    <div
                                        key={i}
                                        className="wave-bar"
                                        style={{
                                            height: `${trackCount > 0 && audioEnabled ? 8 + Math.random() * 16 : 4}px`,
                                            animationDelay: `${i * 0.05}s`
                                        }}
                                    ></div>
                                ))}
                                <span className={`audio-status ${trackCount > 0 ? "connected" : "disconnected"}`}>
                                    {trackCount > 0 ? `CONNECTED [${trackCount} TRACKS]` : "CONNECTING..."}
                                </span>
                            </div>
                            <div className="audio-controls">
                                {!audioEnabled && trackCount > 0 ? (
                                    <button className="audio-btn" onClick={enableAudio}>
                                        [ENABLE AUDIO]
                                    </button>
                                ) : (
                                    <>
                                        <button
                                            className={`audio-btn ${!isMuted ? "enabled" : ""}`}
                                            onClick={() => setIsMuted(!isMuted)}
                                        >
                                            {isMuted ? "[UNMUTE]" : "[MUTE]"}
                                        </button>
                                        <input
                                            type="range"
                                            className="volume-slider"
                                            min="0"
                                            max="100"
                                            value={volume}
                                            onChange={(e) => setVolume(Number(e.target.value))}
                                        />
                                        <span style={{ width: "40px" }}>{volume}%</span>
                                    </>
                                )}
                            </div>
                        </div>
                    </div>

                    {/* Right Panel - Vote Queue + Ben */}
                    <div className="panel vote-panel">
                        <div className="panel-header">
                            <span>VOTE QUEUE</span>
                            {state.phase === "voting" && (
                                <span className="vote-timer">{votingTimeLeft}s</span>
                            )}
                        </div>

                        {state.phase === "voting" && state.candidate_markets.length >= 2 ? (
                            <>
                                <div className="vote-prompt">*** VOTE NOW ***</div>
                                <div className="vote-queue">
                                    <div
                                        className={`vote-option ${selectedVote === 1 ? "selected" : ""}`}
                                        onClick={() => castVote(1)}
                                    >
                                        <div className="vote-option-header">
                                            <span className="vote-number">1&gt;</span>
                                            <span className="vote-question">
                                                {state.candidate_markets[0]?.question}
                                            </span>
                                        </div>
                                        <div className="vote-stats">
                                            <span>VOTES: {state.vote_tally[1]}</span>
                                            <span>({vote1Pct.toFixed(0)}%)</span>
                                        </div>
                                        <div className="vote-bar">
                                            <div className="vote-bar-fill" style={{ width: `${vote1Pct}%` }}></div>
                                        </div>
                                    </div>

                                    <div
                                        className={`vote-option ${selectedVote === 2 ? "selected" : ""}`}
                                        onClick={() => castVote(2)}
                                    >
                                        <div className="vote-option-header">
                                            <span className="vote-number">2&gt;</span>
                                            <span className="vote-question">
                                                {state.candidate_markets[1]?.question}
                                            </span>
                                        </div>
                                        <div className="vote-stats">
                                            <span>VOTES: {state.vote_tally[2]}</span>
                                            <span>({vote2Pct.toFixed(0)}%)</span>
                                        </div>
                                        <div className="vote-bar">
                                            <div className="vote-bar-fill" style={{ width: `${vote2Pct}%` }}></div>
                                        </div>
                                    </div>
                                </div>

                                {hasVoted && (
                                    <div className="vote-confirmed">
                                        VOTE REGISTERED FOR OPTION {selectedVote}
                                    </div>
                                )}
                            </>
                        ) : (
                            <div className="waiting-panel">
                                <div className="waiting-text">
                                    {state.phase === "starting" ? "INITIALIZING..." :
                                        state.phase === "transition" ? "LOADING MARKET..." :
                                            "DISCUSSION IN PROGRESS"}
                                </div>
                                <div className="waiting-subtext">
                                    VOTE QUEUE OPENS T-60 SEC BEFORE MARKET CHANGE
                                </div>
                            </div>
                        )}

                        {/* Ben Panel */}
                        <div style={{ marginTop: "16px" }}>
                            <div className="host-label bear">
                                BULL BEAR BEN
                                <span className={`host-indicator ${state.current_speaker === "ben" ? "host-speaking" : ""}`}>
                                    {state.current_speaker === "ben" ? "LIVE" : "BEAR"}
                                </span>
                            </div>
                            <pre style={{ color: "#CC2222", fontSize: "10px", marginBottom: "8px" }}>
                                {`  _,-""-,_
 /\`      \`\\
|  (o)(o)  |
|    __    |
 \\  \\__/  /
  \`-,__,-\``}
                            </pre>
                            <div className="transcript-box" style={{ maxHeight: "150px" }}>
                                <p>INITIATING BEARISH COUNTER-ANALYSIS...</p>
                                <p>WARNING: EXTREME SKEPTICISM DETECTED</p>
                                <p>RECOMMENDATION: EXERCISE CAUTION</p>
                                <span className="cursor-blink"></span>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Bottom Status Bar */}
                <div className="status-bar">
                    <div className="status-section">
                        <div className="status-item">
                            <span className="status-label">PHASE:</span>
                            <span className={`status-value ${state.phase === "voting" ? "voting" : ""}`}>
                                {state.phase.toUpperCase()}
                            </span>
                        </div>
                        <div className="status-item">
                            <span className="status-label">MARKETS:</span>
                            <span className="status-value">{state.markets_discussed}</span>
                        </div>
                        <div className="status-item">
                            <span className="status-label">VOTES:</span>
                            <span className="status-value">{state.total_votes}</span>
                        </div>
                        <div className="status-item">
                            <span className="status-label">AUDIO:</span>
                            <span className="status-value" style={{ color: trackCount > 0 ? "#00FF41" : "#FF3333" }}>
                                {trackCount > 0 ? "CONNECTED" : "OFFLINE"}
                            </span>
                        </div>
                    </div>
                    <div className="status-section">
                        <div className="status-item">
                            <span className="status-label">WS:</span>
                            <span className="status-value" style={{ color: isConnected ? "#00FF41" : "#FF3333" }}>
                                {isConnected ? "ONLINE" : "OFFLINE"}
                            </span>
                        </div>
                        <div className="status-item">
                            <span className="status-label">TIME:</span>
                            <span className="status-value">{currentTime}</span>
                            <span className="status-cursor"></span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
