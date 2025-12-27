"""
force_import_pdfs.py (v49.5 FIXED)

Kritische Fixes:
- Entfernt aggressives Margin-Clipping (war Ursache für verlorenen Text!)
- Nutzt heuristische Header/Footer-Erkennung (Pattern-Matching)
- Verbesserte Text-Kontinuität über Seitengrenzen hinweg

Usage:
    python force_import_pdfs.py                    # Nutzt Standard-Ordner
    python force_import_pdfs.py /path/to/pdfs      # Nutzt angegebenen Ordner
"""

import os
import sys
import re
import datetime
import logging
from collections import Counter

# WICHTIG: Pfad ZUERST hinzufügen
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, PROJECT_ROOT)

# Imports
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv
import google.generativeai as genai

# Projekt-Module
from modules.config import SERVICE_ACCOUNT_KEY_PATH
from modules.vector_store import FirestoreVectorStore
from modules.database import save_message

# PyMuPDF Check
try:
    import fitz  # PyMuPDF
except ImportError:
    print("❌ FEHLER: pymupdf nicht installiert!")
    print("   Installiere mit: pip install pymupdf")
    sys.exit(1)

# --- KONFIGURATION ---
DEFAULT_PDF_DIR = os.path.join(os.path.expanduser("~"), "Documents", "PDFs_to_import")

# WICHTIG: Keine Margin-Config mehr! 
# Wir nutzen jetzt heuristische Header/Footer-Detection
# ---------------------

def init_environment():
    """Lädt API Keys aus .env"""
    env_path = os.path.join(PROJECT_ROOT, '.env')
    if os.path.exists(env_path):
        load_dotenv(env_path)
        return True
    return False

def init_firestore():
    """Initialisiert Firestore"""
    try:
        firebase_admin.get_app()
    except ValueError:
        key_path = SERVICE_ACCOUNT_KEY_PATH
        if not os.path.exists(key_path):
            print(f"❌ FEHLER: Key nicht gefunden: {key_path}")
            sys.exit(1)
        
        cred = credentials.Certificate(key_path)
        firebase_admin.initialize_app(cred)
    
    return firestore.client()

def parse_pdf_date(date_str):
    """Parst PDF-Datumsformat (z.B. D:20240101120000Z)"""
    if not date_str:
        return datetime.date.today().strftime('%Y-%m-%d')
    
    try:
        # Entferne D:, ', und Zeitzonen-Kram grob
        clean = date_str.replace('D:', '').replace("'", "").split('+')[0].split('Z')[0]
        return datetime.datetime.strptime(clean[:8], '%Y%m%d').strftime('%Y-%m-%d')
    except:
        return datetime.date.today().strftime('%Y-%m-%d')

def detect_headers_footers(doc):
    """
    Erkennt wiederkehrende Header/Footer-Patterns (heuristisch).
    
    Logik:
    - Extrahiert die ersten 2 Zeilen (Header) und letzten 2 Zeilen (Footer) pro Seite
    - Zählt, welche Patterns wiederkehren
    - Alles, was auf >50% der Seiten vorkommt, ist ein Header/Footer
    
    Returns:
        (header_patterns, footer_patterns): Sets von Strings zum Filtern
    """
    header_candidates = []
    footer_candidates = []
    
    for page in doc:
        text = page.get_text("text", sort=True)
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        
        if len(lines) >= 2:
            # Erste 2 Zeilen (Header)
            header_candidates.append(lines[0])
            header_candidates.append(lines[1])
            
            # Letzte 2 Zeilen (Footer)
            footer_candidates.append(lines[-1])
            footer_candidates.append(lines[-2])
    
    # Zähle Häufigkeiten
    header_counts = Counter(header_candidates)
    footer_counts = Counter(footer_candidates)
    
    # Schwellwert: Muss auf mindestens 50% der Seiten vorkommen
    threshold = len(doc) * 0.5
    
    headers = {text for text, count in header_counts.items() if count >= threshold}
    footers = {text for text, count in footer_counts.items() if count >= threshold}
    
    return headers, footers

def clean_text(text, headers, footers):
    """
    Bereinigt Text: Entfernt Header/Footer, De-Hyphenation, Leerzeilen.
    """
    lines = text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        stripped = line.strip()
        
        # Skip leere Zeilen
        if not stripped:
            continue
        
        # Skip Header/Footer-Patterns
        if stripped in headers or stripped in footers:
            continue
        
        # Skip reine Seitenzahlen (Regex: nur Zahlen, evtl. mit "Seite" davor)
        if re.match(r'^(Seite\s+)?\d+$', stripped, re.IGNORECASE):
            continue
        
        cleaned_lines.append(line)  # Behalte Original-Einrückung
    
    # Füge Zeilen zusammen
    result = '\n'.join(cleaned_lines)
    
    # De-Hyphenation (auch für Kyrillisch)
    # Pattern: Wort + Bindestrich + Zeilenumbruch + optional Whitespace + Wort
    result = re.sub(r'(\w+)-\n\s*(\w+)', r'\1\2', result)
    
    # Mehrfache Leerzeilen reduzieren (3+ → 2)
    result = re.sub(r'\n{3,}', '\n\n', result)
    
    return result.strip()

def extract_text_and_metadata(filepath):
    """
    Extrahiert Text mit PyMuPDF, entfernt Header/Footer heuristisch.
    
    KRITISCHE ÄNDERUNG v49.5:
    - KEINE Bounding Box mehr!
    - Header/Footer-Detection via Pattern-Matching
    """
    try:
        doc = fitz.open(filepath)
        
        # 1. Header/Footer-Patterns erkennen
        headers, footers = detect_headers_footers(doc)
        
        # 2. Text Extraktion (OHNE Clipping!)
        full_text_parts = []
        
        for page in doc:
            # Extrahiere vollen Text (sort=True für Column-Detection)
            text = page.get_text("text", sort=True)
            if text.strip():
                full_text_parts.append(text)
        
        raw_text = "\n".join(full_text_parts)
        
        # 3. Cleaning mit erkannten Patterns
        cleaned_text = clean_text(raw_text, headers, footers)
        
        # 4. Metadaten
        meta = doc.metadata
        metadata = {
            'title': meta.get('title') or os.path.basename(filepath).replace('.pdf', ''),
            'author': meta.get('author') or 'Unbekannt',
            'date': parse_pdf_date(meta.get('creationDate'))
        }
        
        doc.close()
        return cleaned_text, metadata
    
    except Exception as e:
        print(f"❌ Fehler beim Lesen von {filepath}: {e}")
        return None, None

def create_chat_metadata(db, chat_id, title, author, date):
    """Erstellt den Eintrag in der 'chats' Collection"""
    try:
        doc_ref = db.collection('chats').document(chat_id)
        doc_ref.set({
            'id': chat_id,
            'title': title,
            'created_at': firestore.SERVER_TIMESTAMP,
            'model': "PDF-Import v49.5",
            'tags': ['pdf', 'import', 'dokument'],
            'is_document': True,
            'metadata': {
                'author': author,
                'date': date,
                'source': 'force_import_pdfs_v49.5'
            }
        }, merge=True)
    except Exception as e:
        print(f"❌ Fehler beim Erstellen der Metadaten: {e}")

def main():
    print("🚀 Starte PDF Force-Import (v49.5 - Heuristic Headers)...")
    print("-" * 50)
    
    init_environment()
    
    # API Key Check
    if not os.environ.get("GEMINI_API_KEY"):
        print("❌ CRITICAL: GEMINI_API_KEY fehlt in .env!")
        return
    
    genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
    
    try:
        db = init_firestore()
        vector_store = FirestoreVectorStore(db)
        print("✅ Datenbank & VectorStore verbunden.")
    except Exception as e:
        print(f"❌ Init Fehler: {e}")
        return
    
    # Ordner bestimmen
    source_dir = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PDF_DIR
    
    if not os.path.exists(source_dir):
        print(f"❌ Ordner nicht gefunden: {source_dir}")
        return
    
    files = [f for f in os.listdir(source_dir) if f.lower().endswith('.pdf')]
    print(f"📂 Gefunden: {len(files)} PDFs in {source_dir}")
    print("-" * 50)
    
    imported_count = 0
    skipped_count = 0
    
    for i, filename in enumerate(files, 1):
        filepath = os.path.join(source_dir, filename)
        print(f"\n[{i}/{len(files)}] Verarbeite: {filename}")
        
        # 1. Text & Meta extrahieren (Heuristic Clean)
        text, metadata = extract_text_and_metadata(filepath)
        
        if not text or len(text) < 100:
            print("⚠️ Überspringe (zu wenig Text).")
            skipped_count += 1
            continue
        
        # 2. ID generieren
        clean_name = re.sub(r'[^a-zA-Z0-9_]', '_', filename.replace('.pdf', ''))
        chat_id = f"doc_{clean_name}"
        
        # 3. Check ob existiert
        if db.collection('chats').document(chat_id).get().exists:
            print("⏭️ Überspringe (bereits importiert).")
            skipped_count += 1
            continue
        
        # 4. Metadaten schreiben
        create_chat_metadata(db, chat_id, metadata['title'], metadata['author'], metadata['date'])
        
        # 5. Vektorisieren
        fake_messages = [{
            "role": "system",
            "content": f"DOKUMENT: {metadata['title']}\nAUTOR: {metadata['author']}\n\n{text}",
            "id": "full_doc"
        }]
        
        custom_meta = {
            "chat_title": metadata['title'],
            "source_type": "pdf_document",
            "author": metadata['author'],
            "date": metadata['date']
        }
        
        try:
            chunks, skipped = vector_store.process_and_store_chat(
                chat_id=chat_id,
                messages=fake_messages,
                custom_metadata=custom_meta
            )
            print(f"✅ Vektoren: {chunks} Chunks gespeichert.")
            
            # 6. Content für UI speichern
            CHUNK_SIZE = 20000
            saved_msgs = 0
            
            # Header Message
            header = f"📄 **{metadata['title']}**\n*{metadata['author']} ({metadata['date']})*\n\n"
            save_message(chat_id, 'system', header)
            
            # Content Messages
            for j in range(0, len(text), CHUNK_SIZE):
                chunk = text[j : j + CHUNK_SIZE]
                save_message(chat_id, 'model', chunk)
                saved_msgs += 1
            
            print(f"✅ UI-Content: {saved_msgs} Nachrichten gespeichert.")
            imported_count += 1
        
        except Exception as e:
            print(f"❌ Fehler beim Speichern: {e}")
            skipped_count += 1
    
    print("\n" + "=" * 50)
    print(f"🎉 Fertig! Importiert: {imported_count} | Übersprungen: {skipped_count}")

if __name__ == "__main__":
    main()