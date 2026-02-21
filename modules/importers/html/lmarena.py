import re
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup

from ..base import HTMLImporter
from ..utils import get_topic_summary
from modules.database import create_chat_in_firestore, save_message

class LMArenaImporter(HTMLImporter):
    @property
    def platform_name(self): return "LM Arena"

    @property
    def platform_id(self): return "lmarena"

    @property
    def detection_signatures(self):
        return [
            'data-sentry-component="SideBySideOrStackedMessageGroup"', 
            'bg-surface-primary relative flex w-full'
        ]

    def parse(self, content: Any, **kwargs) -> List[Dict[str, Any]]:
        """
        Extrahiert Nachrichten aus LM Arena HTML.
        """
        # UI-Container für Status-Updates (optional)
        container = kwargs.get('container')

        soup = self.parse_html(content)
        messages = []

        try:
            # Selektoren aus alter parse_lmarena Funktion
            chat_blocks = soup.select('div.self-end, div[class*="lg:flex-row"]')

            for block in chat_blocks:
                # USER MESSAGE
                if 'self-end' in block.get('class', []):
                    content_element = block.select_one('div.prose')
                    if content_element:
                        messages.append({
                            'role': 'user', 
                            'content': content_element.get_text(separator='\n', strip=True)
                        })

                # MODEL RESPONSE (Arena Turn)
                elif any('lg:flex-row' in cls for cls in block.get('class', [])):
                    arena_turn = {'role': 'arena_turn', 'models': []}
                    model_cards = block.select('div.bg-surface-primary.relative.flex.w-full')

                    for card in model_cards:
                        model_name_element = card.select_one('span.truncate')

                        # Thinking Extraction (Spezifisch für Arena)
                        thought_text = ""
                        reasoning_element = card.select_one('div[data-sentry-component="ReasoningContent"]')
                        if reasoning_element:
                            raw_thought = reasoning_element.get_text(separator='\n', strip=True)
                            raw_thought = re.sub(r'^Thought for \d+ seconds', '', raw_thought).strip()
                            newline_replaced = raw_thought.replace('\n', '\n> ')
                            thought_text = f"> **Thinking:**\n> {newline_replaced}"

                        main_text = ""
                        content_element = card.select_one('div.prose')
                        if content_element:
                            main_text = content_element.get_text(separator='\n', strip=True)

                        if model_name_element and (thought_text or main_text):
                            full_text = thought_text + main_text
                            arena_turn['models'].append({
                                'name': model_name_element.get_text(strip=True),
                                'content': full_text
                            })

                    if arena_turn['models']:
                        messages.append(arena_turn)

            # Alte Logik drehte die Liste um, da Arena oft von unten nach oben parst? 
            # Im alten Code stand messages.reverse(). Ich übernehme das 1:1.
            messages.reverse()

            if container:
                container.success(f"LM Arena Parser: {len(messages)} Interaktionen extrahiert.")

            return messages

        except Exception as e:
            if container:
                container.error(f"❌ LM Arena Parser Fehler: {e}")
            return []

    def import_to_firestore(self, messages: List[Dict[str, Any]], metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Spezial-Logik: Splitte Arena-Vergleich in zwei separate Chats.
        """
        container = metadata.get('container') if metadata else None

        if container:
            container.info("⚔️ LM Arena erkannt: Splitte in zwei separate Chats...")

        chat_a_history = []
        chat_b_history = []
        model_a_name = "Model A"
        model_b_name = "Model B"

        # Namen extrahieren
        for msg in messages:
            if msg['role'] == 'arena_turn':
                models = msg.get('models', [])
                if len(models) >= 1: model_a_name = models[0]['name']
                if len(models) >= 2: model_b_name = models[1]['name']
                break 

        # Historien aufbauen
        for msg in messages:
            if msg['role'] == 'user':
                chat_a_history.append(msg)
                chat_b_history.append(msg)
            elif msg['role'] == 'arena_turn':
                models = msg.get('models', [])
                if len(models) >= 1:
                    chat_a_history.append({'role': 'model', 'content': models[0]['content']})
                if len(models) >= 2:
                    chat_b_history.append({'role': 'model', 'content': models[1]['content']})

        # Titel generieren
        if container: container.info("🧠 Generiere Titel-Zusammenfassung...")
        topic_a = get_topic_summary(chat_a_history)

        # Chat A speichern
        title_a = f"Arena: {model_a_name} | {topic_a}"
        chat_id_a = create_chat_in_firestore(title_a)
        count_a = 0
        if chat_id_a:
            for msg in chat_a_history:
                # Metadaten setzen
                msg_meta = {}
                if msg['role'] == 'model':
                    msg_meta['model_name'] = model_a_name

                if save_message(chat_id_a, msg['role'], msg['content'], metadata=msg_meta): 
                    count_a += 1

        # Chat B speichern
        title_b = f"Arena: {model_b_name} | {topic_a}"
        chat_id_b = create_chat_in_firestore(title_b)
        count_b = 0
        if chat_id_b:
            for msg in chat_b_history:
                # Metadaten setzen
                msg_meta = {}
                if msg['role'] == 'model':
                    msg_meta['model_name'] = model_b_name

                if save_message(chat_id_b, msg['role'], msg['content'], metadata=msg_meta): 
                    count_b += 1

        # --- UPDATE END ---

        if container:
            container.success(f"✅ Split erfolgreich!\n1. {title_a}\n2. {title_b}")

        return {
            'chat_id': chat_id_a,
            'message_count': count_a + count_b,
            'model_name': f"{model_a_name} vs {model_b_name}"
        }