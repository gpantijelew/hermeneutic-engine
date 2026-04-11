# --- OPFER-ZEILE (Schutz vor Copy-Paste-Fehlern) ---
"""
FB2 Importer Module (FictionBook 2.0) - FIXED

Korrektur:
- Fehlender 'except'-Block am Ende der parse-Methode hinzugefügt.
"""

import re
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from ..base import BaseImporter
from modules.database import create_chat_in_firestore, save_message

class FB2Importer(BaseImporter):
    @property
    def platform_name(self): return "eBook (FB2)"

    @property
    def platform_id(self): return "fb2"

    def parse(self, content: Any, **kwargs) -> List[Dict[str, Any]]:
        """
        Extrahiert Text aus FB2 XML.
        """
        container = kwargs.get('container')

        # Check für lxml (wichtig für XML Parsing)
        try:
            import lxml
        except ImportError:
            if container: container.warning("⚠️ 'lxml' fehlt. FB2-Parsing könnte ungenau sein. `pip install lxml` empfohlen.")

        try:
            # 1. Content lesen
            if hasattr(content, 'read'):
                if hasattr(content, 'seek'): content.seek(0)
                file_bytes = content.read()
            else:
                file_bytes = content

            # 2. XML Parsen
            # Wir nutzen 'xml' als Parser, da FB2 valides XML ist
            soup = BeautifulSoup(file_bytes, 'xml')

            # 3. Metadaten extrahieren
            title = "Unbekanntes Buch"
            author = "Unbekannter Autor"

            try:
                desc = soup.find('description')
                if desc:
                    t_info = desc.find('title-info')
                    if t_info:
                        t_tag = t_info.find('book-title')
                        if t_tag: title = t_tag.get_text(strip=True)

                        a_tag = t_info.find('author')
                        if a_tag:
                            # Autoren in FB2 sind oft in <first-name> und <last-name> geteilt
                            f_name = a_tag.find('first-name')
                            l_name = a_tag.find('last-name')
                            parts = []
                            if f_name: parts.append(f_name.get_text(strip=True))
                            if l_name: parts.append(l_name.get_text(strip=True))
                            if parts: author = " ".join(parts)
            except Exception as e:
                if container: container.warning(f"⚠️ Metadaten-Fehler: {e}")

            if container: 
                container.info(f"📚 FB2 erkannt: '{title}' von {author}")

            # 4. Text-Extraktion (Brute Force Logic)

            # Wir suchen den <body>. FB2 kann mehrere Bodies haben.
            bodies = soup.find_all('body')
            full_text_parts = []

            BLOCK_MARKER = " |||BLOCK||| "

            for body in bodies:
                # A. Binärdaten (Bilder) entfernen
                for binary in body.find_all('binary'):
                    binary.decompose()

                # B. Inline-Tags auflösen (UNWRAP)
                inline_tags = ['emphasis', 'strong', 'style', 'a', 'sub', 'sup', 'code']
                for tag in body.find_all(inline_tags):
                    tag.unwrap()

                # C. Block-Tags markieren
                block_tags = ['p', 'title', 'subtitle', 'v', 'stanza', 'section', 'epigraph', 'text-author', 'cite']
                for tag in body.find_all(block_tags):
                    tag.insert_after(BLOCK_MARKER)

                # D. Text extrahieren
                text = body.get_text(separator=' ', strip=False)

                # E. Cleaning

                # Marker zu Newlines
                text = text.replace("|||BLOCK|||", "\n\n")

                # Whitespace
                text = text.replace('\t', ' ').replace('\xa0', ' ')
                lines = [re.sub(r' +', ' ', line).strip() for line in text.split('\n')]
                text = '\n'.join(lines)

                # Typografie Fixes
                text = re.sub(r'(\d)\s+(re|er|e)\b', r'\1\2', text)
                text = re.sub(r"\b(l|d|n|j|m|t|s|c|qu)'\s+", r"\1'", text, flags=re.IGNORECASE)
                text = re.sub(r"\b(l|d|n|j|m|t|s|c|qu)’\s+", r"\1’", text, flags=re.IGNORECASE)

                # Punctuation
                text = re.sub(r'\s+([.,;:)!\]?])', r'\1', text)
                text = re.sub(r'([(\[])\s+', r'\1', text)

                # Leere Zeilen
                text = re.sub(r'\n{3,}', '\n\n', text)

                if len(text) > 50:
                    full_text_parts.append(text)

            if not full_text_parts:
                if container: container.warning("⚠️ FB2 scheint leer zu sein.")
                return []

            # Zusammenfügen
            raw_text = "\n\n--- ABSCHNITT ---\n\n".join(full_text_parts)
            cleaned_text = re.sub(r'\n{3,}', '\n\n', raw_text)

            # Chunking
            CHUNK_SIZE = 15000
            messages = []

            intro_text = (
                f"**FB2 Import**\n"
                f"**Titel:** {title}\n"
                f"**Autor:** {author}\n\n"
                f"*Inhalt aus FB2-Format extrahiert.*"
            )
            messages.append({"role": "system", "content": intro_text})

            for i in range(0, len(cleaned_text), CHUNK_SIZE):
                chunk = cleaned_text[i : i + CHUNK_SIZE]
                messages.append({"role": "model", "content": chunk})

            if container:
                container.success(f"✅ Import fertig: {len(messages)} Abschnitte generiert.")

            return messages

        except Exception as e:
            if container: container.error(f"❌ FB2 Fehler: {e}")
            return []

    def import_to_firestore(self, messages: List[Dict[str, Any]], metadata: Optional[Dict] = None) -> Dict[str, Any]:
        if not messages: return {'chat_id': None, 'message_count': 0}

        first_content = messages[0].get('content', '')
        title_match = re.search(r'\*\*Titel:\*\*\s*(.+)', first_content)
        chat_title = f"📖 {title_match.group(1).strip()}" if title_match else "FB2 Import"

        chat_id = create_chat_in_firestore(chat_title)
        if not chat_id: return {'chat_id': None, 'message_count': 0}

        saved_count = 0
        for msg in messages:
            if msg.get('content'):
                save_message(chat_id, msg.get('role', 'model'), msg['content'])
                saved_count += 1

        return {'chat_id': chat_id, 'message_count': saved_count, 'model_name': 'FB2 Reader'}