#!/usr/bin/env python3
"""
Schnelltest: Wurde der Perplexity-Import korrekt gespeichert?
"""

import sys
import os

sys.path.insert(0, os.path.abspath("."))

from google.cloud import firestore
from modules.config import SERVICE_ACCOUNT_KEY_PATH


def check_chat(chat_id: str):
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = SERVICE_ACCOUNT_KEY_PATH
    db = firestore.Client(project="comparative-studies-ai-models")

    print(f"🔍 Prüfe Chat: {chat_id}\n")

    # Messages
    messages_ref = db.collection("chats").document(chat_id).collection("messages")
    messages = list(messages_ref.order_by("timestamp").stream())

    print(f"📊 Total: {len(messages)} Messages\n")

    if messages:
        print("✅ Messages gefunden!")
        for i, msg in enumerate(messages[:3], 1):
            data = msg.to_dict()
            print(f"\n  Message {i}:")
            print(f"    Role: {data.get('role')}")
            print(f"    Content: {data.get('content')[:100]}...")
    else:
        print("❌ Keine Messages in Firestore!")
        print("   → Parser hat NICHT gespeichert!")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--chat-id", default="bQfDeiM9cWom7XkRDfh0")
    args = parser.parse_args()

    check_chat(args.chat_id)
