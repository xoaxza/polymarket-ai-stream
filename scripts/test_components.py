#!/usr/bin/env python3
"""
Test script for individual components of the Polymarket AI Stream.
Run specific tests to verify each integration is working.
"""

import asyncio
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()


async def test_polymarket():
    """Test Polymarket API integration"""
    print("\n🔍 Testing Polymarket API...")
    
    from src.polymarket.client import PolymarketClient
    
    client = PolymarketClient()
    
    # Test fetching trending markets
    markets = client.get_trending_markets(limit=5)
    
    if not markets:
        print("❌ Failed to fetch markets")
        return False
    
    print(f"✅ Fetched {len(markets)} markets")
    
    # #region agent log
    import json
    log_path = r"c:\Users\Abdul\polymarketai\.cursor\debug.log"
    market_sample = markets[0] if markets else None
    if market_sample:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "A", "location": "test_components.py:33", "message": "Market class info", "data": {"market_class": str(type(market_sample)), "market_module": type(market_sample).__module__, "has_formatted_volume": hasattr(market_sample, "formatted_volume"), "has_formatted_odds": hasattr(market_sample, "formatted_odds"), "dir_attributes": [attr for attr in dir(market_sample) if not attr.startswith("_")]}}) + "\n")
    # #endregion
    
    for i, market in enumerate(markets, 1):
        print(f"\n  {i}. {market.question[:60]}...")
        print(f"     Odds: {market.formatted_odds}")
        # #region agent log
        if not hasattr(market, "formatted_volume"):
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({"timestamp": __import__("time").time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "A", "location": "test_components.py:38", "message": "formatted_volume attribute missing", "data": {"market_class": str(type(market)), "available_attrs": [attr for attr in dir(market) if not attr.startswith("_") and callable(getattr(market, attr, None)) == False]}}) + "\n")
        # #endregion
        print(f"     24h Volume: {market.formatted_volume}")
    
    return True


async def test_openai():
    """Test OpenAI API integration"""
    print("\n🤖 Testing OpenAI API...")
    
    import openai
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ OPENAI_API_KEY not set")
        return False
    
    client = openai.AsyncOpenAI(api_key=api_key)
    
    try:
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "user", "content": "Say 'OpenAI connection successful!' in 5 words or less."}
            ],
            max_tokens=20
        )
        
        result = response.choices[0].message.content
        print(f"✅ OpenAI response: {result}")
        return True
        
    except Exception as e:
        print(f"❌ OpenAI error: {e}")
        return False


async def test_conversation_generation():
    """Test conversation generation"""
    print("\n💬 Testing conversation generation...")
    
    from src.orchestrator.conversation import generate_conversation
    from src.polymarket.client import PolymarketClient
    
    # Get a real market to discuss
    client = PolymarketClient()
    markets = client.get_trending_markets(limit=1)
    
    if not markets:
        print("❌ Could not fetch market for testing")
        return False
    
    market = markets[0]
    print(f"   Testing with market: {market.question[:50]}...")
    
    exchanges = []
    async for speaker, dialogue in generate_conversation(
        market_question=market.question,
        market_odds=market.formatted_odds,
        market_description=market.description,
        num_exchanges=3  # Just 3 for testing
    ):
        exchanges.append((speaker, dialogue))
        print(f"\n   {speaker.upper()}: {dialogue}")
    
    if len(exchanges) >= 3:
        print(f"\n✅ Generated {len(exchanges)} exchanges successfully")
        return True
    else:
        print(f"\n❌ Only generated {len(exchanges)} exchanges")
        return False


async def test_elevenlabs():
    """Test ElevenLabs API (just verification, no actual TTS)"""
    print("\n🎤 Testing ElevenLabs API key...")
    
    import requests
    
    api_key = os.getenv("ELEVEN_API_KEY")
    if not api_key:
        print("❌ ELEVEN_API_KEY not set")
        return False
    
    try:
        response = requests.get(
            "https://api.elevenlabs.io/v1/user",
            headers={"xi-api-key": api_key}
        )
        
        if response.status_code == 200:
            user = response.json()
            print(f"✅ ElevenLabs connected as: {user.get('subscription', {}).get('tier', 'unknown')}")
            return True
        else:
            print(f"❌ ElevenLabs error: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ ElevenLabs error: {e}")
        return False


async def test_livekit():
    """Test LiveKit API connection"""
    print("\n📡 Testing LiveKit API...")
    
    url = os.getenv("LIVEKIT_URL")
    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")
    
    if not all([url, api_key, api_secret]):
        print("❌ Missing LiveKit credentials")
        return False
    
    try:
        from livekit import api
        
        lkapi = api.LiveKitAPI()
        
        # List rooms (this verifies the connection)
        rooms = await lkapi.room.list_rooms(api.ListRoomsRequest())
        
        print(f"✅ LiveKit connected! Found {len(rooms.rooms)} existing rooms")
        await lkapi.aclose()
        return True
        
    except Exception as e:
        print(f"❌ LiveKit error: {e}")
        return False


async def test_twitch_credentials():
    """Test Twitch credentials (doesn't actually connect)"""
    print("\n📺 Testing Twitch credentials...")
    
    oauth = os.getenv("TWITCH_OAUTH_TOKEN")
    channel = os.getenv("TWITCH_CHANNEL_NAME")
    stream_key = os.getenv("TWITCH_STREAM_KEY")
    
    missing = []
    if not oauth:
        missing.append("TWITCH_OAUTH_TOKEN")
    if not channel:
        missing.append("TWITCH_CHANNEL_NAME")
    if not stream_key:
        missing.append("TWITCH_STREAM_KEY")
    
    if missing:
        print(f"❌ Missing: {', '.join(missing)}")
        return False
    
    print(f"✅ Twitch credentials present for channel: {channel}")
    return True


async def test_config():
    """Test configuration loading"""
    print("\n⚙️ Testing configuration...")
    
    from src.utils.config import get_config
    
    config = get_config()
    errors = config.validate()
    
    if errors:
        print("❌ Configuration errors:")
        for error in errors:
            print(f"   - {error}")
        return False
    
    print("✅ Configuration valid")
    print(f"   Room name: {config.stream.room_name}")
    print(f"   Discussion duration: {config.stream.discussion_duration}s")
    print(f"   Voting duration: {config.stream.voting_duration}s")
    return True


async def run_all_tests():
    """Run all tests"""
    print("=" * 50)
    print("  POLYMARKET AI STREAM - COMPONENT TESTS")
    print("=" * 50)
    
    results = {}
    
    # Test each component
    results["Config"] = await test_config()
    results["Polymarket API"] = await test_polymarket()
    results["OpenAI API"] = await test_openai()
    results["ElevenLabs API"] = await test_elevenlabs()
    results["LiveKit API"] = await test_livekit()
    results["Twitch Credentials"] = await test_twitch_credentials()
    results["Conversation Gen"] = await test_conversation_generation()
    
    # Summary
    print("\n" + "=" * 50)
    print("  TEST SUMMARY")
    print("=" * 50)
    
    passed = 0
    failed = 0
    
    for name, result in results.items():
        status = "✅" if result else "❌"
        print(f"  {status} {name}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"\n  Total: {passed} passed, {failed} failed")
    print("=" * 50)
    
    return failed == 0


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test components")
    parser.add_argument("--component", "-c", 
                       choices=["polymarket", "openai", "elevenlabs", "livekit", "twitch", "config", "conversation", "all"],
                       default="all",
                       help="Which component to test")
    
    args = parser.parse_args()
    
    if args.component == "all":
        success = asyncio.run(run_all_tests())
    elif args.component == "polymarket":
        success = asyncio.run(test_polymarket())
    elif args.component == "openai":
        success = asyncio.run(test_openai())
    elif args.component == "elevenlabs":
        success = asyncio.run(test_elevenlabs())
    elif args.component == "livekit":
        success = asyncio.run(test_livekit())
    elif args.component == "twitch":
        success = asyncio.run(test_twitch_credentials())
    elif args.component == "config":
        success = asyncio.run(test_config())
    elif args.component == "conversation":
        success = asyncio.run(test_conversation_generation())
    
    sys.exit(0 if success else 1)
