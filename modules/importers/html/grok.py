from typing import List, Dict, Any, Optional
from ..base import HTMLImporter


class GrokImporter(HTMLImporter):
    """
    Grok (xAI) HTML Importer (v49.6)
    
    Unterstützt:
    - HTML-Export aus Grok.com (x.ai)
    - Stabile CSS-Selektoren für User/AI Messages
    - HTML→Markdown Konversion für strukturierte Inhalte
    
    HTML-Struktur (Audit 2026-01-01):
    - User Messages: div.message-bubble mit "rounded-br-lg" (abgerundete untere rechte Ecke)
    - AI Responses: div.message-bubble mit "w-full max-w-none" (volle Breite)
    - Content: Beide nutzen .response-content-markdown
    
    WICHTIG:
    - Grok nutzt Tailwind CSS mit klaren visuellen Unterschieden
    - User-Bubbles haben border-radius rechts unten
    - AI-Bubbles haben volle Breite
    """
    
    @property
    def platform_name(self):
        return "Grok (xAI)"
    
    @property
    def platform_id(self):
        return "grok"
    
    @property
    def detection_signatures(self):
        return ['grok.com', 'x.ai', 'response-content-markdown', 'message-bubble']
    
    def parse(self, content: Any, **kwargs) -> List[Dict[str, Any]]:
        """
        Parse Grok HTML export mit stabilen CSS-Selektoren
        """
        container = kwargs.get('container')
        soup = self.parse_html(content)
        messages = []
        
        # --- STRATEGIE: CSS-Klassen-basierte Extraktion ---
        # User: div.message-bubble mit "rounded-br-lg" + "bg-surface-l1"
        # AI: div.message-bubble mit "w-full max-w-none"
        
        # Finde alle message-bubbles
        all_bubbles = soup.find_all('div', class_='message-bubble')
        
        if not all_bubbles:
            if container:
                container.warning("⚠️ Grok: Keine Message-Bubbles gefunden")
            return []
        
        if container:
            container.info(f"Grok: {len(all_bubbles)} Message-Bubbles gefunden")
        
        # Sortiere nach Position im Dokument (chronologisch)
        # und identifiziere User vs. AI
        for bubble in all_bubbles:
            classes = ' '.join(bubble.get('class', []))
            
            # Finde Content-Container
            content_div = bubble.find('div', class_='response-content-markdown')
            if not content_div:
                continue
            
            # Bestimme Rolle basierend auf CSS-Klassen
            if 'rounded-br-lg' in classes and 'bg-surface-l1' in classes:
                # User Message (abgerundete untere rechte Ecke + Hintergrund)
                role = 'user'
                # User-Messages können auch HTML haben (bei langen Prompts)
                text = self._html_to_markdown(content_div)
                
            elif 'w-full' in classes and 'max-w-none' in classes:
                # AI Response (volle Breite)
                role = 'model'
                # AI-Messages haben strukturiertes HTML → Markdown
                text = self._html_to_markdown(content_div)
                
            else:
                # Unbekannt → Skip
                if container:
                    container.warning(f"⚠️ Unbekannte Message-Bubble: {classes[:100]}")
                continue
            
            if text and text.strip():
                messages.append({
                    'role': role,
                    'content': text.strip()
                })
        
        if container and messages:
            user_count = sum(1 for m in messages if m['role'] == 'user')
            ai_count = sum(1 for m in messages if m['role'] == 'model')
            container.success(f"✅ {len(messages)} Nachrichten: {user_count} User, {ai_count} AI")
        
        return messages
    
    def _html_to_markdown(self, element) -> str:
        """
        Konvertiert Grok HTML zu Markdown (behält Formatierung).
        
        Grok nutzt sauberes HTML:
        - <h3>, <h4> für Überschriften
        - <p> für Paragraphen
        - <ul><li> für Listen
        - <strong> für Fettdruck
        - <table> für Tabellen
        - <hr> für Trennlinien
        - <a> für Links (mit Citations)
        
        WICHTIG (v49.6 Fixes):
        - Entfernt Grok-UI-Elemente (Copy-Buttons, etc.)
        - Robuste Code-Block-Erkennung
        - Bewahrt Zeilenumbrüche
        """
        if not element:
            return ""
        
        import re
        from bs4 import BeautifulSoup
        
        # 0. ZUERST: Entferne Grok-UI-Elemente (Buttons, Labels, etc.)
        soup = BeautifulSoup(str(element), 'html.parser')
        
        # Entferne Copy-Buttons und andere UI-Controls
        for tag in soup.find_all(['button', 'svg']):
            tag.decompose()
        
        # Entferne versteckte Spans (oft UI-Labels)
        for span in soup.find_all('span', class_=lambda x: x and 'hidden' in x):
            span.decompose()
        
        # Strategie: HTML-String manipulieren
        html_str = str(soup)
        
        # 1. Code-Blöcke (VORHER, bevor andere Replacements!)
        # Erkenne <pre> (mit oder ohne <code>)
        def replace_code_block(match):
            code_content = match.group(1)
            # Entferne innere HTML-Tags
            code_soup = BeautifulSoup(code_content, 'html.parser')
            clean_code = code_soup.get_text()
            # Erkenne Sprache aus class="language-X"
            language = ''
            if 'class=' in match.group(0):
                lang_match = re.search(r'class=["\'](?:language-)?(\w+)', match.group(0))
                if lang_match:
                    language = lang_match.group(1).lower()
            return f'\n```{language}\n{clean_code}\n```\n'
        
        html_str = re.sub(r'<pre[^>]*>(.*?)</pre>', replace_code_block, html_str, flags=re.DOTALL)
        
        # Inline-Code
        html_str = re.sub(r'<code[^>]*>(.*?)</code>', r'`\1`', html_str, flags=re.DOTALL)
        
        # 2. Überschriften
        html_str = re.sub(r'<h3[^>]*>(.*?)</h3>', r'\n### \1\n\n', html_str, flags=re.DOTALL)
        html_str = re.sub(r'<h4[^>]*>(.*?)</h4>', r'\n#### \1\n\n', html_str, flags=re.DOTALL)
        html_str = re.sub(r'<h2[^>]*>(.*?)</h2>', r'\n## \1\n\n', html_str, flags=re.DOTALL)
        
        # 3. Fettdruck
        html_str = re.sub(r'<strong[^>]*>(.*?)</strong>', r'**\1**', html_str, flags=re.DOTALL)
        
        # 4. Kursiv
        html_str = re.sub(r'<em[^>]*>(.*?)</em>', r'*\1*', html_str, flags=re.DOTALL)
        
        # 5. Trennlinien
        html_str = re.sub(r'<hr\s*[^>]*>', '\n\n---\n\n', html_str)
        
        # 6. Listen
        def replace_list(match):
            list_content = match.group(1)
            items = re.findall(r'<li[^>]*>(.*?)</li>', list_content, flags=re.DOTALL)
            if not items:
                return match.group(0)
            
            markdown_items = []
            for item in items:
                # Entferne innere <p> Tags
                clean_item = re.sub(r'<p[^>]*>(.*?)</p>', r'\1', item, flags=re.DOTALL)
                markdown_items.append(f"  * {clean_item.strip()}")
            
            return '\n' + '\n'.join(markdown_items) + '\n'
        
        html_str = re.sub(r'<ul[^>]*>(.*?)</ul>', replace_list, html_str, flags=re.DOTALL)
        html_str = re.sub(r'<ol[^>]*>(.*?)</ol>', replace_list, html_str, flags=re.DOTALL)
        
        # 7. Tabellen (einfache Konversion)
        def replace_table(match):
            table_html = match.group(0)
            table_soup = BeautifulSoup(table_html, 'html.parser')
            
            # Extrahiere Zeilen
            rows = table_soup.find_all('tr')
            if not rows:
                return ''
            
            markdown_table = []
            for i, row in enumerate(rows):
                cells = row.find_all(['th', 'td'])
                if not cells:
                    continue
                
                # Extrahiere Zell-Inhalte
                cell_texts = [cell.get_text(strip=True) for cell in cells]
                markdown_table.append('| ' + ' | '.join(cell_texts) + ' |')
                
                # Header-Separator nach erster Zeile
                if i == 0:
                    markdown_table.append('| ' + ' | '.join(['---'] * len(cell_texts)) + ' |')
            
            return '\n' + '\n'.join(markdown_table) + '\n'
        
        html_str = re.sub(r'<table[^>]*>.*?</table>', replace_table, html_str, flags=re.DOTALL)
        
        # 8. Links (entferne Citation-Badges)
        def replace_link(match):
            url = match.group(1)
            text = match.group(2)
            # Skip Citations (kleine Badges)
            if 'citation' in text.lower() or len(text.strip()) < 3:
                return ''
            return f'[{text.strip()}]({url})'
        
        html_str = re.sub(r'<a[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', replace_link, html_str, flags=re.DOTALL)
        
        # 9. Paragraphen (WICHTIG: Bewahre Absätze!)
        html_str = re.sub(r'<p[^>]*>(.*?)</p>', r'\1\n\n', html_str, flags=re.DOTALL)
        
        # 10. Entferne alle verbleibenden HTML-Tags
        final_soup = BeautifulSoup(html_str, 'html.parser')
        text = final_soup.get_text(separator='\n', strip=False)
        
        # 11. Cleanup: Reduziere multiple Leerzeilen, aber behalte Struktur
        # Entferne 3+ aufeinanderfolgende Leerzeilen
        text = re.sub(r'\n{4,}', '\n\n\n', text)
        
        # Entferne trailing whitespace pro Zeile
        lines = [line.rstrip() for line in text.split('\n')]
        
        # Entferne leere Zeilen am Anfang/Ende
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
        
        return '\n'.join(lines)
    
    def import_to_firestore(
        self, 
        messages: List[Dict[str, Any]], 
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Standard-Import für Grok
        """
        from modules.database import (
            create_chat_in_firestore, 
            save_message, 
            generate_and_update_title, 
            delete_chat
        )
        
        if not messages:
            return {'chat_id': None, 'message_count': 0}
        
        # Chat erstellen
        chat_id = create_chat_in_firestore(f"Import (Grok)")
        
        if not chat_id:
            return {'chat_id': None, 'message_count': 0}
        
        # Nachrichten speichern
        saved_count = 0
        history_for_title = []
        
        for msg in messages:
            if save_message(chat_id, msg['role'], msg['content']):
                saved_count += 1
                history_for_title.append(msg)
        
        # Titel generieren
        if saved_count > 0:
            generate_and_update_title(chat_id, history_for_title[:3])
            return {
                'chat_id': chat_id, 
                'message_count': saved_count,
                'model_name': 'Grok (xAI)'
            }
        else:
            # Keine Nachrichten gespeichert → Chat löschen
            delete_chat(chat_id)
            return {'chat_id': None, 'message_count': 0}