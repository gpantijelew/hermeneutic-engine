# check_deepseek_tags.py
import firebase_admin
from firebase_admin import credentials, firestore
import os

def check():
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

    print("🕵️‍♂️ PRÜFE DEEPSEEK METADATEN...")
    print("="*60)

    # Wir holen alle Chunks und filtern in Python (um Index-Probleme zu umgehen)
    docs = db.collection('embeddings').stream()

    deepseek_count = 0
    types_found = {}

    for doc in docs:
        data = doc.to_dict()
        meta = data.get('metadata', {})
        speaker = meta.get('model_name', 'Unknown')

        # Nur DeepSeek anschauen
        if speaker == 'DeepSeek':
            deepseek_count += 1
            ctype = meta.get('content_type', 'FEHLT')

            # Statistik führen
            types_found[ctype] = types_found.get(ctype, 0) + 1

            # Zeige die ersten 5 Beispiele im Detail
            if deepseek_count <= 5:
                print(f"ID: {doc.id}")
                print(f"📝 Text: {data.get('content', '')[:60]}...")
                print(f"🧠 Typ:  '{ctype}'")
                print("-" * 40)

    print("\n📊 ERGEBNIS:")
    print(f"Gefundene DeepSeek Chunks: {deepseek_count}")
    print("Verteilung der Typen:")
    for t, c in types_found.items():
        print(f"  - '{t}': {c}")

if __name__ == "__main__":
    check()