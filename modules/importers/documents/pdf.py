# modules/importers/documents/pdf.py
"""
PDF Importer Module (v49.5 FIXED)

Kritische Fixes:
- Kein aggressives Bounding-Box-Clipping mehr (frisst Text zwischen Seiten!)
- Intelligente Header/Footer-Erkennung via Pattern-Matching statt Geometrie
- Verbesserte De-Hyphenation (auch für Kyrillisch)
- Seitenübergreifende Text-Kontinuität
- v49.6: Memory Leak Fix (doc.close)

Architektur:
- Extrahiert Text pro Seite mit vollem Rect (keine Margins!)
- Entfernt Header/Footer heuristisch (Seitenzahlen, wiederkehrende Patterns)
- Fügt Seiten nahtlos zusammen
"""
import fitz  # PyMuPDF
import re
from typing import List, Dict, Any, Optional
from collections import Counter
import logging # Für Fehler-Logging

# Relative Imports
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from modules.importers.base import BaseImporter
from modules.database import create_chat_in_firestore, save_message


class PDFImporter(BaseImporter):
    @property
    def platform_name(self): 
        return "PDF Dokument"

    @property
    def platform_id(self): 
        return "pdf"

    def _detect_headers_footers(self, doc: fitz.Document) -> tuple:
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

    def _clean_text(self, text: str, headers: set, footers: set) -> str:
        """
        Bereinigt Text: Entfernt Header/Footer, De-Hyphenation, Leerzeilen.

        Args:
            text: Roher Text
            headers: Set von Header-Patterns
            footers: Set von Footer-Patterns

        Returns:
            Gereinigter Text
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
        # \w+ matcht auch kyrillische Buchstaben in Python 3
        result = re.sub(r'(\w+)-\n\s*(\w+)', r'\1\2', result)

        # Mehrfache Leerzeilen reduzieren (3+ → 2)
        result = re.sub(r'\n{3,}', '\n\n', result)

        return result.strip()

    def parse(self, content: Any, **kwargs) -> List[Dict[str, Any]]:
        """
        Extrahiert Text aus PDF, bereinigt Layout-Artefakte und strukturiert ihn.

        KRITISCHE ÄNDERUNG v49.5:
        - KEINE Bounding Box mehr! (Das war das Problem)
        - Extrahiere vollen Text, filtere heuristisch
        - v49.6: Memory Leak Fix (doc.close)
        """
        container = kwargs.get('container')
        doc = None # Initialisieren für finally-Block

        try:
            # 1. Datei-Bytes laden
            if hasattr(content, 'read'):
                file_bytes = content.read()
            else:
                file_bytes = content

            # Öffnen
            doc = fitz.open(stream=file_bytes, filetype="pdf")

            if container:
                container.info(f"📄 PDF geladen: {len(doc)} Seiten. Analysiere Header/Footer...")

            # 2. Header/Footer-Patterns erkennen
            headers, footers = self._detect_headers_footers(doc)

            if container and (headers or footers):
                container.info(f"🔍 Erkannt: {len(headers)} Header, {len(footers)} Footer-Patterns")

            # 3. Text extrahieren (OHNE Bounding Box!)
            full_content = []

            for i, page in enumerate(doc):
                # Fortschritt im UI
                if container and i % 10 == 0:
                    container.progress(i / len(doc), text=f"Verarbeite Seite {i+1}...")

                # Extrahiere VOLLEN Text (sort=True für Column-Detection)
                text = page.get_text("text", sort=True)

                if text.strip():
                    # Optional: Seiten-Marker (für Referenzen)
                    # Nur bei langen Docs sinnvoll
                    if len(doc) > 5:
                        page_marker = f"\n--- Seite {i+1} ---\n"
                        full_content.append(page_marker + text)
                    else:
                        full_content.append(text)

            if not full_content:
                if container: 
                    container.warning("⚠️ PDF scheint leer zu sein (oder nur Bilder).")
                return []

            # 4. Globales Cleaning
            raw_text = "\n".join(full_content)
            cleaned_text = self._clean_text(raw_text, headers, footers)

            if not cleaned_text or len(cleaned_text) < 100:
                if container:
                    container.warning("⚠️ PDF-Text zu kurz nach Bereinigung.")
                return []

            # 5. Metadaten extrahieren
            meta_info = doc.metadata
            title = meta_info.get('title', 'Unbenanntes Dokument')
            author = meta_info.get('author', 'Unbekannter Autor')

            # 6. In Nachrichten strukturieren
            messages = []

            # Header Message mit Metadaten
            intro_text = (
                f"📄 **{title}**\n"
                f"*Autor: {author}*\n"
                f"*Seiten: {len(doc)}*\n\n"
                f"---\n\n"
                f"*Der folgende Text wurde automatisch aus dem PDF extrahiert und bereinigt.*"
            )

            messages.append({
                "role": "system",
                "content": intro_text
            })

            # Content in Chunks (Firestore-Limit: 1MB pro Doc)
            CHUNK_SIZE = 20000  # Zeichen pro Nachricht

            for i in range(0, len(cleaned_text), CHUNK_SIZE):
                chunk = cleaned_text[i : i + CHUNK_SIZE]
                messages.append({
                    "role": "model",
                    "content": chunk
                })

            if container:
                container.success(f"✅ Import fertig: {len(messages)} Abschnitte, {len(cleaned_text)} Zeichen.")

            return messages

        except Exception as e:
            error_msg = f"❌ Konnte PDF nicht öffnen/verarbeiten: {e}"
            if container: 
                container.error(error_msg)
            logging.error(error_msg, exc_info=True)
            raise ImportError(error_msg)

        finally:
            # WICHTIG: Dokument schließen, um Speicher/Temp freizugeben
            if doc:
                doc.close()

    def import_to_firestore(
        self, 
        messages: List[Dict[str, Any]], 
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Speichert die PDF-Struktur in Firestore.
        """
        if not messages:
            return {'chat_id': None, 'message_count': 0}

        # Titel aus der ersten Nachricht extrahieren
        first_content = messages[0].get('content', '')
        title_match = re.search(r'\*\*(.+?)\*\*', first_content)

        if title_match:
            chat_title = f"PDF: {title_match.group(1)}"
        else:
            chat_title = f"PDF Import ({len(messages)} Teile)"

        # Chat erstellen
        chat_id = create_chat_in_firestore(chat_title)

        if not chat_id:
            return {'chat_id': None, 'message_count': 0}

        # Nachrichten speichern
        saved_count = 0
        for msg in messages:
            role = msg.get('role', 'model')
            content = msg.get('content', '')
            if content and save_message(chat_id, role, content):
                saved_count += 1

        return {
            'chat_id': chat_id,
            'message_count': saved_count,
            'model_name': 'PDF Reader v49.5'
        }