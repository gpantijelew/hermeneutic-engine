# verify_pipeline.py
import sys
import os
from dotenv import load_dotenv

# Umgebung laden
load_dotenv()

# Pfad-Fix
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from modules.citation_rag import CitationRAG
    print("✅ Import modules.citation_rag erfolgreich.")
except ImportError as e:
    print(f"❌ Import Fehler: {e}")
    sys.exit(1)

def test_integration():
    print("\n--- START INTEGRATION TEST (RAG + ENFORCER) ---")

    # Dummy RAG initialisieren (wir brauchen keine echte Vektor-DB für diesen Test)
    # Wir testen nur die verify_fact_match Methode
    rag = CitationRAG() 

    # Szenario: Eine legitime Meta-Aussage (sollte TRUE sein)
    claim = "Die Wiederholung erzeugt einen litaneiartigen Rhythmus"
    source_text = "Não sou nada. / Nunca serei nada. / Não posso querer ser nada."
    source_meta = {"filename": "tabacaria.txt", "page": 1}

    print(f"Prüfe Behauptung: '{claim}'")
    print("Rufe Enforcer via RAG auf...")

    try:
        is_valid, reason = rag.verify_fact_match(claim, source_text, source_meta)

        if is_valid:
            print(f"✅ ERFOLG! RAG hat akzeptiert.")
            print(f"   Begründung vom Enforcer: {reason}")
        else:
            print(f"❌ FEHLER! RAG hat abgelehnt (Unerwartet).")
            print(f"   Grund: {reason}")

    except Exception as e:
        print(f"❌ CRASH im RAG-Call: {e}")

if __name__ == "__main__":
    test_integration()