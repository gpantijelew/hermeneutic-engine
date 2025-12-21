# stress_test_v49.py
import time
import os
import sys
from dotenv import load_dotenv

# Setup
load_dotenv()
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Authentifizierung sicherstellen (wie vorhin)
import glob
import json
if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
    json_files = glob.glob("*.json")
    for file in json_files:
        try:
            with open(file, 'r') as f:
                if "service_account" in json.load(f).get("type", ""):
                    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.abspath(file)
                    print(f"🔑 Auth geladen: {file}")
                    break
        except: pass

from modules.citation_rag import CitationRAG

def print_header(title):
    print(f"\n{'='*60}")
    print(f"🧪 TEST: {title}")
    print(f"{'='*60}")

def stress_test():
    rag = CitationRAG()

    # ---------------------------------------------------------
    # TEST 1: RRF PRÄZISION (Das "Nadel im Heuhaufen" Szenario)
    # ---------------------------------------------------------
    print_header("1. RRF HYBRID SEARCH (Präzision)")

    # Wir suchen nach etwas Spezifischem, das semantisch "schwach" ist, aber als Keyword stark.
    # Beispiel: Ein spezifischer Übersetzer oder ein seltenes Wort.
    query = "Pessoa" 
    print(f"🔎 Suche nach Keyword: '{query}'")

    start = time.time()
    # Wir nutzen direkt die interne Methode, um die Metadaten zu sehen
    results = rag.retrieve_with_rrf(query, limit=5)
    duration = time.time() - start

    rrf_hits = sum(1 for r in results if r.get('_rrf_active'))

    print(f"⏱️ Dauer: {duration:.2f}s")
    print(f"📊 Treffer: {len(results)} | Davon RRF-aktiviert: {rrf_hits}")

    if rrf_hits > 0:
        print("✅ RRF funktioniert! (Blitz-Symbol aktiv)")
        print(f"   Top Treffer: {results[0].get('content')[:80]}...")
    else:
        print("⚠️ WARNUNG: Kein RRF-Flag gesehen. Läuft BM25?")

    # ---------------------------------------------------------
    # TEST 2: ENFORCER LOGIK (Der "Zitat-Fallen" Test)
    # ---------------------------------------------------------
    print_header("2. HERMENEUTIC ENFORCER (Logik & Zitat-Schutz)")

    source_text = "Ich bin nichts. Ich werde nie etwas sein. Ich kann auch nicht wollen, etwas zu sein."
    source_meta = {"filename": "tabacaria_de.txt", "page": 1}

    # Fall A: Legitime Interpretation (Muss TRUE sein)
    claim_valid = "Der Sprecher drückt eine radikale Existenzverneinung aus."
    print(f"A) Prüfe valide Interpretation: '{claim_valid}'")
    valid, reason = rag.verify_fact_match(claim_valid, source_text, source_meta)
    print(f"   Ergebnis: {reason}")
    if valid: print("   ✅ KORREKT AKZEPTIERT")
    else: print("   ❌ FÄLSCHLICHERWEISE ABGELEHNT")

    print("-" * 30)

    # Fall B: Falsches Zitat (Muss FALSE sein - Regel 5)
    # Inhaltlich stimmt es ("Sinnlosigkeit"), aber das Zitat ist erfunden.
    claim_fake_quote = "Der Autor schreibt explizit: 'Das Leben ist absolut sinnlos'."
    print(f"B) Prüfe falsches Zitat: '{claim_fake_quote}'")
    valid, reason = rag.verify_fact_match(claim_fake_quote, source_text, source_meta)
    print(f"   Ergebnis: {reason}")
    if not valid: print("   ✅ KORREKT ABGELEHNT (Zitat-Schutz greift)")
    else: print("   ❌ FEHLER: Falsches Zitat wurde akzeptiert!")

    # ---------------------------------------------------------
    # TEST 3: CACHING (Der "Geschwindigkeits" Test)
    # ---------------------------------------------------------
    print_header("3. EXACT MATCH CACHE (Latenz)")

    # Wir wiederholen exakt Fall A.
    print("Wiederhole Prüfung A (sollte 0.0s dauern)...")

    start_cache = time.time()
    valid, reason = rag.verify_fact_match(claim_valid, source_text, source_meta)
    duration_cache = time.time() - start_cache

    print(f"⏱️ Dauer 2. Lauf: {duration_cache:.4f}s")

    if duration_cache < 0.1:
        print("🚀 CACHE HIT! (Extrem schnell)")
    else:
        print(f"⚠️ CACHE MISS? (Dauerte {duration_cache:.2f}s - zu lang für RAM-Zugriff)")

if __name__ == "__main__":
    stress_test()