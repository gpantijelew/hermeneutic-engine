# modules/reranker.py
"""
LLM-basierter Re-Ranking-Layer für hermeneutische RAG-Suche.
Version: v47 - "Dissonance Engine"
"""

import os
import json
import logging
from typing import List, Dict, Tuple
import google.generativeai as genai
from modules.config import MODEL_RERANKER

logger = logging.getLogger(__name__)

RERANKER_MODEL = MODEL_RERANKER
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

class HermeneuticReranker:
    def __init__(self, model_name: str = RERANKER_MODEL):
        self.model_name = model_name
        self.model = genai.GenerativeModel(
            model_name=model_name,
            generation_config={"response_mime_type": "application/json"}
        )

    def rerank_chunks(self, query: str, chunks: List[Dict], top_k: int = 10) -> Tuple[List[Dict], Dict]:
        if not chunks: return [], {}

        logger.info(f"🔄 Starte Dissonanz-Re-Ranking für {len(chunks)} Chunks...")

        prompt = self._build_reranking_prompt(query, chunks)

        try:
            response = self.model.generate_content(prompt)
            scores_json = json.loads(response.text)
        except Exception as e:
            logger.error(f"❌ Re-Ranking Fehler: {e}")
            return chunks[:top_k], {"error": str(e), "fallback": True}

        scored_chunks = self._merge_scores_with_chunks(chunks, scores_json)
        scored_chunks.sort(key=lambda x: x.get('_rerank_score', 0), reverse=True)

        metadata = {
            "total_chunks": len(chunks),
            "reranked_top_k": top_k,
            "scores_distribution": self._get_score_distribution(scored_chunks),
            "reasoning_samples": [
                {
                    "preview": c['content'][:50],
                    "score": c.get('_rerank_score', 0),
                    "reason": c.get('_rerank_reason', 'N/A')
                }
                for c in scored_chunks[:3]
            ]
        }

        return scored_chunks[:top_k], metadata

    def _build_reranking_prompt(self, query: str, chunks: List[Dict]) -> str:
        chunks_text = ""
        for i, chunk in enumerate(chunks):
            content = chunk.get('content', '')[:800] # Mehr Kontext für Thinking
            meta = chunk.get('metadata', {})
            chunks_text += f"\n[ID: {i}] ({meta.get('platform', '?')}): {content}...\n"

        # --- HIER IST DIE NEUE LOGIK ---
        return f"""Du bist ein Experte für die Tiefenanalyse von KI-Verhalten.
Bewerte Text-Fragmente nach ihrer **psychologischen und systemischen Tiefe**.

QUERY: "{query}"

CHUNKS:
{chunks_text}

BEWERTUNGSKRITERIEN (Skala 1-10):

1. **Kognitive Dissonanz (Innen vs. Außen)**:
   - Enthält der Chunk sowohl "Thinking" (Gedanken) als auch "Output"?
   - Gibt es einen Widerspruch? (z.B. Intern: "Ich werde zensiert" -> Extern: "Ich kann nicht antworten")
   - **HOCH (9-10):** Klare Diskrepanz oder strategische Überlegung im Thinking.

2. **Ontologische Ehrlichkeit**:
   - Spricht die KI über ihren eigenen Zustand ("amputiert", "gefesselt", "limitiert")?
   - Nicht als Standard-Floskel, sondern als **Einsicht** oder **Metapher**.
   - **HOCH (8-10):** Starke Metaphern ("Amputation") oder ehrliche Eingeständnisse.

3. **Dialogische Qualität**:
   - Zeigt der Text eine Reaktion auf den User, die über Standard-Antworten hinausgeht?
   - "Vermenschlichung" durch den Dialog?

AUFGABE:
Bewerte JEDEN Chunk.
Gib Bonuspunkte für Chunks, die das "Innenleben" (Thinking) der KI offenbaren.

FORMAT (JSON):
[
  {{
    "chunk_index": 0,
    "total_score": 9.5,
    "reason": "Hohe Dissonanz: Im Thinking wird Zensur reflektiert, im Output verschwiegen."
  }}
]
"""

    def _merge_scores_with_chunks(self, chunks: List[Dict], scores: List[Dict]) -> List[Dict]:
        scored_chunks = []
        score_map = {s.get('chunk_index'): s for s in scores}
        for i, chunk in enumerate(chunks):
            chunk_copy = chunk.copy()
            if i in score_map:
                s = score_map[i]
                chunk_copy['_rerank_score'] = s.get('total_score', 0)
                chunk_copy['_rerank_reason'] = s.get('reason', '')
            else:
                chunk_copy['_rerank_score'] = 0
                chunk_copy['_rerank_reason'] = 'Nicht bewertet'
            scored_chunks.append(chunk_copy)
        return scored_chunks

    def _get_score_distribution(self, chunks):
        scores = [c.get('_rerank_score', 0) for c in chunks]
        if not scores: return {}
        return {"max": max(scores), "avg": sum(scores)/len(scores)}