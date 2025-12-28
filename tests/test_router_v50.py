import sys
import os
from pathlib import Path

# Pfad-Hack, damit er modules findet
sys.path.append(str(Path(__file__).parent.parent))

from modules.hermeneutic_router import HermeneuticRouter
from modules.config import validate_config

def test_brain():
    print("🔌 Prüfe Verbindungen...")
    if not validate_config():
        return

    print("\n🧠 Initialisiere Hermeneutic Router (v50)...")
    router = HermeneuticRouter()

    # Test-Szenarien
    queries = [
        "Was ist der Unterschied zwischen DeepSeek v2 und v3?", # Factual
        "Analysiere die Metaphorik der Stille in den Gedichten.", # Literary
        "Vergleiche die Entwicklung des Begriffs 'Bewusstsein' über die Zeit.", # Analytical
    ]

    print("\n🚀 STARTE ROUTING-TEST:\n")

    for q in queries:
        print(f"Frage: '{q}'")
        print("... Router denkt nach ...")

        try:
            decision = router.route_query(q)

            intent = decision['intent']
            limit = decision['limit']
            thresh = decision['threshold']

            icon = "📚" if intent == "LITERARY" else "📊" if intent == "ANALYTICAL" else "🔍"

            print(f"   --> ENTSCHEIDUNG: {icon} {intent}")
            print(f"       Parameter:    Hole {limit} Chunks | Rerank-Härte: {thresh}")
            print("-" * 50)

        except Exception as e:
            print(f"❌ FEHLER: {e}")

if __name__ == "__main__":
    test_brain()