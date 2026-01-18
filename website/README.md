# Polymarket AI Show - Streaming Website

A custom streaming website for watching the Polymarket AI Show with two AI hosts debating prediction markets. Viewers can vote for the next market to discuss!

## Features

- 🎧 **Live Audio Streaming** via LiveKit
- 🗳️ **Real-time Voting** - Choose the next market to discuss
- 📊 **Live Market Data** from Polymarket
- 🐂🐻 **Two AI Hosts** - Mad Money Max (bullish) and Bull Bear Ben (skeptical)
- ✨ **Premium UI** with glassmorphism and smooth animations

## Setup

1. Install dependencies:
   ```bash
   npm install
   ```

2. Copy `.env.example` to `.env.local` and fill in your credentials:
   ```bash
   cp .env.example .env.local
   ```

3. Start the development server:
   ```bash
   npm run dev
   ```

4. Open [http://localhost:3000](http://localhost:3000)

## Environment Variables

- `LIVEKIT_URL` - Your LiveKit server URL
- `LIVEKIT_API_KEY` - LiveKit API key
- `LIVEKIT_API_SECRET` - LiveKit API secret
- `ROOM_NAME` - LiveKit room name (should match orchestrator)
- `VOTING_SERVER_URL` - Python voting server URL (default: http://localhost:8080)

## Running the Full System

1. **Start the Python orchestrator** (from project root):
   ```bash
   python -m src.orchestrator.main
   ```

2. **Start the website** (from website directory):
   ```bash
   npm run dev
   ```

3. **Open the website** at http://localhost:3000

The AI hosts will start discussing markets, and you can vote for the next market when the voting phase begins!
