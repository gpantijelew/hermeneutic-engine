# debug_db.py
from modules.database import get_firestore_client

def inspect_db():
    print("🔌 Verbinde mit Firestore...")
    db = get_firestore_client()

    if not db:
        print("❌ Keine Verbindung zur Datenbank.")
        return

    print("🔍 Suche nach Chats...")
    # Hole die letzten 5 Chats
    chats_ref = db.collection('chats').order_by('lastUpdated', direction='DESCENDING').limit(5)
    chats = chats_ref.stream()

    found_any = False
    for chat in chats:
        found_any = True
        chat_data = chat.to_dict()
        chat_id = chat.id
        title = chat_data.get('title', 'Ohne Titel')

        print(f"\n📂 CHAT: {title} (ID: {chat_id})")
        print("=" * 40)

        # Hole Nachrichten dieses Chats
        messages_ref = db.collection('chats').document(chat_id).collection('messages').limit(5)
        messages = messages_ref.stream()

        for msg in messages:
            data = msg.to_dict()
            role = data.get('role', 'unknown')
            content = data.get('content', '')
            meta = data.get('metadata', {})
            speaker = meta.get('model_name', 'N/A')

            # Der kritische Check:
            print(f"   👤 Role: {role} | Speaker: {speaker}")
            print(f"   📄 CONTENT: '{content[:100]}...'") # Zeige die ersten 100 Zeichen

            if content.strip() == speaker.strip():
                print("   🚨 ALARM: Content ist identisch mit Speaker-Name! (Daten-Korruption)")

            print("-" * 20)

    if not found_any:
        print("⚠️ Keine Chats in der Datenbank gefunden.")

if __name__ == "__main__":
    inspect_db()