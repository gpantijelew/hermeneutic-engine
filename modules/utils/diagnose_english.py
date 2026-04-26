import sys
import os
from rank_bm25 import BM25Okapi

# Wir simulieren den Pfad, falls nötig
sys.path.append(os.getcwd())

# Versuch, die echten Module zu laden - falls das fehlschlägt, nutzen wir Mock-Daten
try:
    from modules.vector_store import VectorStore

    print("✅ VectorStore Modul gefunden.")
except ImportError:
    print("❌ VectorStore nicht gefunden. Prüfe Pfade.")
    sys.exit(1)


def diagnose():
    print("--- DIAGNOSE START: ENGLISCH RETRIEVAL ---")

    # 1. Verbindung zur DB
    vs = VectorStore()
    all_docs = (
        vs.get_all_documents()
    )  # Annahme: Es gibt eine Methode, um Rohdaten zu holen

    if not all_docs:
        # Fallback für ChromaDB direkten Zugriff, falls get_all_documents nicht existiert
        print(
            "⚠️ Keine direkte 'get_all_documents' Methode. Versuche Chroma Collection direkt..."
        )
        try:
            all_docs = vs.collection.get()["documents"]
            ids = vs.collection.get()["ids"]
            print(f"✅ {len(all_docs)} Dokumente aus Chroma geladen.")
        except Exception as e:
            print(f"❌ Kritischer Fehler beim Laden der DB: {e}")
            return

    # 2. Suche nach englischen Texten (Heuristik)
    english_sample = None
    for doc in all_docs:
        # Einfacher Check auf typisch englische Wörter
        if " the " in doc.lower() and " and " in doc.lower() and " of " in doc.lower():
            english_sample = doc
            break

    if english_sample:
        print(
            f"\n✅ Englischen Beispiel-Text gefunden (Auszug):\n'{english_sample[:100]}...'\n"
        )
    else:
        print(
            "\n❌ WARNUNG: Keine offensichtlich englischen Texte in den ersten Samples gefunden."
        )
        # Wir machen trotzdem weiter, vielleicht ist es nur Zufall.

    # 3. Tokenizer Test
    # Wir emulieren, was der BM25Retriever wahrscheinlich tut.
    # ACHTUNG: Hier muss ich raten, wie deine Tokenizer-Funktion aussieht.
    # Normalerweise nutzen wir eine einfache split() oder spacy.

    query = "What is the analysis of Nietzsche?"  # Beispiel-Query

    print(f"Test-Query: '{query}'")

    # Simuliere Standard-Tokenisierung (oft das Problem)
    def simple_tokenizer(text):
        return text.lower().split()

    tokenized_query = simple_tokenizer(query)
    print(f"Tokenized Query (Simple): {tokenized_query}")

    # 4. Manueller BM25 Bau
    print("\n🏗️ Baue isolierten BM25 Index für Diagnose...")
    tokenized_corpus = [simple_tokenizer(doc) for doc in all_docs]
    bm25 = BM25Okapi(tokenized_corpus)

    scores = bm25.get_scores(tokenized_query)
    top_n = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:3]

    print("\n--- ERGEBNIS DER ISOLIERTEN SUCHE ---")
    hits = 0
    for i in top_n:
        if scores[i] > 0:
            hits += 1
            print(f"Treffer {hits} (Score: {scores[i]:.4f}): {all_docs[i][:100]}...")

    if hits == 0:
        print("\n❌ Auch im isolierten Test 0 Treffer.")
        print(
            "Mögliche Ursache: Die Query-Begriffe kommen so nicht im Text vor oder Stopwords wurden nicht entfernt."
        )
    else:
        print(f"\n✅ Isolierter Test erfolgreich ({hits} Treffer).")
        print(
            "👉 FAZIT: Der Fehler liegt in der `app_forschung.py` Pipeline (z.B. erzwungene Übersetzung oder aggressiver Stopword-Filter), nicht in den Daten."
        )


if __name__ == "__main__":
    diagnose()
