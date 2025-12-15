from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import re
from bs4 import BeautifulSoup

# Datenbank-Funktionen
from modules.database import (
    create_chat_in_firestore, 
    save_message, 
    generate_and_update_title, 
    delete_chat
)

# ==============================================================================
# KONFIGURATION
# ==============================================================================

PARSER_CONFIGS = {
    # --- Etablierte Plattformen ---
    'chatgpt': {
        'name': 'ChatGPT (OpenAI)',
        'sidebar_selector': '#stage-slideover-sidebar',
        'message_block_selector': 'article[data-testid^="conversation-turn-"]',
        'role_detection': {
            'attribute_based': {
                'element_selector': 'div[data-message-author-role]',
                'attribute': 'data-message-author-role',
                'user_value': 'user',
                'model_value': 'assistant'
            }
        },
        'content_selectors': {'user': '.whitespace-pre-wrap', 'model': '.markdown.prose'},
        'model_name_selector': 'div[data-model-name]'
    },
    'lmarena': {
        'name': 'LM Arena',
        'sidebar_selector': 'div[data-sentry-component="ArenaSidebar"]',
    },
    'kimi': {
        'name': 'Kimi Chat (Moonshot)',
        'message_block_selector': 'div.chat-content-item',
        'role_detection': {'class_based': {'user': 'chat-content-item-user', 'model': 'chat-content-item-assistant'}},
        'content_selectors': {'user': 'div.user-content', 'model': 'div.markdown'}
    },
    'claude': {
        'name': 'Claude (Anthropic)',
        'message_block_selector': 'div[data-test-render-count]',
        'role_detection': {'class_based': {'user': 'font-user-message', 'model': 'font-claude-message'}},
        'content_selectors': {'user': 'div.whitespace-pre-wrap', 'model': 'div.whitespace-pre-wrap'}
    },
    'gemini': {
        'name': 'Gemini (Google)',
        'message_block_selector': 'div.message-box',
        'role_detection': {'class_based': {'user': 'message-box--user', 'model': 'model-response'}},
        'content_selectors': {'user': 'span.prompt-response-text-area', 'model': 'span.ai-markdown-artifact-renderer'}
    },
    'hotbot': {
        'name': 'HotBot',
        'message_block_selector': 'div.tyn-qa-item',
        'role_detection': {'class_based': {'user': 'tyn-qa-item-usr', 'model': 'tyn-qa-item-bot'}},
        'content_selectors': {'user': 'div.tyn-qa-message', 'model': 'div.tyn-qa-message'}
    },

    # --- Neue / Experimentelle Plattformen ---
    'perplexity': {
        'name': 'Perplexity AI',
        'message_block_selector': 'div.perplexity-message', 
        'role_detection': {'class_based': {'user': 'user-message', 'model': 'assistant-message'}},
        'content_selectors': {'user': 'div.content', 'model': 'div.content'}
    },
    'grok': {
        'name': 'Grok (xAI)',
        'message_block_selector': 'div.grok-response',
        'role_detection': {'class_based': {'user': 'user-row', 'model': 'model-row'}},
        'content_selectors': {'user': 'div.text-content', 'model': 'div.text-content'}
    },
    'glm': {
        'name': 'GLM-4 (Zhipu)',
        'message_block_selector': 'div.glm-chat-item',
        'role_detection': {'class_based': {'user': 'user-msg', 'model': 'assistant-msg'}},
        'content_selectors': {'user': 'div.msg-content', 'model': 'div.msg-content'}
    }
}

# ==============================================================================
# BASIS KLASSEN
# ==============================================================================

class BaseImporter(ABC):
    """
    Basis-Interface für alle Importer.
    """

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Menschenlesbarer Name"""
        pass

    @property
    @abstractmethod
    def platform_id(self) -> str:
        """Technische ID"""
        pass

    @property
    def detection_signatures(self) -> List[str]:
        """HTML-Signaturen zur Erkennung"""
        return []

    @abstractmethod
    def parse(self, content: Any, **kwargs) -> List[Dict[str, Any]]:
        """
        Parsed Input -> strukturierte Nachrichten.
        """
        pass

    def validate(self, messages: List[Dict[str, Any]]) -> bool:
        """Prüft Mindestanforderungen an Nachrichten"""
        return len(messages) > 0 and all(
            'role' in msg and 'content' in msg and msg['content'].strip()
            for msg in messages
        )

    @abstractmethod
    def import_to_firestore(
        self, 
        messages: List[Dict[str, Any]], 
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Schreibt in DB"""
        pass


class HTMLImporter(BaseImporter):
    """Basis für HTML-basierte Importer"""

    def parse_html(self, html_content: bytes) -> BeautifulSoup:
        return BeautifulSoup(html_content.decode('utf-8', errors='ignore'), 'html.parser')

    def extract_thinking_block(self, element) -> Optional[str]:
        """
        Versucht, Thinking-Blöcke generisch zu erkennen.
        """
        thinking_markers = [
            'thoughts', 'reasoning', 'model-thoughts', 
            'ai-llm-model-thoughts', 'think-aloud', 'thinking-content'
        ]

        thought_container = element.find(class_=lambda x: x and any(m in x.lower() for m in thinking_markers))

        if not thought_container:
            thought_container = element.find(['ai-llm-model-thoughts-output-box'])

        if thought_container:
            raw_thought = thought_container.get_text(separator='\n', strip=True)
            raw_thought = re.sub(r'^Thought for \d+ seconds', '', raw_thought).strip()

            if raw_thought:
                return f"> **Thinking:**\n> {raw_thought.replace('\n', '\n> ')}\n\n"

        return None


class ConfigBasedImporter(HTMLImporter):
    """
    Nutzt PARSER_CONFIGS Dictionary zur Konfiguration.
    Standard-Implementierung für die meisten Chat-Plattformen.
    """
    config_key: str = None

    def parse(self, content: Any, **kwargs) -> List[Dict[str, Any]]:
        container = kwargs.get('container')
        config = PARSER_CONFIGS.get(self.config_key)

        if not config:
            if container: container.warning(f"⚠️ Keine Parser-Konfiguration für '{self.config_key}' gefunden.")
            return []

        try:
            soup = self.parse_html(content)
            messages = []
            message_blocks = soup.select(config['message_block_selector'])

            if not message_blocks:
                if container: container.warning(f"⚠️ Config-Parser: Keine Nachrichtenblöcke gefunden.")
                return []

            for block in message_blocks:
                role, content_text = None, None
                role_detection_config = config['role_detection']

                # 1. Tag Based
                if 'tag_based' in role_detection_config:
                    tag_config = role_detection_config['tag_based']
                    if block.select_one(tag_config['user']): role = 'user'
                    elif block.select_one(tag_config['model']): role = 'model'

                # 2. Attribute Based
                elif 'attribute_based' in role_detection_config:
                    attr_config = role_detection_config['attribute_based']
                    author_element = block.select_one(attr_config['element_selector'])
                    if author_element:
                        attr_value = author_element.get(attr_config['attribute'])
                        if attr_value == attr_config['user_value']: role = 'user'
                        elif attr_value == attr_config['model_value']: role = 'model'

                # 3. Class Based
                elif 'class_based' in role_detection_config:
                    block_classes = block.get('class', [])
                    if role_detection_config['class_based']['user'] in block_classes: role = 'user'
                    elif role_detection_config['class_based']['model'] in block_classes: role = 'model'
                    else:
                        for role_name, role_class in role_detection_config['class_based'].items():
                            if block.select_one(f'.{role_class}'):
                                role = role_name
                                break

                if not role: continue

                content_selector = config['content_selectors'].get(role)
                if not content_selector: continue

                content_element = block.select_one(content_selector)
                if content_element:
                    content_text = content_element.get_text(separator='\n', strip=True)

                    # Thinking Check
                    thinking_text = self.extract_thinking_block(block)
                    if thinking_text:
                        content_text = thinking_text + content_text

                    if content_text:
                        msg_obj = {'role': role, 'content': content_text}

                        # Feature: Modellname extrahieren
                        model_selector = config.get('model_name_selector')
                        if role == 'model' and model_selector:
                            model_elem = block.select_one(model_selector)
                            if model_elem:
                                msg_obj['model_name'] = model_elem.get_text(strip=True)

                        messages.append(msg_obj)

            return messages

        except Exception as e:
            if container: container.error(f"❌ Config-Parser Fehler für {self.config_key}: {e}")
            return []

    def import_to_firestore(self, messages: List[Dict[str, Any]], metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Standard-Import für Single-Chat-Plattformen.
        """
        if not messages:
            return {'chat_id': None, 'message_count': 0}

        # Titel generieren
        title_suffix = f" ({self.platform_name})"
        chat_id = create_chat_in_firestore(f"Import{title_suffix}")

        if not chat_id:
            return {'chat_id': None, 'message_count': 0}

        saved_count = 0
        history_for_title = []
        detected_model_name = self.platform_name

        for msg in messages:
            # Metadaten für diese spezifische Nachricht vorbereiten
            msg_meta = {}

            # 1. Modellname
            if msg.get('model_name'):
                msg_meta['model_name'] = msg['model_name']
                detected_model_name = msg['model_name']

            # 2. Thinking vorhanden?
            if '> **Thinking:**' in msg['content']:
                msg_meta['has_thinking'] = True

            # Speichern mit Metadaten
            if save_message(chat_id, msg['role'], msg['content'], metadata=msg_meta):
                saved_count += 1
                history_for_title.append(msg)

        if saved_count > 0:
            generate_and_update_title(chat_id, history_for_title[:3])
            return {
                'chat_id': chat_id, 
                'message_count': saved_count,
                'model_name': detected_model_name
            }
        else:
            delete_chat(chat_id)
            return {'chat_id': None, 'message_count': 0}