# verify_data.py
import firebase_admin
from firebase_admin import credentials, firestore
import os

def show_truth():
    # 1. Verbindung (wie immer)
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

    # 2. Alle Chats auflisten
    print("\n📊 VERFÜGBARE CHATS:")
    chats = list(db.collection('chats').stream())

    for i, chat in enumerate(chats):
        data = chat.to_dict()
        print(f"[{i}] ID: {chat.id} | Titel: {data.get('title', 'Ohne Titel')}")

    # 3. Auswahl
    try:
        selection = int(input("\nWelchen Chat (Nummer) willst du prüfen? "))
        target_chat = chats[selection]
    except:
        print("Ungültige Eingabe.")
        return

    # 4. Die nackten Daten zeigen
    print(f"\n🔍 PRÜFE INHALT VON: {target_chat.to_dict().get('title')}")
    print("="*60)

    messages = db.collection('chats').document(target_chat.id).collection('messages').order_by('timestamp').limit(5).stream()

    count = 0
    for msg in messages:
        count += 1
        data = msg.to_dict()
        role = data.get('role', 'unknown')
        content = data.get('content', 'LEER')

        print(f"\n--- Nachricht {count} ({role}) ---")
        print(f"RAW CONTENT: {repr(content)}") 
        # repr() zeigt uns ALLES, auch versteckte Zeichen oder HTML

    if count == 0:
        print("❌ Dieser Chat hat KEINE Nachrichten.")
    print("\n" + "="*60)

if __name__ == "__main__":
    show_truth()