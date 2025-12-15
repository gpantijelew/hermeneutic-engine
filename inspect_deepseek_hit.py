import firebase_admin
from firebase_admin import credentials, firestore
import os

def biopsy():
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

    # Die ID von "DeepSeek am 04122025" (aus deinem Log)
    CHAT_ID = "BTUqEoQDrxT38T4ifQlX" 
    SEARCH_TERM = "Blade Runner"

    print(f"🔬 Untersuche Chat {CHAT_ID} nach '{SEARCH_TERM}'...\n")

    msgs = db.collection('chats').document(CHAT_ID).collection('messages').order_by('timestamp').stream()

    found = False
    for msg in msgs:
        data = msg.to_dict()
        content = data.get('content', '')
        role = data.get('role', 'unknown')

        if SEARCH_TERM.lower() in content.lower():
            found = True
            print(f"=== TREFFER ({role}) ===")
            print(content)
            print("========================\n")

    if not found:
        print("❌ Nichts gefunden. War die ID richtig?")

if __name__ == "__main__":
    biopsy()