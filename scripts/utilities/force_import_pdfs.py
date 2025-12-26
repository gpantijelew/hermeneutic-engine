import os
import sys
import firebase_admin
from firebase_admin import credentials, firestore
from pypdf import PdfReader
from dotenv import load_dotenv
import google.generativeai as genai
import datetime # <--- NEU

# Pfad-Hack
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.vector_store import FirestoreVectorStore

# --- KONFIGURATION ---
PDF_SOURCE_DIR = r"c:\SharedWin11\Verwaltungsgerichte" 
KEY_FILE = "comparative-studies-ai-models-1bf59eb77077.json"
# ---------------------

def init_environment():
    """Lädt API Keys aus .env"""
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    if not os.path.exists(env_path):
        env_path = os.path.join(os.path.dirname(__file__), '..', '.env')

    if os.path.exists(env_path):
        print(f"🌍 Lade Umgebungsvariablen aus: {os.path.abspath(env_path)}")
        load_dotenv(env_path)
        return True
    return False

def init_firestore():
    """Initialisiert Firestore"""
    if not firebase_admin._apps:
        key_path = KEY_FILE
        if not os.path.exists(key_path):
            key_path = os.path.join(os.path.dirname(__file__), KEY_FILE)
        if not os.path.exists(key_path):
            key_path = os.path.join(os.path.dirname(__file__), '..', KEY_FILE)

        print(f"🔑 Nutze DB-Schlüssel: {os.path.abspath(key_path)}")

        if os.path.exists(key_path):
            cred = credentials.Certificate(key_path)
            firebase_admin.initialize_app(cred)
        else:
            print(f"❌ FEHLER: Schlüsseldatei nicht gefunden!")
            sys.exit(1)

    return firestore.client()

def extract_text_from_pdf(filepath):
    try:
        reader = PdfReader(filepath)
        text = ""
        for page in reader.pages:
            t = page.extract_text()
            if t: text += t + "\n"
        return text
    except Exception as e:
        print(f"❌ Fehler beim Lesen von {filepath}: {e}")
        return None

def create_chat_metadata(db, chat_id, title, model_name="PDF-Import"):
    """
    Erstellt den 'Katalog-Eintrag' in der 'chats' Collection,
    damit die UI die Datei anzeigt.
    """
    try:
        doc_ref = db.collection('chats').document(chat_id)
        doc_ref.set({
            'id': chat_id,
            'title': title,
            'created_at': firestore.SERVER_TIMESTAMP,
            'model': model_name,
            'tags': ['pdf', 'import', 'dokument'],
            'message_count': 1,
            'is_document': True # Optionales Flag für später
        }, merge=True)
        print(f"📝 Metadaten für UI erstellt: {title}")
    except Exception as e:
        print(f"❌ Fehler beim Erstellen der Metadaten: {e}")

def main():
    print("🚀 Starte PDF Force-Import (mit UI-Fix)...")

    init_environment()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("❌ CRITICAL: GEMINI_API_KEY fehlt in .env!")
        return

    genai.configure(api_key=api_key)
    print("✅ Gemini API Key konfiguriert.")

    try:
        db = init_firestore()
        vector_store = FirestoreVectorStore(db)
        print("✅ Datenbank & VectorStore verbunden.")
    except Exception as e:
        print(f"❌ Init Fehler: {e}")
        return

    if len(sys.argv) > 1:
        source_dir = sys.argv[1]
    else:
        source_dir = PDF_SOURCE_DIR

    if not os.path.exists(source_dir):
        print(f"❌ Ordner nicht gefunden: {source_dir}")
        return

    files = [f for f in os.listdir(source_dir) if f.lower().endswith('.pdf')]
    print(f"📂 Gefunden: {len(files)} PDFs in {source_dir}")

    for filename in files:
        filepath = os.path.join(source_dir, filename)
        print(f"\n--- Verarbeite: {filename} ---")

        text = extract_text_from_pdf(filepath)
        if not text or len(text) < 100:
            print("⚠️ Überspringe (zu wenig Text).")
            continue

        clean_name = filename.replace(' ', '_').replace('.', '_')
        fake_chat_id = f"doc_{clean_name}"

        # 1. Metadaten für UI erstellen (DAS HAT GEFEHLT!)
        create_chat_metadata(db, fake_chat_id, filename)

        # 2. Vektorisieren (Wie vorher)
        custom_meta = {
            "chat_title": filename,
            "source_type": "pdf_document",
            "speaker": "Dokument",
            "model_name": "PDF-Import",
            "date": "2024-01-01" 
        }

        fake_messages = [{
            "role": "system",
            "content": f"DOKUMENT INHALT:\n{text}",
            "id": "part_1"
        }]

        try:
            chunks, skipped = vector_store.process_and_store_chat(
                chat_id=fake_chat_id,
                messages=fake_messages,
                custom_metadata=custom_meta
            )
            print(f"✅ Vektoren gespeichert: {chunks} Chunks.")
        except Exception as e:
            print(f"❌ Fehler beim Speichern der Vektoren: {e}")

    print("\n🎉 Fertig. Jetzt sollten sie in der Liste auftauchen!")

if __name__ == "__main__":
    main()