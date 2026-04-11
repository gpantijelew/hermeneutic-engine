# modules/hermeneutic_reranker.py
"""Hermeneutic Reranker: LLM-as-Judge für RAG-Systeme.

VERBESSERUNGEN v49.2:
- Essay-Analyse wird als LITERARY erkannt (war vorher FACTUAL!)
- Erweiterte Literary-Signals: essay, gattung, stilistik, Autoren-Namen
- Polyglotte Unterstützung: эссе, essai, ensaio

VERBESSERUNGEN v47.1:
- Literarische Texte: Original-Zitate SIND relevant (als Beispiele)
- Analyse-Queries: Auch Kontext-Chunks sind wertvoll
- Polyglotte Texte: Chunks in Fremdsprachen korrekt bewertet

ÄNDERUNGSHISTORIE:
- v50.9-local: Migration auf llm_wrapper (kein genai-Import mehr)
- v50.9: SDK Migration (google.genai)
"""

import logging
import re
from typing import List, Dict, Tuple

from modules.llm_wrapper import llm_call
from modules.llm_instructions import RERANKER_INSTRUCTION

logger = logging.getLogger(__name__)




class HermeneuticReranker:
    """Filtert semantische Treffer durch hermeneutische LLM-Validierung.

    Methode:
    1. Semantic Search holt 140 Kandidaten (Broad Recall)
    2. LLM-Judge bewertet jeden: 0.0 (irrelevant) bis 1.0 (hochrelevant)
    3. Nur Kandidaten ≥ threshold (0.7) passieren
    4. Top 60 gehen zur Synthesis

    v50.9-local:
    - Kein genai.Client mehr – llm_call übernimmt
    - system_instruction via llm_call-Parameter (siehe _USE_SYSTEM_INSTRUCTION)
    - Temperatursteuerung: reranker_temp geht verloren, da llm_wrapper einheitliche
      Temperatur nutzt. Falls nötig: llm_wrapper um temp-Parameter erweitern.
    """

    def __init__(self, threshold: float = 0.7):
        self.threshold = threshold
        logger.info("✅ HermeneuticReranker initialized (llm_wrapper backend).")

    def _detect_query_type(self, query: str) -> str:
        """
        Erkennt Query-Typ für angepasste Bewertung.

        v49.2: Erweiterte Literary-Signals (Essay, Gattung, Autoren)

        Returns:
            "literary" | "analytical" | "factual"
        """
        literary_signals = [
            # Gedichte & Lyrik
            'gedicht', 'übersetzung', 'musikalität', 'rhythmus', 'metapher',
            'poem', 'poetry', 'translation', 'verse', 'stanza',
            'поэзия', 'стих', 'перевод',
            'poesia', 'verso', 'tradução',
            # Essays & Prosa (NEU in v49.2!)
            'essay', 'essai', 'эссе', 'ensaio',
            'gattung', 'genre', 'жанр',
            'literarische analyse', 'literary analysis', 'литературный анализ',
            'stilistik', 'style', 'стиль',
            'prosa', 'prose', 'проза',
            # Literaturwissenschaftliche Begriffe
            'definition', 'definiert', 'defines',
            'text', 'texte', 'текст',
            'autor', 'author', 'автор',
            # Bekannte Autoren (für literarische Vergleiche)
            'adorno', 'chesterton', 'valéry', 'valery',
            'шкловский', 'shklovskii', 'shklovsky',
            'тынянов', 'tynyanov', 'tynianov',
            'pessoa', 'celan', 'ayer', 'voltaire'
        ]

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

    def judge_relevance(self, query: str, chunk: str, chunk_meta: Dict, intent: str = None) -> float:
        """
        Fragt das LLM: "Beantwortet dieser Chunk die Query DIREKT?"

        v50.9-local: llm_call statt genai.Client
        Temperatursteuerung (0.1 vs 0.3) geht verloren → ggf. llm_wrapper erweitern.

        Returns:
            float: 0.0 (irrelevant) bis 1.0 (hochrelevant)
        """
        # Kontext aus Metadaten
        speaker = chunk_meta.get('metadata', {}).get('model_name', 'Unbekannt')
        chat_title = chunk_meta.get('chat_title', 'Unbekannt')

        # Query-Typ erkennen (v50.9 FIX: Router-Intent respektieren!)
        if intent:
            query_type = intent.lower()
            if query_type == "analytical_forensic":
                query_type = "analytical"
            if query_type not in ["literary", "analytical", "factual"]:
                query_type = "factual"
        else:
            query_type = self._detect_query_type(query)

        # Chunk kürzen (max 800 Zeichen für Performance)
        chunk_short = chunk[:800] + ("..." if len(chunk) > 800 else "")

        # ADAPTIVE PROMPT (je nach Query-Typ)
        if query_type == "literary":
            prompt = f"""
FRAGE: "{query}"

TEXT-CHUNK (von {speaker}, Chat: "{chat_title}"): {chunk_short}

BEWERTUNGS-KONTEXT: Diese Frage bezieht sich auf literarische Analyse (Gedichte, Essays, Übersetzungen, Stilistik, Gattungen).

WICHTIG - LITERARISCHE CHUNKS RICHTIG BEWERTEN:
- Original-Texte SIND relevant (als Beispiele für Analyse)
- Bei "Essay-Definition von Adorno" ist Adornos Original-Text HOCHRELEVANT
- Theoretische Texte SIND relevant (Essays über Essays!)
- Kontext-Chunks SIND wertvoll
- Autoren-Namen MATCHEN: Query "Adorno" + Chunk von Adorno → HOCHRELEVANT!

BEWERTUNGS-SKALA:
0.9-1.0: Direkte Antwort (Essay-Definition vom genannten Autor)
0.7-0.9: Kontext-Text (theoretischer Text über Essay-Gattung)
0.4-0.7: Tangential relevant (erwähnt Essay, aber wenig Substanz)
0.0-0.4: Irrelevant (anderes Thema, Meta-Chat, etc.)

FRAGE DICH: "Könnte die Synthese aus diesem Chunk eine Essay-Definition ableiten?" Falls JA → mindestens 0.7!

Bewerte die Relevanz (0.0-1.0): """

        elif query_type == "analytical":
            prompt = f"""
FRAGE: "{query}"

TEXT-CHUNK (von {speaker}, Chat: "{chat_title}"): {chunk_short}

BEWERTUNGS-KONTEXT: Diese Frage verlangt Vergleich/Analyse (z.B. "Vergleiche X und Y").

WICHTIG - ANALYTISCHE CHUNKS RICHTIG BEWERTEN:
- Direkte Analyse-Aussagen = hochrelevant (0.8-1.0)
- Implizite Kontext-Chunks = relevant (0.6-0.8)
- Meta-Reflexionen = relevant (0.5-0.7)

BEWERTUNGS-SKALA:
0.8-1.0: Direkte Analyse mit Vergleich/Entwicklung
0.6-0.8: Einseitige Analyse (nur X oder nur Y)
0.4-0.6: Kontext ohne explizite Analyse
0.0-0.4: Irrelevant

Bewerte die Relevanz (0.0-1.0): """

        else:  # factual
            prompt = f"""
FRAGE: "{query}"

TEXT-CHUNK (von {speaker}, Chat: "{chat_title}"): {chunk_short}

BEWERTUNGS-KONTEXT: Diese Frage verlangt faktische Information (z.B. "Was ist X?", "Wie funktioniert Y?").

BEWERTUNGS-SKALA:
0.8-1.0: Direkte, detaillierte Antwort
0.6-0.8: Teilweise Antwort oder relevanter Kontext
0.4-0.6: Tangential relevant (erwähnt Thema am Rande)
0.0-0.4: Irrelevant

Bewerte die Relevanz (0.0-1.0): """

        try:
            # Temperatursteuerung: analytisch/forensisch → 0.1 (deterministisch),
            # literarisch/faktisch → 0.3 (etwas mehr Nuance)
            reranker_temp = 0.1 if (intent and intent.lower() in ["analytical_forensic", "analytical"]) else 0.3

            score_text = llm_call(
                prompt,
                task="reranker",
                system_instruction=RERANKER_INSTRUCTION,
                temperature=reranker_temp,
            )

            score_text = score_text.strip()

            # Robust gegen Whitespace-Fehler wie "1.  0" → "1.0"
            score_clean = re.sub(r'(\d+)[.,]\s+(\d+)', r'\1.\2', score_text)

            match = re.search(r'(\d+[.,]\d+)', score_clean)
            if match:
                score = float(match.group(1).replace(',', '.'))
                return max(0.0, min(1.0, score))
            else:
                logger.warning(f"⚠️ Unparseable Score: '{score_text}' → Fallback 0.5")
                return 0.5

        except Exception as e:
            logger.error(f"❌ Reranker-Fehler: {e}")
            return 0.5

    def rerank(self, query: str, candidates: List[Dict], max_results: int = 60, intent: str = None) -> Tuple[List[Dict], Dict]:
        """
        Filtert Kandidaten durch LLM-Judge (v49.2: Essay-Aware).

        Args:
            query: User-Frage
            candidates: Liste von Chunks aus Vector Store
            max_results: Max. Anzahl Ergebnisse (nach Filterung)
            intent: Optional, Router-Intent für Query-Type-Awareness

        Returns:
            Tuple[filtered_results, stats]
        """
        if not candidates:
            return [], {"total": 0, "passed": 0, "rejected": 0, "query_type": "unknown"}

        # Query-Typ erkennen (v50.9 FIX: Router-Intent hat Vorrang!)
        if intent:
            query_type = intent.lower()
            if query_type == "analytical_forensic":
                query_type = "analytical"
            if query_type not in ["literary", "analytical", "factual"]:
                query_type = "factual"
        else:
            query_type = self._detect_query_type(query)

        logger.info(f"🔍 Reranker: Prüfe {len(candidates)} Kandidaten (Query-Typ: {query_type.upper()})...")

        filtered = []
        rejected_count = 0

        # --- PARETO-TURBO: 10 parallele Threads ---
        import concurrent.futures

        def process_candidate(candidate):
            """Hilfsfunktion für einen einzelnen Thread."""
            chunk_text = candidate.get('content', '')

            # VIP-SCHUTZ (Rescue Mission)
            if candidate.get('_is_rescued', False):
                candidate['hermeneutic_score'] = 1.0
                return candidate, 1.0

            # LLM-Judge
            score = self.judge_relevance(query, chunk_text, candidate, intent=intent)
            candidate['hermeneutic_score'] = score
            return candidate, score

        # Wir feuern max. 5 Anfragen gleichzeitig ab (Rate-Limit Schutz)
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            future_to_candidate = {executor.submit(process_candidate, c): c for c in candidates}

            processed_count = 0
            for future in concurrent.futures.as_completed(future_to_candidate, timeout=300):
                processed_count += 1
                try:
                    cand, score = future.result(timeout=45)
                    if score >= self.threshold:
                        filtered.append(cand)
                    else:
                        rejected_count += 1

                    # Progress-Logging alle 10 Chunks
                    if processed_count % 10 == 0 or processed_count == len(candidates):
                        logger.info(f"   ... {processed_count}/{len(candidates)} geprüft, {len(filtered)} bestanden")
                except Exception as e:
                    logger.error(f"❌ Fehler im Reranker-Thread: {e}")
                    rejected_count += 1
        # ------------------------------------------

        # Sortiere nach hermeneutischem Score
        filtered.sort(key=lambda x: x['hermeneutic_score'], reverse=True)
        final_results = filtered[:max_results]

        stats = {
            "total": len(candidates),
            "passed": len(filtered),
            "rejected": rejected_count,
            "avg_score": sum(r['hermeneutic_score'] for r in filtered) / len(filtered) if filtered else 0,
            "query_type": query_type
        }

        logger.info(f"✅ Reranker: {stats['passed']}/{stats['total']} bestanden (Ø {stats['avg_score']:.2f}, Typ: {query_type})")

        return final_results, stats