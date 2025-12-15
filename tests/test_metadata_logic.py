import sys
import os

# Pfad anpassen, damit Module gefunden werden
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.utils.date_extractor import extract_date_from_chat_title
from modules.utils.version_extractor import extract_version_from_chat_title

def run_tests():
    print("🔧 STARTING METADATA LOGIC TESTS\n")

    # --- TEST DATUM ---
    date_cases = [
        ("DeepSeek Mai 2025", "2025-05-01"),
        ("DeepSeek am 04122025", "2025-12-04"),
        ("Kimi und Zensur 05102025", "2025-10-05"),
        ("Arena: deepseek-v3.2-exp-thinking", None),
        ("Ein Chat ohne Datum", None)
    ]

    print("📅 Testing Date Extraction:")
    date_errors = 0
    for title, expected in date_cases:
        result = extract_date_from_chat_title(title)
        if result == expected:
            print(f"  ✅ '{title}' -> {result}")
        else:
            print(f"  ❌ '{title}' -> {result} (Erwartet: {expected})")
            date_errors += 1

    # --- TEST VERSION ---
    version_cases = [
        ("Arena: deepseek-v3.2-exp-thinking", "DeepSeek", "3.2"),
        ("Arena: glm-4.6", "GLM-4.6", "4.6"),
        ("DeepSeek Mai 2025", "DeepSeek", "2.5"),      # Vor Nov 2025
        ("DeepSeek am 04122025", "DeepSeek", "3.0"),   # Nach Nov 2025
        ("Claude 3.5 Sonnet Test", "Claude", "3.5"),
        ("Unbekanntes Modell", "Bot", None)
    ]

    print("\n🤖 Testing Version Extraction:")
    version_errors = 0
    for title, speaker, expected in version_cases:
        result = extract_version_from_chat_title(title, speaker)
        if result == expected:
            print(f"  ✅ '{title}' ({speaker}) -> {result}")
        else:
            print(f"  ❌ '{title}' ({speaker}) -> {result} (Erwartet: {expected})")
            version_errors += 1

    print("\n" + "="*30)
    if date_errors == 0 and version_errors == 0:
        print("🎉 ALLE TESTS BESTANDEN. Logik ist bereit.")
    else:
        print(f"⚠️ FEHLER GEFUNDEN: {date_errors + version_errors}")

if __name__ == "__main__":
    run_tests()