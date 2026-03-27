# export_firestore.py — einmaliges Export-Skript

import firebase_admin
from firebase_admin import credentials, firestore
import json, uuid
from datetime import datetime

cred = credentials.Certificate(".secrets/comparative-studies-ai-models-1bf59eb77077.json")  # oder Service-Account-JSON
firebase_admin.initialize_app(cred)
db = firestore.client()

# Custom Serializer für Firestore-Timestamps
def firestore_serializer(obj):
    if hasattr(obj, 'isoformat'):
        return obj.isoformat()
    if hasattr(obj, '_seconds'):  # DatetimeWithNanoseconds
        return datetime.fromtimestamp(obj._seconds).isoformat()
    raise TypeError(f"Not serializable: {type(obj)}")

# 1. Chunks exportieren (Text + Metadaten, OHNE Embeddings)
chunks = []
for doc in db.collection("embeddings").stream():
    data = doc.to_dict()
    chunks.append({
        "id": doc.id,
        "text": data.get("text", ""),
        "metadata": {
            "speaker": data.get("speaker"),
            "date": data.get("date"),
            "version": data.get("version"),
            "chunk_type": data.get("chunk_type"),
            "source": data.get("source"),
            # alle weiteren Felder, die du in Metadaten-Extraktoren verwendest
        }
    })

with open("export_chunks.json", "w", encoding="utf-8") as f:
    json.dump(chunks, f, ensure_ascii=False, indent=2, default=firestore_serializer)

print(f"Exportiert: {len(chunks)} Chunks")

# 2. Chats exportieren
chats = []
for chat_doc in db.collection("chats").stream():
    chat_data = chat_doc.to_dict()
    messages = []
    for msg in db.collection("chats").document(chat_doc.id)\
                 .collection("messages").order_by("timestamp").stream():
        messages.append(msg.to_dict())
    chats.append({
        "id": chat_doc.id,
        "metadata": chat_data,
        "messages": messages
    })

with open("export_chats.json", "w", encoding="utf-8") as f:
    json.dump(chats, f, ensure_ascii=False, indent=2, default=firestore_serializer)

print(f"Exportiert: {len(chats)} Chats")

# 3. Settings exportieren
settings = db.collection("settings").document("global").get().to_dict()
with open("export_settings.json", "w", encoding="utf-8") as f:
    json.dump(settings, f, ensure_ascii=False, indent=2, default=firestore_serializer)

print("Settings exportiert.")