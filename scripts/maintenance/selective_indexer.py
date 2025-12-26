# selective_indexer.py
import firebase_admin
from firebase_admin import credentials, firestore
import os
import time
from modules.vector_store import FirestoreVectorStore

def selective_reindex():
    # 1. Init
    key_path = "comparative-studies-ai-models-1bf59eb77077.json"
    if os.path.exists(key_path):
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = key_path
        if not firebase_admin._apps:
            cred = credentials.Certificate(key_path)
            firebase_admin.initialize_app(cred)
    else:
        if not firebase_admin._apps:
            firebase_admin.initialize_app()

    db = firestore.Client()
    vector_store = FirestoreVectorStore(db)

    # 2. Index leeren?
    print("⚠️  ACHTUNG: Soll der aktuelle Such-Index komplett geleert werden?")
    print("   (Empfohlen, um 'Müll' loszuwerden)")
    choice = input("   Tippe 'wipe' zum Löschen, oder Enter zum Behalten: ")

    if choice.lower() == 'wipe':
        print("🔥 Lösche Index...")
        # Batch delete logic
        coll = db.collection('embeddings')
        while True:
            docs = list(coll.limit(500).stream())
            if not docs: break
            batch = db.batch()
            for d in docs: batch.delete(d.reference)
            batch.commit()
            print(f"   ... {len(docs)} gelöscht.")
        print("✅ Index ist leer.")

    # 3. Chats auflisten
    print("\n📂 VERFÜGBARE CHATS IN DER DATENBANK:")
    chats = list(db.collection('chats').order_by('lastUpdated', direction='DESCENDING').stream())

    chat_map = {}
    for i, chat in enumerate(chats):
        data = chat.to_dict()
        title = data.get('title', 'Unbekannt')
        chat_map[i] = chat
        print(f"[{i}] {title}")

    # 4. Auswahl
    print("\nWelche Chats sollen in den Such-Index aufgenommen werden?")
    print("Gib die Nummern getrennt durch Komma ein (z.B. '0, 3, 5').")
    selection = input("Auswahl: ")

    try:
        indices = [int(x.strip()) for x in selection.split(',') if x.strip().isdigit()]
    except:
        print("❌ Ungültige Eingabe.")
        return

    print(f"\n🚀 Starte Indizierung für {len(indices)} Chats...")

    for idx in indices:
        if idx not in chat_map:
            print(f"⚠️ Index {idx} nicht gefunden.")
            continue

        chat = chat_map[idx]
        chat_id = chat.id
        title = chat.to_dict().get('title', 'Unbekannt')

        print(f"\n🔄 Verarbeite: {title}")

        msgs_ref = db.collection('chats').document(chat_id).collection('messages').order_by('timestamp')
        messages = [m.to_dict() for m in msgs_ref.stream()]

        if not messages:
            print("   ⚠️ Leer.")
            continue

        # Metadaten
        metadata = {'title': title, 'source': 'selective_index'}

        try:
            # Erst alte Chunks dieses Chats löschen (Sicherheit)
            vector_store.delete_chat_embeddings(chat_id)
            # Neu indizieren
            chunks, skipped = vector_store.process_and_store_chat(chat_id, messages, metadata)
            print(f"   ✅ {chunks} Chunks erstellt.")
            time.sleep(1)
        except Exception as e:
            print(f"   ❌ Fehler: {e}")

    print("\n✅ Fertig. Nur die ausgewählten Chats sind jetzt im Wissen.")

if __name__ == "__main__":
    selective_reindex()