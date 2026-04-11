from typing import List, Dict, Any
import re
from ..base import ConfigBasedImporter


class DeepSeekImporter(ConfigBasedImporter):
    """
    DeepSeek Chat HTML Importer (v49.6)
    
    Unterstützt:
    - Standard DeepSeek Web-Export mit obfuscated CSS classes
    - Clean API-Format (falls vorhanden)
    - HTML→Markdown Konversion (erbt von ConfigBasedImporter)
    
    HTML-Struktur (Audit 2025-12-31):
    - User Messages: <div class="fbb737a4">
    - Assistant Messages: <div class="ds-markdown">
    - Message Container: <div class="_9663006" data-um-id="1,3,5,...">
    
    CHANGELOG v49.6:
    - Entfernt: Redundante _html_to_markdown() Methode
    - Nutzt jetzt: Zentrale Markdown-Konversion aus ConfigBasedImporter
    - Formatierung (fett, listen, Tabellen) bleibt erhalten
    """
    
    @property
    def platform_name(self):
        return "DeepSeek"
    
    @property
    def platform_id(self):
        return "deepseek"
    
    @property
    def detection_signatures(self):
        return ['ds-message', 'ds-markdown', 'ds-theme', 'deepseek', 'fbb737a4']
    
    def parse(self, content: Any, **kwargs) -> List[Dict[str, Any]]:
        """
        Parse DeepSeek HTML export mit mehreren Strategien
        """
        container = kwargs.get('container')
        soup = self.parse_html(content)
        messages = []
        
        # --- STRATEGIE 1: Präzise Klassen-basierte Extraktion (v49.5) ---
        # HTML-Struktur: User-Wrapper mit data-um-id, Assistant als next_sibling
        user_wrappers = soup.find_all('div', attrs={'data-um-id': True})
        
        if user_wrappers:
            if container:
                container.info(f"DeepSeek: Präzise Extraktion ({len(user_wrappers)} Message-Paare)")
            
            for wrapper in user_wrappers:
                um_id = int(wrapper.get('data-um-id', 0))
                
                # 1. User Message aus Wrapper
                user_msg_div = wrapper.find('div', class_='fbb737a4')
                if user_msg_div:
                    text = user_msg_div.get_text(separator='\n', strip=True)
                    if text:
                        messages.append({
                            'role': 'user',
                            'content': text
                        })
                
                # 2. Assistant Message im next_sibling
                next_sibling = wrapper.find_next_sibling('div')
                if next_sibling:
                    assistant_msg_div = next_sibling.find('div', class_='ds-markdown')
                    if assistant_msg_div:
                        # WICHTIG: HTML zu Markdown konvertieren, nicht nur Text!
                        text = self._html_to_markdown(assistant_msg_div)
                        
                        # Thinking-Block extrahieren (falls vorhanden)
                        thinking = self.extract_thinking_block(next_sibling)
                        if thinking:
                            text = thinking + text
                        
                        if text:
                            messages.append({
                                'role': 'model',
                                'content': text
                            })
            
            if messages:
                return messages
        
        # --- STRATEGIE 2: Standard ds-message Fallback ---
        all_msgs = soup.find_all("div", class_=lambda x: x and "ds-message" in x)
        if all_msgs:
            if container:
                container.info(f"DeepSeek: Standard-Format erkannt ({len(all_msgs)} Nachrichten)")
            
            for msg_div in all_msgs:
                # Role Detection
                is_user = self._detect_user_message(msg_div)
                role = 'user' if is_user else 'model'
                
                # Content Extraction
                content_div = msg_div.find(class_=lambda x: x and "ds-markdown" in x)
                if not content_div:
                    content_div = msg_div
                
                text = content_div.get_text(separator='\n', strip=True)
                
                # Thinking Block (nur für Assistant)
                if role == 'model':
                    thinking = self.extract_thinking_block(msg_div)
                    if thinking:
                        text = thinking + text
                
                if text:
                    messages.append({'role': role, 'content': text})
            
            return messages
        
        # --- STRATEGIE 3: Heuristik für stark obfuscated Exports ---
        root = soup.find(class_=lambda x: x and "ds-theme" in x)
        if root:
            if container:
                container.warning("DeepSeek: Stark obfuscated Format. Verwende Heuristik...")
            
            messages = self._heuristic_extraction(root, container)
            if messages:
                return messages
        
        # --- STRATEGIE 4: Letzte Hoffnung - Pure Text Blocks ---
        if container:
            container.warning("DeepSeek: Keine Struktur gefunden. Versuche Text-Block-Extraktion...")
        
        return self._fallback_text_extraction(soup)
    
    def _detect_user_message(self, msg_div) -> bool:
        """
        Erkennt ob eine Message vom User stammt
        """
        classes = msg_div.get("class", [])
        
        # Direkte Klassen-Prüfung
        if any('user' in str(c).lower() for c in classes):
            return True
        if 'fbb737a4' in classes:
            return True
        
        # Parent-Prüfung
        parent = msg_div.find_parent('div', class_='fbb737a4')
        if parent:
            return True
        
        # Child-Prüfung
        user_child = msg_div.find(class_=lambda x: x and 'fbb737a4' in str(x))
        if user_child:
            return True
        
        # Default: Assistant
        return False
    
    def _heuristic_extraction(self, root, container) -> List[Dict[str, Any]]:
        """
        Heuristische Extraktion für obfuscated HTML
        """
        text_elements = []
        
        # Sammle alle Text-Elemente
        for elem in root.find_all(['div', 'p']):
            # Nur Leaf-Nodes mit Text
            if not elem.find_all(recursive=False):
                text = elem.get_text(separator='\n', strip=True)
                if len(text) > 2:
                    text_elements.append(text)
        
        # Filtere UI-Elemente
        ui_keywords = [
            "DeepSeek", "Copy", "Regenerate", "Good response", "Bad response",
            "Share", "Edit", "Delete", "New Chat", "Heute", "7 Tage", "30 Tage"
        ]
        
        filtered_texts = [
            t for t in text_elements 
            if not any(keyword in t for keyword in ui_keywords) and len(t) > 5
        ]
        
        # Role-Assignment Heuristik
        messages = []
        current_role = 'user'
        
        for text in filtered_texts:
            # Lange Texte = wahrscheinlich Assistant
            if len(text) > 500:
                current_role = 'model'
            
            messages.append({
                'role': current_role,
                'content': text
            })
            
            # Toggle Role
            current_role = 'model' if current_role == 'user' else 'user'
        
        if container and messages:
            container.success(f"✅ Heuristik: {len(messages)} Textblöcke extrahiert")
        
        return messages
    
    def _fallback_text_extraction(self, soup) -> List[Dict[str, Any]]:
        """
        Letzte Fallback-Strategie: Pure Text-Extraktion
        """
        # Entferne Script/Style
        for tag in soup(['script', 'style', 'nav', 'header', 'footer']):
            tag.decompose()
        
        # Sammle alle Textblöcke
        text_blocks = []
        for elem in soup.find_all(['div', 'p']):
            text = elem.get_text(separator='\n', strip=True)
            if len(text) > 20 and text not in text_blocks:
                text_blocks.append(text)
        
        # Erste Message = User, Rest alternierend
        messages = []
        for i, text in enumerate(text_blocks[:10]):  # Max 10 Messages
            role = 'user' if i % 2 == 0 else 'model'
            messages.append({
                'role': role,
                'content': text
            })
        
        return messages
    
    def extract_thinking_block(self, element) -> str:
        """
        Extrahiert Thinking-Block (falls vorhanden)
        """
        if not element:
            return ""
        
        # Suche nach Thinking-Marker
        thinking = element.find(class_=lambda x: x and 'thinking' in str(x).lower())
        if thinking:
            text = thinking.get_text(separator='\n', strip=True)
            return f"<thinking>\n{text}\n</thinking>\n\n"
        
        return ""