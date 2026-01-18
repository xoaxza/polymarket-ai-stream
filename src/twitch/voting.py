import asyncio
from collections import defaultdict
from twitchio.ext import commands
import os

class VotingBot(commands.Bot):
    def __init__(self):
        # TwitchIO v3.x requires bot_id (the numeric user ID of the bot account)
        super().__init__(
            token=os.environ['TWITCH_OAUTH_TOKEN'],
            client_id=os.environ['TWITCH_CLIENT_ID'],
            client_secret=os.environ['TWITCH_CLIENT_SECRET'],
            bot_id=os.environ.get('TWITCH_BOT_ID', ''),  # Bot's numeric user ID
            prefix='!',
            initial_channels=[os.environ['TWITCH_CHANNEL_NAME']]
        )
        self.votes = {}  # user_id -> vote_option
        self.voting_open = False
        self.candidates = []  # List of candidate market names
        self._channel = None  # Cached channel reference
        
    async def event_ready(self):
        # Get bot username - try multiple attributes for compatibility
        try:
            bot_name = self.nick
        except AttributeError:
            try:
                bot_name = self.user.name if self.user else 'bot'
            except AttributeError:
                bot_name = 'bot'
        print(f'✅ Twitch bot connected as {bot_name}')
        
        # Cache the channel reference when bot is ready
        self._channel = self._get_channel()
        if self._channel:
            print(f'   ✅ Channel reference cached: {self._channel.name}')
    
    async def event_message(self, message):
        if message.echo:
            return
        
        # Cache channel reference from message if we don't have it yet
        if not self._channel and hasattr(message, 'channel') and message.channel:
            self._channel = message.channel
            print(f'   ✅ Channel reference cached from message: {self._channel.name}')
        
        if self.voting_open:
            content = message.content.lower().strip()
            
            # Accept: !vote 1, !vote 2, or just "1", "2"
            vote_option = None
            if content.startswith('!vote '):
                try:
                    vote_option = int(content.split()[1])
                except (ValueError, IndexError):
                    pass
            elif content in ['1', '2']:
                try:
                    vote_option = int(content)
                except ValueError:
                    pass
            
            if vote_option in [1, 2]:
                self.votes[message.author.id] = vote_option
                # Optional: acknowledge vote
                # await message.channel.send(f"@{message.author.name} voted for option {vote_option}!")
        
        await self.handle_commands(message)
    
    def get_current_tally(self) -> dict:
        """Get current vote counts while voting is open"""
        tally = defaultdict(int)
        for vote in self.votes.values():
            tally[vote] += 1
        return dict(tally)
    
    def _get_channel(self):
        """Get the Twitch channel - try multiple methods for compatibility"""
        # First, try cached channel reference
        if self._channel:
            return self._channel
        
        channel_name = os.environ['TWITCH_CHANNEL_NAME']
        
        # Try different methods to get the channel
        # Method 1: connected_channels list (if it exists)
        if hasattr(self, 'connected_channels') and self.connected_channels:
            # connected_channels is a list, get first one
            return self.connected_channels[0]
        
        # Method 2: get_channel method (if it exists)
        if hasattr(self, 'get_channel'):
            try:
                channel = self.get_channel(channel_name)
                if channel:
                    return channel
            except:
                pass
        
        # Method 3: Try lowercase version
        if hasattr(self, 'get_channel'):
            try:
                channel = self.get_channel(channel_name.lower())
                if channel:
                    return channel
            except:
                pass
        
        # Method 4: Try accessing channels attribute directly
        if hasattr(self, 'channels'):
            try:
                # channels might be a dict or list
                if isinstance(self.channels, dict):
                    return self.channels.get(channel_name) or self.channels.get(channel_name.lower())
                elif isinstance(self.channels, list) and self.channels:
                    return self.channels[0]
            except:
                pass
        
        return None
    
    async def send_announcement(self, message: str):
        """Send a message to the Twitch channel"""
        channel = self._get_channel()
        if channel:
            try:
                await channel.send(message)
            except Exception as e:
                print(f"⚠️ Could not send announcement: {e}")
        else:
            print(f"⚠️ Could not get channel to send announcement")
    
    async def open_voting(self, candidates: list):
        """Start a voting round with 2 candidate markets"""
        self.votes.clear()
        self.candidates = candidates
        self.voting_open = True
        
        channel = self._get_channel()
        if channel:
            try:
                await channel.send(
                    f"🗳️ VOTE NOW! Type 1 or 2 in chat! "
                    f"Option 1: {candidates[0]} | Option 2: {candidates[1]}"
                )
            except Exception as e:
                print(f"⚠️ Could not send voting message: {e}")
        else:
            print(f"⚠️ Could not get channel to open voting (voting still active, votes will be collected)")
    
    async def close_voting(self) -> dict:
        """End voting and return results"""
        self.voting_open = False
        
        tally = defaultdict(int)
        for vote in self.votes.values():
            tally[vote] += 1
        
        total = len(self.votes)
        # Default to option 1 if no votes
        if not tally:
            winner = 1
        else:
            winner = max(tally.items(), key=lambda x: x[1])[0]
        
        result = {
            "winner": winner,
            "winner_market": self.candidates[winner - 1] if self.candidates else None,
            "tally": dict(tally),
            "total_votes": total
        }
        
        # Announce results
        channel = self._get_channel()
        if channel:
            try:
                await channel.send(
                    f"🏆 VOTING CLOSED! Winner: Option {winner} with {tally.get(winner, 0)} votes! "
                    f"Total votes: {total}"
                )
            except Exception as e:
                print(f"⚠️ Could not send voting results: {e}")
        
        return result