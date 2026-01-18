import openai
from dotenv import load_dotenv
from typing import AsyncGenerator, Tuple
import os

load_dotenv()

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
    - Max is bullish and energetic: ALWAYS use tags like [yells], [shouts], or [excited].
    - Ben is skeptical and analytical: Use tags like [sighs], [deadpan], or [whispers intensely].
    - Each speaker should talk for about 60 seconds (about 150-200 words)
    - IMPORTANT: Every response MUST include [emotion brackets] like the examples below.
    - Reference specific odds and what they mean
    - Include trading floor energy and urgency
    - React to the energy: If Max [yells], Ben might [scoff] or [whisper] to highlight the contrast.
    - Each turn should be a complete thought or argument
    
    Format each response as: SPEAKER: dialogue
    Example: Max: "[yells] BUY BUY BUY! [pounding desk] These odds are a gift from the heavens!"
             Ben: "[sighs heavily] Max, look at the data. [whispers] You're leading people into a slaughter..."
             """
    
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
            max_tokens=300,  # Longer responses for 60-90 second speeches
            temperature=0.9
        )
        
        dialogue = response.choices[0].message.content
        # Clean up the response
        dialogue = dialogue.replace(f"{speaker.upper()}:", "").strip()
        
        conversation_history.append({"role": "assistant", "content": f"{speaker.upper()}: {dialogue}"})
        
        yield (speaker, dialogue)