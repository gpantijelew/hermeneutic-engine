from typing import List, Dict, Any, Optional
from ..base import BaseImporter
from ..text_parser import TextParserImporter

class PDFImporter(BaseImporter):
    @property
    def platform_name(self): return "PDF Dokument"

    @property
    def platform_id(self): return "pdf"

    def parse(self, content: Any, **kwargs) -> List[Dict[str, Any]]:
        """
        Extrahiert Text aus PDF und nutzt LLM zur Strukturierung.
        Content erwartet: Bytes oder File-Objekt.
        """
        container = kwargs.get('container')

        try:
            import fitz  # PyMuPDF
        except ImportError:
            error_msg = "❌ Bibliothek 'pymupdf' fehlt. Bitte `pip install pymupdf` ausführen."
            if container: container.error(error_msg)
            raise ImportError(error_msg)

        try:
            # PyMuPDF erwartet Bytes oder Filename. 
            # Wenn content ein Stream ist (Streamlit UploadedFile), lesen wir die Bytes.
            if hasattr(content, 'read'):
                file_bytes = content.read()
            else:
                file_bytes = content

            doc = fitz.open(stream=file_bytes, filetype="pdf")
            full_text = ""

            if container:
                container.info(f"📄 Analysiere PDF mit {len(doc)} Seiten...")

            for page in doc:
                full_text += page.get_text() + "\n"

            if not full_text.strip():
                if container: container.warning("⚠️ PDF scheint leer zu sein oder enthält nur Bilder.")
                return []

            # Delegation an den TextParser (LLM)
            if container: container.info("🧠 Übergebe extrahierten Text an KI-Parser...")
            text_parser = TextParserImporter()
            return text_parser.parse(full_text, container=container)

        except Exception as e:
            if container: container.error(f"❌ PDF Fehler: {e}")
            return []

    def import_to_firestore(self, messages: List[Dict[str, Any]], metadata: Optional[Dict] = None) -> Dict[str, Any]:
        # Wir nutzen die Logik des TextParsers, da es sich effektiv um Text-Import handelt
        return TextParserImporter().import_to_firestore(messages, metadata)