import io
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from ..base import BaseImporter
from ..text_parser import TextParserImporter

class EPubImporter(BaseImporter):
    @property
    def platform_name(self): return "eBook (ePub)"

    @property
    def platform_id(self): return "epub"

    def parse(self, content: Any, **kwargs) -> List[Dict[str, Any]]:
        container = kwargs.get('container')

        try:
            import ebooklib
            from ebooklib import epub
        except ImportError:
            error_msg = "❌ Bibliothek 'ebooklib' fehlt. Bitte `pip install ebooklib` ausführen."
            if container: container.error(error_msg)
            raise ImportError(error_msg)

        try:
            # EbookLib ist etwas eigen mit Streams. Wir speichern Bytes in BytesIO.
            if hasattr(content, 'read'):
                # Reset pointer if needed or read
                if hasattr(content, 'seek'): content.seek(0)
                file_bytes = content.read()
            else:
                file_bytes = content

            # EbookLib braucht oft einen Dateipfad, aber wir versuchen es via BytesIO als 'file-like'
            # Workaround: EbookLib write_epub nutzt zipfile, read_epub nutzt auch zipfile.
            # Wir speichern es temporär ab, da ebooklib read_epub einen Pfad will (meistens).
            # ABER: Neuere Versionen akzeptieren file-like objects. Wir testen BytesIO.

            # Fallback: Wir schreiben temporäre Datei, da ebooklib manchmal zickt
            import tempfile
            import os

            with tempfile.NamedTemporaryFile(delete=False, suffix='.epub') as tmp:
                tmp.write(file_bytes)
                tmp_path = tmp.name

            book = epub.read_epub(tmp_path)

            full_text = ""
            if container: container.info("📚 Extrahiere Kapitel aus ePub...")

            for item in book.get_items():
                if item.get_type() == ebooklib.ITEM_DOCUMENT:
                    # HTML Content extrahieren
                    soup = BeautifulSoup(item.get_content(), 'html.parser')
                    text = soup.get_text(separator='\n', strip=True)
                    full_text += text + "\n\n"

            # Cleanup Temp File
            os.unlink(tmp_path)

            if not full_text.strip():
                if container: container.warning("⚠️ ePub scheint leer zu sein.")
                return []

            # Delegation an den TextParser (LLM)
            if container: container.info("🧠 Übergebe Buch-Text an KI-Parser...")
            text_parser = TextParserImporter()
            return text_parser.parse(full_text, container=container)

        except Exception as e:
            if container: container.error(f"❌ ePub Fehler: {e}")
            return []

    def import_to_firestore(self, messages: List[Dict[str, Any]], metadata: Optional[Dict] = None) -> Dict[str, Any]:
        return TextParserImporter().import_to_firestore(messages, metadata)