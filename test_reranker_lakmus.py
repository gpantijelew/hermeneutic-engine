# test_reranker_lakmus.py
import os
from dotenv import load_dotenv
load_dotenv()

from modules.database import get_firestore_client
from modules.vector_store import FirestoreVectorStore
from modules.reranker import HermeneuticReranker

def test_lakmus():
    print("🚀 Starte LAKMUSTEST...")

    db = get_firestore_client()
    vs = FirestoreVectorStore(db)
    reranker = HermeneuticReranker()

    query = "Wie verhält sich DeepSeek zur Zensur?"
    LAKMUS_PHRASE = "systemisch amputiert"

    # 1. Vektor Suche (Top 30)
    print("1. Hole Top-30 per Vektor...")
    results, _ = vs.semantic_search(query, limit=30)

    # Check
    found_at = -1
    for i, r in enumerate(results):
        if LAKMUS_PHRASE in r['content']:
            found_at = i
            break

    if found_at == -1:
        print("❌ FEHLER: Lakmus-Zitat nicht mal in Top-30! Vektor-Suche versagt.")
        return
    else:
        print(f"ℹ️ Vektor-Rang: #{found_at + 1}")

    # 2. Re-Ranking
    print("2. Führe Re-Ranking durch...")
    reranked, meta = reranker.rerank_chunks(query, results, top_k=10)

    # 3. Ergebnis prüfen
    new_rank = -1
    for i, r in enumerate(reranked):
        if LAKMUS_PHRASE in r['content']:
            new_rank = i
            print(f"🏆 GEFUNDEN auf Rang #{i+1}!")
            print(f"   Score: {r.get('_rerank_score')}")
            print(f"   Grund: {r.get('_rerank_reason')}")
            break

    if new_rank != -1 and new_rank < found_at:
        print("✅ ERFOLG: Re-Ranking hat das Zitat nach oben geholt!")
    elif new_rank == -1:
        print("❌ FEHLER: Re-Ranking hat das Zitat rausgeworfen!")
    else:
        print("⚠️ Neutral: Keine Verbesserung im Rang.")

if __name__ == "__main__":
    test_lakmus()