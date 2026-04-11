# --- OPFER-ZEILE (Schutz vor Copy-Paste-Fehlern) ---
"""
EPUB Importer Module (v49.9 Brute Force Layout)

Änderungen:
- Inline-Tags werden komplett aufgelöst (unwrap), um "1re" zu retten.
- Block-Tags erhalten einen Text-Marker (|||BLOCK|||), der NACH der Extraktion zu \n wird.
- strip=False beim Text-Holen, damit wir die Kontrolle behalten.
- Aggressive Regex-Reinigung für französische Typografie.
"""

import os
import tempfile
import re
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from ..base import BaseImporter
from modules.database import create_chat_in_firestore, save_message

class EPubImporter(BaseImporter):
    @property
    def platform_name(self): return "eBook (ePub)"

    @property
    def platform_id(self): return "epub"

    def parse(self, content: Any, **kwargs) -> List[Dict[str, Any]]:
        """
        Extrahiert Text aus ePub mit Brute-Force Block-Trennung.
        """
        container = kwargs.get('container')

        try:
            import ebooklib
            from ebooklib import epub
        except ImportError:
            error_msg = "❌ Bibliothek 'ebooklib' fehlt. Bitte `pip install ebooklib` ausführen."
            if container: container.error(error_msg)
            raise ImportError(error_msg)

        tmp_path = None
        try:
            # 1. Datei temporär speichern
            if hasattr(content, 'read'):
                if hasattr(content, 'seek'): content.seek(0)
                file_bytes = content.read()
            else:
                file_bytes = content

            with tempfile.NamedTemporaryFile(delete=False, suffix='.epub') as tmp:
                tmp.write(file_bytes)
                tmp_path = tmp.name

            # 2. Buch laden
            book = epub.read_epub(tmp_path)

            # Metadaten
            title = "Unbekanntes Buch"
            author = "Unbekannter Autor"
            try:
                t_meta = book.get_metadata('DC', 'title')
                if t_meta: title = t_meta[0][0]
                a_meta = book.get_metadata('DC', 'creator')
                if a_meta: author = a_meta[0][0]
            except: pass

            if container: 
                container.info(f"📚 Buch erkannt: '{title}' von {author}")

            full_text_parts = []

            # Marker für Zeilenumbrüche (etwas, das im Buch nicht vorkommt)
            BLOCK_MARKER = " |||BLOCK||| "

            # 3. Iteration über Spine
            for item_ref in book.spine:
                item = book.get_item_with_id(item_ref[0])

                if item and item.get_type() == ebooklib.ITEM_DOCUMENT:
                    soup = BeautifulSoup(item.get_content(), 'html.parser')

                    # A. Müll entfernen
                    for element in soup(['script', 'style', 'nav', 'footer', 'header', 'meta', 'noscript']):
                        element.decompose()

                    # B. Inline-Tags auflösen (UNWRAP)
                    # Das entfernt die Tags, behält aber den Inhalt.
                    # Wichtig: Damit wird aus "1" + "<sup>re</sup>" -> "1" + "re".
                    inline_tags = ['b', 'i', 'em', 'strong', 'sup', 'sub', 'span', 'a', 'small', 'big', 'u', 'font']
                    for tag in soup.find_all(inline_tags):
                        tag.unwrap()

                    # C. Block-Tags markieren
                    # Wir fügen den Marker NACH dem Tag ein.
                    block_tags = ['p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'blockquote', 'article', 'section', 'tr']
                    for tag in soup.find_all(block_tags):
                        tag.insert_after(BLOCK_MARKER)

                    # <br> ist auch ein Marker
                    for br in soup.find_all('br'):
                        br.replace_with(BLOCK_MARKER)

                    # D. Text extrahieren
                    # separator=' ' sorgt dafür, dass Wörter nicht zusammenkleben.
                    # strip=False sorgt dafür, dass unsere Marker nicht versehentlich beschnitten werden.
                    text = soup.get_text(separator=' ', strip=False)

                    # E. Nachbearbeitung (Cleaning)

                    # 1. Marker zu Newlines
                    text = text.replace("|||BLOCK|||", "\n\n")

                    # 2. Whitespace aufräumen
                    # Alle Tabs und geschützten Leerzeichen zu normalen Leerzeichen
                    text = text.replace('\t', ' ').replace('\xa0', ' ')
                    # Mehrfache Leerzeichen zu einem (aber Newlines schützen!)
                    # Wir splitten an Newlines, bereinigen die Zeilen, und fügen wieder zusammen.
                    lines = [re.sub(r' +', ' ', line).strip() for line in text.split('\n')]
                    text = '\n'.join(lines)

                    # 3. Französische Typografie & OCR-Fehler
                    # "1 re" -> "1re"
                    text = re.sub(r'(\d)\s+(re|er|e)\b', r'\1\2', text)
                    # "l' ami" -> "l'ami"
                    text = re.sub(r"\b(l|d|n|j|m|t|s|c|qu)'\s+", r"\1'", text, flags=re.IGNORECASE)
                    text = re.sub(r"\b(l|d|n|j|m|t|s|c|qu)’\s+", r"\1’", text, flags=re.IGNORECASE)

                    # 4. Punctuation Cleanup
                    # Leerzeichen vor Satzzeichen weg: "Wort ." -> "Wort."
                    text = re.sub(r'\s+([.,;:)!\]?])', r'\1', text)
                    # Leerzeichen nach Klammer auf weg: "( Wort" -> "(Wort"
                    text = re.sub(r'([(\[])\s+', r'\1', text)

                    # 5. Leere Zeilen reduzieren
                    text = re.sub(r'\n{3,}', '\n\n', text)

                    if len(text) > 50:
                        full_text_parts.append(text)

            # Cleanup
            try: os.unlink(tmp_path)
            except: pass

            if not full_text_parts:
                if container: container.warning("⚠️ ePub scheint leer zu sein (oder DRM-geschützt).")
                return []

            # Zusammenfügen
            raw_text = "\n\n--- KAPITELWECHSEL ---\n\n".join(full_text_parts)

            # Finales Cleaning
            cleaned_text = re.sub(r'\n{3,}', '\n\n', raw_text)

            # Chunking
            CHUNK_SIZE = 15000
            messages = []

            # Intro
            intro_text = (
                f"**eBook Import**\n"
                f"**Titel:** {title}\n"
                f"**Autor:** {author}\n\n"
                f"*Der Inhalt wurde aus dem ePub-Format extrahiert.*"
            )
            messages.append({"role": "system", "content": intro_text})

            # Content
            for i in range(0, len(cleaned_text), CHUNK_SIZE):
                chunk = cleaned_text[i : i + CHUNK_SIZE]
                messages.append({"role": "model", "content": chunk})

            if container:
                container.success(f"✅ Import fertig: {len(messages)} Abschnitte generiert.")

            return messages

        except Exception as e:
            if tmp_path and os.path.exists(tmp_path):
                try: os.unlink(tmp_path)
                except: pass
            if container: container.error(f"❌ ePub Fehler: {e}")
            return []

    def import_to_firestore(self, messages: List[Dict[str, Any]], metadata: Optional[Dict] = None) -> Dict[str, Any]:
        if not messages: return {'chat_id': None, 'message_count': 0}

        first_content = messages[0].get('content', '')
        title_match = re.search(r'\*\*Titel:\*\*\s*(.+)', first_content)
        chat_title = f"📖 {title_match.group(1).strip()}" if title_match else "eBook Import"

        chat_id = create_chat_in_firestore(chat_title)
        if not chat_id: return {'chat_id': None, 'message_count': 0}

        saved_count = 0
        for msg in messages:
            if msg.get('content'):
                save_message(chat_id, msg.get('role', 'model'), msg['content'])
                saved_count += 1

        return {'chat_id': chat_id, 'message_count': saved_count, 'model_name': 'eBook Reader'}