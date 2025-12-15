from typing import List, Dict, Any
import re
from ..base import ConfigBasedImporter

class DeepSeekImporter(ConfigBasedImporter):
    @property
    def platform_name(self): return "DeepSeek"

    @property
    def platform_id(self): return "deepseek"

    @property
    def detection_signatures(self):
        return ['ds-message', 'ds-markdown', 'ds-theme', 'deepseek']

    def parse(self, content: Any, **kwargs) -> List[Dict[str, Any]]:
        container = kwargs.get('container')
        soup = self.parse_html(content)
        messages = []

        # --- STRATEGIE 1: Standard "ds-message" ---
        all_msgs = soup.find_all("div", class_=lambda x: x and "ds-message" in x)

        if all_msgs:
            if container: container.info(f"DeepSeek: Standard-Format erkannt ({len(all_msgs)} Nachrichten).")
            for msg_div in all_msgs:
                is_user = "ds-message-user" in msg_div.get("class", []) or \
                          msg_div.find(class_=lambda x: x and "user" in x)
                role = 'user' if is_user else 'model'

                content_div = msg_div.find(class_=lambda x: x and "ds-markdown" in x)
                if not content_div: content_div = msg_div

                text = content_div.get_text(separator='\n', strip=True)

                if role == 'model':
                    thinking = self.extract_thinking_block(msg_div)
                    if thinking: text = thinking + text

                if text: messages.append({'role': role, 'content': text})
            return messages

        # --- STRATEGIE 2: Obfuscated Web-Save (Heuristik) ---
        root = soup.find(class_=lambda x: x and "ds-theme" in x)
        if root:
            if container: container.warning("DeepSeek: Obfuscated Web-Format erkannt. Starte Heuristik...")

            text_elements = []
            for elem in root.find_all(['div', 'p']):
                if not elem.find_all(recursive=False) and elem.get_text(strip=True):
                    text = elem.get_text(separator='\n', strip=True)
                    if len(text) > 2: text_elements.append(text)

            current_role = 'user'
            for text in text_elements:
                if text in ["DeepSeek", "Copy", "Regenerate", "Good response", "Bad response"]: continue
                if len(text) > 500: current_role = 'model'

                messages.append({'role': current_role, 'content': text})
                current_role = 'model' if current_role == 'user' else 'user'

            if container: container.success(f"✅ Heuristik: {len(messages)} Textblöcke extrahiert.")
            return messages

        return []