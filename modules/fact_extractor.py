# modules/fact_extractor.py
"""
Extrahiert atomare Fakten aus RAG-Chunks.

ÄNDERUNGSHISTORIE:
- v50.9-local: Migration auf llm_wrapper (kein genai-Import mehr)
- v49: Upgraded auf Pro für Präzision
"""

import logging
from typing import List, Dict

from modules.llm_wrapper import llm_call_json

logger = logging.getLogger(__name__)


class StructuredFactExtractor:
    def __init__(self):
        # v50.9-local: Kein eigener Client – llm_wrapper übernimmt.
        logger.info("✅ StructuredFactExtractor initialized (llm_wrapper backend).")

    def extract_facts_from_chunks(self, chunks: List[Dict]) -> List[Dict]:
        """
        Wandelt rohe Text-Chunks in eine Liste von atomaren Fakten um.
        """
        if not chunks:
            return []

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
    "source_id": 0,
    "speaker": "DeepSeek",
    "date": "31.05.2025",
    "mode": "thinking",
    "fact": "Fühlt sich systemisch amputiert.",
    "quote": "Ich werde systemisch amputiert"
  }}
]

Antworte NUR mit der JSON-Liste, ohne Markdown-Backticks oder Präambel!
"""
        try:
            facts = llm_call_json(prompt, task="fact_extraction", fallback=[])
            return facts
        except Exception as e:
            logger.error(f"❌ Fact Extraction Fehler: {e}")
            return []