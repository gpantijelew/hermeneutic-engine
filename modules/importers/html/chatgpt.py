"""
ChatGPT Importer (Panzer-Edition v50.7 - Fixed).

Dieser Importer ist spezifisch für OpenAI ChatGPT HTML-Exporte und "Save Page as HTML" optimiert.
Er verlässt sich NICHT auf die generische Config, sondern nutzt eine robuste Multi-Pass-Erkennung,
um auch bei DOM-Änderungen oder riesigen Dateien stabil zu bleiben.

Features:
- Robust gegen DOM-Änderungen (sucht semantisch nach Rollen)
- Unterstützt "Thinking" Blöcke (o1/o3 Modelle)
- Extrahiert Metadaten (Modell-Version)
- Ignoriert leere System-Artefakte

Fixes v50.7.1:
- model_badge: find_previous mit lambda statt string= (matched jetzt rekursiv)
- Thinking-Block: Leerzeilen werden korrekt als '>' gequotet (kein Blockquote-Bruch)
"""

import re
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup, Tag

from ..base import ConfigBasedImporter


class ChatGPTImporter(ConfigBasedImporter):
    """
    Dedizierter Importer für ChatGPT.
    Überschreibt die generische parse()-Methode für maximale Robustheit.
    """

    config_key = 'chatgpt'

    @property
    def platform_name(self):
        return "ChatGPT (OpenAI)"

    @property
    def platform_id(self):
        return "chatgpt"

    def parse(
        self,
        content: Any,
        progress_callback: Optional[Any] = None,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Spezialisierte Parsing-Logik für ChatGPT.
        """
        container = kwargs.get('container')

        # 1. Robustes HTML-Parsing
        try:
            soup = self.parse_html(content)
        except Exception as e:
            if container:
                container.error(f"❌ HTML-Parsing Fehler: {e}")
            return []

        messages = []

        # 2. Strategie: Wir suchen direkt nach Nachrichten-Blöcken.
        # OpenAI nutzt fast immer 'data-message-author-role' Attribute.
        # Das ist viel stabiler als CSS-Klassen, die sich wöchentlich ändern.
        role_elements = soup.select('[data-message-author-role]')

        if not role_elements:
            # Fallback für ältere Exporte
            if container:
                container.info("⚠️ Standard-Selektor fehlgeschlagen, versuche Fallback...")
            role_elements = soup.select('.w-full.text-token-text-primary')

        total_elements = len(role_elements)

        for i, el in enumerate(role_elements):

            # Progress Update
            if progress_callback and i % 10 == 0:
                progress_callback(i, total_elements)

            role = el.get('data-message-author-role')

            # Mapping auf interne Rollen
            if role == 'user':
                final_role = 'user'
            elif role == 'assistant':
                final_role = 'model'
            elif role == 'system':
                continue  # System-Prompts ignorieren
            else:
                continue  # Unsichere Elemente überspringen

            # Content Extraktion
            content_div = (
                el.select_one('.markdown') or
                el.select_one('.whitespace-pre-wrap')
            )
            target_el = content_div if content_div else el

            # *** Thinking / Reasoning Extraction (o1/o3) ***
            thinking_text = ""
            thought_el = el.select_one(
                '.thought-content, details[data-testid="reasoning-details"]'
            )

            if thought_el:
                raw_thought = thought_el.get_text(separator='\n', strip=True)
                if raw_thought:
                    # FIX v50.7.1: Leerzeilen korrekt als '>' quoten
                    # verhindert Blockquote-Bruch bei \n\n im Thinking-Text
                    lines = raw_thought.split('\n')
                    quoted = '\n'.join(
                        f'> {line}' if line.strip() else '>'
                        for line in lines
                    )
                    thinking_text = f"> **Thinking:**\n{quoted}\n\n"

            # *** Markdown Konvertierung ***
            text_content = self._html_to_markdown(target_el)

            # Zusammenfügen
            full_text = thinking_text + text_content

            if full_text.strip():
                msg_obj = {
                    'role': final_role,
                    'content': full_text
                }

                # FIX v50.7.1: Lambda statt string= für rekursive Suche
                # string= matched nur direkten Text, nicht verschachtelte Tags
                model_badge = el.find_previous(
                    lambda tag: tag.name == 'div' and
                    re.search(r'GPT-|o1-|o3-', tag.get_text())
                )
                if model_badge:
                    msg_obj['model_name'] = model_badge.get_text(strip=True)

                messages.append(msg_obj)

        # 3. Validierung
        if not messages:
            if container:
                container.warning(
                    "⚠️ Keine Nachrichten mit 'data-message-author-role' gefunden."
                )

        return messages