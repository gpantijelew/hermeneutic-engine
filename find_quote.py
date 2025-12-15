import firebase_admin
from firebase_admin import credentials, firestore
import os

def find_the_needle():
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

    SEARCH_TERM = "Blade Runner"
    print(f"🕵️‍♂️ Suche in der GESAMTEN Datenbank nach: '{SEARCH_TERM}'...\n")

    chats = db.collection('chats').stream()
    found_count = 0

    for chat in chats:
        chat_id = chat.id
        title = chat.to_dict().get('title', 'Unbekannt')

        # Nachrichten streamen
        msgs = db.collection('chats').document(chat_id).collection('messages').stream()

        for msg in msgs:
            data = msg.to_dict()
            content = data.get('content', '')
            role = data.get('role', 'unknown')

            if SEARCH_TERM.lower() in content.lower():
                found_count += 1
                print(f"✅ GEFUNDEN in Chat: '{title}'")
                print(f"   ID: {chat_id}")
                print(f"   Rolle: {role}")
                print(f"   Ausschnitt: ...{content[:100].replace(chr(10), ' ')}...")
                print("-" * 40)

    if found_count == 0:
        print("❌ Das Wort wurde in KEINEM Chat gefunden.")
        print("   Schlussfolgerung: Der Import hat den Text verschluckt oder er war nie da.")
    else:
        print(f"🎉 Insgesamt {found_count} Treffer.")

if __name__ == "__main__":
    find_the_needle()