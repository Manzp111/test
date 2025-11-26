# requests/ai_matching.py
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def are_items_same(name1: str, name2: str) -> bool:
    """
    Uses OpenAI to determine if two item names refer to the same product,
    ignoring word order, synonyms, or minor phrasing differences.
    """
    # Craft the prompt
    prompt = f"""
    You are a smart procurement assistant. Determine if these two item names 
    refer to the same physical product or service. Ignore word order, extra words,
    synonyms, or minor typos. Respond ONLY with "YES" or "NO".

    Item 1: "{name1}"
    Item 2: "{name2}"
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=5
        )
        return response.choices[0].message.content.strip().upper() == "YES"
    except Exception:
        # Fallback to normalized exact match if AI fails
        from .utils import normalize_text
        return normalize_text(name1) == normalize_text(name2)