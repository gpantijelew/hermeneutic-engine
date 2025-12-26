import os
import sys
import firebase_admin
from firebase_admin import credentials, firestore
from pypdf import PdfReader
from dotenv import load_dotenv

# Konfiguration
PDF_SOURCE_DIR = r"c:\SharedWin11\Verwaltungsgerichte"
KEY_FILE = "comparative-studies-ai-models-1bf59eb77077.json"

def init_firestore():
    if not firebase_admin._apps:
        key_path = os.path.join(os.path.dirname(__file__), KEY_FILE)
        if os.path.exists(key_path):
            print(f"🔑 Nutze Schlüssel: {key_path}")
            cred = credentials.Certificate(key_path)
            firebase_admin.initialize_app(cred)
            return firestore.client()
        else:
            print(f"❌ FEHLER: Schlüsseldatei nicht gefunden: {key_path}")
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

def main():
    print("📝 Starte Reparatur der PDF-Inhalte (Sichtbarkeit)...")

    try:
        db = init_firestore()
    except Exception as e:
        print(f"❌ DB Fehler: {e}")
        return

    if not os.path.exists(PDF_SOURCE_DIR):
        print(f"❌ Ordner nicht gefunden: {PDF_SOURCE_DIR}")
        return

    files = [f for f in os.listdir(PDF_SOURCE_DIR) if f.lower().endswith('.pdf')]
    print(f"📂 Gefunden: {len(files)} PDFs.")

    for filename in files:
        filepath = os.path.join(PDF_SOURCE_DIR, filename)

        # ID rekonstruieren (muss exakt gleich sein wie beim Import!)
        clean_name = filename.replace(' ', '_').replace('.', '_')
        chat_id = f"doc_{clean_name}"

        print(f"\n--- Prüfe: {filename} ---")

        # Checken, ob schon Nachrichten da sind
        messages_ref = db.collection('chats').document(chat_id).collection('messages')
        existing_msgs = list(messages_ref.limit(1).stream())

        if len(existing_msgs) > 0:
            print("✅ Inhalt bereits sichtbar (überspringe).")
            continue

        # Text holen
        text = extract_text_from_pdf(filepath)
        if not text:
            print("⚠️ Kein Text extrahierbar.")
            continue

        # Als Nachricht speichern
        try:
            # Wir speichern es als "model"-Nachricht, damit es links erscheint (wie eine Antwort)
            # oder als "user", je nach Geschmack. "model" liest sich bei Dokumenten oft besser.
            message_data = {
                'role': 'model', 
                'content': f"📄 **DOKUMENT-INHALT**\n\n{text}",
                'timestamp': firestore.SERVER_TIMESTAMP,
                'type': 'pdf_content'
            }

            messages_ref.add(message_data)
            print(f"✅ Inhalt gespeichert! (Jetzt sichtbar)")

        except Exception as e:
            print(f"❌ Fehler beim Speichern: {e}")

    print("\n🎉 Fertig. Lade die App neu und klicke auf die PDFs!")

if __name__ == "__main__":
    main()