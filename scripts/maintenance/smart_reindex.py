import firebase_admin
from firebase_admin import credentials, firestore
import os
import time
from modules.vector_store import FirestoreVectorStore

def smart_reindex():
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

    print("🧠 STARTE SMARTE RE-INDIZIERUNG (MIT IDENTITÄT)...")

    # 2. Wir holen NUR die relevanten Chats (um Zeit zu sparen)
    # Wir suchen nach Chats, die wir reparieren wollen
    target_titles = [
        "Kimi und Zensur sowie htm 05102025",
        "DeepSeek am 04122025",
        "DeepSeek Mai 2025"
    ]

    all_chats = db.collection('chats').stream()

    for chat in all_chats:
        data = chat.to_dict()
        title = data.get('title', 'Unbekannt')
        chat_id = chat.id

        # Prüfen, ob dieser Chat relevant ist (oder wir machen alle, wenn du willst)
        # Hier machen wir einen "Soft Match"
        is_relevant = any(t in title for t in target_titles)

        # Wenn du ALLE neu machen willst, nimm die nächste Zeile raus:
        # if not is_relevant: continue 

        print(f"\n🔄 Verarbeite: {title}")

        # --- INTELLIGENZ: Modell erkennen ---
        model_name = "Unbekannt"
        title_lower = title.lower()

        if "kimi" in title_lower: model_name = "Kimi"
        elif "deepseek" in title_lower: model_name = "DeepSeek"
        elif "chatgpt" in title_lower: model_name = "ChatGPT"
        elif "claude" in title_lower: model_name = "Claude"
        elif "gemini" in title_lower: model_name = "Gemini"

        print(f"   🏷️  Identifizierter Sprecher: {model_name}")
        # ------------------------------------

        msgs_ref = db.collection('chats').document(chat_id).collection('messages').order_by('timestamp')
        messages = [m.to_dict() for m in msgs_ref.stream()]

        if not messages:
            print("   ⚠️ Leer.")
            continue

        # Metadaten MIT MODELLNAME
        metadata = {
            'title': title,
            'source': 'smart_reindex',
            'model_name': model_name, # <--- DAS HAT GEFEHLT!
            'platform': model_name
        }

        try:
            # Alte Vektoren löschen
            vector_store.delete_chat_embeddings(chat_id)
            # Neu mit Metadaten speichern
            chunks, skipped = vector_store.process_and_store_chat(chat_id, messages, metadata)
            print(f"   ✅ {chunks} Chunks gespeichert (als {model_name}).")
            time.sleep(1)
        except Exception as e:
            print(f"   ❌ Fehler: {e}")

    print("\n✅ Fertig. Die KI weiß jetzt, wer wer ist.")

if __name__ == "__main__":
    smart_reindex()