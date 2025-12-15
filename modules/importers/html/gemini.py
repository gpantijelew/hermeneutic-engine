import re
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup

from ..base import ConfigBasedImporter

class GeminiImporter(ConfigBasedImporter):
    config_key = 'gemini'

    @property
    def platform_name(self): return "Gemini (Google)"

    @property
    def platform_id(self): return "gemini"

    @property
    def detection_signatures(self):
        return [
            'message-box', 'ai-markdown-artifact-renderer', 
            'user-query', 'model-thoughts', 'message-content'
        ]

    def parse(self, content: Any, **kwargs) -> List[Dict[str, Any]]:
        container = kwargs.get('container')
        target_word = kwargs.get('target_word', "")

        soup = self.parse_html(content)
        messages = []

        # --- STRATEGIE 1: Angular / Live-Export ---
        angular_elements = soup.find_all(['user-query', 'model-thoughts', 'message-content'])

        if angular_elements:
            if container: container.info(f"Gemini Live-Export: {len(angular_elements)} Elemente gefunden.")

            current_thought = None 

            for i, elem in enumerate(angular_elements):
                tag_name = elem.name.lower()

                # DEBUG-AUSGABE (nur die ersten 5 und bei Fehlern)
                # if container and i < 5:
                #    container.text(f"Element {i}: <{tag_name}>")

                # 1. USER
                if tag_name == 'user-query':
                    text_div = elem.find('div', class_='query-text')
                    if text_div:
                        text = text_div.get_text(separator='\n', strip=True)
                    else:
                        text = elem.get_text(separator='\n', strip=True)
                        text = text.replace('text_minimize', '').replace('content_copy', '').strip()

                    if text:
                        # Explizit USER setzen
                        messages.append({'role': 'user', 'content': text})
                        # if container: container.write(f"✅ User-Nachricht erkannt: {text[:30]}...")

                # 2. THINKING
                elif tag_name == 'model-thoughts':
                    thought_div = elem.find('div', class_='markdown')
                    if thought_div:
                        raw_thought = thought_div.get_text(separator='\n', strip=True)
                        current_thought = f"> **Thinking:**\n> {raw_thought.replace('\n', '\n> ')}\n\n"

                # 3. MODEL
                elif tag_name == 'message-content':
                    text_div = elem.find('div', class_='markdown')
                    if text_div:
                        text = text_div.get_text(separator='\n', strip=True)
                    else:
                        text = elem.get_text(separator='\n', strip=True)

                    if current_thought:
                        text = current_thought + text
                        current_thought = None

                    if text:
                        # Explizit MODEL setzen
                        messages.append({'role': 'model', 'content': text})
                        # if container: container.write(f"🤖 Model-Nachricht erkannt: {text[:30]}...")

            if messages:
                # Zähle Rollen für Diagnose
                user_count = sum(1 for m in messages if m['role'] == 'user')
                model_count = sum(1 for m in messages if m['role'] == 'model')

                if container: 
                    container.success(f"✅ Parser Ergebnis: {len(messages)} Nachrichten.")
                    container.info(f"📊 Verteilung: {user_count} User / {model_count} Model")

                    if user_count == 0:
                        container.error("⚠️ WARNUNG: Keine User-Nachrichten erkannt! Prüfe Tag-Namen.")

                return messages

        # --- STRATEGIE 2: Standard Takeout ---
        all_boxes = soup.find_all("div", class_="message-box")
        if all_boxes:
            if container: container.info("Standard Takeout Format erkannt.")
            for box in all_boxes:
                classes = box.get("class", [])
                role = "user" if "message-box--user" in classes else "model"
                content_parts = []
                thought_box = box.find("ai-llm-model-thoughts-output-box")
                if thought_box:
                    thought_renderer = thought_box.find("span", class_="ai-markdown-artifact-renderer")
                    if thought_renderer:
                        thought_text = thought_renderer.get_text(separator="\n").strip()
                        content_parts.append(f"> **Thinking:**\n> {thought_text.replace('\n', '\n> ')}\n\n")
                renderers = box.find_all("span", class_="ai-markdown-artifact-renderer")
                for renderer in renderers:
                    if thought_box and renderer in thought_box.descendants: continue
                    content_parts.append(renderer.get_text(separator="\n").strip())
                if role == "user" and not content_parts:
                    text_area = box.find("span", class_="prompt-response-text-area")
                    if text_area: content_parts.append(text_area.get_text(separator="\n").strip())
                full_content = "\n".join(content_parts).strip()
                if full_content: messages.append({"role": role, "content": full_content})
            return messages

        # --- STRATEGIE 4: Diagnose ---
        if target_word:
            if container: container.warning(f"🔎 Deep Scan nach '{target_word}'...")
            found_elements = soup.find_all(string=re.compile(re.escape(target_word), re.IGNORECASE))
            if found_elements:
                if container:
                    container.success(f"✅ {len(found_elements)} Treffer gefunden! Zeige Kontexte...")
                    count = 0
                    for element in found_elements:
                        if count >= 3: break
                        parent = element.parent
                        if parent.name in ['button', 'script', 'style']: continue
                        container.markdown(f"**Treffer {count+1} (Tag: {parent.name}):**")
                        container.code(parent.prettify()[:1500], language='html')
                        count += 1
                return [{'role': 'user', 'content': 'Diagnose Mode - Kein Import'}]
            else:
                if container: container.error(f"❌ Das Wort '{target_word}' wurde im HTML nicht gefunden.")
                return []

        return []