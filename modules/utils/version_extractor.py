import re
from typing import Optional
from modules.utils.date_extractor import extract_date_from_chat_title

# --- KONFIGURATION HEURISTIKEN ---
# Ab wann gilt DeepSeek als v3.0? (Format: YYYY-MM-DD)
DEEPSEEK_V3_CUTOFF = "2025-11-01"


def extract_version_from_chat_title(
    chat_title: str, speaker: str = ""
) -> Optional[str]:
    """
    Extrahiert Modell-Version aus Chat-Titel oder Speaker-Name.
    """
    if not chat_title:
        return None

    chat_title_lower = chat_title.lower()
    speaker_lower = speaker.lower() if speaker else ""

    # 1. Explizite Version im Titel (z.B. "v3.2", "v2.5", "4.0")
    # Sucht nach vX.Y oder X.Y in Kombination mit Modellnamen
    version_pattern = r"v(\d+\.\d+)"
    match = re.search(version_pattern, chat_title, re.IGNORECASE)
    if match:
        return match.group(1)

    # 2. Version im Speaker-String (z.B. "GLM-4.6")
    if speaker:
        version_in_speaker = re.search(r"[-\s](\d+\.\d+)", speaker)
        if version_in_speaker:
            return version_in_speaker.group(1)

    # 3. Spezifische Heuristiken für DeepSeek
    if "deepseek" in chat_title_lower or "deepseek" in speaker_lower:
        # Arena Tests sind meist bleeding edge
        if "arena" in chat_title_lower:
            return "3.2"

        # Zeitliche Heuristik
        date_str = extract_date_from_chat_title(chat_title)
        if date_str:
            if date_str >= DEEPSEEK_V3_CUTOFF:
                return "3.0"
            else:
                return "2.5"

    # 4. Fallback für bekannte Modelle ohne explizite Version im Titel
    if "gpt-4o" in chat_title_lower:
        return "4o"
    if "claude 3.5" in chat_title_lower:
        return "3.5"

    return None
