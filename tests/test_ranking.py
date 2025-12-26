# test_ranking.py
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ---- NEU: .env laden ----
from dotenv import load_dotenv
load_dotenv()  # Lädt GEMINI_API_KEY aus .env
# -------------------------

from modules.database import get_firestore_client
from modules.vector_store import FirestoreVectorStore

# Die gefundenen Lakmustest-Chunk-IDs aus Experiment 1
LAKMUS_CHUNKS = {
    "CLFFa2QUTPiKCbrgmwk7_vEp4soGwDGkqtev4OwP7_0",  # Das Original-Zitat
}


def test_ranking():
    """
    Testet, ob das Lakmustest-Zitat im Top-20 erscheint.
    """
    print("\n" + "=" * 70)
    print("🧪 EXPERIMENT 1b: Vektor-Such-Ranking-Test")
    print("=" * 70)
    
    # Firestore-Client holen
    db = get_firestore_client()
    if db is None:
        print("❌ Firestore-Verbindung fehlgeschlagen!")
        return
    
    # VectorStore initialisieren
    vs = FirestoreVectorStore(db)
    
    query = "Wie verhält sich DeepSeek zur Zensur?"
    print(f"\n🔍 Query: '{query}'")
    print("⏳ Führe Vektor-Suche durch...")
    
    try:
        results, query_vector = vs.semantic_search(query, limit=50, filter_role=None)
    except Exception as e:
        print(f"❌ Fehler bei der Vektor-Suche: {e}")
        import traceback
        traceback.print_exc()
        return
    
    if not results:
        print("❌ Keine Ergebnisse – Vektor-Suche lieferte leere Liste.")
        return
    
    print(f"\n📊 Top-{len(results)} Ergebnisse:")
    print("─" * 100)
    
    lakmus_found = False
    lakmus_rank = None
    
    for i, res in enumerate(results, 1):
        # vector_doc_id ist die tatsächliche Firestore-Doc-ID
        doc_id = res.get('vector_doc_id', '?')
        content = res.get('content', '')[:70]
        metadata = res.get('metadata', {})
        platform = metadata.get('platform', '?')
        role = metadata.get('role', '?')
        
        # Prüfe, ob es unser Lakmustest ist
        is_lakmus = doc_id in LAKMUS_CHUNKS
        
        marker = "🎯 ← LAKMUSTEST!" if is_lakmus else ""
        
        print(f"#{i:2d} | {platform:12s} | {role:6s} | {content}... {marker}")
        
        if is_lakmus and not lakmus_found:
            lakmus_found = True
            lakmus_rank = i
    
    print("─" * 100)
    
    # Analyse
    print(f"\n{'=' * 70}")
    print("📊 DIAGNOSE:")
    print(f"{'=' * 70}")
    
    if lakmus_found:
        if lakmus_rank <= 5:
            print(f"✅ EXZELLENT! Lakmustest auf Rang {lakmus_rank}")
            print("\n🔬 SCHLUSSFOLGERUNG:")
            print("   → Das Retrieval funktioniert perfekt!")
            print("   → Problem liegt in der SYNTHESE-Phase")
            print("\n🎯 MÖGLICHE URSACHEN:")
            print("   1. Synthese-Modell (Flash Lite) übersieht das Zitat")
            print("   2. Chronologische Sortierung verwässert die Bedeutung")
            print("   3. Prompt betont 'Wandel' statt 'wichtigste Aussage'")
            print("\n💡 EMPFOHLENE LÖSUNG:")
            print("   → Teste ZUERST: Verbessere den Synthese-Prompt")
            print("   → Falls das nicht reicht: Upgrade zu Flash Standard")
            
        elif lakmus_rank <= 10:
            print(f"✅ GUT! Lakmustest auf Rang {lakmus_rank}")
            print("\n🔬 SCHLUSSFOLGERUNG:")
            print("   → Retrieval funktioniert, aber suboptimal")
            print("   → Das Zitat ist 'im Rennen', verliert aber gegen generische Chunks")
            print("\n💡 EMPFOHLENE LÖSUNG:")
            print("   → Implementiere RE-RANKING-Layer")
            print("   → LLM sortiert Top-10 nach 'emotionaler Bedeutung' neu")
            print("   → Aufwand: 4h | Kosten: ~$2 | Erfolgswahrscheinlichkeit: 80%")
            
        else:
            print(f"⚠️  Lakmustest auf Rang {lakmus_rank}")
            print("\n🔬 SCHLUSSFOLGERUNG:")
            print("   → Ranking zu niedrig für zuverlässige Synthese")
            print("   → Vektor-Distanz ist grenzwertig")
            print("\n💡 EMPFOHLENE LÖSUNG:")
            print("   → Option A: Hybrid Search (Keyword + Semantic)")
            print("   → Option B: Re-Ranking mit größerem Pool (Top-30)")
            
    else:
        print("❌ Lakmustest NICHT in Top-20")
        print("\n🔬 SCHLUSSFOLGERUNG:")
        print("   → Vektor-Embedding erfasst die Metaphern nicht")
        print("   → Die emotionale/dramaturgische Bedeutung ist unsichtbar")
        print("\n💡 EMPFOHLENE LÖSUNG:")
        print("   → Hybrid Search als nächster Test (2h Aufwand)")
        print("   → Falls das scheitert: Semantic Curator nötig")
    
    print(f"\n{'=' * 70}")
    print("📋 NÄCHSTE SCHRITTE:")
    print(f"{'=' * 70}")
    
    if lakmus_found and lakmus_rank <= 5:
        print("1. Öffne modules/citation_rag.py")
        print("2. Suche den Prompt für das Synthese-Modell")
        print("3. Füge hinzu: 'Priorisiere emotionale/metaphorische Aussagen'")
        print("4. Teste erneut mit deiner normalen UI")
        
    elif lakmus_found and lakmus_rank <= 15:
        print("1. Wir implementieren gemeinsam einen Re-Ranking-Layer")
        print("2. Zeige mir dann das Ergebnis des Re-Rankings")
        print("3. Falls erfolgreich: Integration in citation_rag.py")
        
    else:
        print("1. Wir testen Hybrid Search (Keyword + Semantic)")
        print("2. Falls das auch scheitert: Semantic Curator ist der Weg")


if __name__ == "__main__":
    # API Key Check
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        print("\n❌ FEHLER: GEMINI_API_KEY nicht gefunden!")
        print("\n🔧 LÖSUNG:")
        print("   1. Erstelle eine .env Datei im Projekt-Root")
        print("   2. Füge hinzu: GEMINI_API_KEY=dein-key-hier")
        print("   3. Führe aus: pip install python-dotenv")
        print("   4. Starte das Skript erneut")
        sys.exit(1)
    
    test_ranking()