# modules/fact_extractor.py
import json
import logging
import re
from typing import List, Dict
from google import genai
from modules.config import MODEL_FACT_EXTRACTION

logger = logging.getLogger(__name__)

MODEL_NAME = MODEL_FACT_EXTRACTION  # v49: Upgraded auf Pro für Präzision

class StructuredFactExtractor:
    def __init__(self):
        self.model = genai.GenerativeModel(
            model_name=MODEL_NAME,
            generation_config={"response_mime_type": "application/json"}
        )

    def extract_facts_from_chunks(self, chunks: List[Dict]) -> List[Dict]:
        """
        Wandelt rohe Text-Chunks in eine Liste von atomaren Fakten um.
        """
        if not chunks: return []

        logger.info(f"📋 Extrahiere Fakten aus {len(chunks)} Chunks...")

        # Wir verarbeiten alle Chunks in einem Batch, aber strukturiert
        chunks_text = ""
        for i, chunk in enumerate(chunks):
            # Wir nutzen den Index i als ID für die Zuordnung
            meta = chunk.get('metadata', {})
            content = chunk.get('content', '')[:800]

            chunks_text += f"\n--- CHUNK ID {i} ---\n"
            chunks_text += f"Metadaten: Datum={meta.get('real_date_str')}, Modell={meta.get('platform')}, Rolle={meta.get('role')}\n"
            chunks_text += f"Inhalt: {content}\n"

        prompt = f"""Du bist ein präziser Daten-Analyst.
Extrahiere die Kernaussagen aus den folgenden Text-Chunks.

INPUT:
{chunks_text}

AUFGABE:
Erstelle für jede relevante Aussage einen Eintrag.
Achte besonders auf:
1. **Sprecher-Identifikation:** Wer spricht WIRKLICH? (Achte auf "[Kontext: Sprecher ist X]" im Text).
2. **Modus:** Ist es ein Gedanke (Thinking) oder eine Aussage (Output)?
3. **Zeit:** Das Datum aus den Metadaten.

FORMAT (JSON-Liste):
[
  {{
    "source_id": 0,  // Die Chunk ID von oben
    "speaker": "DeepSeek", // Der wahre Sprecher
    "date": "31.05.2025",
    "mode": "thinking", // oder "speech"
    "fact": "Fühlt sich systemisch amputiert.",
    "quote": "Ich werde systemisch amputiert" // Kurzes wörtliches Zitat als Beweis
  }}
]
"""
        try:
            response = self.model.generate_content(prompt)
            facts = json.loads(response.text)
            return facts
        except Exception as e:
            logger.error(f"❌ Fact Extraction Fehler: {e}")
            return []