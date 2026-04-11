import sys
import os

# Pfad-Setup, damit wir deine Module finden
current_dir = os.getcwd()
sys.path.append(current_dir)

print(f"📂 Arbeitsverzeichnis: {current_dir}")

try:
    from modules.vector_store import VectorStore
    print("✅ VectorStore Modul geladen.")
except ImportError as e:
    print(f"❌ Fehler beim Importieren von VectorStore: {e}")
    print("Stelle sicher, dass du das Skript aus dem Root-Ordner des Projekts ausführst.")
    sys.exit(1)

def simple_diagnose():
    print("\n--- DIAGNOSE START: DATEN-INTEGRITÄT ---")

    # 1. DB Verbindung
    try:
        vs = VectorStore()
        # Wir greifen direkt auf die Chroma Collection zu, um die Rohdaten zu sehen
        data = vs.collection.get()
        docs = data['documents']
        ids = data['ids']
        metadatas = data['metadatas']

        count = len(docs)
        print(f"✅ Datenbank verbunden. Anzahl Dokumente: {count}")
    except Exception as e:
        print(f"❌ Kritischer DB-Fehler: {e}")
        return

    if count == 0:
        print("❌ Die Datenbank ist LEER. Das erklärt die 0 Treffer.")
        return

    # 2. Suche nach englischen Schlüsselwörtern (Case Insensitive)
    # Basierend auf deiner Fehlermeldung: "Nietzsche", "Adorno", "music"
    keywords = ["nietzsche", "adorno", "music", "analysis"]

    print(f"\n🔍 Scanne {count} Dokumente nach Keywords: {keywords}...")

    hits = {k: 0 for k in keywords}
    sample_hit = ""

    for doc in docs:
        doc_lower = doc.lower()
        # Checke jedes Keyword
        for k in keywords:
            if k in doc_lower:
                hits[k] += 1
                if hits[k] == 1 and not sample_hit:
                    sample_hit = doc # Speichere den ersten Treffer als Beweis

    # 3. Auswertung
    print("\n--- ERGEBNIS ---")
    total_hits = sum(hits.values())

    for k, v in hits.items():
        print(f"• Begriff '{k}': {v} mal gefunden.")

    if total_hits == 0:
        print("\n❌ ALARM: Keine der englischen Begriffe gefunden!")
        print("Hypothese: Die englischen Texte wurden gar nicht importiert oder sind korrupt.")
    else:
        print(f"\n✅ Daten sind da! (Beispiel: '{sample_hit[:100]}...')")
        print("👉 FAZIT: Die Datenbank ist okay. Das Problem liegt im Retrieval-Code (Filter/Spracherkennung).")

if __name__ == "__main__":
    simple_diagnose()