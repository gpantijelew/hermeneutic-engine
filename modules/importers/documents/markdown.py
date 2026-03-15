"""
Markdown Importer (v50.8).

Spezialisiert auf Typora-Texte, Buchfragmente und Markdown-Notizen.
Erhält die native Markdown-Formatierung, was für das spätere semantische Chunking
im Vector-Store (RAG) extrem wertvoll ist.
"""

import re
from typing import List, Dict, Any, Optional
from ..base import BaseImporter

# Datenbank-Funktionen (wie in base.py)
from modules.database import (
    create_chat_in_firestore, 
    save_message, 
    generate_and_update_title, 
    delete_chat
)

class MarkdownImporter(BaseImporter):
    @property
    def platform_name(self) -> str: 
        return "Markdown Document"

    @property
    def platform_id(self) -> str: 
        return "markdown"

    def parse(self, content: Any, **kwargs) -> List[Dict[str, Any]]:
        """
        Liest die Markdown-Datei. Erkennt automatisch, ob es sich um einen
        zusammenhängenden Text (Typora/Buch) oder einen Chat-Export handelt.
        """
        # 1. Sicheres Decoding
        if isinstance(content, bytes):
            try:
                text = content.decode('utf-8')
            except UnicodeDecodeError:
                text = content.decode('latin-1', errors='ignore')
        else:
            text = str(content)

        # BOM (Byte Order Mark) entfernen, falls vorhanden
        text = text.lstrip('\ufeff')

        # NEU: Überflüssige Zeilenumbrüche (3 oder mehr) auf exakt 2 (Standard-Absatz) reduzieren
        text = re.sub(r'\n{3,}', '\n\n', text)

        if not text.strip():
            return []

        # 2. Heuristik: Ist es ein Chat-Protokoll?
        # Sucht nach Mustern wie "**User:**", "### Assistant:", "Human:" am Zeilenanfang
        chat_pattern = re.compile(
            r'^(?:\*\*|###\s*)?(User|Human|Assistant|Model|AI|System)(?:\*\*|:)\s*$', 
            re.IGNORECASE | re.MULTILINE
        )

        # Wenn wir mehr als 2 solcher Marker finden, behandeln wir es als Chat
        if len(chat_pattern.findall(text)) > 2:
            return self._parse_as_chat(text, chat_pattern)

        # 3. Standard-Fall (Typora, Buchfragmente)
        # Das gesamte Dokument wird als eine kohärente Nachricht importiert.
        return [{'role': 'user', 'content': text.strip()}]

    def _parse_as_chat(self, text: str, pattern: re.Pattern) -> List[Dict[str, Any]]:
        """Splittet ein Markdown-Dokument, wenn es als Chat erkannt wurde."""
        messages = []
        parts = pattern.split(text)

        # Preamble (Text vor dem ersten Marker)
        if parts[0].strip():
            messages.append({'role': 'system', 'content': parts[0].strip()})

        for i in range(1, len(parts), 2):
            role_str = parts[i].lower()
            content_str = parts[i+1].strip() if i+1 < len(parts) else ""

            if not content_str: 
                continue

            # Rollen-Mapping
            if role_str in ['assistant', 'model', 'ai']:
                role = 'model'
            elif role_str == 'system':
                role = 'system'
            else:
                role = 'user'

            messages.append({'role': role, 'content': content_str})

        return messages

    def import_to_firestore(
        self, 
        messages: List[Dict[str, Any]], 
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Speichert das Markdown-Dokument in der Datenbank."""
        if not messages:
            return {'chat_id': None, 'message_count': 0}

        # Dokument in DB anlegen
        chat_id = create_chat_in_firestore("Import (Markdown)")
        if not chat_id:
            return {'chat_id': None, 'message_count': 0}

        # NEU: Metadaten bereinigen (Streamlit-Container entfernen, da nicht DB-kompatibel)
        safe_metadata = {}
        if metadata:
            for key, value in metadata.items():
                # Wir speichern nur einfache Datentypen, keine UI-Objekte
                if key != 'container' and isinstance(value, (str, int, float, bool, list, dict)):
                    safe_metadata[key] = value

        saved_count = 0
        for msg in messages:
            # Hier nutzen wir jetzt safe_metadata statt metadata
            if save_message(chat_id, msg['role'], msg['content'], metadata=safe_metadata):
                saved_count += 1

        # Titel generieren (aus dem Inhalt)
        if saved_count > 0:
            generate_and_update_title(chat_id, messages[:3])
            return {'chat_id': chat_id, 'message_count': saved_count}
        else:
            delete_chat(chat_id)
            return {'chat_id': None, 'message_count': 0}