# debug_metadata.py
import firebase_admin
from firebase_admin import credentials, firestore
import os

def inspect_raw_metadata():
    # 1. Init (Standard-Verbindung)
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

    print("🕵️‍♂️ UNTERSUCHE METADATEN IN 'embeddings'...")
    print("="*60)

    # Hole 10 beliebige Chunks
    docs = db.collection('embeddings').limit(10).stream()

    count = 0
    for doc in docs:
        count += 1
        data = doc.to_dict()
        meta = data.get('metadata', {})

        print(f"ID: {doc.id}")
        print(f"📝 Content Preview: {data.get('content', '')[:50]}...")
        print(f"🏷️  model_name:   '{meta.get('model_name')}'")   # Sprecher
        print(f"🧠  content_type: '{meta.get('content_type')}'") # Der neue Typ
        print(f"🎯  subjects:     '{meta.get('subjects')}'")     # Die neuen Themen
        print("-" * 40)

    if count == 0:
        print("❌ Die Collection 'embeddings' ist LEER.")
    else:
        print(f"✅ {count} Chunks geprüft.")

if __name__ == "__main__":
    inspect_raw_metadata()