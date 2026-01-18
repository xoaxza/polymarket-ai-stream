#!/bin/bash

# Polymarket AI Stream - Startup Script
# This script starts all components needed for the stream

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "🚀 Starting Polymarket AI Stream..."

# Check for .env file
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo "❌ Error: .env file not found!"
    echo "   Copy .env.example to .env and fill in your credentials"
    exit 1
fi

# Load environment variables
export $(grep -v '^#' "$PROJECT_DIR/.env" | xargs)

# Check for required environment variables
required_vars=(
    "LIVEKIT_URL"
    "LIVEKIT_API_KEY"
    "LIVEKIT_API_SECRET"
    "ELEVEN_API_KEY"
    "OPENAI_API_KEY"
    "TWITCH_OAUTH_TOKEN"
    "TWITCH_CHANNEL_NAME"
    "TWITCH_STREAM_KEY"
)

missing_vars=()
for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        missing_vars+=("$var")
    fi
done

if [ ${#missing_vars[@]} -ne 0 ]; then
    echo "❌ Error: Missing required environment variables:"
    for var in "${missing_vars[@]}"; do
        echo "   - $var"
    done
    exit 1
fi

echo "✅ Environment variables loaded"

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "🛑 Shutting down..."
    
    # Kill background processes
    if [ ! -z "$MAX_PID" ]; then
        kill $MAX_PID 2>/dev/null || true
    fi
    if [ ! -z "$BEN_PID" ]; then
        kill $BEN_PID 2>/dev/null || true
    fi
    if [ ! -z "$ORCH_PID" ]; then
        kill $ORCH_PID 2>/dev/null || true
    fi
    
    echo "👋 Goodbye!"
    exit 0
}

trap cleanup SIGINT SIGTERM

# Activate virtual environment if it exists
if [ -d "$PROJECT_DIR/venv" ]; then
    source "$PROJECT_DIR/venv/bin/activate"
    echo "✅ Virtual environment activated"
fi

cd "$PROJECT_DIR"

# Start Agent Host Max in background
echo "🎙️ Starting Host Max agent..."
python -m src.agents.host_max connect --room "${ROOM_NAME:-polymarket-ai-show}" &
MAX_PID=$!

# Wait a moment for first agent
sleep 2

# Start Agent Host Ben in background
echo "🎙️ Starting Host Ben agent..."
python -m src.agents.host_ben connect --room "${ROOM_NAME:-polymarket-ai-show}" &
BEN_PID=$!

# Wait for agents to initialize
sleep 3

# Start the main orchestrator
echo "🎬 Starting orchestrator..."
python -m src.orchestrator.main &
ORCH_PID=$!

echo ""
echo "============================================"
echo "  🎉 Polymarket AI Show is LIVE!            "
echo "============================================"
echo ""
echo "  Twitch Channel: ${TWITCH_CHANNEL_NAME}"
echo "  LiveKit Room:   ${ROOM_NAME:-polymarket-ai-show}"
echo ""
echo "  Press Ctrl+C to stop the stream"
echo ""

# Wait for orchestrator to finish
wait $ORCH_PID
