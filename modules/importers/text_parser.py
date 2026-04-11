# modules/importers/text_parser.py
"""
TextParserImporter - Intelligenter Hybrid-Parser (LLM + Direct Chunking)

VERWENDUNG:
- Für Chat-Exports (nutzt LLM zur Strukturierung)
- Für Bücher/Dokumente (nutzt Direct Chunking für Stabilität)

PHILOSOPHIE:
- Wenn Text wie ein Chat aussieht (viele Sprecherwechsel) -> LLM Parsing (Original-Logik)
- Wenn Text wie ein Buch aussieht (Fließtext) -> Mechanisches Chunking (Neu)
- Verhindert JSON-Fehler bei großen Textmengen

ÄNDERUNGSHISTORIE:
- v50.9: FULL RESTORE (Original Chat-Logik wiederhergestellt + Buch-Modus)
- v50.8: "Book-Mode" eingeführt
- v50.7: Byte-Fix für Uploads
"""

import os
import json
import re
import time
import logging
from google import genai
import streamlit as st
from typing import List, Dict, Any, Optional

from .base import BaseImporter
from modules.database import create_chat_in_firestore, save_message, generate_and_update_title

logger = logging.getLogger(__name__)

class TextParserImporter(BaseImporter):

    @property
    def platform_name(self): 
        return "Text / Buch / Fallback"

    @property
    def platform_id(self): 
        return "text_fallback"

    def _estimate_message_density(self, sample_text: str) -> float:
        """
        Schätzt, ob es ein Chat oder ein Buch ist.
        Nutzt Regex für Geschwindigkeit (LLM hierfür zu langsam/teuer).
        """
        if not sample_text:
            return 0.0

        # Zähle typische Chat-Indikatoren (User:, Model:, Zeitstempel [HH:MM], Datum)
        # Diese Muster kommen in Romanen fast nie in dieser Dichte vor.
        indicators = len(re.findall(r'(User:|Model:|Assistant:|\[\d{2}:\d{2}\]|\b20\d{2}-\d{2}-\d{2}\b)', sample_text, re.IGNORECASE))

        # Berechne Dichte pro 1000 Zeichen
        density = (indicators / len(sample_text)) * 1000
        logger.info(f"📊 Message-Density Score: {density:.2f} (Indikatoren/1k Zeichen)")
        return density

    def _simple_chunking(self, text: str, chunk_size: int = 15000) -> List[Dict[str, Any]]:
        """
        Mechanisches Chunking für Bücher. Keine KI, keine JSON-Fehler.
        Schneidet Text an Absatzgrenzen.
        """
        messages = []
        start = 0
        text_len = len(text)

        logger.info(f"📚 Buch-Modus: Schneide {text_len} Zeichen in ~{chunk_size}er Blöcke...")

        while start < text_len:
            end = start + chunk_size

            # Versuche, an einem Absatz oder Satzende zu schneiden
            if end < text_len:
                # Suche nach letztem Absatz (bevorzugt)
                last_break = text.rfind('\n\n', start, end)
                if last_break != -1 and last_break > start + (chunk_size // 2):
                    end = last_break + 2
                else:
                    # Suche nach Satzende (Fallback)
                    last_period = text.rfind('. ', start, end)
                    if last_period != -1 and last_period > start + (chunk_size // 2):
                        end = last_period + 1

            chunk_content = text[start:end].strip()
            if chunk_content:
                # Wir speichern Buch-Teile als "Model"-Nachrichten
                # Titel-Zeile hilft beim Wiederfinden im RAG
                part_num = len(messages) + 1
                messages.append({
                    "role": "model", 
                    "content": f"**[Buch-Auszug Teil {part_num}]**\n\n{chunk_content}"
                })

            start = end

        return messages

    def _calculate_adaptive_chunk_size(self, total_chars: int, density: float) -> int:
        """
        Berechnet adaptive Chunk-Size basierend auf Message-Density.
        (Original-Logik wiederhergestellt)
        """
        # Fallback für sehr kleine Density
        if density <= 0.1: density = 0.5

        target_messages_per_chunk = 12  # Ziel: ~12 Messages pro Chunk

        # Berechne: Wie viele Zeichen brauchen wir für 12 Messages?
        chars_per_message = 1000 / density
        adaptive_size = int(chars_per_message * target_messages_per_chunk)

        # Clamp zwischen 10k-50k (verhindert zu kleine/große Chunks)
        adaptive_size = max(10000, min(50000, adaptive_size))

        logger.info(f"🎯 Adaptive Chunk-Size: {adaptive_size:,} Zeichen (Ziel: {target_messages_per_chunk} Msgs/Chunk)")

        return adaptive_size

    def parse(self, content: Any, container=None) -> List[Dict[str, Any]]:
        """
        Haupt-Logik: Entscheidet zwischen Chat-Parse und Buch-Import.
        """

        # ==========================================
        # 1. FIX: BYTES AUTOMATISCH DECODIEREN
        # ==========================================
        if isinstance(content, bytes):
            try:
                content = content.decode('utf-8', errors='ignore')
                logger.info("✅ Bytes erfolgreich zu UTF-8 String konvertiert.")
            except Exception as e:
                logger.error(f"❌ Fehler beim Decodieren der Bytes: {e}")
                # Fallback: Versuch als String zu behandeln
                content = str(content)

        chat_text = content

        # UI-Handling
        status = container.empty() if container else st.empty()
        progress_bar = container.progress(0, text="Starte Analyse...") if container else None

        try:
            # ====== VALIDATION ======
            if not chat_text or not chat_text.strip():
                status.error("❌ Leerer Text übergeben.")
                return []

            char_count = len(chat_text)
            status.info(f"📊 Analysiere {char_count:,} Zeichen...")


            # ==========================================
            # 2. ENTSCHEIDUNG: BUCH ODER CHAT?
            # ==========================================
            sample_size = min(5000, char_count)
            sample_text = chat_text[:sample_size]
            density = self._estimate_message_density(sample_text)

            # SCHWELLENWERT: Unter 0.5 bedeutet "Buch/Artikel"
            # (Dein Buch hatte 0.20 -> wird korrekt erkannt)
            if density < 0.5:
                if progress_bar: progress_bar.empty()
                status.info(f"📚 Dokument erkannt (Density {density:.2f}). Importiere als Buch...")
                # Nutze den sicheren Buch-Modus (Direct Chunking)
                return self._simple_chunking(chat_text, chunk_size=15000)

            # ============================================================
            # 3. CHAT-MODUS (ORIGINAL-LOGIK WIEDERHERGESTELLT)
            # ============================================================
            status.info(f"💬 Chat-Struktur erkannt (Density {density:.2f}). Starte KI-Analyse...")

            # Schritt A: Berechne adaptive Chunk-Size
            chunk_size = self._calculate_adaptive_chunk_size(char_count, density)
            overlap = min(1000, chunk_size // 10)  # Overlap = 10% der Chunk-Size

            # Schritt B: Erstelle Chunks
            chunks = []
            for i in range(0, char_count, chunk_size - overlap):
                chunks.append(chat_text[i : i + chunk_size])

            total_chunks = len(chunks)
            status.info(f"🔪 Text in {total_chunks} adaptive Teile zerlegt (Ø {chunk_size/1000:.1f}k Zeichen/Teil)")

            # Schritt C: Generischer System-Prompt (Original)
            system_prompt = """You are a chat message parser. Convert unstructured text into structured JSON messages.

TASK:
Parse the input text and identify individual messages between a user and an AI assistant.

OUTPUT FORMAT:
Return ONLY a valid JSON array: [{"role": "user" or "model", "content": "..."}]

RULES:
1. Preserve original text verbatim - no summaries or paraphrasing
2. Identify speaker changes (user questions vs AI responses)
3. If you detect reasoning/thinking blocks (e.g., "Thinking:", "Evaluating:"), format them as quoted text (>) at the start of the model's message
4. Separate thinking blocks from the answer with a blank line
5. Handle multi-turn conversations gracefully
6. If uncertain about speaker, default to "user"

EXAMPLES OF VALID OUTPUT:
[
  {"role": "user", "content": "What is quantum computing?"},
  {"role": "model", "content": "> Analyzing question complexity...\\n\\nQuantum computing uses..."}
]

Input Text:"""

            # Schritt D: LLM Processing Loop (Original)
            all_messages = []
            failed_chunks = []

            for i, chunk in enumerate(chunks):
                current_step = i + 1

                if progress_bar:
                    progress_bar.progress(
                        int((current_step / total_chunks) * 100),
                        text=f"Verarbeite Teil {current_step} von {total_chunks}..."
                    )

                # Kontext-Header für Multi-Chunk-Texte
                context_header = ""
                if total_chunks > 1:
                    context_header = f"CONTEXT: This is part {current_step} of {total_chunks} of a longer chat. Text may start/end mid-sentence.\n\n"

                full_prompt = context_header + system_prompt + chunk + "\n----------------\nJSON Output:"

                try:
                    model = genai.GenerativeModel(
                        model_name="gemini-2.0-flash-lite-001",
                        generation_config={
                            "temperature": 0.0,
                            "max_output_tokens": 8192,
                            "response_mime_type": "application/json"
                        }
                    )

                    response = model.generate_content(full_prompt)
                    raw_response = response.text.strip()

                    # JSON-Extraktion (robust gegen Markdown-Fences)
                    cleaned_json = re.sub(r'^```json\s*|\s*```$', '', raw_response, flags=re.MULTILINE).strip()

                    # Finde JSON-Array
                    start_idx = cleaned_json.find('[')
                    end_idx = cleaned_json.rfind(']')

                    if start_idx != -1 and end_idx != -1:
                        json_str = cleaned_json[start_idx:end_idx+1]
                        chunk_messages = json.loads(json_str)

                        if isinstance(chunk_messages, list):
                            all_messages.extend(chunk_messages)
                            logger.info(f"✅ Chunk {current_step}/{total_chunks}: {len(chunk_messages)} Messages extrahiert")
                        else:
                            logger.warning(f"⚠️ Chunk {current_step}/{total_chunks}: Kein Array zurückgegeben")
                            failed_chunks.append(current_step)
                    else:
                        logger.warning(f"⚠️ Chunk {current_step}/{total_chunks}: Kein JSON gefunden")
                        failed_chunks.append(current_step)

                except json.JSONDecodeError as e:
                    logger.error(f"❌ Chunk {current_step}/{total_chunks}: JSON-Parse-Fehler: {e}")
                    failed_chunks.append(current_step)
                    continue

                except Exception as e:
                    logger.error(f"❌ Chunk {current_step}/{total_chunks}: Unerwarteter Fehler: {e}", exc_info=True)
                    failed_chunks.append(current_step)
                    continue

                # Rate-Limiting (0.5s zwischen Requests)
                time.sleep(0.5)

            # Schritt E: Ergebnis-Report
            if progress_bar: 
                progress_bar.empty()

            if failed_chunks:
                status.warning(
                    f"⚠️ {len(failed_chunks)} von {total_chunks} Chunks fehlgeschlagen: {failed_chunks}\n"
                    f"✅ {len(all_messages)} Messages erfolgreich extrahiert."
                )
            else:
                status.success(f"✅ Alle {total_chunks} Chunks erfolgreich verarbeitet! ({len(all_messages)} Messages)")

            return all_messages

        except Exception as e:
            logger.error(f"Parse Error: {e}", exc_info=True)
            status.error(f"Fehler beim Parsen: {e}")
            return []

    def import_to_firestore(self, messages: List[Dict[str, Any]], metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Speichert die geparsten Nachrichten in Firestore.
        (Original-Logik wiederhergestellt)
        """
        if not messages:
            return {'chat_id': None, 'message_count': 0}

        source = metadata.get('source', 'unknown') if metadata else 'unknown'
        import_type = "Paste" if "paste" in source.lower() else "File"
        chat_title = f"Text Import ({import_type}) - {len(messages)} Messages"

        # ====== FIRESTORE SPEICHERUNG ======
        chat_id = create_chat_in_firestore(chat_title)
        if not chat_id:
            return {'chat_id': None, 'message_count': 0}

        saved_count = 0
        for msg in messages:
            role = msg.get('role', 'user').lower()
            if role not in ['user', 'model']: 
                role = 'user'

            content = msg.get('content', '')
            if content:
                save_message(chat_id, role, content)
                saved_count += 1

        # Titel nachträglich via LLM verbessern
        if saved_count > 0:
            # Nimm nur die ersten 3 Messages/Chunks für den Titel, um Zeit zu sparen
            generate_and_update_title(chat_id, messages[:3])

        return {
            'chat_id': chat_id,
            'message_count': saved_count,
            'model_name': 'Text Import (Hybrid)'
        }