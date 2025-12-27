"""
Löscht die beiden Test-PDFs aus Firestore, damit wir sie neu importieren können.
"""
import firebase_admin
from firebase_admin import credentials, firestore
import os

# Service Account Key laden
key_path = os.path.join('.secrets', 'comparative-studies-ai-models-1bf59eb77077.json')

if not firebase_admin._apps:
    cred = credentials.Certificate(key_path)
    firebase_admin.initialize_app(cred)

db = firestore.client()

print("🗑️ Lösche Test-PDFs aus Firestore...\n")

# Die beiden PDFs, die wir neu importieren wollen
test_pdf_ids = [
    'doc_Adorno_Essay',
    'doc_Voltaire_(Ayer,_A._J._(Alfred_Jules),_1910-)_(Z-Library)_1986'
]

for chat_id in test_pdf_ids:
    print(f"Lösche: {chat_id}")
    
    # 1. Lösche den Chat-Eintrag
    db.collection('chats').document(chat_id).delete()
    
    # 2. Lösche alle Messages (falls vorhanden)
    messages = db.collection('chats').document(chat_id).collection('messages').stream()
    for msg in messages:
        msg.reference.delete()
    
    # 3. Lösche alle Embeddings
    embeddings = db.collection('embeddings').where('chat_id', '==', chat_id).stream()
    deleted_embeddings = 0
    for emb in embeddings:
        emb.reference.delete()
        deleted_embeddings += 1
    
    print(f"  ✅ Chat gelöscht")
    print(f"  ✅ {deleted_embeddings} Embeddings gelöscht\n")

print("🎉 Fertig! Jetzt kannst du die PDFs neu importieren.")