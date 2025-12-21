# test_rrf.py
import os
import sys
import glob
import json
from dotenv import load_dotenv
from google.cloud import firestore

# 1. Umgebung laden
load_dotenv()
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# WICHTIG: Wir importieren das Modul als Alias, um auf globale Variablen zuzugreifen
import modules.vector_store as vs_module
from modules.vector_store import FirestoreVectorStore

def setup_auth():
    """
    Sucht automatisch nach dem Service-Account-Key.
    """
    if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        print(f"🔑 Auth via Env-Var: {os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')}")
        return True

    print("🔍 Suche nach Service-Account-Key im Ordner...")
    json_files = glob.glob("*.json")

    for file in json_files:
        try:
            with open(file, 'r') as f:
                content = json.load(f)
                if "type" in content and content["type"] == "service_account":
                    print(f"✅ Key gefunden: {file}")
                    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.abspath(file)
                    return True
        except:
            continue

    print("❌ KEIN Service-Account-Key (*.json) gefunden!")
    return False

def test_rrf_logic():
    print("\n--- TEST: RRF (Reciprocal Rank Fusion) ---")

    if not setup_auth():
        return

    try:
        db = firestore.Client()
        print("✅ Firestore Verbindung: OK")
    except Exception as e:
        print(f"❌ Firestore Verbindung fehlgeschlagen: {e}")
        return

    store = FirestoreVectorStore(db)

    # 1. Index erzwingen
    print("1. Baue BM25 Index (kann kurz dauern)...")
    store._ensure_bm25_index()

    # FIX: Zugriff auf die GLOBALE Variable im Modul, nicht in der Klasse
    if vs_module._BM25_INDEX is None:
        print("❌ FEHLER: BM25 Index konnte nicht gebaut werden.")
        return
    else:
        # Wir prüfen die Map-Größe als Beweis
        doc_count = len(vs_module._BM25_DOC_MAP)
        print(f"✅ Index-Check: {doc_count} Dokumente im RAM.")

    # 2. Test-Query
    query = "Pessoa" 

    print(f"\n2. Suche nach '{query}' mit RRF...")
    results, _ = store.hybrid_search(query, limit=5)

    print(f"\nErgebnisse ({len(results)}):")
    for i, doc in enumerate(results, 1):
        content_snippet = doc.get('content', '')[:100].replace('\n', ' ')

        # Prüfen ob RRF aktiv war
        rrf_active = doc.get('_rrf_active', False)
        rrf_status = "⚡ RRF" if rrf_active else "Standard"

        # Score anzeigen (hilft beim Debuggen)
        score = doc.get('score', 0)

        print(f"{i}. [{rrf_status}] (Score: {score:.4f}) {content_snippet}...")

    if len(results) > 0:
        print("\n✅ RRF Test erfolgreich: Dokumente gefunden und fusioniert.")
    else:
        print("\n⚠️ Keine Ergebnisse. Ist die Datenbank leer?")

if __name__ == "__main__":
    test_rrf_logic()