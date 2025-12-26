import logging
import json
import re
import os
import time
import asyncio
from functools import partial
import google.generativeai as genai
from typing import List, Dict, Any, Tuple
from modules.config import (
    MODEL_SYNTHESIS,
    MODEL_QUERY_EXPANSION,
    MODEL_ENFORCER
)

# Eigene Module
from modules.vector_store import FirestoreVectorStore
from modules.evidence_synthesis import EvidenceFirstSynthesizer
from modules.llm_instructions import ENFORCER_INSTRUCTION
from .query_classifier import QueryClassifier
from .types import QueryType
from .llm_instructions import EXEGESIS_SYNTHESIS_PROMPT, SYNTHESIS_INSTRUCTION
from modules.hermeneutic_reranker import HermeneuticReranker

logger = logging.getLogger(__name__)

class CitationRAG:
    def __init__(self, vector_store: FirestoreVectorStore = None, model_name: str = MODEL_SYNTHESIS):
        # Falls kein Store übergeben wurde, initialisieren wir ihn (wichtig für Standalone-Tests)
        if vector_store is None:
            from google.cloud import firestore
            db = firestore.Client()
            vector_store = FirestoreVectorStore(db)

        self.vector_store = vector_store
        self.model_name = model_name
        self.classifier = QueryClassifier()
        self.synthesizer = EvidenceFirstSynthesizer(model_name)
        api_key = os.environ.get("GEMINI_API_KEY")
        if api_key:
            genai.configure(api_key=api_key)

    # --- NEU (v49.1): Polyglot Query Expansion ---
    def expand_query_multilingual(self, query: str) -> str:
        """
        Erweitert die Suchanfrage um mehrsprachige Keywords (DE, EN, RU, FR),
        um die BM25-Suche in polyglotten Datenbanken zu verbessern.
        """
        try:
            # Wir nutzen das schnelle Flash-Modell für minimale Latenz (ca. 0.5s)
            model = genai.GenerativeModel(MODEL_QUERY_EXPANSION)

            prompt = f"""
            Du bist ein Such-Optimierer für eine Vektor-Datenbank.

            USER QUERY: "{query}"

            AUFGABE:
            Generiere 3-5 relevante Suchbegriffe oder Synonyme in ENGLISCH, DEUTSCH und RUSSISCH, die den Kern der Frage treffen.
            Konzentriere dich auf Fachbegriffe (z.B. "Zirkelschluss" -> "circular reasoning", "tautology").

            OUTPUT FORMAT:
            Nur die Begriffe, getrennt durch Leerzeichen. Keine Erklärungen.
            """

            # Kurzer Timeout, damit die Suche nicht hängt
            response = model.generate_content(prompt, request_options={'timeout': 5})
            expanded_terms = response.text.strip()

            # Logging für Debugging
            logger.info(f"🌍 Polyglot Expansion: '{query}' -> +[{expanded_terms}]")

            # Wir hängen die neuen Begriffe an die Original-Query an
            return f"{query} {expanded_terms}"

        except Exception as e:
            logger.warning(f"Query Expansion failed (Fallback to original): {e}")
            return query 

    # --- NEU (v49): RRF Retrieval Wrapper ---
    def retrieve_with_rrf(self, query: str, limit: int = 15, chat_id: Any = None) -> List[Dict]:
        """
        Nutzt die neue Hybrid-Suche (RRF) aus dem VectorStore.
        Dient als Einstiegspunkt für die Pipeline.
        """
        # 1. Query Expansion (NEU v49.1)
        # Wir erweitern die Query für das Retrieval, damit BM25 auch englische/russische Texte findet
        expanded_query = self.expand_query_multilingual(query)

        # FIX: Robustes ID-Handling (String vs. List für Investigativ-Modus)
        allowed_ids = None
        if chat_id:
            if isinstance(chat_id, list):
                allowed_ids = chat_id  # Es ist schon eine Liste (z.B. ['id1', 'id2'])
            else:
                allowed_ids = [chat_id] # Es ist ein einzelner String

        # Ruft die neue hybrid_search Methode in vector_store.py auf
        # WICHTIG: Wir nutzen hier die expanded_query!
        results, _ = self.vector_store.hybrid_search(
            query=expanded_query,
            limit=limit,
            allowed_chat_ids=allowed_ids
        )
        return results
    # ----------------------------------------

    def extract_keywords(self, query: str) -> List[str]:
        clean_query = query.replace("-", " ").replace("_", " ")
        ignore = {'wie', 'was', 'wo', 'und', 'oder', 'der', 'die', 'das', 'bei', 'mit', 'von', 'über', 'ist', 'sind', 'jeweils', 'erwähnung', 'auf', 'den', 'dem', 'sagen', 'meinen'}
        keywords = []
        for w in clean_query.split():
            w_clean = w.lower().strip('?".,!:')
            if w_clean not in ignore and len(w_clean) > 2:
                keywords.append(w_clean)
        return keywords

    def clean_citation_format(self, text: str) -> str:
        text = re.sub(r'\[source_id:\s*(\d+)\]', r'[\1]', text)
        text = re.sub(r'\[Quelle:\s*(\d+)\]', r'[\1]', text)
        return text

    def generate_answer(self, query: str, results: List[Dict]) -> Tuple[str, List[Dict], str]:
        """
        Generiert Antwort basierend auf Ergebnissen (Fusion v49: RRF -> Reranking -> Chronologische Speaker-Blöcke).
        """
        if not results:
            return "Ich habe keine relevanten Informationen in den Dokumenten gefunden.", [], "unknown"

        # --- SCHRITT A: Basis-Scoring & Sortierung ---
        # UPDATE v49: Wenn RRF aktiv war (erkennbar am Flag), vertrauen wir dem RRF-Ranking
        is_rrf_result = any(res.get('_rrf_active') for res in results)

        if is_rrf_result:
            # RRF hat schon sortiert. Wir übernehmen das.
            for res in results:
                if '_final_score' not in res:
                    res['_final_score'] = res.get('score', 0.0) # RRF Score nutzen
            logger.info("⚡ RRF-Ranking erkannt. Überspringe manuelles Boosting.")
        else:
            # Legacy Fallback
            for res in results:
                base_score = res.get('score', 0.0)
                kw_boost = res.get('_keyword_boost', 0.0)
                res['_final_score'] = base_score + kw_boost
            results.sort(key=lambda x: x.get('_final_score', 0), reverse=True)

        # --- SCHRITT B: Hermeneutic Reranking (Erzeugt top_results) ---
        top_candidates = results[:100]
        reranker = HermeneuticReranker(threshold=0.7)
        top_results, rerank_stats = reranker.rerank(query, top_candidates, max_results=60)

        # Fallback bei zu wenig Treffern
        if len(top_results) < 20:
            logger.warning("⚠️ Zu wenig Treffer nach Reranking. Senke Schwellwert auf 0.5...")
            reranker_relaxed = HermeneuticReranker(threshold=0.5)
            top_results, rerank_stats = reranker_relaxed.rerank(query, top_candidates, max_results=60)

        # --- SCHRITT C: Klassifizierung ---
        mode = self.classifier.classify(query, top_results)
        print(f"🧠 RAG Modus: {mode.value.upper()}")

        if mode == QueryType.EXEGESIS:
            system_instruction = EXEGESIS_SYNTHESIS_PROMPT
        else:
            system_instruction = SYNTHESIS_INSTRUCTION 

        # --- SCHRITT D: Kontext aufbereiten (Gruppiert nach Speaker) ---
        from collections import defaultdict

        sources_by_speaker = defaultdict(list)
        for i, res in enumerate(top_results):
            meta = res.get('metadata', {})
            speaker = meta.get('model_name') or meta.get('speaker') or 'KI'
            res['source_id'] = i + 1
            sources_by_speaker[speaker].append(res)

        for speaker, sources in sources_by_speaker.items():
            sources.sort(key=lambda x: x.get('metadata', {}).get('date') or '9999-99-99')

        context_text = ""
        for speaker, sources in sorted(sources_by_speaker.items()):
            context_text += f"\n### {speaker.upper()}\n"
            for res in sources:
                meta = res.get('metadata', {})
                sid = res['source_id']
                version = meta.get('version')
                date = meta.get('date')

                source_label = f"{speaker}"
                if version:
                    source_label += f" v{version}"
                if date:
                    source_label += f" ({date})"

                context_text += f"QUELLE [{sid}] von {source_label}:\n{res.get('content')}\n\n"

        # --- SCHRITT E: Der User-Prompt ---
        prompt = f"""
FRAGE: "{query}"

QUELLEN (Gruppiert nach Modell, chronologisch sortiert):
{context_text}

AUFGABE:
Beantworte die Frage mit hermeneutischer Tiefe und achte besonders auf ZEITLICHE ENTWICKLUNG und MODELL-VERGLEICHE.

ANALYSE-DIMENSIONEN:
1. **Pro-Modell-Chronologie** (PRIORITÄT):
   - Analysiere JEDEN Modell-Block separat.
   - Beschreibe die Entwicklungslinie.
2. **Cross-Modell-Vergleich**:
   - Wo sind sie sich einig? Wo divergieren sie?
3. **Hermeneutische Tiefe**:
   - Explizit vs. Implizit.
   - Paradoxien.
4. **Synthetisches Fazit**:
   - Muster, Konvergenz oder Divergenz?

FORMALIEN:
- Zitiere präzise mit Nummer: [1], [2].
- Nutze Markdown.
- Schreibe "DeepSeek v3.2 (Dez 2025) [1] sagt..."

Jetzt die Analyse:
"""

        # --- SCHRITT F: Generierung ---
        max_retries = 3
        for attempt in range(max_retries):
            try:
                model = genai.GenerativeModel(
                    model_name=MODEL_SYNTHESIS,
                    system_instruction=system_instruction 
                )
                response = model.generate_content(prompt)
                final_text = self.clean_citation_format(response.text)
                return final_text, top_results, mode.value

            except Exception as e:
                error_msg = str(e)
                if "429" in error_msg or "Resource exhausted" in error_msg:
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 10
                        logger.warning(f"⏳ Rate Limit erreicht. Warte {wait_time}s...")
                        time.sleep(wait_time)
                        continue
                    else:
                        return f"❌ API-Limit erreicht. Bitte warte 1 Minute.\nDetails: {e}", top_results, mode.value
                else:
                    return f"Fehler bei der Generierung: {e}", top_results, mode.value

        return "❌ Maximale Versuche erreicht. API nicht verfügbar.", top_results, mode.value

    def split_thought_and_speech(self, text: str) -> Tuple[str, str]:
        if not text:
            return "", ""
        pattern = r'(> \*\*Thinking:\*\*.*?)(\n\n|$)(.*)'
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(1).strip(), match.group(3).strip()
        return "", text

    def validate_citations(self, answer: str, num_sources: int) -> List[str]:
        warnings = []
        matches = re.findall(r'\[(\d+)\]', answer)
        if not matches:
            warnings.append("⚠️ Warnung: Die Antwort enthält keine Zitationen (z.B. [1]).")
            return warnings
        for m in matches:
            idx = int(m)
            if idx < 1 or idx > num_sources:
                warnings.append(f"⚠️ Ungültige Zitation: [{idx}] (Nur 1-{num_sources} verfügbar)")
        return warnings

    def verify_fact_match(self, claim: str, source_text: str, source_meta: Dict) -> Tuple[bool, str]:
        """
        Validiert eine Behauptung mit dem Hermeneutic Enforcer (v48).
        """
        try:
            from modules.hermeneutic_enforcer import HermeneuticEnforcer
            enforcer = HermeneuticEnforcer()
            sources = [{"content": source_text, "metadata": source_meta}]

            is_valid, classification, reason = enforcer.validate_claim(
                claim=claim, 
                sources=sources
            )

            status_icon = "✅" if is_valid else "❌"
            print(f"   {status_icon} [{classification.upper()}] {reason}")

            return is_valid, f"[{classification.upper()}] {reason}"

        except Exception as e:
            print(f"⚠️ Enforcer Error: {e}")
            return True, f"ENFORCER ERROR (Skipped): {e}"

    def test_empty_sources_hallucination(self) -> Tuple[bool, str]:
        answer, _ = self.generate_answer("Test", [])
        if "keine" in answer.lower():
            return True, "Bestanden"
        return False, "Halluzination"

    # =========================================================================
    # NEU in v49.1: Asynchrone Parallel-Verarbeitung für den Enforcer
    # =========================================================================

    async def verify_facts_parallel(self, sentences: List[str], results: List[Dict], progress_callback=None) -> List[Dict]:
        """
        Führt den Faktencheck parallel durch (Asyncio + ThreadPool).
        Reduziert die Wartezeit von Minuten auf Sekunden.
        """
        # Semaphore: Begrenzt gleichzeitige API-Calls auf 5 (Konservativ für Rate Limits)
        # Wir wollen nicht ins 429 Limit laufen.
        sem = asyncio.Semaphore(5) 

        verified_logs = []
        total = len(sentences)
        completed = 0

        async def _bounded_check(sent):
            nonlocal completed
            async with sem:
                # Wir wrappen den synchronen Call in einen Thread
                loop = asyncio.get_running_loop()

                # Extrahiere Zitat-IDs [1], [2]...
                matches = re.findall(r'\[(\d+)\]', sent)
                if not matches:
                    return None # Satz ohne Zitat überspringen

                # Wir prüfen nur das erste Zitat pro Satz für Speed (oder alle? Hier: Erstes)
                # Grigori-Modus: Wir prüfen ALLE im Satz genannten Quellen.
                results_for_sentence = []

                for m in matches:
                    idx = int(m) - 1
                    if 0 <= idx < len(results):
                        source_content = results[idx].get('content', '')
                        source_meta = results[idx].get('metadata', {})

                        # Der eigentliche synchrone Call wird in einen Thread ausgelagert
                        # damit er den Event Loop nicht blockiert
                        is_valid, reason = await loop.run_in_executor(
                            None, 
                            partial(self.verify_fact_match, sent, source_content, source_meta)
                        )

                        results_for_sentence.append({
                            'sentence': sent,
                            'source_id': m,
                            'valid': is_valid,
                            'reason': reason
                        })

                completed += 1
                if progress_callback:
                    progress_callback(completed / total)

                return results_for_sentence

        # Erstelle Tasks für alle Sätze
        tasks = [_bounded_check(sent) for sent in sentences]

        # Führe alle parallel aus
        all_results = await asyncio.gather(*tasks)

        # Flatten list of lists
        flat_log = []
        for res_list in all_results:
            if res_list:
                flat_log.extend(res_list)

        return flat_log