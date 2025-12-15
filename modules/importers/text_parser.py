import os
import json
import re
import time
import logging
import google.generativeai as genai
import streamlit as st
from typing import List, Dict, Any, Optional

from .base import BaseImporter
from .utils import get_topic_summary
from modules.database import create_chat_in_firestore, save_message, generate_and_update_title

logger = logging.getLogger(__name__)

class TextParserImporter(BaseImporter):
    @property
    def platform_name(self): return "Text / Fallback (LLM)"

    @property
    def platform_id(self): return "text_fallback"

    def parse(self, content: str, container=None) -> List[Dict[str, Any]]:
        """
        Zerlegt Text mittels LLM in Nachrichten.
        'container' ist optional für Streamlit-Progress-Bars.
        """
        chat_text = content

        # UI-Handling (Fallback, falls kein Container übergeben wird)
        status = container.empty() if container else st.empty()
        progress_bar = container.progress(0, text="Starte Analyse...") if container else None

        try:
            if not chat_text or not chat_text.strip():
                status.error("❌ Leerer Text übergeben.")
                return []

            char_count = len(chat_text)
            status.info(f"📊 Analysiere {char_count:,} Zeichen...")

            if not os.environ.get('GEMINI_API_KEY'):
                status.error("❌ API-Key fehlt (GEMINI_API_KEY).")
                return []

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
                if progress_bar:
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

            if progress_bar: progress_bar.empty()
            return all_messages

        except Exception as e:
            logger.error(f"Parse Error: {e}", exc_info=True)
            status.error(f"Fehler beim Parsen: {e}")
            return []

    def import_to_firestore(self, messages: List[Dict[str, Any]], metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Speichert die geparsten Nachrichten in Firestore.
        """
        if not messages:
            return {'chat_id': None, 'message_count': 0}

        # Metadaten auswerten
        source = metadata.get('source', 'unknown') if metadata else 'unknown'

        # Titel generieren
        platform_label = "Gemini" # Default Annahme im alten Code
        # Einfache Heuristik aus altem Code
        first_chunk = messages[0].get('content', '') if messages else ""
        if "chatgpt" in first_chunk.lower(): platform_label = "ChatGPT"

        import_type = "Paste" if "paste" in source else "File"
        chat_title = f"Import: {platform_label} ({import_type}) - {len(messages)} Msgs"

        chat_id = create_chat_in_firestore(chat_title)

        if not chat_id:
            return {'chat_id': None, 'message_count': 0}

        saved_count = 0
        for msg in messages:
            role = msg.get('role', 'user').lower()
            if role not in ['user', 'model']: role = 'user'
            content = msg.get('content', '')

            if content:
                save_message(chat_id, role, content)
                saved_count += 1

        if saved_count > 0:
            generate_and_update_title(chat_id, messages[:3])

        return {
            'chat_id': chat_id,
            'message_count': saved_count,
            'model_name': platform_label
        }