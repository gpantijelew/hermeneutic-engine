# debug_raw.py
import os
import glob
import json
from google.cloud import firestore
from dotenv import load_dotenv
import datetime

# Auth Setup
load_dotenv()
if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
    for f in glob.glob("*.json"):
        if "service_account" in open(f).read():
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.abspath(f)
            print(f"🔑 Auth: {f}")
            break

# Helper für JSON Datum
def json_serial(obj):
    if isinstance(obj, (datetime.datetime, datetime.date)):
        return obj.isoformat()
    raise TypeError ("Type not serializable")

def deep_scan():
    db = firestore.Client()
    print("\n--- RAW DATA INSPECTOR ---")

    # 1. Zeige 3 zufällige Dokumente KOMPLETT an
    print("1. Analysiere Schema (3 zufällige Samples):")
    docs = db.collection("embeddings").limit(3).stream()

    for i, doc in enumerate(docs, 1):
        data = doc.to_dict()
        # Embedding Vektor kürzen für Lesbarkeit
        if 'embedding' in data:
            data['embedding'] = "[VECTOR DATA HIDDEN]"

        print(f"\n--- SAMPLE {i} (ID: {doc.id}) ---")
        print(json.dumps(data, indent=2, default=json_serial, ensure_ascii=False))

    # 2. Suche den ChatGPT Text über den INHALT (nicht Metadaten)
    print("\n2. Suche nach 'ChatGPT 5.2' im INHALT (Content Scan)...")
    # Wir scannen bis zu 1000 Dokumente
    all_docs = db.collection("embeddings").limit(1000).stream()

    found = False
    for doc in all_docs:
        data = doc.to_dict()
        content = data.get('content', '')

        # Suche nach Fragmenten
        if "ChatGPT" in content and "5.2" in content:
            print(f"\n✅ TREFFER GEFUNDEN! (ID: {doc.id})")
            print("Hier sind die Metadaten dieses Dokuments:")
            print(json.dumps(data.get('metadata', {}), indent=2, ensure_ascii=False))
            found = True
            break

    if not found:
        print("❌ Auch im Inhalt nichts gefunden. Wurde die Datei überhaupt importiert?")

if __name__ == "__main__":
    deep_scan()