# inspect_index.py
import firebase_admin
from firebase_admin import credentials, firestore
import os

def inspect():
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

    print("📊 ANALYSE DES SUCH-INDEX (Vector Store)...")
    print("-" * 60)
    print(f"{'ID':<22} | {'Chunks':<6} | {'Titel'}")
    print("-" * 60)

    # Wir holen alle Chats, um die Titel zu haben
    all_chats = {doc.id: doc.to_dict().get('title', 'Unbekannt') for doc in db.collection('chats').stream()}

    # Wir zählen die Chunks im Index
    # Achtung: Das kann bei 4000 Chunks kurz dauern
    chunks = db.collection('embeddings').stream()

    stats = {}
    total_chunks = 0

    for chunk in chunks:
        data = chunk.to_dict()
        chat_id = data.get('chat_id')
        if chat_id:
            stats[chat_id] = stats.get(chat_id, 0) + 1
            total_chunks += 1

    # Ausgabe sortiert nach Anzahl Chunks
    for chat_id, count in sorted(stats.items(), key=lambda item: item[1], reverse=True):
        title = all_chats.get(chat_id, "Gelöschter Chat?")
        print(f"{chat_id:<22} | {count:<6} | {title}")

    print("-" * 60)
    print(f"GESAMT: {total_chunks} Chunks im Index.")

if __name__ == "__main__":
    inspect()