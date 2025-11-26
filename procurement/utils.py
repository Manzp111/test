# requests/utils.py
import re
import unicodedata

def normalize_text(text: str) -> str:
    """Normalize text for fallback matching."""
    if not text:
        return ""
    text = unicodedata.normalize('NFD', text)
    text = ''.join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r'[^\w\s]', ' ', text.lower())
    return ' '.join(text.split())