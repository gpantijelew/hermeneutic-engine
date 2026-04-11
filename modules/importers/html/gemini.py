"""
Gemini Importer (v50.6 FIXED)

Kritische Fixes:
- Problem 2: Fallback zu Strategie 2, wenn Strategie 1 keine User-Messages findet
- Problem 4: Thinking-Blocks werden in Liste gesammelt (kein State-Leak mehr)
- Problem 5: Validierung mit self.validate() vor Return
- Problem 6: Strategie 2 nutzt jetzt extract_thinking_block() aus base.py
- Problem 3: Debug-Modus ist jetzt opt-in (kwargs['debug'])
- Problem 7: Diagnose-Modus returned [] statt Fake-Message
- Problem 1: Nummerierung korrigiert (Strategie 4 → Strategie 3)

Architektur:
    - Strategie 1: Angular/Live-Export (<user-query>, <model-thoughts>, <message-content>)
    - Strategie 2: Standard Takeout (.message-box)
    - Strategie 3: Diagnose-Modus (Deep Scan mit target_word)
    
Usage:
    from modules.importers.html.gemini import GeminiImporter
    
    importer = GeminiImporter()
    messages = importer.parse(html_content, debug=True)  # Opt-in Debug
"""

import re
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from ..base import ConfigBasedImporter


class GeminiImporter(ConfigBasedImporter):
    """
    Custom parser for Gemini HTML exports (does not use ConfigBasedImporter logic).
    
    Inherits from ConfigBasedImporter for consistency, but overrides parse() completely
    due to Gemini's complex multi-format structure.
    """
    
    config_key = 'gemini'
    
    @property
    def platform_name(self): 
        return "Gemini (Google)"
    
    @property
    def platform_id(self): 
        return "gemini"
    
    @property
    def detection_signatures(self):
        return [
            'message-box', 'ai-markdown-artifact-renderer', 
            'user-query', 'model-thoughts', 'message-content'
        ]
    
    def parse(self, content: Any, **kwargs) -> List[Dict[str, Any]]:
        """
        Parses Gemini HTML with multi-strategy approach.
        
        Args:
            content: HTML content (bytes or str)
            **kwargs:
                - container: Streamlit container for UI feedback
                - target_word: Enable diagnostic deep scan for specific word
                - debug: Enable verbose debug output (default: False)
        
        Returns:
            List of message dicts: [{'role': 'user'|'model', 'content': '...'}, ...]
        """
        container = kwargs.get('container')
        target_word = kwargs.get('target_word', "")
        debug_mode = kwargs.get('debug', False)
        
        soup = self.parse_html(content)
        messages = []
        
        # --- STRATEGIE 1: Angular / Live-Export ---
        angular_elements = soup.find_all(['user-query', 'model-thoughts', 'message-content'])
        
        if angular_elements:
            if container: 
                container.info(f"🔄 Strategie 1 (Angular): {len(angular_elements)} Elemente gefunden.")
            
            # FIX Problem 4: Thinking-Blocks als Liste sammeln (statt einzelne Variable)
            thinking_blocks = []
            
            for i, elem in enumerate(angular_elements):
                tag_name = elem.name.lower()
                
                # FIX Problem 3: Debug-Modus ist jetzt opt-in
                if debug_mode and container and i < 5:
                    container.text(f"🔍 Debug Element {i}: <{tag_name}>")
                
                # 1. USER
                if tag_name == 'user-query':
                    text_div = elem.find('div', class_='query-text')
                    if text_div:
                        text = text_div.get_text(separator='\n', strip=True)
                    else:
                        text = elem.get_text(separator='\n', strip=True)
                        # Cleanup: Entferne UI-Elemente
                        text = text.replace('text_minimize', '').replace('content_copy', '').strip()
                    
                    if text:
                        # Entferne Gemini UI-Label "Du hast gesagt" (und Varianten)
                        text = re.sub(r'^Du hast gesagt\s*\n?', '', text).strip()
                        if text:
                            messages.append({'role': 'user', 'content': text})
                        if debug_mode and container:
                            container.write(f"✅ User-Nachricht: {text[:50]}...")
                
                # 2. THINKING (sammeln für nächste Model-Message)
                elif tag_name == 'model-thoughts':
                    thought_div = elem.find('div', class_='markdown')
                    if thought_div:
                        raw_thought = thought_div.get_text(separator='\n', strip=True)
                        thinking_formatted = f"> **Thinking:**\n> {raw_thought.replace(chr(10), chr(10) + '> ')}\n\n"
                        thinking_blocks.append(thinking_formatted)
                        
                        if debug_mode and container:
                            container.write(f"💭 Thinking-Block gesammelt: {raw_thought[:50]}...")
                
                # 3. MODEL (mit gesammelten Thinking-Blocks)
                elif tag_name == 'message-content':
                    text_div = elem.find('div', class_='markdown')
                    if text_div:
                        text = text_div.get_text(separator='\n', strip=True)
                    else:
                        text = elem.get_text(separator='\n', strip=True)
                    
                    # FIX Problem 4: Füge alle gesammelten Thinking-Blocks hinzu
                    if thinking_blocks:
                        text = "\n".join(thinking_blocks) + text
                        thinking_blocks = []  # Reset nach Verwendung
                    
                    if text:
                        messages.append({'role': 'model', 'content': text})
                        if debug_mode and container:
                            container.write(f"🤖 Model-Nachricht: {text[:50]}...")
            
            # FIX Problem 2: Validiere Strategie 1 Ergebnisse
            if messages:
                user_count = sum(1 for m in messages if m['role'] == 'user')
                model_count = sum(1 for m in messages if m['role'] == 'model')
                
                if container: 
                    container.info(f"📊 Strategie 1: {len(messages)} Nachrichten ({user_count} User / {model_count} Model)")
                
                # Nur returnen, wenn mindestens eine User-Message vorhanden!
                if user_count > 0:
                    # FIX Problem 5: Validierung vor Return
                    if self.validate(messages):
                        if container:
                            container.success(f"✅ Strategie 1 erfolgreich!")
                        return messages
                    else:
                        if container:
                            container.warning("⚠️ Strategie 1: Validierung fehlgeschlagen. Versuche Strategie 2...")
                else:
                    if container:
                        container.warning("⚠️ Strategie 1: Keine User-Nachrichten. Versuche Strategie 2...")
            
            # Falls Strategie 1 fehlschlug, reset messages für Strategie 2
            messages = []
        
        # --- STRATEGIE 2: Standard Takeout ---
        all_boxes = soup.find_all("div", class_="message-box")
        
        if all_boxes:
            if container: 
                container.info(f"🔄 Strategie 2 (Takeout): {len(all_boxes)} Message-Boxen gefunden.")
            
            for box in all_boxes:
                classes = box.get("class", [])
                role = "user" if "message-box--user" in classes else "model"
                
                content_parts = []
                
                # FIX Problem 6: Nutze extract_thinking_block() aus base.py
                thinking_formatted = self.extract_thinking_block(box)
                if thinking_formatted:
                    content_parts.append(thinking_formatted)
                
                # Haupt-Content
                renderers = box.find_all("span", class_="ai-markdown-artifact-renderer")
                for renderer in renderers:
                    # Skip Thinking-Block-Renderer (wurde bereits verarbeitet)
                    thought_box = box.find("ai-llm-model-thoughts-output-box")
                    if thought_box and renderer in thought_box.descendants:
                        continue
                    
                    content_parts.append(renderer.get_text(separator="\n").strip())
                
                # Fallback für User-Messages ohne Renderer
                if role == "user" and not content_parts:
                    text_area = box.find("span", class_="prompt-response-text-area")
                    if text_area: 
                        content_parts.append(text_area.get_text(separator="\n").strip())
                
                full_content = "\n".join(content_parts).strip()
                
                if full_content: 
                    messages.append({"role": role, "content": full_content})
            
            # FIX Problem 5: Validierung vor Return
            if messages and self.validate(messages):
                if container:
                    container.success(f"✅ Strategie 2 erfolgreich: {len(messages)} Nachrichten.")
                return messages
            elif container:
                container.warning("⚠️ Strategie 2: Validierung fehlgeschlagen.")
        
        # --- STRATEGIE 3: Diagnose-Modus (nur wenn target_word gesetzt) ---
        if target_word:
            if container: 
                container.warning(f"🔎 Strategie 3 (Diagnose): Deep Scan nach '{target_word}'...")
            
            found_elements = soup.find_all(string=re.compile(re.escape(target_word), re.IGNORECASE))
            
            if found_elements:
                if container:
                    container.success(f"✅ {len(found_elements)} Treffer gefunden! Zeige Kontexte...")
                    
                    count = 0
                    for element in found_elements:
                        if count >= 3: 
                            break
                        
                        parent = element.parent
                        
                        # Skip irrelevante Tags
                        if parent.name in ['button', 'script', 'style']: 
                            continue
                        
                        container.markdown(f"**Treffer {count+1} (Tag: {parent.name}):**")
                        container.code(parent.prettify()[:1500], language='html')
                        count += 1
                
                # FIX Problem 7: Return leere Liste statt Fake-Message
                return []
            else:
                if container: 
                    container.error(f"❌ Das Wort '{target_word}' wurde im HTML nicht gefunden.")
                return []
        
        # Wenn alle Strategien fehlschlugen
        if container:
            container.error("❌ Alle Strategien fehlgeschlagen. HTML-Struktur unbekannt.")
        
        return []