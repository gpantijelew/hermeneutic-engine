import os
import json
import re
import time
import logging
import traceback
from typing import Optional, List, Dict, Tuple, Any

# Drittanbieter-Bibliotheken
from bs4 import BeautifulSoup
import google.generativeai as genai
import streamlit as st

# PROJEKT-IMPORTE
from modules.database import (
    create_chat_in_firestore,
    save_message,
    generate_and_update_title,
    delete_chat
)

print("--- IMPORTER MODUL WURDE GELADEN (v46.16 DOM Walker) ---")
# ==============================================================================
# 1. KONFIGURATION & KONSTANTEN
# ==============================================================================

logger = logging.getLogger(__name__)

# API Key Setup
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# Marker zur automatischen Erkennung
PLATFORM_MARKERS = {
    'chatgpt': ['data-testid="conversation-turn-'],
    'kimi': ['chat-content-item-user', 'chat-content-item-assistant'],
    'claude': ['font-user-message', 'font-claude-message'],
    'gemini': ['message-box', 'ai-markdown-artifact-renderer', 'bard-chat-ui', 'markdown-main-panel'],
    'hotbot': ['tyn-qa-item', 'tyn-qa-item-usr'],
    'lmarena': ['data-sentry-component="SideBySideOrStackedMessageGroup"', 'bg-surface-primary relative flex w-full']
}

# Konfigurationen für generische Parser
PARSER_CONFIGS = {
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
        'content_selectors': {'user': '.whitespace-pre-wrap', 'model': '.markdown.prose'}
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
    }
}

# ==============================================================================
# 2. HILFSFUNKTIONEN
# ==============================================================================

def detect_platform(html_content: bytes) -> Tuple[Optional[str], float, Dict]:
    try:
        html_str = html_content.decode('utf-8', errors='ignore').lower()
    except Exception:
        return None, 0.0, {}

    found_signatures = {}
    for platform, signatures in PLATFORM_MARKERS.items():
        matches = [sig for sig in signatures if sig in html_str]
        if matches:
            found_signatures[platform] = len(matches)

    if not found_signatures:
        return None, 0.0, {}

    best_match_platform = max(found_signatures, key=found_signatures.get)
    confidence = found_signatures[best_match_platform] / len(PLATFORM_MARKERS[best_match_platform])
    diag_signatures = {p: [s for s in PLATFORM_MARKERS[p] if s in html_str] for p in found_signatures}

    return best_match_platform, confidence, diag_signatures

def get_topic_summary(history: List[Dict]) -> str:
    try:
        context_text = ""
        for msg in history[:4]:
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')[:500]
            context_text += f"{role}: {content}\n"

        model = genai.GenerativeModel("gemini-2.0-flash-lite-001")
        prompt = f"Fasse das Thema dieses Chats in maximal 3-5 Worten zusammen. Chat:\n{context_text}"
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception:
        return "Analyse"

# ==============================================================================
# 3. TEXT PARSER
# ==============================================================================

def parse_and_import_text_chat(chat_text: str, source: str, container) -> Tuple[Optional[str], int]:
    status = container.empty()
    progress_bar = container.progress(0, text="Starte Analyse...")

    try:
        if not chat_text or not chat_text.strip():
            status.error("❌ Leerer Text übergeben.")
            return None, 0

        char_count = len(chat_text)
        status.info(f"📊 Analysiere {char_count:,} Zeichen...")

        if not GEMINI_API_KEY:
            status.error("❌ API-Key fehlt (GEMINI_API_KEY).")
            return None, 0

        CHUNK_SIZE = 40000 
        OVERLAP = 1000 

        chunks = []
        for i in range(0, char_count, CHUNK_SIZE - OVERLAP):
            chunks.append(chat_text[i : i + CHUNK_SIZE])

        total_chunks = len(chunks)
        status.info(f"🔪 Text ist zu groß. Zerlege in {total_chunks} Teile...")

        all_messages = []

        for i, chunk in enumerate(chunks):
            current_step = i + 1
            progress_bar.progress(int((current_step / total_chunks) * 100), text=f"Verarbeite Teil {current_step} von {total_chunks}...")

            context_header = f"KONTEXT: Dies ist Teil {current_step} von {total_chunks} eines langen Chats. Der Text kann mitten im Satz beginnen oder enden.\n\n"

            system_prompt = """Du bist ein spezialisierter Parser, der schlecht formatierten Chat-Text repariert und strukturiert.
            DAS PROBLEM: Im Input kleben User-Fragen, KI-Gedanken und KI-Antworten oft ohne Absatz aneinander. 
            DEINE MISSION: Trenne diese Elemente chirurgisch präzise.
            REGELN:
            1. Identifiziere die Sprecher: "user" und "model".
            2. HARTER SCHNITT BEI GEDANKEN: Sobald du Wörter wie "Thinking", "Evaluating..." siehst, beginnt SOFORT eine neue Nachricht mit role: "model".
            3. Formatiere den gesamten Gedanken-Block als Zitat (>) am Anfang der Nachricht.
            4. Trenne Gedanken und Antwort zwingend durch eine Leerzeile.
            5. INHALT: Behalte den Text Wort für Wort bei. Keine Zusammenfassungen.
            6. Gib NUR das JSON-Array zurück: [{"role": "user", "content": "..."}, ...]
            Input Text (Ausschnitt): """

            full_prompt = context_header + system_prompt + chunk + "\n----------------\nJSON Output:"

            model = genai.GenerativeModel(
                model_name="gemini-2.0-flash-lite-001", 
                generation_config={
                    "temperature": 0.0, 
                    "max_output_tokens": 8192,
                    "response_mime_type": "application/json"
                }
            )

            try:
                response = model.generate_content(full_prompt)
                raw_response = response.text.strip()

                cleaned_json = re.sub(r'^```json\s*|\s*```$', '', raw_response, flags=re.MULTILINE).strip()
                start_idx = cleaned_json.find('[')
                end_idx = cleaned_json.rfind(']')

                if start_idx != -1 and end_idx != -1:
                    json_str = cleaned_json[start_idx:end_idx+1]
                    chunk_messages = json.loads(json_str)

                    if isinstance(chunk_messages, list):
                        all_messages.extend(chunk_messages)
                    else:
                        logger.warning(f"Chunk {current_step} lieferte kein Array.")
                else:
                    logger.warning(f"Chunk {current_step}: Kein JSON gefunden.")

            except Exception as e:
                logger.error(f"Fehler in Chunk {current_step}: {e}")
                continue

            time.sleep(0.5)

        progress_bar.empty()

        if not all_messages:
            status.error("❌ Konnte keine Nachrichten extrahieren.")
            return None, 0

        status.info(f"💾 Speichere insgesamt {len(all_messages)} Nachrichten...")

        platform_label = "Gemini"
        if "chatgpt" in chat_text[:500].lower(): platform_label = "ChatGPT"

        import_type = "Paste" if "paste" in source else "File"
        chat_title = f"Import: {platform_label} ({import_type}) - {len(all_messages)} Msgs"

        chat_id = create_chat_in_firestore(chat_title)

        if not chat_id:
            status.error("❌ DB-Fehler.")
            return None, 0

        saved_count = 0
        for msg in all_messages:
            role = msg.get('role', 'user').lower()
            if role not in ['user', 'model']: role = 'user'
            content = msg.get('content', '')

            if content:
                save_message(chat_id, role, content)
                saved_count += 1

        if saved_count > 0:
            generate_and_update_title(chat_id, all_messages[:3])

        status.success(f"✅ Fertig! {saved_count} Nachrichten importiert.")
        return chat_id, saved_count

    except Exception as e:
        status.error(f"❌ Ein unerwarteter Fehler ist aufgetreten: {str(e)}")
        logger.error(f"Import Error: {e}", exc_info=True)
        return None, 0

# ==============================================================================
# 4. SPEZIAL-PARSER (DOM WALKER)
# ==============================================================================

def parse_gemini_html_export(html_content: str, target_word: str = "") -> list[dict]:
    """
    Spezial-Parser für Gemini mit DOM WALKER (v46.16).
    Sammelt User- und Model-Blöcke basierend auf Klassen und Position.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    messages = []

    # 1. Standard-Suche (Takeout) - Wenn das klappt, nehmen wir das
    all_boxes = soup.find_all("div", class_="message-box")
    if all_boxes:
        logger.info("Standard Takeout Format erkannt.")
        # ... (Standard Logik hier einfügen oder an separate Funktion delegieren)
        # Der Einfachheit halber nutzen wir hier die Standard-Logik von vorhin:
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

    # 2. DOM WALKER (für Live-Abzüge)
    logger.info("Starte DOM Walker für Live-Abzug...")

    # Wir suchen ALLE relevanten Container und sortieren sie nach Auftreten im HTML
    # User: oft 'query-content' oder 'user-query-container'
    # Model: 'markdown-main-panel' oder 'model-response-content'

    # Wir nutzen eine Liste von Tupeln: (Element, Rolle)
    found_elements = []

    # Suche User-Blöcke
    for user_div in soup.find_all(class_=re.compile(r'(query-content|user-query)')):
        found_elements.append((user_div, 'user'))

    # Suche Model-Blöcke
    for model_div in soup.find_all(class_=re.compile(r'(markdown-main-panel|model-response)')):
        found_elements.append((model_div, 'model'))

    # Sortieren nach Position im Dokument (sourceline ist in BS4 nicht immer da, wir nutzen index)
    # Trick: Wir nutzen die Tatsache, dass find_all die Dokumentenreihenfolge einhält, aber wir haben zwei Listen gemischt.
    # Besser: Wir iterieren über alle DIVs und prüfen die Klasse.

    messages = []
    all_divs = soup.find_all("div")

    for div in all_divs:
        classes = div.get("class", [])
        if not classes: continue

        role = None
        if any(c in classes for c in ['query-content', 'user-query-container']):
            role = 'user'
        elif any(c in classes for c in ['markdown-main-panel', 'model-response-content']):
            role = 'model'

        if role:
            # Text extrahieren
            text = div.get_text(separator="\n").strip()

            # Thinking Extraktion (nur bei Model)
            if role == 'model':
                # Wir suchen nach einem Thinking-Container INNERHALB dieses Divs oder direkt davor
                # In Live-Abzügen ist Thinking oft in 'model-thoughts-container' oder ähnlich
                thought_text = ""

                # Versuch 1: Suche nach spezifischem Thinking-Container im Block
                thought_container = div.find(class_=re.compile(r'thoughts|reasoning'))
                if thought_container:
                    raw_thought = thought_container.get_text(separator="\n").strip()
                    thought_text = f"> **Thinking:**\n> {raw_thought.replace('\n', '\n> ')}\n\n"
                    # Entfernen, damit es nicht doppelt ist? Vorsicht bei Live-Abzügen.

                # Versuch 2: Wenn kein Container, prüfen wir, ob der Text mit "Thinking:" beginnt (selten)

                full_content = thought_text + text
                # Duplikate vermeiden (manchmal sind Container verschachtelt)
                if messages and messages[-1]['content'] == full_content:
                    continue

                if full_content:
                    messages.append({"role": role, "content": full_content})

            elif role == 'user':
                if text:
                     # Duplikate vermeiden
                    if messages and messages[-1]['content'] == text:
                        continue
                    messages.append({"role": role, "content": text})

    if messages:
        st.success(f"✅ DOM Walker: {len(messages)} Nachrichten gefunden (User & Model).")
        return messages

    # 3. Fallback: Diagnose (wenn Suchwort da ist)
    if target_word:
        st.warning(f"🔎 Deep Scan nach '{target_word}'...")
        found_elements = soup.find_all(string=re.compile(re.escape(target_word), re.IGNORECASE))
        if found_elements:
            st.success(f"✅ {len(found_elements)} Treffer gefunden! Zeige Kontexte...")
            count = 0
            for element in found_elements:
                if count >= 3: break
                parent = element.parent
                if parent.name in ['button', 'script', 'style']: continue
                if 'conversation-title' in str(parent.get('class', [])): continue
                st.markdown(f"**Treffer {count+1} (Tag: {parent.name}):**")
                st.code(parent.prettify()[:1500], language='html')
                count += 1
            return [{'role': 'user', 'content': 'Diagnose Mode'}]
        else:
            st.error(f"❌ Das Wort '{target_word}' wurde im HTML nicht gefunden.")
            return []

    return []

def parse_lmarena(soup: BeautifulSoup, status_container) -> Optional[List[Dict]]:
    """
    Spezial-Parser für LM Arena (v46.7).
    """
    try:
        messages = []
        chat_blocks = soup.select('div.self-end, div[class*="lg:flex-row"]')

        for block in chat_blocks:
            if 'self-end' in block.get('class', []):
                content_element = block.select_one('div.prose')
                if content_element:
                    messages.append({'role': 'user', 'content': content_element.get_text(separator='\n', strip=True)})

            elif any('lg:flex-row' in cls for cls in block.get('class', [])):
                arena_turn = {'role': 'arena_turn', 'models': []}
                model_cards = block.select('div.bg-surface-primary.relative.flex.w-full')

                for card in model_cards:
                    model_name_element = card.select_one('span.truncate')

                    thought_text = ""
                    reasoning_element = card.select_one('div[data-sentry-component="ReasoningContent"]')
                    if reasoning_element:
                        raw_thought = reasoning_element.get_text(separator='\n', strip=True)
                        raw_thought = re.sub(r'^Thought for \d+ seconds', '', raw_thought).strip()
                        thought_text = f"> **Thinking:**\n> {raw_thought.replace('\n', '\n> ')}\n\n"

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

        messages.reverse()
        status_container.success(f"LM Arena Parser: {len(messages)} Interaktionen extrahiert.")
        return messages if messages else None
    except Exception as e:
        status_container.error(f"❌ LM Arena Parser Fehler: {e}")
        return None

# ==============================================================================
# 5. GENERISCHE PARSER
# ==============================================================================

def parse_with_config(soup: BeautifulSoup, platform: str, status_container) -> Optional[List[Dict]]:
    config = PARSER_CONFIGS.get(platform)
    if not config:
        status_container.warning(f"⚠️ Keine Parser-Konfiguration für '{platform}' gefunden.")
        return None

    try:
        messages = []
        message_blocks = soup.select(config['message_block_selector'])

        if not message_blocks:
            status_container.warning(f"⚠️ Config-Parser: Keine Nachrichtenblöcke für Selektor '{config['message_block_selector']}' gefunden.")
            return None

        for block in message_blocks:
            role, content = None, None
            role_detection_config = config['role_detection']

            if 'tag_based' in role_detection_config:
                tag_config = role_detection_config['tag_based']
                if block.select_one(tag_config['user']): role = 'user'
                elif block.select_one(tag_config['model']): role = 'model'

            elif 'attribute_based' in role_detection_config:
                attr_config = role_detection_config['attribute_based']
                author_element = block.select_one(attr_config['element_selector'])
                if author_element:
                    attr_value = author_element.get(attr_config['attribute'])
                    if attr_value == attr_config['user_value']: role = 'user'
                    elif attr_value == attr_config['model_value']: role = 'model'

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
                content = content_element.get_text(separator='\n', strip=True)
                if content:
                    messages.append({'role': role, 'content': content})

        return messages if messages else None
    except Exception as e:
        status_container.error(f"❌ Config-Parser Fehler für {platform}: {e}")
        return None

def parse_with_ai_fallback(html_content: str, status_container) -> Optional[List[Dict]]:
    status_container.info("🧠 Nutze KI-Fallback (via Text-Parser)...")
    return None 

# ==============================================================================
# 6. HAUPT-IMPORT-LOGIK (ORCHESTRATOR)
# ==============================================================================

def parse_and_import_html(html_content_bytes: bytes, force_mode: Optional[str], file_container, manual_platform: Optional[str] = None) -> Tuple[Optional[str], int]:
    messages, used_method, detected_platform = None, None, None

    try:
        diag_container = file_container.container()
        status_container = file_container.container()

        # --- NEU: Suchfeld in der SIDEBAR ---
        target_word = ""
        if manual_platform == 'gemini':
            with st.sidebar:
                st.markdown("### 🕵️‍♀️ Gemini Diagnose")
                st.info("Falls der Import scheitert, gib hier ein Wort aus dem Chat ein:")
                target_word = st.text_input("Suchwort (z.B. 'Wiesel'):", key="gemini_biopsy_word")
        # ----------------------------------

        platform = None
        confidence = 0.0

        if manual_platform:
            platform = manual_platform
            confidence = 1.0
            status_container.info(f"🎯 Manuelle Auswahl: {PARSER_CONFIGS.get(platform, {'name': platform.upper()})['name']}")
            force_mode = None
        elif force_mode == 'ai':
            pass 
        else:
            platform, confidence, found_signatures = detect_platform(html_content_bytes)
            detected_platform = platform
            with diag_container:
                if not found_signatures:
                    st.warning("⚠️ Keine bekannte Plattform-Signatur gefunden")

        if not messages and force_mode != 'ai':
            if platform:
                platform_name = PARSER_CONFIGS.get(platform, {'name': platform.upper()})['name']
                if not manual_platform:
                    status_container.success(f"✅ Plattform erkannt: **{platform_name}** (Confidence: {confidence:.0%})")

                html_string = html_content_bytes.decode('utf-8', errors='ignore')

                if platform == 'gemini':
                     status_container.info(f"✨ Starte spezialisierten Gemini-Parser...")
                     # WICHTIG: Wir übergeben das Target Word!
                     messages = parse_gemini_html_export(html_string, target_word)
                     if messages: used_method = "Spezial-Parser (Gemini)"

                elif platform == 'lmarena':
                    soup = BeautifulSoup(html_string, 'html.parser')
                    status_container.info(f"🚀 Starte spezialisierten Parser für {platform_name}...")
                    messages = parse_lmarena(soup, status_container)
                    if messages: used_method = f"Spezial-Parser ({platform_name})"

                elif confidence >= 0.5:
                    soup = BeautifulSoup(html_string, 'html.parser')
                    status_container.info(f"📋 Versuche Config-Parser für {platform_name}...")
                    messages = parse_with_config(soup, platform, status_container)
                    if messages:
                        used_method = f"Config-Parser ({platform_name})"
                    else:
                        status_container.warning(f"⚠️ Config-Parser fehlgeschlagen.")

        if not messages:
            html_string_fallback = html_content_bytes.decode('utf-8', errors='ignore')
            status_container.info("🔄 Wechsle zu KI-Fallback (Text-Analyse)...")
            return parse_and_import_text_chat(html_string_fallback, "html_fallback", status_container)

        # 4. SPEZIAL-LOGIK: LM ARENA SPLIT
        if platform == 'lmarena' and messages:
            status_container.info("⚔️ LM Arena erkannt: Splitte in zwei separate Chats...")

            chat_a_history = []
            chat_b_history = []
            model_a_name = "Model A"
            model_b_name = "Model B"

            for msg in messages:
                if msg['role'] == 'arena_turn':
                    models = msg.get('models', [])
                    if len(models) >= 1: model_a_name = models[0]['name']
                    if len(models) >= 2: model_b_name = models[1]['name']
                    break 

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

            status_container.info("🧠 Generiere Titel-Zusammenfassung...")
            topic_a = get_topic_summary(chat_a_history)

            title_a = f"Arena: {model_a_name} | {topic_a}"
            chat_id_a = create_chat_in_firestore(title_a)
            count_a = 0
            if chat_id_a:
                for msg in chat_a_history:
                    if save_message(chat_id_a, msg['role'], msg['content']): count_a += 1

            title_b = f"Arena: {model_b_name} | {topic_a}"
            chat_id_b = create_chat_in_firestore(title_b)
            count_b = 0
            if chat_id_b:
                for msg in chat_b_history:
                    if save_message(chat_id_b, msg['role'], msg['content']): count_b += 1

            status_container.success(f"✅ Split erfolgreich!\n1. {title_a}\n2. {title_b}")
            return chat_id_a, count_a + count_b

        if not messages:
            status_container.error("❌ Keine Nachrichten extrahiert")
            return None, 0

        title_suffix = f" ({detected_platform.upper()})" if detected_platform and detected_platform != "N/A" else " (Import)"
        chat_id = create_chat_in_firestore(f"Import{title_suffix}")

        if not chat_id:
            status_container.error("❌ Konnte Chat nicht in DB erstellen")
            return None, 0

        message_count, history_for_title = 0, []
        for msg in messages:
            if msg['role'] in ['user', 'model']:
                if save_message(chat_id, msg['role'], msg['content']):
                    message_count += 1
                    history_for_title.append({'role': msg['role'], 'content': msg['content']})
            elif msg['role'] == 'arena_turn':
                combined_content = f"--- Arena-Vergleich ---\n\n"
                for model_response in msg['models']:
                    combined_content += f"**Modell: {model_response['name']}**\n\n{model_response['content']}\n\n---\n\n"
                if save_message(chat_id, 'model', combined_content):
                    message_count += 1

        if message_count > 0:
            if history_for_title:
                generate_and_update_title(chat_id, history_for_title)
            status_container.info(f"ℹ️ Methode: {used_method}")
            return chat_id, message_count
        else:
            delete_chat(chat_id)
            return None, 0

    except Exception as e:
        file_container.error(f"❌ Ein unerwarteter Fehler ist aufgetreten: {str(e)}")
        logger.error(f"Import Error: {e}", exc_info=True)
        return None, 0