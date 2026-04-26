#!/usr/bin/env python3
"""
Debug: Was ist in Firestore für den DeepSeek-Import gespeichert?
"""

import sys
import os

# Path Fix
sys.path.insert(0, os.path.abspath("."))

from google.cloud import firestore
from modules.config import SERVICE_ACCOUNT_KEY_PATH


def get_firestore_client():
    """Initialisiert Firestore"""
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = SERVICE_ACCOUNT_KEY_PATH
    return firestore.Client(project="comparative-studies-ai-models")


def inspect_chat(chat_id: str):
    """Untersucht einen Chat im Detail"""
    db = get_firestore_client()

    print("=" * 80)
    print(f"🔍 INSPIZIERE CHAT: {chat_id}")
    print("=" * 80)

    # 1. Chat-Dokument
    chat_doc = db.collection("chats").document(chat_id).get()

    if not chat_doc.exists:
        print("❌ Chat existiert NICHT in Firestore!")
        return

    print("\n✅ Chat-Dokument gefunden:")
    chat_data = chat_doc.to_dict()
    for key, value in chat_data.items():
        print(f"  {key}: {value}")

    # 2. Messages
    print("\n📨 Messages:")
    messages_ref = db.collection("chats").document(chat_id).collection("messages")
    messages = messages_ref.order_by("timestamp").stream()

    message_list = []
    for msg in messages:
        msg_data = msg.to_dict()
        message_list.append(msg_data)

        role = msg_data.get("role", "unknown")
        content_preview = msg_data.get("content", "")[:100]
        timestamp = msg_data.get("timestamp", "NO TIMESTAMP")

        print(f"\n  [{msg.id}]")
        print(f"    Role: {role}")
        print(f"    Timestamp: {timestamp}")
        print(f"    Content Preview: {content_preview}...")
        print(f"    Full Content Length: {len(msg_data.get('content', ''))} chars")

        # Metadaten?
        if "metadata" in msg_data:
            print(f"    Metadata: {msg_data['metadata']}")

    print(f"\n📊 TOTAL: {len(message_list)} Messages gefunden")

    # 3. Embeddings?
    print("\n🧠 Embeddings:")
    embeddings_ref = db.collection("embeddings")
    query = embeddings_ref.where("chat_id", "==", chat_id).limit(5)
    embeddings = list(query.stream())

    if embeddings:
        print(f"  ✅ {len(embeddings)} Embeddings gefunden (zeige erste 5)")
        for emb in embeddings[:3]:
            emb_data = emb.to_dict()
            print(f"    - Message ID: {emb_data.get('message_id', 'N/A')}")
    else:
        print("  ⚠️ Keine Embeddings gefunden")

    print("\n" + "=" * 80)

    # 4. DIAGNOSE
    print("\n🩺 DIAGNOSE:")

    if not message_list:
        print("❌ PROBLEM: Keine Messages in Firestore!")
        print("   Mögliche Ursachen:")
        print("   - save_message() schlägt fehl")
        print("   - Permissions-Problem")
        print("   - Parser gibt leere Messages zurück")
    elif all(msg.get("timestamp") is None for msg in message_list):
        print("⚠️ PROBLEM: Keine Timestamps!")
        print("   → Messages können nicht sortiert werden")
        print("   → Werden möglicherweise nicht im Chat angezeigt")
    else:
        print("✅ Messages haben Timestamps")

        # Prüfe Reihenfolge
        timestamps = [
            msg.get("timestamp") for msg in message_list if msg.get("timestamp")
        ]
        if len(set(timestamps)) == 1:
            print("⚠️ WARNUNG: Alle Messages haben EXAKT denselben Timestamp!")
            print("   → Reihenfolge ist undefiniert")
        else:
            print("✅ Messages haben unterschiedliche Timestamps")


def find_latest_deepseek_import():
    """Findet den neuesten DeepSeek-Import"""
    db = get_firestore_client()

    # Suche nach "Import (DeepSeek)"
    chats_ref = db.collection("chats")
    query = (
        chats_ref.where("title", "==", "Import (DeepSeek)")
        .order_by("createdAt", direction=firestore.Query.DESCENDING)
        .limit(1)
    )

    results = list(query.stream())

    if not results:
        print("❌ Kein 'Import (DeepSeek)' Chat gefunden!")
        print("\nSuche nach allen Chats mit 'DeepSeek' im Titel...")

        # Fallback: Alle Chats durchsuchen
        all_chats = (
            chats_ref.order_by("createdAt", direction=firestore.Query.DESCENDING)
            .limit(20)
            .stream()
        )

        for chat in all_chats:
            data = chat.to_dict()
            title = data.get("title", "")
            if "deepseek" in title.lower():
                print(f"  Gefunden: {title} (ID: {chat.id})")
                return chat.id

        return None

    chat_doc = results[0]
    print(f"✅ Neuester Import gefunden: {chat_doc.id}")
    return chat_doc.id


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Inspiziert DeepSeek-Import in Firestore"
    )
    parser.add_argument(
        "--chat-id", help="Spezifische Chat-ID (oder leer für neuesten Import)"
    )

    args = parser.parse_args()

    if args.chat_id:
        chat_id = args.chat_id
    else:
        print("🔍 Suche neuesten DeepSeek-Import...\n")
        chat_id = find_latest_deepseek_import()

        if not chat_id:
            print("\n❌ Kein DeepSeek-Import gefunden!")
            return

    inspect_chat(chat_id)


if __name__ == "__main__":
    main()
