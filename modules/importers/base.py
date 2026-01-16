"""
Base Classes für alle Importer (v50.6 - mit HTML→Markdown Konverter).

CHANGELOG v50.6:
- Hinzugefügt: _html_to_markdown() in ConfigBasedImporter
- Alle Plattformen (ChatGPT, Kimi, Claude, etc.) behalten jetzt Formatierung
- Fix: get_text() wird durch Markdown-Konversion ersetzt

Architektur:
    BaseImporter (ABC)
        ├── HTMLImporter (HTML-Parsing + Thinking-Extraktion)
        └── ConfigBasedImporter (Config-driven + Markdown-Konversion)
"""
import sys
import os
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Callable
from enum import Enum
import re
from bs4 import BeautifulSoup

# Path-Fix für direkte Ausführung (Tests)
if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

# Datenbank-Funktionen
from modules.database import (
    create_chat_in_firestore, 
    save_message, 
    generate_and_update_title, 
    delete_chat
)

# ==============================================================================
# PLATFORM KEYS (Type-Safe)
# ==============================================================================

class PlatformKey(Enum):
    """Enum für Type-Safe Platform-Keys."""
    CHATGPT = 'chatgpt'
    KIMI = 'kimi'
    CLAUDE = 'claude'
    GEMINI = 'gemini'
    HOTBOT = 'hotbot'
    PERPLEXITY = 'perplexity'
    GROK = 'grok'
    GLM = 'glm'
    DEEPSEEK = 'deepseek'

# ==============================================================================
# PARSER CONFIGURATIONS
# ==============================================================================

PARSER_CONFIGS = {
    # --- Etablierte Plattformen ---
    PlatformKey.CHATGPT.value: {
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
   
    PlatformKey.KIMI.value: {
        'name': 'Kimi Chat (Moonshot)',
        'message_block_selector': 'div.chat-content-item',
        'role_detection': {
            'class_based': {
                'user': 'chat-content-item-user', 
                'model': 'chat-content-item-assistant'
            }
        },
        'content_selectors': {'user': 'div.user-content', 'model': 'div.markdown'}
    },
    
    PlatformKey.CLAUDE.value: {
        'name': 'Claude (Anthropic)',
        'message_block_selector': 'div[data-test-render-count]',
        'role_detection': {
            'class_based': {
                'user': 'font-user-message', 
                'model': 'font-claude-message'
            }
        },
        'content_selectors': {
            'user': 'div.whitespace-pre-wrap', 
            'model': 'div.whitespace-pre-wrap'
        }
    },
    
    PlatformKey.GEMINI.value: {
        'name': 'Gemini (Google)',
        'message_block_selector': 'div.message-box',
        'role_detection': {
            'class_based': {
                'user': 'message-box--user', 
                'model': 'model-response'
            }
        },
        'content_selectors': {
            'user': 'span.prompt-response-text-area', 
            'model': 'span.ai-markdown-artifact-renderer'
        }
    },
    
    PlatformKey.HOTBOT.value: {
        'name': 'HotBot',
        'message_block_selector': 'div.tyn-qa-item',
        'role_detection': {
            'class_based': {
                'user': 'tyn-qa-item-usr', 
                'model': 'tyn-qa-item-bot'
            }
        },
        'content_selectors': {
            'user': 'div.tyn-qa-message', 
            'model': 'div.tyn-qa-message'
        }
    },
    
    # --- Neue / Experimentelle Plattformen ---
    PlatformKey.PERPLEXITY.value: {
        'name': 'Perplexity AI',
        'message_block_selector': 'div.perplexity-message', 
        'role_detection': {
            'class_based': {
                'user': 'user-message', 
                'model': 'assistant-message'
            }
        },
        'content_selectors': {
            'user': 'div.content', 
            'model': 'div.content'
        }
    },
    
    PlatformKey.GROK.value: {
        'name': 'Grok (xAI)',
        'message_block_selector': 'div.grok-response',
        'role_detection': {
            'class_based': {
                'user': 'user-row', 
                'model': 'model-row'
            }
        },
        'content_selectors': {
            'user': 'div.text-content', 
            'model': 'div.text-content'
        }
    },
    
    PlatformKey.GLM.value: {
        'name': 'GLM-4 (Zhipu)',
        'message_block_selector': 'div.glm-chat-item',
        'role_detection': {
            'class_based': {
                'user': 'user-msg', 
                'model': 'assistant-msg'
            }
        },
        'content_selectors': {
            'user': 'div.msg-content', 
            'model': 'div.msg-content'
        }
    }
}

# ==============================================================================
# CONFIG VALIDATION (v49.3)
# ==============================================================================

def validate_parser_configs():
    """
    Prüft alle PARSER_CONFIGS auf Vollständigkeit.
    Sollte beim App-Start einmal ausgeführt werden.
    
    Raises:
        ValueError: Wenn eine Config unvollständig ist
    """
    required_keys = ['name', 'message_block_selector', 'role_detection', 'content_selectors']
    
    for platform, config in PARSER_CONFIGS.items():
        # Prüfe erforderliche Keys
        for key in required_keys:
            if key not in config:
                raise ValueError(f"Config für '{platform}' fehlt Key: '{key}'")
        
        # Role-Detection muss mindestens eine Methode haben
        role_methods = ['tag_based', 'attribute_based', 'class_based']
        if not any(k in config['role_detection'] for k in role_methods):
            raise ValueError(
                f"Config für '{platform}' hat keine Role-Detection-Methode! "
                f"Erlaubt: {role_methods}"
            )
    
    print(f"✅ Alle {len(PARSER_CONFIGS)} Parser-Configs validiert.")

# ==============================================================================
# BASE CLASSES
# ==============================================================================

class BaseImporter(ABC):
    """
    Basis-Interface für alle Importer.
    
    Alle Subklassen müssen implementieren:
    - platform_name: Menschenlesbarer Name (z.B. "ChatGPT")
    - platform_id: Technische ID (z.B. "chatgpt")
    - parse(): Parsed Input → strukturierte Nachrichten
    - import_to_firestore(): Schreibt Nachrichten in DB
    """
    
    # Erlaubte Rollen
    VALID_ROLES = {'user', 'model', 'system'}
    
    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Menschenlesbarer Name (z.B. 'ChatGPT')"""
        pass
    
    @property
    @abstractmethod
    def platform_id(self) -> str:
        """Technische ID (z.B. 'chatgpt')"""
        pass
    
    @property
    def detection_signatures(self) -> List[str]:
        """
        HTML-Signaturen zur automatischen Plattform-Erkennung.
        
        Returns:
            Liste von Strings/Selektoren, die in HTML vorkommen müssen
        """
        return []
    
    @abstractmethod
    def parse(self, content: Any, **kwargs) -> List[Dict[str, Any]]:
        """
        Parsed Input → strukturierte Nachrichten.
        
        Args:
            content: HTML-Content (bytes oder str)
            **kwargs: Zusätzliche Parameter (z.B. container für UI-Feedback)
        
        Returns:
            Liste von Nachrichten: [{'role': 'user', 'content': '...'}, ...]
        """
        pass
    
    def validate(self, messages: List[Dict[str, Any]]) -> bool:
        """
        Validiert Nachrichten-Liste (v49.3 - verbessert).
        
        Bedingungen:
        - Mindestens 1 Nachricht
        - Jede Nachricht hat 'role' und 'content'
        - 'role' ist entweder 'user', 'model', oder 'system'
        - Content ist nicht leer
        
        Args:
            messages: Liste von Nachrichten-Dicts
        
        Returns:
            True wenn valide, False sonst
        """
        if not messages:
            return False
        
        for msg in messages:
            # Struktur-Check
            if 'role' not in msg or 'content' not in msg:
                return False
            
            # Role-Check
            if msg['role'] not in self.VALID_ROLES:
                return False
            
            # Content-Check
            if not msg['content'].strip():
                return False
        
        return True
    
    @abstractmethod
    def import_to_firestore(
        self, 
        messages: List[Dict[str, Any]], 
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Schreibt Nachrichten in Firestore.
        
        Args:
            messages: Liste von Nachrichten
            metadata: Optionale Metadaten (z.B. model_name, date)
        
        Returns:
            Dict mit 'chat_id' und 'message_count'
        """
        pass


class HTMLImporter(BaseImporter):
    """
    Basis für HTML-basierte Importer.
    
    Bietet:
    - parse_html(): Konvertiert bytes/str → BeautifulSoup
    - extract_thinking_block(): Generische Thinking-Extraktion
    """
    
    def parse_html(self, html_content: bytes) -> BeautifulSoup:
        """
        Konvertiert HTML-Content zu BeautifulSoup-Objekt.
        
        Args:
            html_content: Rohe HTML-Daten (bytes)
        
        Returns:
            BeautifulSoup-Objekt
        """
        return BeautifulSoup(
            html_content.decode('utf-8', errors='ignore'), 
            'html.parser'
        )
    
    def extract_thinking_block(self, element) -> Optional[str]:
        """
        Versucht, Thinking-Blöcke generisch zu erkennen (v49.3 - verbessert).
        
        Funktioniert für:
        - ChatGPT ("Thought for X seconds")
        - DeepSeek (ähnliches Format)
        - Andere Plattformen mit "thinking", "reasoning", etc.
        
        Args:
            element: BeautifulSoup-Element (Message-Block)
        
        Returns:
            Formatierter Thinking-Block (Markdown) oder None
        """
        # Marker für Thinking-Container (verschiedene Plattformen)
        thinking_markers = [
            'thoughts', 'reasoning', 'model-thoughts', 
            'ai-llm-model-thoughts', 'think-aloud', 'thinking-content'
        ]
        
        # Suche Container mit einem der Marker
        thought_container = element.find(
            class_=lambda x: x and any(m in x.lower() for m in thinking_markers)
        )
        
        # Fallback: Suche nach spezifischen Tags (ChatGPT)
        if not thought_container:
            thought_container = element.find(['ai-llm-model-thoughts-output-box'])
        
        if thought_container:
            raw_thought = thought_container.get_text(separator='\n', strip=True)
            
            # Entferne "Thought for X seconds" Präfix (v49.3 - robust)
            # Unterstützt: "Thought for 5 seconds", "  Thought for 10 second  "
            raw_thought = re.sub(
                r'^\s*Thought for \d+ seconds?\s*', 
                '', 
                raw_thought, 
                flags=re.IGNORECASE
            ).strip()
            
            if raw_thought:
                # Formatiere als Markdown-Blockquote
                thinking_formatted = f"> **Thinking:**\n> {raw_thought.replace(chr(10), chr(10) + '> ')}\n\n"
                return thinking_formatted
        
        return None


class ConfigBasedImporter(HTMLImporter):
    """
    Nutzt PARSER_CONFIGS Dictionary zur Konfiguration (v49.6 - mit Markdown-Konverter).
    Standard-Implementierung für die meisten Chat-Plattformen.
    
    NEU in v49.6:
    - _html_to_markdown(): Behält Formatierung (fett, listen, Tabellen, etc.)
    - Alle Plattformen profitieren automatisch
    
    Subklassen müssen nur setzen:
    - config_key (z.B. PlatformKey.CHATGPT.value)
    - platform_name
    - platform_id
    
    Example:
        class ChatGPTImporter(ConfigBasedImporter):
            config_key = PlatformKey.CHATGPT.value
            platform_name = "ChatGPT"
            platform_id = "chatgpt"
    """
    
    config_key: str = None  # Muss von Subklasse gesetzt werden
    
    def _html_to_markdown(self, element) -> str:
        """
        Konvertiert HTML-Content zu Markdown (behält Formatierung).
        
        Unterstützt:
        - <strong>, <b> → **fett**
        - <em>, <i> → *kursiv*
        - <ul><li>, <ol><li> → Listen
        - <hr/> → Trennlinien
        - <h2>, <h3>, <h4> → Überschriften
        - <table> → Markdown-Tabellen
        - <code>, <pre> → Code-Blöcke
        
        Args:
            element: BeautifulSoup-Element mit HTML-Content
        
        Returns:
            Markdown-formatierter Text
        """
        if not element:
            return ""
        
        # Strategie: HTML-String manipulieren statt DOM
        html_str = str(element)
        
        # 1. Überschriften
        html_str = re.sub(r'<h2[^>]*>(.*?)</h2>', r'\n## \1\n', html_str, flags=re.DOTALL)
        html_str = re.sub(r'<h3[^>]*>(.*?)</h3>', r'\n### \1\n', html_str, flags=re.DOTALL)
        html_str = re.sub(r'<h4[^>]*>(.*?)</h4>', r'\n#### \1\n', html_str, flags=re.DOTALL)
        
        # 2. Fettdruck
        html_str = re.sub(r'<strong[^>]*>(.*?)</strong>', r'**\1**', html_str, flags=re.DOTALL)
        html_str = re.sub(r'<b[^>]*>(.*?)</b>', r'**\1**', html_str, flags=re.DOTALL)
        
        # 3. Kursiv
        html_str = re.sub(r'<em[^>]*>(.*?)</em>', r'*\1*', html_str, flags=re.DOTALL)
        html_str = re.sub(r'<i[^>]*>(.*?)</i>', r'*\1*', html_str, flags=re.DOTALL)
        
        # 4. Trennlinien
        html_str = re.sub(r'<hr\s*/?>', '\n\n---\n\n', html_str)
        
        # 5. Listen (komplexer)
        def replace_list(match):
            list_content = match.group(1)
            # Finde alle <li> Items
            items = re.findall(r'<li[^>]*>(.*?)</li>', list_content, flags=re.DOTALL)
            if not items:
                return match.group(0)
            
            # Konvertiere zu Markdown-Liste
            markdown_items = []
            for item in items:
                # Entferne innere HTML-Tags (außer strong/em die schon konvertiert wurden)
                clean_item = re.sub(r'<p[^>]*>(.*?)</p>', r'\1', item, flags=re.DOTALL)
                markdown_items.append(f"  * {clean_item.strip()}")
            
            return '\n' + '\n'.join(markdown_items) + '\n'
        
        html_str = re.sub(r'<ul[^>]*>(.*?)</ul>', replace_list, html_str, flags=re.DOTALL)
        html_str = re.sub(r'<ol[^>]*>(.*?)</ol>', replace_list, html_str, flags=re.DOTALL)
        
        # 6. Code-Blöcke
        html_str = re.sub(r'<code[^>]*>(.*?)</code>', r'`\1`', html_str, flags=re.DOTALL)
        html_str = re.sub(r'<pre[^>]*>(.*?)</pre>', r'\n```\n\1\n```\n', html_str, flags=re.DOTALL)
        
        # 7. Tabellen (vereinfacht)
        def replace_table(match):
            # Extrahiere Table-HTML
            table_html = match.group(0)
            
            try:
                # Parse nur diese Tabelle
                temp_soup = BeautifulSoup(table_html, 'html.parser')
                table = temp_soup.find('table')
                
                if not table:
                    return match.group(0)
                
                # Header
                headers = []
                thead = table.find('thead')
                if thead:
                    for th in thead.find_all('th'):
                        headers.append(th.get_text(strip=True))
                
                # Rows
                rows = []
                tbody = table.find('tbody')
                if tbody:
                    for tr in tbody.find_all('tr'):
                        row = [td.get_text(strip=True) for td in tr.find_all('td')]
                        if row:
                            rows.append(row)
                
                # Baue Markdown
                if headers:
                    md = '\n\n| ' + ' | '.join(headers) + ' |\n'
                    md += '| ' + ' | '.join(['---'] * len(headers)) + ' |\n'
                    for row in rows:
                        md += '| ' + ' | '.join(row) + ' |\n'
                    return md + '\n'
            except:
                pass
            
            return match.group(0)
        
        html_str = re.sub(r'<table[^>]*>.*?</table>', replace_table, html_str, flags=re.DOTALL)
        
        # 8. Paragraphen → Doppelte Zeilenumbrüche
        html_str = re.sub(r'<p[^>]*>(.*?)</p>', r'\1\n\n', html_str, flags=re.DOTALL)
        
        # 9. Entferne alle verbleibenden HTML-Tags
        soup = BeautifulSoup(html_str, 'html.parser')
        text = soup.get_text(separator='', strip=False)
        
        # 10. Cleanup
        # Entferne mehrfache Leerzeilen
        text = re.sub(r'\n{3,}', '\n\n', text)
        # Entferne Leerzeichen am Zeilenanfang (außer bei Listen/Überschriften)
        lines = []
        for line in text.split('\n'):
            stripped = line.strip()
            if stripped.startswith('*') or stripped.startswith('#') or stripped.startswith('-'):
                lines.append(line)
            else:
                lines.append(stripped)
        
        return '\n'.join(lines).strip()
    
    def parse(
        self, 
        content: Any, 
        progress_callback: Optional[Callable[[int, int], None]] = None,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Config-basiertes Parsing (v49.6 - mit Markdown-Konversion).
        
        Args:
            content: HTML-Content (bytes oder str)
            progress_callback: Optional. Funktion(current, total) für Progress-Updates
            **kwargs: container für UI-Feedback (Streamlit)
        
        Returns:
            Liste von Nachrichten
        """
        container = kwargs.get('container')
        
        # Config laden
        config = PARSER_CONFIGS.get(self.config_key)
        if not config:
            error_msg = f"⚠️ Keine Parser-Konfiguration für '{self.config_key}' gefunden."
            if container:
                container.warning(error_msg)
            else:
                print(error_msg)
            return []
        
        try:
            soup = self.parse_html(content)
            messages = []
            
            # Nachrichten-Blöcke finden
            message_blocks = soup.select(config['message_block_selector'])
            
            if not message_blocks:
                warning_msg = f"⚠️ Config-Parser: Keine Nachrichtenblöcke gefunden."
                if container:
                    container.warning(warning_msg)
                else:
                    print(warning_msg)
                return []
            
            # Blöcke verarbeiten
            for i, block in enumerate(message_blocks):
                role, content_text = None, None
                
                # Role-Detection (3 Methoden)
                role_detection_config = config['role_detection']
                
                # 1. Tag Based
                if 'tag_based' in role_detection_config:
                    tag_config = role_detection_config['tag_based']
                    if block.select_one(tag_config['user']):
                        role = 'user'
                    elif block.select_one(tag_config['model']):
                        role = 'model'
                
                # 2. Attribute Based
                elif 'attribute_based' in role_detection_config:
                    attr_config = role_detection_config['attribute_based']
                    author_element = block.select_one(attr_config['element_selector'])
                    if author_element:
                        attr_value = author_element.get(attr_config['attribute'])
                        if attr_value == attr_config['user_value']:
                            role = 'user'
                        elif attr_value == attr_config['model_value']:
                            role = 'model'
                
                # 3. Class Based
                elif 'class_based' in role_detection_config:
                    block_classes = block.get('class', [])
                    class_config = role_detection_config['class_based']
                    
                    if class_config['user'] in block_classes:
                        role = 'user'
                    elif class_config['model'] in block_classes:
                        role = 'model'
                    else:
                        # Fallback: Suche in Kinder-Elementen
                        for role_name, role_class in class_config.items():
                            if block.select_one(f'.{role_class}'):
                                role = role_name
                                break
                
                # Wenn keine Role erkannt → überspringen
                if not role:
                    continue
                
                # Content extrahieren
                content_selector = config['content_selectors'].get(role)
                if not content_selector:
                    continue
                
                content_element = block.select_one(content_selector)
                if content_element:
                    # *** NEU in v49.6: Markdown-Konversion statt get_text() ***
                    content_text = self._html_to_markdown(content_element)
                    
                    # Thinking-Block prüfen (falls vorhanden)
                    thinking_text = self.extract_thinking_block(block)
                    if thinking_text:
                        content_text = thinking_text + content_text
                    
                    if content_text:
                        msg_obj = {
                            'role': role, 
                            'content': content_text
                        }
                        
                        # Feature: Modellname extrahieren (falls konfiguriert)
                        model_selector = config.get('model_name_selector')
                        if role == 'model' and model_selector:
                            model_elem = block.select_one(model_selector)
                            if model_elem:
                                msg_obj['model_name'] = model_elem.get_text(strip=True)
                        
                        messages.append(msg_obj)
                
                # Progress-Callback (für UI)
                if progress_callback:
                    progress_callback(i + 1, len(message_blocks))
            
            return messages
        
        except Exception as e:
            # Verbesserte Fehlerausgabe (v49.3)
            error_details = f"❌ Config-Parser Fehler für {self.config_key}: {e}"
            if 'message_blocks' in locals():
                error_details += f"\n   Block: {i + 1}/{len(message_blocks)}"
            
            if container:
                container.error(error_details)
            else:
                print(error_details)
            
            return []
    
    def import_to_firestore(
        self, 
        messages: List[Dict[str, Any]], 
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Standard-Import für Single-Chat-Plattformen.
        
        Args:
            messages: Liste von Nachrichten
            metadata: Optionale globale Metadaten
        
        Returns:
            Dict mit 'chat_id', 'message_count', 'model_name'
        """
        if not messages:
            return {'chat_id': None, 'message_count': 0}
        
        # Chat erstellen
        title_suffix = f" ({self.platform_name})"
        chat_id = create_chat_in_firestore(f"Import{title_suffix}")
        
        if not chat_id:
            return {'chat_id': None, 'message_count': 0}
        
        # Nachrichten speichern
        saved_count = 0
        history_for_title = []
        detected_model_name = self.platform_name
        
        for msg in messages:
            # Metadaten für diese spezifische Nachricht vorbereiten
            msg_meta = {}
            
            # 1. Modellname (falls in Message vorhanden)
            if msg.get('model_name'):
                msg_meta['model_name'] = msg['model_name']
                detected_model_name = msg['model_name']
            
            # 2. Thinking-Block erkannt?
            if '> **Thinking:**' in msg['content']:
                msg_meta['has_thinking'] = True
            
            # Speichern mit Metadaten
            if save_message(chat_id, msg['role'], msg['content'], metadata=msg_meta):
                saved_count += 1
                history_for_title.append(msg)
        
        # Titel generieren (aus ersten 3 Nachrichten)
        if saved_count > 0:
            generate_and_update_title(chat_id, history_for_title[:3])
            return {
                'chat_id': chat_id, 
                'message_count': saved_count,
                'model_name': detected_model_name
            }
        else:
            # Kein einzige Nachricht gespeichert → Chat löschen
            delete_chat(chat_id)
            return {'chat_id': None, 'message_count': 0}

# ==============================================================================
# STARTUP VALIDATION (Optional - für Tests)
# ==============================================================================

if __name__ == "__main__":
    print("🔍 Validiere Parser-Konfigurationen...")
    try:
        validate_parser_configs()
        print("✅ Alle Configs sind valide!")
    except ValueError as e:
        print(f"❌ Config-Fehler: {e}")