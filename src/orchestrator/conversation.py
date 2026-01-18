import openai
from typing import AsyncGenerator, Tuple
import os

client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

async def generate_conversation(
    market_question: str,
    market_odds: dict,
    market_description: str,
    num_exchanges: int = 8
) -> AsyncGenerator[Tuple[str, str], None]:
    """Generate a back-and-forth conversation about a market.
    
    Yields: (speaker: "max" | "ben", dialogue: str)
    """
    
    conversation_history = []
    
    system_prompt = f"""You are a conversation writer for a Jim Cramer-style trading show.
    Write dialogue between two hosts discussing this prediction market:
    
    MARKET: {market_question}
    CURRENT ODDS: {market_odds}
    DESCRIPTION: {market_description}
    
    Rules:
    - Max is bullish and energetic, uses "BUY BUY BUY!" style language
    - Ben is skeptical and analytical, plays devil's advocate
    - Each line should be 1-3 sentences
    - Make it entertaining and dramatic
    - Reference specific odds and what they mean
    - Include trading floor energy and urgency
    
    Format each response as: SPEAKER: dialogue
    Example: MAX: This market is SCREAMING opportunity! 65% odds? That's basically free money!"""
    
    for i in range(num_exchanges):
        speaker = "max" if i % 2 == 0 else "ben"
        
        messages = [
            {"role": "system", "content": system_prompt},
            *conversation_history,
            {"role": "user", "content": f"Write {speaker.upper()}'s next line (exchange {i+1}/{num_exchanges})"}
        ]
        
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            max_tokens=150,
            temperature=0.9
        )
        
        dialogue = response.choices[0].message.content
        # Clean up the response
        dialogue = dialogue.replace(f"{speaker.upper()}:", "").strip()
        
        conversation_history.append({"role": "assistant", "content": f"{speaker.upper()}: {dialogue}"})
        
        yield (speaker, dialogue)