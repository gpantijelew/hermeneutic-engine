"""
Wikisource Importer (v49.4)

Spezialisiert auf MediaWiki/Wikisource HTML-Exporte.
Extrahiert sauber den Haupt-Content ohne Navigation, Footer, Scripts.

Architektur:
    - Nutzt BeautifulSoup für präzise Selektion
    - Entfernt MediaWiki-spezifische Elemente (VE-Editor-Artefakte, etc.)
    - Behält Formatierung und Struktur bei (Absätze, Listen, Zitate)

Usage:
    from modules.importers.html.wikisource import WikisourceImporter
    
    importer = WikisourceImporter()
    messages = importer.parse(html_content)
"""

from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup, Tag
import re

# Relative Imports für BaseImporter
import sys
import os
if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from modules.importers.base import HTMLImporter
from modules.database import create_chat_in_firestore, save_message


class WikisourceImporter(HTMLImporter):
    """
    Importer für Wikisource/MediaWiki-Seiten.
    
    Features:
    - Extrahiert nur Content aus <div class="mw-parser-output">
    - Entfernt Navigation, Footer, Edit-Buttons
    - Behält Formatierung (kursiv, fett, Zitate) bei
    - Bereinigt MediaWiki-Artefakte (VE-Editor, Infoboxen)
    """
    
    @property
    def platform_name(self) -> str:
        return "Wikisource"
    
    @property
    def platform_id(self) -> str:
        return "wikisource"
    
    @property
    def detection_signatures(self) -> List[str]:
        """HTML-Signaturen zur Auto-Detection."""
        return [
            'mw-parser-output',  # MediaWiki Content-Container
            'wikisource',         # Domain-Hinweis
            'mw-content-text'    # MediaWiki Content-Wrapper
        ]
    
    def parse(self, content: Any, **kwargs) -> List[Dict[str, Any]]:
        """
        Extrahiert sauberen Text aus Wikisource HTML.
        
        Args:
            content: HTML-Content (bytes oder str)
            **kwargs: container für UI-Feedback
        
        Returns:
            Liste mit einer Message (role='model', content=gereinigte Text)
        """
        container = kwargs.get('container')
        
        try:
            # HTML parsen
            soup = self.parse_html(content)
            
            # 1. HAUPTCONTENT FINDEN
            # Wikisource verwendet <div class="mw-parser-output"> für den Inhalt
            content_div = soup.find('div', class_='mw-parser-output')
            
            if not content_div:
                # Fallback: Versuche andere MediaWiki-Container
                content_div = soup.find('div', id='mw-content-text')
                
            if not content_div:
                error_msg = "❌ Konnte Wikisource-Content nicht finden (kein 'mw-parser-output')."
                if container:
                    container.error(error_msg)
                return []
            
            if container:
                container.info("📄 Wikisource-Content gefunden. Starte Bereinigung...")
            
            # 2. UNERWÜNSCHTE ELEMENTE ENTFERNEN
            # Liste aller störenden Elemente
            unwanted_selectors = [
                # Navigation & UI
                'nav', 'header', 'footer', '.mw-editsection',
                # Scripts & Styles
                'script', 'style', 'noscript',
                # MediaWiki-Metadaten
                '.printfooter', '.catlinks', '.mw-cite-backlink',
                # Visual Editor Artefakte
                '[class*="ve-ce-"]', '[class*="oo-ui-"]',
                # Infoboxen (optional, manchmal nützlich)
                # '.infobox',  # Auskommentiert, da manchmal relevant
                # Hidden Elements
                '[style*="display:none"]', '[style*="display: none"]',
                # Bearbeitungs-Hinweise
                '.mw-editsection', '.mw-editsection-bracket',
                # Externe Links-Icons
                '.mw-ext-cite-error',
            ]
            
            for selector in unwanted_selectors:
                for element in content_div.select(selector):
                    element.decompose()  # Vollständig entfernen
            
            # 3. METADATEN EXTRAHIEREN (optional)
            # Titel der Seite
            title_element = soup.find('h1', id='firstHeading')
            page_title = title_element.get_text(strip=True) if title_element else "Wikisource Dokument"
            
            # Autor (falls vorhanden in Metadaten)
            author_meta = soup.find('meta', attrs={'name': 'author'})
            author = author_meta.get('content', 'Unbekannt') if author_meta else 'Unbekannt'
            
            # 4. TEXT EXTRAHIEREN & FORMATIEREN
            # Wir nutzen get_text() mit Separator für Absätze
            raw_text = content_div.get_text(separator='\n', strip=True)
            
            # 5. CLEANING
            # Mehrfache Leerzeilen reduzieren (3+ → 2)
            cleaned_text = re.sub(r'\n{3,}', '\n\n', raw_text)
            
            # Entferne MediaWiki-Editor-Artefakte (Regex-basiert)
            # Beispiel: "r:default}.ve-ce-mwTableNode..." → entfernen
            cleaned_text = re.sub(
                r'[a-z]+:[a-z]+\}\.ve-ce-[a-zA-Z\-\.]+\{[^\}]*\}', 
                '', 
                cleaned_text
            )
            
            # Entferne JavaScript-Code-Blöcke (falls noch welche durchgerutscht sind)
            # Erkennt: "var x = ...", "function() {...}", etc.
            cleaned_text = re.sub(
                r'(var|const|let|function)\s+\w+\s*[=\(].*?[;\}]', 
                '', 
                cleaned_text, 
                flags=re.DOTALL
            )
            
            # Entferne JSON-Blöcke (MediaWiki-Metadaten am Ende)
            # Erkennt: '{"key": "value", ...}'
            cleaned_text = re.sub(
                r'\{["\'][\w\-]+["\']\s*:\s*[\{\[\"].*?\}', 
                '', 
                cleaned_text, 
                flags=re.DOTALL
            )
            
            # Trimme Whitespace
            cleaned_text = cleaned_text.strip()
            
            # 6. STRUKTUR ERSTELLEN
            if not cleaned_text or len(cleaned_text) < 50:
                warning_msg = "⚠️ Wikisource-Import: Text zu kurz nach Bereinigung."
                if container:
                    container.warning(warning_msg)
                return []
            
            # Wir erstellen eine System-Message mit Metadaten + Content
            header = f"**{page_title}**\n"
            if author and author != 'Unbekannt':
                header += f"*Autor: {author}*\n"
            header += f"*Quelle: Wikisource*\n\n---\n\n"
            
            full_content = header + cleaned_text
            
            messages = [{
                'role': 'model',  # Oder 'system', je nach Präferenz
                'content': full_content
            }]
            
            if container:
                container.success(f"✅ Wikisource-Import: {len(cleaned_text)} Zeichen extrahiert.")
            
            return messages
        
        except Exception as e:
            error_msg = f"❌ Wikisource-Import Fehler: {e}"
            if container:
                container.error(error_msg)
            else:
                print(error_msg)
            return []
    
    def import_to_firestore(
        self, 
        messages: List[Dict[str, Any]], 
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Speichert Wikisource-Content in Firestore.
        
        Args:
            messages: Liste von Nachrichten (sollte nur 1 sein)
            metadata: Optionale Metadaten
        
        Returns:
            Dict mit 'chat_id', 'message_count'
        """
        if not messages:
            return {'chat_id': None, 'message_count': 0}
        
        # Titel aus Content extrahieren
        first_content = messages[0].get('content', '')
        title_match = re.search(r'\*\*(.+?)\*\*', first_content)
        
        if title_match:
            chat_title = f"Wikisource: {title_match.group(1)}"
        else:
            chat_title = "Wikisource Import"
        
        # Chat erstellen
        chat_id = create_chat_in_firestore(chat_title)
        
        if not chat_id:
            return {'chat_id': None, 'message_count': 0}
        
        # Content speichern
        # Falls sehr groß (>20k Zeichen), in Chunks aufteilen
        content = messages[0]['content']
        CHUNK_SIZE = 20000
        
        saved_count = 0
        for i in range(0, len(content), CHUNK_SIZE):
            chunk = content[i : i + CHUNK_SIZE]
            if save_message(chat_id, 'model', chunk):
                saved_count += 1
        
        return {
            'chat_id': chat_id,
            'message_count': saved_count,
            'model_name': 'Wikisource'
        }