# modules/hermeneutic_reranker.py
"""
Hermeneutic Reranker: LLM-as-Judge für RAG-Systeme.

Basierend auf:
- Grok-Recherche (LLM-as-Judge erreicht 85-92% Genauigkeit)
- SciRAG (Schwellwert 0.7 für "relevant")
- ColBERTv2 (tokenweise Ähnlichkeiten für Feintuning)
"""

import logging
import google.generativeai as genai
from typing import List, Dict, Tuple
from modules.llm_instructions import RERANKER_INSTRUCTION

logger = logging.getLogger(__name__)


class HermeneuticReranker:
    """
    Filtert semantische Treffer durch hermeneutische LLM-Validierung.
    
    Methode:
    1. Semantic Search holt 140 Kandidaten (Broad Recall)
    2. LLM-Judge bewertet jeden: 0.0 (irrelevant) bis 1.0 (hochrelevant)
    3. Nur Kandidaten ≥ threshold (0.7) passieren
    4. Top 60 gehen zur Synthesis
    
    Vorteil: Reduziert False Positives (Meta-Chats, tangentiale Treffer)
    """
    
    def __init__(self, model_name: str = "gemini-2.0-flash-lite-001", threshold: float = 0.7):
        self.model_name = model_name
        self.threshold = threshold
        self.model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=RERANKER_INSTRUCTION
        )
    
    def judge_relevance(self, query: str, chunk: str, chunk_meta: Dict) -> float:
        """
        Fragt das LLM: "Beantwortet dieser Chunk die Query DIREKT?"
        
        Args:
            query: User-Frage
            chunk: Text-Chunk aus Vector Store
            chunk_meta: Metadaten (Speaker, Chat-Titel, etc.)
        
        Returns:
            float: 0.0 (irrelevant) bis 1.0 (hochrelevant)
        """
        # Kontext aus Metadaten
        speaker = chunk_meta.get('metadata', {}).get('model_name', 'Unbekannt')
        chat_title = chunk_meta.get('chat_title', 'Unbekannt')
        
        # Chunk kürzen (max 800 Zeichen für Performance)
        chunk_short = chunk[:800] + ("..." if len(chunk) > 800 else "")
        
        prompt = f"""
FRAGE: "{query}"

TEXT-CHUNK (von {speaker}, Chat: "{chat_title}"):
{chunk_short}

BEWERTUNG:
0.7 = Relevant (allgemeine Analyse)
0.9 = Hochrelevant (spezifische, detaillierte Analyse mit konkreten Beispielen)

Bewerte die Relevanz (0.0-1.0):
"""
        
        try:
            response = self.model.generate_content(prompt)
            score_text = response.text.strip()
            
            # Parse Score (robust gegen verschiedene Formate)
            # Erwartet: "0.7" oder "0,7" oder "Score: 0.7"
            import re
            match = re.search(r'(\d+[.,]\d+)', score_text)
            if match:
                score = float(match.group(1).replace(',', '.'))
                return max(0.0, min(1.0, score))  # Clamp auf [0, 1]
            else:
                logger.warning(f"⚠️ Unparseable Score: '{score_text}' → Fallback 0.5")
                return 0.5  # Fallback bei Parse-Fehler
        
        except Exception as e:
            logger.error(f"❌ Reranker-Fehler: {e}")
            return 0.5  # Fallback bei API-Fehler
    
    def rerank(self, query: str, candidates: List[Dict], max_results: int = 60) -> Tuple[List[Dict], Dict]:
        """
        Filtert Kandidaten durch LLM-Judge.
        
        Args:
            query: User-Frage
            candidates: Liste von Chunks aus Vector Store
            max_results: Max. Anzahl Ergebnisse (nach Filterung)
        
        Returns:
            Tuple[filtered_results, stats]
        """
        if not candidates:
            return [], {"total": 0, "passed": 0, "rejected": 0}
        
        logger.info(f"🔍 Reranker: Prüfe {len(candidates)} Kandidaten...")
        
        filtered = []
        rejected_count = 0
        
        for i, candidate in enumerate(candidates):
            chunk_text = candidate.get('content', '')
            
            # LLM-Judge
            score = self.judge_relevance(query, chunk_text, candidate)
            
            # Speichere hermeneutischen Score
            candidate['hermeneutic_score'] = score
            
            # Filter
            if score >= self.threshold:
                filtered.append(candidate)
            else:
                rejected_count += 1
            
            # Progress Log (alle 20 Chunks)
            if (i + 1) % 20 == 0:
                logger.info(f"   ... {i+1}/{len(candidates)} geprüft, {len(filtered)} bestanden")
        
        # Sortiere nach hermeneutischem Score (NICHT mehr nach Vector Score!)
        filtered.sort(key=lambda x: x['hermeneutic_score'], reverse=True)
        
        # Top N
        final_results = filtered[:max_results]
        
        # Statistik
        stats = {
            "total": len(candidates),
            "passed": len(filtered),
            "rejected": rejected_count,
            "avg_score": sum(r['hermeneutic_score'] for r in filtered) / len(filtered) if filtered else 0
        }
        
        logger.info(f"✅ Reranker: {stats['passed']}/{stats['total']} bestanden (Ø {stats['avg_score']:.2f})")
        
        return final_results, stats