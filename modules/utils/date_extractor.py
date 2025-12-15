import re
from datetime import datetime
from typing import Optional

def extract_date_from_chat_title(chat_title: str) -> Optional[str]:
    """
    Extrahiert Datum aus Chat-Titel.
    Returns: ISO-Format "YYYY-MM-DD" oder None
    """
    if not chat_title:
        return None

    # Pattern 1: "Mai 2025", "Oktober 2024" (Deutsch)
    month_pattern = r"(Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)\s+(\d{4})"
    match = re.search(month_pattern, chat_title, re.IGNORECASE)
    if match:
        month_name, year = match.groups()
        month_map = {
            "januar": "01", "februar": "02", "märz": "03", "april": "04",
            "mai": "05", "juni": "06", "juli": "07", "august": "08",
            "september": "09", "oktober": "10", "november": "11", "dezember": "12"
        }
        month_num = month_map.get(month_name.lower())
        if month_num:
            return f"{year}-{month_num}-01"

    # Pattern 2: "am 04122025" (DDMMYYYY)
    date_pattern = r"am\s+(\d{2})(\d{2})(\d{4})"
    match = re.search(date_pattern, chat_title)
    if match:
        day, month, year = match.groups()
        try:
            # Validierung ob echtes Datum
            datetime(int(year), int(month), int(day))
            return f"{year}-{month}-{day}"
        except ValueError:
            pass

    # Pattern 3: "05102025" (DDMMYYYY ohne "am", oft am Ende oder isoliert)
    # Wir suchen nach 8 Ziffern, die ein valides Datum ergeben könnten
    date_pattern_short = r"(\d{2})(\d{2})(\d{4})"
    matches = re.finditer(date_pattern_short, chat_title)
    for match in matches:
        day, month, year = match.groups()
        try:
            # Plausibilitätscheck Jahr (2023-2030) um False Positives bei IDs zu vermeiden
            if 2023 <= int(year) <= 2030:
                datetime(int(year), int(month), int(day))
                return f"{year}-{month}-{day}"
        except ValueError:
            continue

    return None