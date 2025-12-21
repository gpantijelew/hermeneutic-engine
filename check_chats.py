import firebase_admin
from firebase_admin import credentials, firestore
import os
from dotenv import load_dotenv

# Config laden
load_dotenv()
KEY_FILE = "comparative-studies-ai-models-1bf59eb77077.json"

if not firebase_admin._apps:
    cred = credentials.Certificate(KEY_FILE)
    firebase_admin.initialize_app(cred)

db = firestore.client()

print("🔍 Lese 'chats' Collection...")
docs = db.collection('chats').stream()

count = 0
pdf_count = 0

for doc in docs:
    data = doc.to_dict()
    count += 1
    title = data.get('title', 'Ohne Titel')
    model = data.get('model') or data.get('model_name')

    if "doc_" in doc.id:
        pdf_count += 1
        print(f"✅ PDF GEFUNDEN: ID={doc.id} | Title='{title}' | Model='{model}'")

print(f"\nGesamt: {count} Chats. Davon PDFs: {pdf_count}")