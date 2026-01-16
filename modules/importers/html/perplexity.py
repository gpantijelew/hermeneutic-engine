from typing import List, Dict, Any, Optional
from ..base import HTMLImporter


class PerplexityImporter(HTMLImporter):
    """
    Perplexity AI HTML Importer (v50.6)
    
    Unterstützt:
    - HTML-Export aus Perplexity.ai (Browser oder Comet)
    - Stabile CSS-Selektoren für User/AI Messages
    - HTML→Markdown Konversion (erbt von ConfigBasedImporter)
    
    HTML-Struktur (Audit 2026-01-01):
    - User Messages: <div class="group/query"> → <span class="select-text">
    - AI Responses: <div class="prose dark:prose-invert">
    
    WICHTIG:
    - Perplexity nutzt Tailwind CSS mit escaped Selektoren!
    - "group/query" wird zu CSS: "group/query" (escaped in HTML)
    - "dark:prose-invert" wird zu CSS: "dark:prose-invert" (escaped in HTML)
    """
    
    @property
    def platform_name(self):
        return "Perplexity AI"
    
    @property
    def platform_id(self):
        return "perplexity"
    
    @property
    def detection_signatures(self):
        return ['perplexity.ai', 'group/query', 'prose dark:prose-invert', 'pplx-icon']
    
    def parse(self, content: Any, **kwargs) -> List[Dict[str, Any]]:
        """
        Parse Perplexity HTML export mit stabilen CSS-Selektoren
        """
        container = kwargs.get('container')
        soup = self.parse_html(content)
        messages = []
        
        # --- STRATEGIE: CSS-Klassen-basierte Extraktion ---
        # User: div.group/query → span.select-text
        # AI: div.prose.dark:prose-invert
        
        # 1. Finde alle User-Messages
        # WICHTIG: CSS escaping! "group/query" → [class*="group/query"]
        user_blocks = soup.find_all('span', class_='select-text')
        
        if not user_blocks:
            if container:
                container.warning("⚠️ Perplexity: Keine User-Nachrichten gefunden (span.select-text)")
            return []
        
        # 2. Finde alle AI-Responses
        # WICHTIG: Beide Klassen müssen vorhanden sein!
        ai_blocks = soup.find_all('div', class_=lambda x: x and 'prose' in x and 'dark:prose-invert' in x)
        
        if not ai_blocks:
            if container:
                container.warning("⚠️ Perplexity: Keine AI-Antworten gefunden (div.prose)")
            return []
        
        if container:
            container.info(f"Perplexity: {len(user_blocks)} User-Nachrichten, {len(ai_blocks)} AI-Antworten")
        
        # 3. Paare User ↔ AI Messages
        # Annahme: Alternierend (User → AI → User → AI)
        for i in range(max(len(user_blocks), len(ai_blocks))):
            # User Message
            if i < len(user_blocks):
                user_text = user_blocks[i].get_text(strip=True)
                if user_text:
                    messages.append({
                        'role': 'user',
                        'content': user_text
                    })
            
            # AI Response
            if i < len(ai_blocks):
                # Nutze Markdown-Konversion für Formatierung
                ai_text = self._html_to_markdown(ai_blocks[i])
                if ai_text:
                    messages.append({
                        'role': 'model',
                        'content': ai_text
                    })
        
        if container and messages:
            container.success(f"✅ {len(messages)} Nachrichten extrahiert")
        
        return messages
    
    def _html_to_markdown(self, element) -> str:
        """
        Konvertiert Perplexity HTML zu Markdown (behält Formatierung).
        
        Perplexity nutzt clean HTML-Struktur:
        - <p> für Paragraphen
        - <h2>, <h3> für Überschriften
        - <ul><li> für Listen
        - <strong> für Fettdruck
        - <hr> für Trennlinien
        - <a> für Links (mit Citations)
        """
        if not element:
            return ""
        
        import re
        from bs4 import BeautifulSoup
        
        # Strategie: HTML-String manipulieren
        html_str = str(element)
        
        # 1. Überschriften
        html_str = re.sub(r'<h2[^>]*>(.*?)</h2>', r'\n## \1\n', html_str, flags=re.DOTALL)
        html_str = re.sub(r'<h3[^>]*>(.*?)</h3>', r'\n### \1\n', html_str, flags=re.DOTALL)
        
        # 2. Fettdruck
        html_str = re.sub(r'<strong[^>]*>(.*?)</strong>', r'**\1**', html_str, flags=re.DOTALL)
        
        # 3. Kursiv
        html_str = re.sub(r'<em[^>]*>(.*?)</em>', r'*\1*', html_str, flags=re.DOTALL)
        
        # 4. Trennlinien
        html_str = re.sub(r'<hr\s*[^>]*>', '\n\n---\n\n', html_str)
        
        # 5. Listen
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
        
        # 6. Links (Perplexity hat spezielle Citation-Links)
        # Format: <a href="...">text</a> → [text](url)
        def replace_link(match):
            url = match.group(1)
            text = match.group(2)
            # Entferne Citation-Badges (die kleinen [1], [2] etc.)
            if 'citation' in text.lower() or len(text) < 3:
                return ''  # Skip Citations
            return f'[{text}]({url})'
        
        html_str = re.sub(r'<a[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', replace_link, html_str, flags=re.DOTALL)
        
        # 7. Paragraphen
        html_str = re.sub(r'<p[^>]*>(.*?)</p>', r'\1\n\n', html_str, flags=re.DOTALL)
        
        # 8. Entferne alle verbleibenden HTML-Tags
        soup = BeautifulSoup(html_str, 'html.parser')
        text = soup.get_text(separator='', strip=False)
        
        # 9. Cleanup
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Entferne leere Zeilen am Anfang/Ende
        lines = []
        for line in text.split('\n'):
            stripped = line.strip()
            if stripped.startswith('*') or stripped.startswith('#') or stripped.startswith('-'):
                lines.append(line)
            else:
                lines.append(stripped)
        
        return '\n'.join(lines).strip()
    
    def import_to_firestore(
        self, 
        messages: List[Dict[str, Any]], 
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Standard-Import für Perplexity
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
        chat_id = create_chat_in_firestore(f"Import (Perplexity AI)")
        
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
                'model_name': 'Perplexity AI'
            }
        else:
            # Keine Nachrichten gespeichert → Chat löschen
            delete_chat(chat_id)
            return {'chat_id': None, 'message_count': 0}