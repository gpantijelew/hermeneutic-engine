# modules/hermeneutic_reranker.py
"""
Hermeneutic Reranker: LLM-as-Judge für RAG-Systeme (v47.1 - Literatur-Sensitiv).

VERBESSERUNGEN (Option C):
- Literarische Texte: Original-Zitate SIND relevant (als Beispiele)
- Analyse-Queries: Auch Kontext-Chunks sind wertvoll (nicht nur direkte Antworten)
- Polyglotte Texte: Chunks in Fremdsprachen werden erkannt und korrekt bewertet

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
    
    v47.1 VERBESSERUNG:
    - Literatur-sensitiv: Erkennt Original-Zitate als relevant
    - Kontext-bewusst: Wertet impliziten Kontext höher
    - Polyglott: Behandelt Fremdsprachen korrekt
    
    Vorteil: Reduziert False Positives (Meta-Chats, tangentiale Treffer)
             OHNE False Negatives (wichtige Kontext-Chunks bleiben erhalten)
    """
    
    def __init__(self, model_name: str = "gemini-2.0-flash-lite-001", threshold: float = 0.7):
        self.model_name = model_name
        self.threshold = threshold
        self.model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=RERANKER_INSTRUCTION
        )
    
    def _detect_query_type(self, query: str) -> str:
        """
        Erkennt Query-Typ für angepasste Bewertung.
        
        Returns:
            "literary" | "analytical" | "factual"
        """
        # Literary Signals
        literary_signals = [
            'gedicht', 'übersetzung', 'musikalität', 'rhythmus', 'metapher',
            'poem', 'poetry', 'translation', 'verse', 'stanza',
            'поэзия', 'стих', 'перевод',  # Russisch
            'poesia', 'verso', 'tradução'   # Portugiesisch
        ]
        
        # Analytical Signals
        analytical_signals = [
            'vergleiche', 'analyse', 'unterschied', 'entwicklung',
            'compare', 'analyze', 'difference', 'evolution',
            'сравни', 'анализ', 'различие'
        ]
        
        query_lower = query.lower()
        
        if any(sig in query_lower for sig in literary_signals):
            return "literary"
        elif any(sig in query_lower for sig in analytical_signals):
            return "analytical"
        else:
            return "factual"
    
    def judge_relevance(self, query: str, chunk: str, chunk_meta: Dict) -> float:
        """
        Fragt das LLM: "Beantwortet dieser Chunk die Query DIREKT?"
        
        v47.1 VERBESSERUNG: Query-Type-Awareness für bessere Bewertung.
        
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
        
        # Query-Typ erkennen
        query_type = self._detect_query_type(query)
        
        # Chunk kürzen (max 800 Zeichen für Performance)
        chunk_short = chunk[:800] + ("..." if len(chunk) > 800 else "")
        
        # ADAPTIVE PROMPT (je nach Query-Typ)
        if query_type == "literary":
            prompt = f"""
FRAGE: "{query}"

TEXT-CHUNK (von {speaker}, Chat: "{chat_title}"):
{chunk_short}

BEWERTUNGS-KONTEXT:
Diese Frage bezieht sich auf literarische Analyse (Gedichte, Übersetzungen, Stilistik).

WICHTIG - LITERARISCHE CHUNKS RICHTIG BEWERTEN:
1. **Original-Texte SIND relevant** (als Beispiele für Analyse)
   - Beispiel: Bei "Musikalität von Pessoa" ist der portugiesische Original-Text HOCHRELEVANT
   - Auch wenn er keine Meta-Aussage enthält!

2. **Übersetzungen SIND relevant** (als Vergleichsmaterial)
   - Deutsche/Englische/Russische Übersetzungen sind ALLE relevant für Vergleiche
   - Auch wenn sie die Frage nicht "direkt" beantworten

3. **Kontext-Chunks SIND wertvoll**
   - Ein Chunk mit "Não sou nada" ist relevant für "Wie ist die Musikalität?"
   - Weil die Synthese daraus Beispiele zitieren kann!

BEWERTUNGS-SKALA:
- 0.9-1.0: Original-Text / Übersetzungs-Text (direkt zitierbar als Beispiel)
- 0.7-0.9: Kontext-Text (liefert Hintergrund für Analyse)
- 0.4-0.7: Tangential relevant (erwähnt Thema, aber wenig Substanz)
- 0.0-0.4: Irrelevant (anderes Thema, Meta-Chat, etc.)

FRAGE DICH:
"Könnte die Synthese aus diesem Chunk ein konkretes Beispiel zitieren?"
Falls JA → mindestens 0.7!

Bewerte die Relevanz (0.0-1.0):
"""
        
        elif query_type == "analytical":
            prompt = f"""
FRAGE: "{query}"

TEXT-CHUNK (von {speaker}, Chat: "{chat_title}"):
{chunk_short}

BEWERTUNGS-KONTEXT:
Diese Frage verlangt Vergleich/Analyse (z.B. "Vergleiche X und Y").

WICHTIG - ANALYTISCHE CHUNKS RICHTIG BEWERTEN:
1. **Direkte Analyse-Aussagen** = hochrelevant (0.8-1.0)
   - "X ist besser als Y, weil..."
   - "Die Entwicklung von A zu B zeigt..."

2. **Implizite Kontext-Chunks** = relevant (0.6-0.8)
   - Ein Chunk über X (ohne Y zu erwähnen) ist TROTZDEM relevant für "Vergleiche X und Y"
   - Weil die Synthese daraus X-Eigenschaften ableiten kann!

3. **Meta-Reflexionen** = relevant (0.5-0.7)
   - "Ich habe beobachtet, dass..."
   - Auch wenn keine direkte Antwort

BEWERTUNGS-SKALA:
- 0.8-1.0: Direkte Analyse mit Vergleich/Entwicklung
- 0.6-0.8: Einseitige Analyse (nur X oder nur Y)
- 0.4-0.6: Kontext ohne explizite Analyse
- 0.0-0.4: Irrelevant

Bewerte die Relevanz (0.0-1.0):
"""
        
        else:  # factual
            prompt = f"""
FRAGE: "{query}"

TEXT-CHUNK (von {speaker}, Chat: "{chat_title}"):
{chunk_short}

BEWERTUNGS-KONTEXT:
Diese Frage verlangt faktische Information (z.B. "Was ist X?", "Wie funktioniert Y?").

BEWERTUNGS-SKALA:
- 0.8-1.0: Direkte, detaillierte Antwort
- 0.6-0.8: Teilweise Antwort oder relevanter Kontext
- 0.4-0.6: Tangential relevant (erwähnt Thema am Rande)
- 0.0-0.4: Irrelevant

Bewerte die Relevanz (0.0-1.0):
"""
        
        try:
            response = self.model.generate_content(prompt)
            score_text = response.text.strip()
            
            # Parse Score (robust gegen verschiedene Formate)
            # Erwartet: "0.7" oder "0,7" oder "1.  0" (Gemini-Bug) oder "Score: 0.7"
            import re
            
            # Clean Score-Text (entferne Whitespace-Fehler wie "1.  0" → "1.0")
            score_clean = re.sub(r'(\d+)[.,]\s+(\d+)', r'\1.\2', score_text)
            
            # Parse Score
            match = re.search(r'(\d+[.,]\d+)', score_clean)
            if match:
                score = float(match.group(1).replace(',', '.'))
                return max(0.0, min(1.0, score))  # Clamp auf [0, 1]
            else:
                logger.warning(f"⚠️ Unparseable Score: '{score_text}' (cleaned: '{score_clean}') → Fallback 0.5")
                return 0.5  # Fallback bei Parse-Fehler
        
        except Exception as e:
            logger.error(f"❌ Reranker-Fehler: {e}")
            return 0.5  # Fallback bei API-Fehler
    
    def rerank(self, query: str, candidates: List[Dict], max_results: int = 60) -> Tuple[List[Dict], Dict]:
        """
        Filtert Kandidaten durch LLM-Judge (v47.1: Query-Type-Aware).
        
        Args:
            query: User-Frage
            candidates: Liste von Chunks aus Vector Store
            max_results: Max. Anzahl Ergebnisse (nach Filterung)
        
        Returns:
            Tuple[filtered_results, stats]
        """
        if not candidates:
            return [], {"total": 0, "passed": 0, "rejected": 0, "query_type": "unknown"}
        
        # Query-Typ erkennen (für Logging)
        query_type = self._detect_query_type(query)
        logger.info(f"🔍 Reranker: Prüfe {len(candidates)} Kandidaten (Query-Typ: {query_type.upper()})...")
        
        filtered = []
        rejected_count = 0
        
        for i, candidate in enumerate(candidates):
            chunk_text = candidate.get('content', '')
            
            # LLM-Judge (mit Query-Type-Awareness!)
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
            "avg_score": sum(r['hermeneutic_score'] for r in filtered) / len(filtered) if filtered else 0,
            "query_type": query_type  # NEU in v47.1
        }
        
        logger.info(f"✅ Reranker: {stats['passed']}/{stats['total']} bestanden (Ø {stats['avg_score']:.2f}, Typ: {query_type})")
        
        return final_results, stats