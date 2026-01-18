#!/bin/bash
# Start script for Polymarket AI Show
# Run this from the project root directory

echo "🚀 Starting Polymarket AI Show..."
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "⚠️  Virtual environment not found. Creating one..."
    python -m venv venv
    source venv/Scripts/activate  # Windows
    pip install -r requirements.txt
else
    source venv/Scripts/activate  # Windows
fi

# Install Python dependencies if needed
echo "📦 Checking Python dependencies..."
pip install -r requirements.txt --quiet

# Start the orchestrator
echo "🎙️ Starting AI Show orchestrator..."
echo "   - Voting server: http://localhost:8080"
echo "   - Website: http://localhost:3000 (run 'cd website && npm run dev' in another terminal)"
echo ""
python -m src.orchestrator.main
