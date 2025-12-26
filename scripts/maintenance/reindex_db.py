# reindex_db.py
import firebase_admin
from firebase_admin import credentials, firestore
import os
import time
from modules.vector_store import FirestoreVectorStore

def reindex_all_chats():
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

    print("🚀 STARTE RE-INDIZIERUNG (RESUME MODE)...")

    # 2. Alle Chats holen
    chats = list(db.collection('chats').stream()) # Liste laden, um Timeouts beim Streamen zu vermeiden

    total_chunks = 0
    processed_chats = 0

    for chat in chats:
        chat_id = chat.id
        data = chat.to_dict()
        title = data.get('title', 'Unbekannt')

        # --- RESUME CHECK ---
        # Prüfen, ob schon Vektoren für diesen Chat existieren
        existing_vectors = db.collection('embeddings').where('chat_id', '==', chat_id).limit(1).stream()
        if any(existing_vectors):
            print(f"⏭️ Überspringe {title} (bereits indiziert).")
            continue
        # --------------------

        print(f"\n🔄 Verarbeite Chat: {title} ({chat_id})")

        # Nachrichten laden
        msgs_ref = db.collection('chats').document(chat_id).collection('messages').order_by('timestamp')
        messages = [m.to_dict() for m in msgs_ref.stream()]

        if not messages:
            print("   ⚠️ Leer. Überspringe.")
            continue

        metadata = {
            'source': 'reindex_script',
            'title': title
        }

        try:
            chunks, skipped = vector_store.process_and_store_chat(chat_id, messages, metadata)
            print(f"   ✅ Indiziert: {chunks} Chunks (Übersprungen: {skipped})")
            total_chunks += chunks
            processed_chats += 1
            time.sleep(1) # Kurze Pause gegen Rate Limits
        except Exception as e:
            print(f"   ❌ Fehler beim Indizieren: {e}")

    print("\n" + "="*40)
    print(f"🎉 FERTIG! {processed_chats} Chats neu verarbeitet.")
    print("="*40)

if __name__ == "__main__":
    reindex_all_chats()