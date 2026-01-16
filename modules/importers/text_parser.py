# modules/importers/text_parser.py
"""
TextParserImporter - LLM-basierter Fallback für unstrukturierten Text

VERWENDUNG:
- Für Chat-Exports ohne klare HTML-Struktur
- Für Copy-Paste aus unbekannten Quellen
- Für PDF/OCR-Transkripte

PHILOSOPHIE:
- Generisch: Funktioniert für alle Chat-Formate (WhatsApp, Twitter, etc.)
- Adaptiv: Passt Chunk-Größe an Message-Density an
- Robust: Loggt Fehler transparent, schluckt sie nicht still

ÄNDERUNGSHISTORIE:
- v50.6: Adaptive Chunking, generischer Prompt, besseres Error-Handling
- v49: Initiale Version mit Fixed-Size-Chunking
"""

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
    def platform_name(self): 
        return "Text / Fallback (LLM)"
    
    @property
    def platform_id(self): 
        return "text_fallback"
    
    def _estimate_message_density(self, sample_text: str) -> float:
        """
        Schätzt die Message-Density (Messages pro 1000 Zeichen) via Probe-Parse.
        
        Args:
            sample_text: Erste ~5000 Zeichen des Texts
            
        Returns:
            Geschätzte Messages pro 1000 Zeichen (z.B. 0.8 = 4 Messages in 5k Zeichen)
        """
        try:
            model = genai.GenerativeModel(
                model_name="gemini-2.0-flash-lite-001",
                generation_config={
                    "temperature": 0.0,
                    "max_output_tokens": 2048,
                    "response_mime_type": "application/json"
                }
            )
            
            probe_prompt = """Count the number of distinct messages in this chat excerpt.
Return ONLY a JSON object: {"message_count": <number>}

Chat excerpt:
""" + sample_text
            
            response = model.generate_content(probe_prompt)
            result = json.loads(response.text.strip())
            message_count = result.get('message_count', 1)
            
            # Berechne Density (Messages pro 1000 Zeichen)
            density = (message_count / len(sample_text)) * 1000
            logger.info(f"📊 Geschätzte Message-Density: {density:.2f} Messages/1k Zeichen")
            
            return max(0.1, density)  # Minimum 0.1 als Fallback
            
        except Exception as e:
            logger.warning(f"Density-Schätzung fehlgeschlagen: {e}. Nutze Default.")
            return 0.5  # Default: ~5 Messages pro 10k Zeichen
    
    def _calculate_adaptive_chunk_size(self, total_chars: int, density: float) -> int:
        """
        Berechnet adaptive Chunk-Size basierend auf Message-Density.
        
        PHILOSOPHIE:
        - Dichte Texte (Philosophie-Dialoge): Kleinere Chunks → mehr Präzision
        - Flache Texte (Romane): Größere Chunks → weniger Overhead
        - Ziel: ~10-15 Messages pro Chunk (unabhängig von Zeichenlänge)
        
        Args:
            total_chars: Gesamtlänge des Texts
            density: Messages pro 1000 Zeichen
            
        Returns:
            Optimale Chunk-Size (geclampt zwischen 10k-50k)
        """
        target_messages_per_chunk = 12  # Ziel: ~12 Messages pro Chunk
        
        # Berechne: Wie viele Zeichen brauchen wir für 12 Messages?
        chars_per_message = 1000 / density
        adaptive_size = int(chars_per_message * target_messages_per_chunk)
        
        # Clamp zwischen 10k-50k (verhindert zu kleine/große Chunks)
        adaptive_size = max(10000, min(50000, adaptive_size))
        
        logger.info(f"🎯 Adaptive Chunk-Size: {adaptive_size:,} Zeichen (Ziel: {target_messages_per_chunk} Msgs/Chunk)")
        
        return adaptive_size
    
    def parse(self, content: str, container=None) -> List[Dict[str, Any]]:
        """
        Zerlegt Text mittels LLM in Nachrichten.
        
        NEU in v50.6:
        - Adaptive Chunking basierend auf Message-Density
        - Generischer System-Prompt (funktioniert für alle Chat-Typen)
        - Transparentes Error-Handling (zeigt fehlgeschlagene Chunks)
        
        Args:
            content: Roher Chat-Text
            container: Optional Streamlit-Container für Progress-UI
            
        Returns:
            Liste von Message-Dicts: [{"role": "user/model", "content": "..."}]
        """
        chat_text = content
        
        # UI-Handling (Fallback, falls kein Container übergeben wird)
        status = container.empty() if container else st.empty()
        progress_bar = container.progress(0, text="Starte Analyse...") if container else None
        
        try:
            # ====== VALIDATION ======
            if not chat_text or not chat_text.strip():
                status.error("❌ Leerer Text übergeben.")
                return []
            
            char_count = len(chat_text)
            status.info(f"📊 Analysiere {char_count:,} Zeichen...")
            
            if not os.environ.get('GEMINI_API_KEY'):
                status.error("❌ API-Key fehlt (GEMINI_API_KEY).")
                return []
            
            # ====== ADAPTIVE CHUNKING (NEU v50.6) ======
            # Schritt 1: Schätze Message-Density mit Probe-Parse
            sample_size = min(5000, char_count)
            sample_text = chat_text[:sample_size]
            density = self._estimate_message_density(sample_text)
            
            # Schritt 2: Berechne adaptive Chunk-Size
            chunk_size = self._calculate_adaptive_chunk_size(char_count, density)
            overlap = min(1000, chunk_size // 10)  # Overlap = 10% der Chunk-Size
            
            # Schritt 3: Erstelle Chunks
            chunks = []
            for i in range(0, char_count, chunk_size - overlap):
                chunks.append(chat_text[i : i + chunk_size])
            
            total_chunks = len(chunks)
            status.info(f"🔪 Text in {total_chunks} adaptive Teile zerlegt (Ø {chunk_size/1000:.1f}k Zeichen/Teil)")
            
            # ====== GENERISCHER SYSTEM-PROMPT (NEU v50.6) ======
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
            
            # ====== LLM PROCESSING MIT ERROR-TRACKING (NEU v50.6) ======
            all_messages = []
            failed_chunks = []  # NEU: Track fehlgeschlagene Chunks
            
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
            
            # ====== ERGEBNIS-REPORT (NEU v50.6) ======
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
        
        NEU in v50.6:
        - Platform-Detection entfernt (unnötig bei 11 Spezial-Importern)
        - Generischer Titel: "Text Import (Paste/File)"
        
        Args:
            messages: Liste von Message-Dicts
            metadata: Optional, enthält 'source' (paste/file)
            
        Returns:
            Dict mit chat_id, message_count, model_name
        """
        if not messages:
            return {'chat_id': None, 'message_count': 0}
        
        # ====== TITEL-GENERIERUNG (VEREINFACHT v50.6) ======
        # Rationale: Wir haben 11 spezialisierte Importer. Was hier landet,
        # ist "unbekanntes Zeug". Keine Heuristik nötig – wird eh von
        # generate_and_update_title() überschrieben.
        
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
            generate_and_update_title(chat_id, messages[:3])
        
        return {
            'chat_id': chat_id,
            'message_count': saved_count,
            'model_name': 'Text Import (LLM-Parsed)'
        }