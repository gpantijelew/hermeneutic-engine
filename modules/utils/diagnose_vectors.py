import numpy as np
from dotenv import load_dotenv

# 1. ZUERST die Umgebungsvariablen laden (.env)
load_dotenv()

# 2. DANN erst die HRE-Module importieren
from modules.database import get_firestore_client


def run_diagnostics():
    print("🔍 Starte ultimativen Vektor-Scan...")
    db = get_firestore_client()

    if not db:
        print("❌ Konnte keine Datenbankverbindung herstellen.")
        return

    print("\n1️⃣ Suche nach dem Chat 'Schulungsdrehbuch'...")
    chats = db.collection("chats").stream()
    target_id = None
    target_title = None

    for chat in chats:
        data = chat.to_dict()
        title = data.get("title", "")
        if "Schulungsdrehbuch" in title:
            target_id = chat.id
            target_title = title
            print(f"✅ Chat gefunden! Echte ID: {target_id} | Titel: '{title}'")
            break

    if not target_id:
        print("❌ Chat nicht in der 'chats' Collection gefunden!")
        return

    print("\n2️⃣ Suche nach der richtigen Chunk-Collection...")
    possible_collections = [
        "chunks",
        "document_chunks",
        "vector_chunks",
        "embeddings",
        "chat_chunks",
    ]
    found_collection = None

    for coll in possible_collections:
        # Wir prüfen, ob es in dieser Collection Dokumente mit unserer chat_id gibt
        docs = list(
            db.collection(coll).where("chat_id", "==", target_id).limit(1).stream()
        )
        if docs:
            found_collection = coll
            print(f"✅ BINGO! Chunks liegen in der Collection: '{coll}'")
            break

    if not found_collection:
        print(
            f"❌ Keine Chunks für ID {target_id} in den bekannten Collections gefunden."
        )
        print(
            "Tipp: Schau in der vector_store.py nach, wie COLLECTION_NAME definiert ist."
        )
        return

    print(f"\n3️⃣ Analysiere Vektoren in Collection '{found_collection}'...")
    docs = (
        db.collection(found_collection)
        .where("chat_id", "==", target_id)
        .limit(3)
        .stream()
    )

    for doc in docs:
        data = doc.to_dict()
        print("\n" + "=" * 50)
        print(f"📄 Chunk ID: {doc.id}")

        # 1. Content prüfen
        content = data.get("content", "")
        print(f"📝 Content-Länge: {len(content)} Zeichen")
        print(f"📝 Content-Vorschau: {content[:80]}...")

        # 2. Embedding prüfen
        embedding = data.get("embedding")
        if not embedding:
            print("❌ FEHLER: Kein 'embedding' Feld in der Datenbank gefunden!")
            continue

        try:
            vec = np.array(list(embedding))
            print(f"🔢 Dimensionen: {len(vec)} (Erwartet: 768 für Gemini)")

            # Die mathematische Wahrheit: Die Vektor-Norm (Länge)
            norm = np.linalg.norm(vec)
            print(f"📐 Vektor-Norm: {norm:.6f}")

            if norm == 0.0:
                print(
                    "🚨 ALARM: Dies ist ein absoluter Null-Vektor! (Mathematisch tot)"
                )
            elif np.isnan(norm):
                print("🚨 ALARM: Vektor enthält NaN (Not a Number) Werte!")
            else:
                print("✅ Vektor scheint mathematisch intakt zu sein.")

        except Exception as e:
            print(f"❌ FEHLER beim Parsen des Embeddings: {e}")


if __name__ == "__main__":
    run_diagnostics()
