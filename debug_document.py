# debug_document.py
import os
import sys
import glob
import json
from google.cloud import firestore
from dotenv import load_dotenv

# Auth Setup
load_dotenv()
if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
    for f in glob.glob("*.json"):
        if "service_account" in open(f).read():
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.abspath(f)
            print(f"🔑 Auth: {f}")
            break

def inspect_document():
    db = firestore.Client()
    print("\n--- DOKUMENT INSPEKTOR ---")

    # 1. Suche nach dem Dokument-Titel
    search_term = "ChatGPT 5.2" # Teil des Titels
    print(f"Suche nach Chunks mit Titel-Fragment: '{search_term}'...")

    # Wir müssen leider scannen, da Titel oft in Metadata stecken
    # Wir schauen uns die ersten 500 Chunks an (sollte reichen)
    docs = db.collection("embeddings").limit(500).stream()

    found_chunks = []

    for doc in docs:
        data = doc.to_dict()
        meta = data.get('metadata', {})
        title = meta.get('chat_title', '') or meta.get('filename', '')

        if search_term.lower() in title.lower():
            found_chunks.append(data)

    if not found_chunks:
        print("❌ Nichts gefunden! Ist der Titel in der DB vielleicht anders?")
        print("   Hier sind 5 zufällige Titel aus der DB:")
        for i, doc in enumerate(db.collection("embeddings").limit(5).stream()):
            m = doc.to_dict().get('metadata', {})
            print(f"   - {m.get('chat_title') or m.get('filename')}")
        return

    print(f"✅ {len(found_chunks)} Chunks gefunden.")

    # 2. Analyse des ersten Treffers
    sample = found_chunks[0]
    meta = sample.get('metadata', {})

    print("\n--- METADATEN ANALYSE (Erster Chunk) ---")
    print(f"ID (chat_id):  {sample.get('chat_id')}")
    print(f"Rolle (role):  '{meta.get('role')}'")  # <--- DAS IST DER KNACKPUNKT
    print(f"Speaker:       '{meta.get('speaker')}'")
    print(f"Model Name:    '{meta.get('model_name')}'")
    print(f"Titel:         '{meta.get('chat_title')}'")

    print("\n--- FILTER CHECK ---")
    role = meta.get('role', 'unknown')
    print(f"Wenn du im UI 'Nur KI' wählst, suchen wir nach: ['model', 'assistant', 'ai', 'ki']")

    if role in ['model', 'assistant', 'ai', 'ki']:
        print("✅ Filter würde PASSEN.")
    else:
        print(f"❌ Filter würde BLOCKIEREN! (Weil '{role}' nicht in der Liste ist)")

if __name__ == "__main__":
    inspect_document()