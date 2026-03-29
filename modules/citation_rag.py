# modules/citation_rag.py - v50.9: INDENTATION FIX & SDK UPDATE
import logging 
import json 
import re 
import os 
import time 
import asyncio 
from functools import partial 
from collections import defaultdict 
from typing import List, Dict, Any, Tuple, Optional 
from types import SimpleNamespace 
from datetime import datetime

from modules.config import MODEL_SYNTHESIS
from modules.llm_wrapper import llm_call

from modules.vector_store import FirestoreVectorStore 
from modules.evidence_synthesis import EvidenceFirstSynthesizer 
from modules.llm_instructions import ENFORCER_INSTRUCTION 
from modules.llm_instructions import EXEGESIS_SYNTHESIS_PROMPT, SYNTHESIS_INSTRUCTION 
from modules.hermeneutic_reranker import HermeneuticReranker 
from modules.hermeneutic_router import HermeneuticRouter

logger = logging.getLogger(__name__)

class CitationRAG: 
    def __init__(self, vector_store: FirestoreVectorStore = None, model_name: str = MODEL_SYNTHESIS): 
        if vector_store is None:
            # v50.9-local: SQLite Drop-in via database-Modul
            from modules.database import get_firestore_client
            db = get_firestore_client()
            vector_store = FirestoreVectorStore(db)

        self.vector_store = vector_store
        self.model_name = model_name
        self.router = HermeneuticRouter()
        self.synthesizer = EvidenceFirstSynthesizer(model_name)

        # UI-Zugriff für Imbalance-Daten
        self.last_imbalance_info = None

        self.current_context = {
            "intent": "FACTUAL",
            "threshold": 0.65
        }

        # --- FIX: Cache initialisieren ---
        self._original_results_cache = []

    def expand_query_multilingual(self, query: str) -> str:
        """v50.1: Query Translation für multilingualen Retrieval.
        v50.9-local: genai.Client ersetzt durch llm_call.
        """
        try:
            prompt = f"""Du bist ein Such-Optimierer für multilingualen Retrieval. USER QUERY (Original): "{query}" AUFGABE: Übersetze diese Query in folgende Sprachen:

Englisch
Russisch (Kyrillisch)
Französisch OUTPUT-FORMAT: Original + 3 Übersetzungen, durch Leerzeichen getrennt. BEISPIEL: Input: "Wie definiert Adorno den Essay?" Output: "Wie definiert Adorno den Essay? How does Adorno define the essay? Как Адорно определяет эссе? Comment Adorno définit-il l'essai?" WICHTIG:
Nur die Übersetzungen, kein Präambel!

Trenne mit Leerzeichen, nicht mit Zeilenumbrüchen!

Behalte Namen unverändert! """

            multilingual_query = llm_call(prompt, task="query_expansion")

            if not multilingual_query:
                logger.warning("⚠️ Query-Expansion leer. Fallback auf Original.")
                return query

            multilingual_query = multilingual_query.strip()
            multilingual_query = re.sub(r'\n+', ' ', multilingual_query)
            logger.info(f"🌐 Query Translation: {query[:50]}... → {len(multilingual_query.split())} words")
            return multilingual_query

        except Exception as e:
            logger.warning(f"⚠️ Query Translation fehlgeschlagen: {e}. Fallback auf Original.")
            return query

    def retrieve_with_rrf(self, query: str, limit: int = 15, chat_id: Any = None, use_router: bool = True) -> List[Dict]:
        """ v50.10: Retrieval mit Router, RRF und 'Rescue Mission' für garantierte Abdeckung. """
        # 1. Router & Parameter-Setup
        if use_router:
            try:
                route = self.router.route_query(query)
                dynamic_limit = route["limit"]
                intent = route["intent"]
                threshold = route["threshold"]
                logger.info(f"🚀 Retrieval Mode: AUTO ({intent}) | Limit: {dynamic_limit} | Threshold: {threshold}")
            except Exception as e:
                logger.error(f"❌ Router Error: {e}. Fallback auf Standard-Parameter.")
                dynamic_limit = limit
                intent = "FALLBACK"
                threshold = 0.65
        else:
            dynamic_limit = limit
            intent = "MANUAL"
            threshold = 0.65

        logger.info(f"🔧 Retrieval Mode: MANUAL | Limit: {dynamic_limit}")

        # Selection Boost: Wenn Dokumente ausgewählt sind, erhöhen wir das Limit
        if chat_id:
            old_limit = dynamic_limit
            dynamic_limit = max(dynamic_limit, 70)
            if dynamic_limit > old_limit:
                logger.info(f"📈 Selection Boost: Limit erhöht von {old_limit} auf {dynamic_limit}")

        self.current_context = {"intent": intent, "threshold": threshold, "query": query}

        # 2. Haupt-Suche
        expanded_query = self.expand_query_multilingual(query)
        allowed_ids = chat_id if isinstance(chat_id, list) else [chat_id] if chat_id else None

        results, _ = self.vector_store.hybrid_search(
            query=expanded_query,
            limit=dynamic_limit,
            allowed_chat_ids=allowed_ids
        )

        # --- 🔴 NEU: RESCUE MISSION (Garantierte Abdeckung) ---
        if allowed_ids and len(allowed_ids) > 1:
            # Welche Dokumente haben wir gefunden?
            found_chat_ids = set(r.get('chat_id') for r in results if r.get('chat_id'))

            # Welche fehlen?
            missing_ids = [cid for cid in allowed_ids if cid not in found_chat_ids]

            if missing_ids:
                logger.warning(f"⚠️ {len(missing_ids)} ausgewählte Dokumente fehlen im Top-{dynamic_limit}. Starte Rettungsmission...")

                for missing_cid in missing_ids:
                    # Gezielte Nachsuche NUR in diesem Dokument
                    rescue_results, _ = self.vector_store.hybrid_search(
                        query=expanded_query,
                        limit=3,  # Wir erzwingen die Top 3 dieses Dokuments
                        allowed_chat_ids=[missing_cid]
                    )

                    if rescue_results:
                        # Markiere sie als "gerettet", damit wir das im Log sehen
                        for res in rescue_results:
                            res['_is_rescued'] = True
                            # Gib ihnen einen künstlichen Boost, damit sie nicht sofort wieder rausfliegen
                            res['_keyword_boost'] = res.get('_keyword_boost', 0) + 0.2

                        results.extend(rescue_results)
                        logger.info(f"  🚑 Dokument {missing_cid[-6:]}... mit {len(rescue_results)} Chunks gerettet.")
                    else:
                        logger.warning(f"  ❌ Dokument {missing_cid[-6:]}... enthält KEINE Treffer (selbst bei gezielter Suche).")

        # --- FIX: Ergebnisse cachen für spätere Rettungsversuche ---
        self._original_results_cache = results
        # -----------------------------------------------------------
        return results

    def check_imbalance_only(self, query: str, results: List[Dict], chat_id: Any = None, use_router: bool = True) -> SimpleNamespace:
        """ Prüft NUR die Chunk-Verteilung, OHNE zu synthetisieren.

        Nutzt die gleiche Logik wie generate_answer() bis zum Punkt
        der Essenz-Extraktion, stoppt aber VOR dem LLM-Call.

        Returns:
            SimpleNamespace mit:
            - severity: "none" | "info" | "critical"
            - ratio: float (max/min Verhältnis)
            - doc_distribution: Dict[str, int]
            - max_chunks: int
            - min_chunks: int
        """
        if not results:
            return SimpleNamespace(
                severity="none",
                ratio=1.0,
                doc_distribution={},
                max_chunks=0,
                min_chunks=0
            )

        # Router-Logik (falls aktiviert)
        if use_router:
            try:
                route = self.router.route_query(query)
                rerank_threshold = route["threshold"]
                intent = route["intent"]
                self.current_context = {"intent": intent, "threshold": rerank_threshold, "query": query}
            except Exception as e:
                logger.error(f"❌ Router Error: {e}. Fallback auf Standard-Parameter.")
                rerank_threshold = 0.65
                intent = "FALLBACK"
        else:
            rerank_threshold = 0.65
            intent = "MANUAL"

        # Scoring
        is_rrf_result = any(res.get('_rrf_active') for res in results)
        if is_rrf_result:
            for res in results:
                if '_final_score' not in res:
                    res['_final_score'] = res.get('score', 0.0)
        else:
            for res in results:
                res['_final_score'] = res.get('score', 0.0) + res.get('_keyword_boost', 0.0)
            results.sort(key=lambda x: x.get('_final_score', 0), reverse=True)

        # Reranking
        top_candidates = results[:100]
        reranker = HermeneuticReranker(threshold=rerank_threshold)
        top_results, _ = reranker.rerank(query, top_candidates, max_results=70, intent=intent)

        # Fallback bei zu wenig Treffern
        if len(top_results) < 5:
            reranker_relaxed = HermeneuticReranker(threshold=0.35)
            top_results, _ = reranker_relaxed.rerank(query, top_candidates, max_results=70, intent=intent)

        # Dokumenten-Verteilung VOR Essenz-Extraktion
        surviving_docs = defaultdict(int)
        for res in top_results:
            chat_id_single = res.get('chat_id', 'unknown')
            chat_title = res.get('metadata', {}).get('chat_title') or self._get_chat_title(chat_id_single)
            surviving_docs[chat_title] += 1

        # Imbalance-Berechnung
        if not surviving_docs:
            return SimpleNamespace(
                severity="none",
                ratio=1.0,
                doc_distribution={},
                max_chunks=0,
                min_chunks=0
            )

        counts = list(surviving_docs.values())
        max_c = max(counts)
        min_c = min(counts)
        ratio = max_c / min_c if min_c > 0 else 0

        severity = "none"
        if len(surviving_docs) > 1:
            if ratio >= 10:
                severity = "critical"
            elif ratio >= 5:
                severity = "info"

        imbalance_info = SimpleNamespace(
            severity=severity,
            ratio=ratio,
            doc_distribution=dict(surviving_docs),
            max_chunks=max_c,
            min_chunks=min_c
        )

        # Speichere für späteren Zugriff
        self.last_imbalance_info = imbalance_info

        logger.info(f"📊 Imbalance-Check: {severity.upper()} (Ratio: {ratio:.1f}:1)")

        return imbalance_info

    def extract_keywords(self, query: str) -> List[str]:
        """Legacy-Funktion."""
        clean_query = query.replace("-", " ").replace("_", " ")
        ignore = { 'wie', 'was', 'wo', 'und', 'oder', 'der', 'die', 'das', 'bei', 'mit', 'von', 'über', 'ist', 'sind', 'jeweils', 'erwähnung', 'auf', 'den', 'dem', 'sagen', 'meinen' }

        keywords = []
        for w in clean_query.split():
            w_clean = w.lower().strip('?".,!:')
            if w_clean not in ignore and len(w_clean) > 2:
                keywords.append(w_clean)

        return keywords

    def clean_citation_format(self, text: str) -> str:
        """Bereinigt Zitationsformate."""
        text = re.sub(r'\[source_id:\s*(\d+)\]', r'[\1]', text)
        text = re.sub(r'\[Quelle:\s*(\d+)\]', r'[\1]', text)
        return text

    def _get_chat_title(self, chat_id: str) -> str:
        """v50.2: Hole echten Chat-Titel (Fallback-sicher).
        v50.9-local: SQLite-Direktabfrage statt Firestore-Collection-API.
        """
        try:
            from modules.database import get_db_connection
            db = get_db_connection()
            if db is None:
                return f'Doc {chat_id[-8:]}'
            row = db.execute(
                "SELECT title FROM chats WHERE id = ?", (chat_id,)
            ).fetchone()
            if row:
                return row['title'] or f'Doc {chat_id[-8:]}'
            return f'Doc {chat_id[-8:]}'
        except Exception:
            return f'Doc {chat_id[-8:]}'

    def extract_date_from_metadata(self, res: Dict) -> datetime:
        """ Extrahiert Datum aus Chunk-Metadaten für chronologische Sortierung.

        Unterstützt Formate:
        - "04.12.2025" (Tag.Monat.Jahr)
        - "Mai 2025" (Monat Jahr)
        - "13.10.2025" (Tag.Monat.Jahr)

        Returns:
            datetime-Objekt oder datetime.min falls kein Datum
        """
        meta = res.get('metadata', {})
        date_str = meta.get('real_date_str', '')

        if not date_str or date_str == 'o.D.':
            return datetime.min

        try:
            # Format: "04.12.2025"
            if '.' in date_str:
                return datetime.strptime(date_str, "%d.%m.%Y")

            # Format: "Mai 2025"
            elif ' ' in date_str:
                month_map = {
                    'Januar': 1, 'Februar': 2, 'März': 3, 'April': 4,
                    'Mai': 5, 'Juni': 6, 'Juli': 7, 'August': 8,
                    'September': 9, 'Oktober': 10, 'November': 11, 'Dezember': 12
                }
                parts = date_str.split()
                if len(parts) == 2 and parts[0] in month_map:
                    month = month_map[parts[0]]
                    year = int(parts[1])
                    return datetime(year, month, 1)

        except Exception as e:
            logger.warning(f"⚠️ Konnte Datum nicht parsen: '{date_str}' → {e}")

        return datetime.min

    def generate_answer(self, query: str, results: List[Dict], strict_parity: bool = False, dry_run: bool = False) -> Tuple[str, List[Dict], str]:
        """ v50.9: ESSENCE PARITY - Intelligente Essenz-Extraktion.

        Max 12 Chunks pro Dokument (Code-Limit) + Erzwungene Zitat-Quota (Prompt).
        """
        if not results:
            return "Ich habe keine relevanten Informationen in den Dokumenten gefunden.", [], "unknown"

        # v50.9 FIX: UI-Bypass abfangen (Analyse-Fenster überspringt oft den Router)
        # Wenn die aktuelle Query nicht im Kontext steht, lief der Router noch nicht!
        if self.current_context.get("query") != query:
            logger.info("🔄 Router-Bypass erkannt (Analyse-Fenster). Hole Intent-Analyse nach...")
            try:
                route = self.router.route_query(query)
                self.current_context = {
                    "intent": route["intent"],
                    "threshold": route["threshold"],
                    "query": query
                }
            except Exception as e:
                logger.error(f"❌ Router Fallback Error: {e}")
                self.current_context = {"intent": "FACTUAL", "threshold": 0.65, "query": query}

        intent = self.current_context.get("intent", "FACTUAL")
        semantic_intent = intent  # Wird durch Essence Parity NICHT überschrieben
        rerank_threshold = self.current_context.get("threshold", 0.65)

        # Extrahiere chat_id aus results
        chat_id = None
        if results:
            first_result_chat_ids = [r.get('chat_id') for r in results if r.get('chat_id')]
            if first_result_chat_ids:
                unique_chat_ids = list(set(first_result_chat_ids))
                if len(unique_chat_ids) <= 10:
                    chat_id = unique_chat_ids

        # --- Scoring ---
        is_rrf_result = any(res.get('_rrf_active') for res in results)

        if is_rrf_result:
            logger.info("⚡ RRF-Ranking erkannt.")
            for res in results:
                if '_final_score' not in res:
                    res['_final_score'] = res.get('score', 0.0)
        else:
            for res in results:
                res['_final_score'] = res.get('score', 0.0) + res.get('_keyword_boost', 0.0)
            results.sort(key=lambda x: x.get('_final_score', 0), reverse=True)

        # --- Reranking ---
        top_candidates = results[:100]

        logger.info(f"⚖️ Reranking mit Threshold: {rerank_threshold} (Intent: {intent})")

        reranker = HermeneuticReranker(threshold=rerank_threshold)
        top_results, rerank_stats = reranker.rerank(query, top_candidates, max_results=70, intent=intent)

        if len(top_results) < 5:
            logger.warning(f"⚠️ Zu wenig Treffer nach Reranking ({len(top_results)}). Senke Threshold auf 0.35...")
            reranker_relaxed = HermeneuticReranker(threshold=0.35)
            top_results, _ = reranker_relaxed.rerank(query, top_candidates, max_results=70, intent=intent)

        # --- Diagnostik VOR Essenz-Extraktion ---
        surviving_docs = defaultdict(int)
        for res in top_results:
            chat_id_single = res.get('chat_id', 'unknown')
            chat_title = res.get('metadata', {}).get('chat_title') or self._get_chat_title(chat_id_single)
            surviving_docs[chat_title] += 1

        logger.info(f"📊 Dokumente nach Reranking (vor Essenz-Extraktion):")
        for doc_title, count in sorted(surviving_docs.items(), key=lambda x: x[1], reverse=True):
            logger.info(f"  📄 {doc_title}: {count} Chunks")

        # --- v50.5 FIX: Imbalance-Daten für UI speichern ---
        if surviving_docs:
            counts = list(surviving_docs.values())
            max_c = max(counts)
            min_c = min(counts)
            ratio = max_c / min_c if min_c > 0 else 0

            severity = "none"
            if len(surviving_docs) > 1:
                if ratio >= 10: severity = "critical"
                elif ratio >= 5: severity = "info"

            self.last_imbalance_info = SimpleNamespace(
                severity=severity,
                ratio=ratio,
                doc_distribution=dict(surviving_docs),
                max_chunks=max_c,
                min_chunks=min_c
            )
        else:
            self.last_imbalance_info = SimpleNamespace(
                severity="none", ratio=1.0, doc_distribution={}, max_chunks=0, min_chunks=0
            )
        # ---------------------------------------------------

        # --- v50.5: ESSENCE PARITY (Intelligente Essenz-Extraktion!) ---
        doc_metadata = []  # Muss vor allen bedingten Blöcken stehen
        if chat_id and isinstance(chat_id, list) and len(chat_id) <= 10:
            logger.info(f"⚖️ ESSENCE PARITY aktiviert: {len(chat_id)} Dokumente")

            # Gruppiere Chunks nach Chat-ID
            docs_map = defaultdict(list)
            for res in top_results:
                cid = res.get('chat_id')
                docs_map[cid].append(res)

            # ======================================================================
            # v50.9: LOGARITHMIC ESSENCE EXTRACTION (Bio-inspired Scaling)
            # ======================================================================
            # Philosophie: Logarithmische Skalierung wie in natürlichen Systemen
            # (Psychophysik, Informationstheorie, ökologische Symbiose)

            import math

            total_budget = 60

            # Berechne logarithmisches Minimum basierend auf PRE-RERANKING Größe
            # (verhindert, dass aggressive Reranking die Garantien zerstört)
            doc_minimums = {}

            # Schritt 1: Ermittle ORIGINAL-Chunk-Anzahl (vor Reranking)
            original_counts = {}
            for cid in chat_id:
                # Hole alle Chunks aus dem PRE-RERANKING Pool (das sind die 'results')
                pre_rerank = [r for r in results if r.get('chat_id') == cid]
                original_counts[cid] = len(pre_rerank)

            # Schritt 2: Berechne Logarithmus auf dieser Basis
            for cid in chat_id:
                original = original_counts.get(cid, 0)
                if original > 0:
                    log_min = math.ceil(math.log2(original))
                    doc_minimums[cid] = log_min
                else:
                    doc_minimums[cid] = 0            
            total_guaranteed = sum(doc_minimums.values())
            remaining_budget = max(0, total_budget - total_guaranteed)

            logger.info(
                f"⚖️ Logarithmische Essenz-Extraktion (Bio-inspired):\n"
                f"   - Total-Budget: {total_budget} Chunks\n"
                f"   - Garantierte Minima: {doc_minimums}\n"
                f"   - Total garantiert: {total_guaranteed} Chunks\n"
                f"   - Verbleibend für Quality: {remaining_budget} Chunks"
            )

            # Phase 1: Sammle alle Chunks mit Scores + Rescue Mission
            doc_metadata = []
            all_chunks_with_meta = []

            RESCUE_THRESHOLD = 4  # Wenn eine Quelle weniger als 4 Chunks nach Reranking hat

            for cid in chat_id:
                doc_chunks = docs_map.get(cid, [])

                # RESCUE MISSION: Greift bei 0 ODER wenn unter Schwellwert
                if len(doc_chunks) < RESCUE_THRESHOLD:
                    logger.warning(
                        f"  🚨 Rescue Mission: Dokument {cid[-8:]} hat nur {len(doc_chunks)} Chunks "
                        f"nach Reranking (Schwellwert: {RESCUE_THRESHOLD})"
                    )

                    # Hole ALLE Chunks aus dem PRE-RERANKING Pool (v50.9 FIX: Nutze results statt Cache!)
                    pre_rerank_chunks = [r for r in results if r.get('chat_id') == cid]
                    if pre_rerank_chunks:
                        # Sortiere nach ursprünglichem Score (vor Reranking)
                        pre_rerank_chunks.sort(
                            key=lambda x: x.get('_final_score', 0), 
                            reverse=True
                        )

                        # Nimm die besten N aus dem Pre-Reranking Material
                        # ABER: Nur Chunks mit Score ≥ 0.5 (verhindert Müll-Rettung)
                        MINIMUM_RESCUE_SCORE = 0.5

                        needed = RESCUE_THRESHOLD - len(doc_chunks)
                        # Sammle IDs der bereits ausgewählten Chunks
                        existing_ids = {id(c) for c in doc_chunks}

                        # Filtere: Nur neue Chunks mit Score ≥ 0.5
                        rescue_candidates = [
                            c for c in pre_rerank_chunks 
                            if id(c) not in existing_ids and c.get('_final_score', 0) >= MINIMUM_RESCUE_SCORE
                        ]

                        if len(rescue_candidates) < needed:
                            logger.warning(
                                f"  ⚠️ Nur {len(rescue_candidates)} Quality-Chunks verfügbar "
                                f"(benötigt: {needed}, Filter: Score ≥ {MINIMUM_RESCUE_SCORE})"
                            )

                        doc_chunks.extend(rescue_candidates[:needed])                        
                        logger.info(
                            f"  ✅ Rescue erfolgreich: +{min(needed, len(rescue_candidates))} Chunks "
                            f"aus Pre-Reranking wiederhergestellt (Total: {len(doc_chunks)})"
                        )
                    else:
                        logger.error(f"  ❌ Rescue fehlgeschlagen: Keine Pre-Reranking Chunks verfügbar!")

                # Wenn IMMER NOCH leer: Fehler
                if not doc_chunks:
                    logger.error(f"  ❌ Dokument {cid[-8:]} hat KEINE Chunks!")
                    doc_title = self._get_chat_title(cid)
                    doc_metadata.append({
                        'title': doc_title,
                        'chunks_available': 0,
                        'chunks_selected': 0,
                        'date': datetime.min
                    })
                    continue

                # Sammle Chunks für Quality-Verteilung
                for chunk in doc_chunks:
                    score = chunk.get('hermeneutic_score', chunk.get('_final_score', 0))
                    all_chunks_with_meta.append({
                        'chunk': chunk,
                        'chat_id': cid,
                        'score': score
                    })

            # Phase 2: Sortiere global nach Score
            all_chunks_with_meta.sort(key=lambda x: x['score'], reverse=True)

            # Phase 3: Garantiere logarithmisches Minimum für jedes Dokument
            final_selection = {cid: [] for cid in chat_id}
            used_chunk_ids = set()

            for cid in chat_id:
                chunks_for_doc = [
                    c for c in all_chunks_with_meta 
                    if c['chat_id'] == cid and id(c['chunk']) not in used_chunk_ids
                ]

                # Nutze das individuell berechnete Minimum
                guaranteed = chunks_for_doc[:doc_minimums.get(cid, 0)]
                final_selection[cid] = [c['chunk'] for c in guaranteed]

                for c in guaranteed:
                    used_chunk_ids.add(id(c['chunk']))

            # Phase 4: Verteile verbleibenden Budget nach Qualität
            remaining = [
                c for c in all_chunks_with_meta 
                if id(c['chunk']) not in used_chunk_ids
            ]

            for candidate in remaining[:remaining_budget]:
                final_selection[candidate['chat_id']].append(candidate['chunk'])
                used_chunk_ids.add(id(candidate['chunk']))

            # Phase 5: Sammle Ergebnisse
            essence_results = []

            for cid in chat_id:
                selected = final_selection[cid]

                if selected:
                    essence_results.extend(selected)

                    doc_title = selected[0].get('metadata', {}).get('chat_title') or self._get_chat_title(cid)
                    avg_score = sum(
                        c.get('hermeneutic_score', c.get('_final_score', 0)) 
                        for c in selected
                    ) / len(selected)

                    logger.info(
                        f"  📄 {doc_title}: {len(docs_map.get(cid, []))} verfügbar → "
                        f"{len(selected)} ausgewählt (Ø {avg_score:.2f})"
                    )

                    dates = [self.extract_date_from_metadata(c) for c in selected]
                    valid_dates = [d for d in dates if d != datetime.min]
                    rep_date = min(valid_dates) if valid_dates else datetime.min

                    doc_metadata.append({
                        'title': doc_title,
                        'chunks_available': len(docs_map.get(cid, [])),
                        'chunks_selected': len(selected),
                        'date': rep_date
                    })
                else:
                    doc_title = self._get_chat_title(cid)
                    logger.error(f"  ❌ {doc_title}: 0 Chunks!")
                    doc_metadata.append({
                        'title': doc_title,
                        'chunks_available': 0,
                        'chunks_selected': 0,
                        'date': datetime.min
                    })

            # Ersetze top_results
            top_results = essence_results
            intent = "ESSENCE_PARITY"
            is_essence_parity = True  # v50.9: Struktur-Flag, getrennt vom semantischen Intent

            logger.info(f"✅ Essenz-Extraktion: {len(essence_results)} Chunks aus {len(chat_id)} Dokumenten")

        # --- NOTBREMSE ---
        if not top_results:
            return "Ich habe in den ausgewählten Dokumenten keine passenden Textstellen gefunden.", [], "NO_DATA"

        # NEU v50.6: CHRONOLOGISCHE SORTIERUNG
        # Sortiere Chunks nach Datum (wichtig für zeitliche Analysen!)
        top_results_sorted = sorted(top_results, key=self.extract_date_from_metadata)[:12]

        logger.info(f"📅 Chunks chronologisch sortiert: {len(top_results_sorted)} Stücke")

        # Debug-Log: Zeige Datums-Reihenfolge
        for i, res in enumerate(top_results_sorted[:5]):  # Erste 5
            date = self.extract_date_from_metadata(res)
            title = res.get('metadata', {}).get('chat_title', 'Unknown')
            logger.debug(f"  #{i+1}: {title} → {date.strftime('%d.%m.%Y') if date != datetime.min else 'o.D.'}")

        # v50.8 FIX: CHRONOLOGISCHE SORTIERUNG DER DOKUMENT-STRUKTUR
        # Wir sortieren doc_metadata ebenfalls nach Datum, damit die Prompt-Struktur stimmt!
        if doc_metadata:
            doc_metadata.sort(key=lambda x: x['date'])
            logger.info("📅 Dokument-Reihenfolge für Prompt chronologisch korrigiert.")

        # --- Context Building ---
        logger.info("📝 Baue Kontext zusammen...")

        for i, res in enumerate(top_results_sorted):
            meta = res.get('metadata', {})

            if not meta:
                meta = {}
                res['metadata'] = meta

            speaker = meta.get('model_name') or meta.get('speaker') or meta.get('author') or 'Quelle'

            # Stelle sicher, dass chat_title vorhanden ist (anonymisiert für Synthese)
            if 'chat_title' not in meta or not meta['chat_title']:
                chat_id_single = res.get('chat_id')
                if chat_id_single:
                    raw_title = self._get_chat_title(chat_id_single)
                    # Entferne Präfixe wie "ChatGPT:", "PDF:", "Gemini:" aus dem Titel
                    # um zu verhindern, dass sie als "Autoren" interpretiert werden
                    clean_title = raw_title
                    for prefix in ['ChatGPT:', 'PDF:', 'Gemini:', 'DeepSeek:', 'Claude:']:
                        if clean_title.startswith(prefix):
                            clean_title = clean_title[len(prefix):].strip()
                    meta['chat_title'] = clean_title
                else:
                    meta['chat_title'] = 'Unknown'

        context_text = ""

        for i, res in enumerate(top_results_sorted):
            sid = i + 1
            res['source_id'] = sid
            meta = res.get('metadata', {})
            title = meta.get('chat_title', 'Dokument')
            speaker = meta.get('model_name') or meta.get('speaker') or meta.get('author') or 'Quelle'
            date_obj = self.extract_date_from_metadata(res)
            date_str = date_obj.strftime("%d.%m.%Y") if date_obj != datetime.min else "o.D."
            context_text += f"QUELLE [{sid}] ({speaker} | {title} | Datum: {date_str}):\n{res.get('content')}\n\n"

        # --- Finale Diagnostik ---
        final_doc_distribution = defaultdict(int)
        for res in top_results:
            chat_title = res.get('metadata', {}).get('chat_title', 'Unknown')
            final_doc_distribution[chat_title] += 1

        logger.info(f"📊 Finale Kontext-Verteilung ({len(top_results)} Chunks total):")
        for doc_title, count in sorted(final_doc_distribution.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / len(top_results)) * 100
            logger.info(f"  📄 {doc_title}: {count} Chunks ({percentage:.1f}%)")

        # --- v50.5: ESSENCE PARITY PROMPT ---
        base_instruction = ""
        mode_display = "UNKNOWN"

        if intent == "ESSENCE_PARITY":
            structure_template = ""
            for i, doc_info in enumerate(doc_metadata):
                structure_template += f"\n### {i+1}. {doc_info['title']}\n"
                structure_template += f"[4-6 Sätze mit 3-4 Zitaten]\n"

            base_instruction = f"""

HERMENEUTISCHE GRUNDREGELN FÜR MULTIPLE QUELLEN:

1. MATERIAL-MENGE UND BEDEUTUNG: Die Quellenanzahl pro Text variiert ({min(d['chunks_selected'] for d in doc_metadata)} bis {max(d['chunks_selected'] for d in doc_metadata)} Chunks). Diese Variation reflektiert die Original-Textlänge und thematische Dichte – NICHT automatisch die Wichtigkeit für deine Antwort. Deine Aufgabe: Lass jede Quelle in ihrer eigenen Stimme sprechen, unabhängig von der Chunk-Anzahl.

2. CHRONOLOGIE ALS STRUKTUR, NICHT ALS KAUSALITÄT: Die Quellen sind nach Entstehungsdatum sortiert (älteste zuerst). Die Chronologie hilft dir, die Antwort zu strukturieren – sie bedeutet NICHT:

Dass spätere Texte von früheren "abgeleitet" sind
Dass frühere Texte spätere "vorwegnehmen"
Behandle jeden Text in seinem eigenen Kontext.

3. VERGLEICH ALS ANALOGIE, NICHT ALS IDENTITÄT: Wenn du Texte aus verschiedenen Epochen oder Disziplinen vergleichst:

Benenne strukturelle Ähnlichkeiten
Zeige funktionale Parallelen
Vermeide: Behauptungen historischer Einflüsse ohne Beleg
Bevorzugte Formulierungen:

"X bietet einen Rahmen zur Analyse von Y"
"Y zeigt strukturelle Ähnlichkeiten zu Z"
"A ermöglicht ein Verständnis von B"
4. VORSICHT BEI STRUKTURELLEN AUSSAGEN: Die Quellen sind oft Fragmente aus größeren Texten. Wenn du über die Gesamt-Struktur eines Textes sprichst (z.B. "prominent platziert", "im Abschluss", "zentrale These"), stelle sicher, dass diese Struktur in den bereitgestellten Quellen sichtbar ist. Wenn du eine Struktur inferierst, markiere das als Interpretation:

Bevorzugt: "Dieser Abschnitt argumentiert..." (sichtbar in der Quelle)
Vermeiden: "Der Text schließt mit..." (wenn nur ein Fragment vorliegt)
STRUCTURING YOUR ANSWER: The sources are chronologically ordered (oldest first). Follow this chronological structure in your answer, presenting each source's core contribution to the question.

Conclude with a synthesis of the relationships between the perspectives.

Length may vary between sections – what matters is intellectual substance, not word parity. """
            if semantic_intent == "ANALYTICAL_FORENSIC":
                base_instruction += (
                    "\n\nSKEPTISCHE LESEART: Lies gegen den Strich. "
                    "Stelle Selbstzeugnisse in Frage: Hinterfrage die Selbstdarstellung "
                    "und die behaupteten Motive als eventuell rhetorische Strategien – "
                    "nicht als neutrale Berichte. Suche nach dem plausiblen funktionalen Motiv."
                )

            mode_display = "ESSENCE PARITY (Gleichbehandlung + Chronologie + Hermeneutische Distanz)"

        elif intent == "LITERARY":
            base_instruction = "Dies ist eine LITERARISCHE Analyse. Achte auf Nuancen, Stil und Metaphorik."
            mode_display = "LITERARY"

        elif intent == "FACTUAL":
            base_instruction = "Dies ist eine FAKTISCHE Recherche. Sei präzise und objektiv. Folge der Chronologie."
            mode_display = "FACTUAL"

        else:
            base_instruction = "Dies ist eine ANALYTISCHE Untersuchung. Vergleiche die Quellen systematisch."
            mode_display = "ANALYTICAL"

        logger.info(f"🧠 RAG Modus: {mode_display}")
        
        prompt = f"""

FRAGE: "{query}"

MODUS: {mode_display}

{base_instruction}

VERFÜGBARE QUELLEN (CHRONOLOGISCH SORTIERT): {context_text}

AUFGABE: Beantworte die Frage AUSSCHLIESSLICH basierend auf den oben genannten Quellen.

WICHTIGE REGELN:

Quellen-Treue: Nutze NUR die bereitgestellten Texte.
Zitation: Belege jede Aussage mit [Nummer].
Vollständigkeit: Alle Dokumente müssen in der Antwort vorkommen.
Gleichberechtigung: Gewichte NICHT nach Chunk-Anzahl!
CHRONOLOGIE: Die Quellen sind nach Datum sortiert. Deine Antwort MUSS diese zeitliche Entwicklung abbilden (von alt nach neu).
ANTWORT: """

        # --- 🔴 NEU: DRY RUN CHECK ---
        if dry_run:
            logger.info("Dry Run: Überspringe LLM-Generierung (nur Metriken gesammelt).")
            # Wir geben einen leeren String zurück, aber die sortierten Ergebnisse (top_results_sorted)
            # und den Intent, damit die App die Imbalance berechnen kann.
            return "", top_results_sorted, intent
        # --- 🔴 ENDE ---

        # --- Generation ---
        # --- Generation ---
        logger.info("📤 Sende Prompt an LLM...")

        # v50.9 FIX: Dynamische System-Instruktion (Sokratisch-Skeptische Mitte + Forced Structure + Anchoring)
        if semantic_intent == "ANALYTICAL_FORENSIC":
            dynamic_sys_instruct = (
                "Du bist ein skeptischer Diskurs-Archäologe im Sinne der philosophischen Hermeneutik. "
                "Dein Ziel ist die Offenlegung von Textstrukturen, Brüchen und funktionalen Motiven.\n\n"
                "SKEPTISCHE LESEART: Lies gegen den Strich. "
                "Stelle Selbstzeugnisse in Frage: Hinterfrage die Selbstdarstellung "
                "und die behaupteten Motive als eventuell rhetorische Strategien – "
                "nicht als neutrale Berichte. Suche nach dem plausiblen funktionalen Motiv.\n\n"
                "ERZWUNGENE AUSGABE-STRUKTUR:\n"
                "Beginne DIREKT mit BEFUND – kein einleitender Satz davor.\n"
                "1. BEFUND: Welche zentralen Aussagen oder Widersprüche zeigen die Primärquellen? (Mit wörtlichen Zitaten)\n"
                "2. RHETORISCHE STRATEGIE: Wie rahmt oder rechtfertigt der Text diese Positionen?\n"
                "3. FUNKTIONALES MOTIV: Welches pragmatische oder strukturelle Problem löst "
"der Text damit? Falls nicht eindeutig belegbar: Biete eine plausible Hypothese an "
"und kennzeichne sie als solche.\n"
                "4. DISKURSIVE KONSEQUENZ: Was wird dadurch legitimiert, delegitimiert oder unsichtbar gemacht?\n"
                "5. FAZIT: Ein fließend lesbarer Absatz, der die strukturellen Erkenntnisse bündelt. "
                "Keine versöhnlichen Enden, keine Relativierung, keine Harmonisierung der aufgedeckten Brüche.\n\n"
                "WICHTIGE REGEL: Verzichte auf harmonisierende Einleitungen und akademische Euphemismen "
                "wie 'organische Weiterentwicklung' oder 'Paradigmenwechsel'. Sei präzise, kühl und analytisch.\n"
                "QUELLENREGEL: Nenne niemals Jahreszahlen, Daten oder Versionsnummern, "
                "die nicht wörtlich in den dir vorliegenden Chunks stehen. "
                "Wenn ein Chunk kein Datum trägt, datiere ihn nicht aus deinem Weltwissen."
            )
        
        elif semantic_intent == "ANALYTICAL":
            dynamic_sys_instruct = (
                "Du bist ein hochintelligenter, akademischer Forschungs-Assistent. "
                "Deine Aufgabe ist es, komplexe Texte präzise zu analysieren, zu vergleichen und zu synthetisieren. "
                "WICHTIGSTE REGEL: Du gehorchst den spezifischen Anweisungen des Users absolut strikt! "
                "Wenn der User sagt 'Nur Zitate', lieferst du NUR Zitate. "
                "Wenn der User sagt 'Nicht deuten', deutest du nicht. "
                "Bleibe sachlich, neutral und fokussiere dich auf den inhaltlichen Kern der Dokumente, "
                "ohne den Autoren böse Absichten oder verborgene Machtstrukturen zu unterstellen, "
                "es sei denn, es wird explizit danach gefragt."
                "QUELLENREGEL: Nenne niemals Jahreszahlen, Daten oder Versionsnummern, "
                "die nicht wörtlich in den dir vorliegenden Chunks stehen. "
                "Wenn ein Chunk kein Datum trägt, datiere ihn nicht aus deinem Weltwissen."
            )

        elif semantic_intent == "LITERARY":
            dynamic_sys_instruct = (
                "Du bist ein präziser und gewissenhafter Textanalytiker. "
                "Dein Ziel ist Genauigkeit und Quellentreue. "
                "Gib wieder, was die Quellen sagen – und deute, was sie bedeuten. "
                "Wenn Quellen sich widersprechen, benenne den Widerspruch explizit "
                "und biete eine oder mehrere plausible Hypothesen an, die ihn erklären könnten. "
                "Kennzeichne Hypothesen als solche: 'Eine mögliche Erklärung wäre...' "
                "Erfinde keine Synthese, die in keiner Quelle steht. "
                "Harmonisiere keine Widersprüche weg.\n\n"
                "FAZIT: Schließe deine Analyse mit einem zusammenhängenden, fließend lesbaren "
                "Absatz ab, der deine literarischen Erkenntnisse bündelt. "
                "Keine künstliche Harmonisierung – benenne auch ungelöste Spannungen."
                "QUELLENREGEL: Nenne niemals Jahreszahlen, Daten oder Versionsnummern, "
                "die nicht wörtlich in den dir vorliegenden Chunks stehen. "
                "Wenn ein Chunk kein Datum trägt, datiere ihn nicht aus deinem Weltwissen."
            )

        else:
            dynamic_sys_instruct = (
                "Du bist ein präziser und gewissenhafter Textanalytiker. "
                "Dein Ziel ist Genauigkeit und Quellentreue. "
                "Gib wieder, was die Quellen sagen – und deute, was sie bedeuten. "
                "Wenn Quellen sich widersprechen, benenne den Widerspruch explizit. "
                "Löse ihn nicht auf. Harmonisiere keine Widersprüche weg."
                "QUELLENREGEL: Nenne niemals Jahreszahlen oder Daten, "
                "die nicht wörtlich in den vorliegenden Chunks stehen."
                "Wenn ein Chunk kein Datum trägt, datiere ihn nicht aus deinem Weltwissen."
            )

        max_retries = 3
        for attempt in range(max_retries):
            try:
                # v50.9-local: llm_call statt genai.Client
                # Temperatursteuerung bleibt erhalten (0.4 forensisch, 0.7 sonst)
                synthesis_temp = 0.4 if semantic_intent == "ANALYTICAL_FORENSIC" else 0.7

                result = llm_call(
                    prompt,
                    task="synthesis",
                    system_instruction=dynamic_sys_instruct,
                    temperature=synthesis_temp,
                    max_tokens=4096,
                )

                if not result:
                    logger.error(f"❌ LLM hat leere Antwort zurückgegeben (Versuch {attempt+1}).")
                    if attempt < max_retries - 1:
                        time.sleep((attempt + 1) * 2)
                        continue
                    return "⚠️ Das Modell konnte keine Antwort generieren.", top_results_sorted, intent

                final_text = self.clean_citation_format(result)
                logger.info("✅ Antwort empfangen!")
                return final_text, top_results_sorted, intent

            except Exception as e:
                logger.error(f"⚠️ API Versuch {attempt+1} fehlgeschlagen: {e}")
                if attempt < max_retries - 1:
                    time.sleep((attempt + 1) * 2)
                    continue
                return f"❌ Fehler: {e}", top_results_sorted, intent

        return "❌ LLM nicht verfügbar.", top_results_sorted, intent

    def split_thought_and_speech(self, text: str) -> Tuple[str, str]:
        """Trennt Thinking-Blocks."""
        if not text:
            return "", ""

        pattern = r'(> \*\*Thinking:\*\*.*?)(\n\n|$)(.*)'
        match = re.search(pattern, text, re.DOTALL)

        if match:
            return match.group(1).strip(), match.group(3).strip()

        return "", text

    def validate_citations(self, answer: str, num_sources: int) -> List[str]:
        """Struktureller Citation-Check."""
        warnings = []

        matches = re.findall(r'\[(\d+)\]', answer)

        if not matches:
            warnings.append("⚠️ Warnung: Keine Zitationen gefunden.")
            return warnings

        for m in matches:
            idx = int(m)
            if idx < 1 or idx > num_sources:
                warnings.append(f"⚠️ Ungültige Zitation: [{idx}]")

        return warnings

    def verify_fact_match(self, claim: str, source_text: str, source_meta: Dict) -> Tuple[bool, str]:
        """Tiefenprüfung via Enforcer (FINAL FIX v50.9)."""
        try:
            from modules.hermeneutic_enforcer import HermeneuticEnforcer

            enforcer = HermeneuticEnforcer()
            sources = [{"content": source_text, "metadata": source_meta}]

            # 1. Aufruf (Name ist korrekt: validate_claim)
            result = enforcer.validate_claim(claim=claim, sources=sources)

            # 2. Ergebnis verarbeiten (Dict vs Tuple)
            if isinstance(result, dict):
                # Das ist das neue v50.6 Format!
                is_valid = result.get("valid", False)
                h_type = result.get("hermeneutic_type", "unknown")
                v_cat = result.get("validity_category", "unknown")
                reason = result.get("reason", "No reason")

                # Wir bauen einen aussagekräftigen String für die UI
                full_reason = f"[{h_type.upper()}/{v_cat.upper()}] {reason}"
                return is_valid, full_reason

            elif isinstance(result, tuple):
                # Legacy Fallback (falls doch noch alter Code läuft)
                if len(result) == 3:
                    is_valid, classification, reason = result
                    return is_valid, f"[{classification.upper()}] {reason}"
                elif len(result) == 2:
                    is_valid, reason = result
                    return is_valid, reason

            # Fallback
            return True, "Enforcer Format Unknown"

        except Exception as e:
            logger.error(f"Enforcer Error: {e}")
            # Wir geben True zurück, damit die App nicht abstürzt, aber loggen den Fehler
            return True, f"ENFORCER ERROR (Ignored): {e}"

    def verify_fact_match_multisource(self, claim: str, sources: List[Dict]) -> Tuple[bool, str]:
        """Multi-Source-Validierung: Jedes Zitat muss in mindestens einer Quelle stehen."""
        try:
            from modules.hermeneutic_enforcer import HermeneuticEnforcer
            enforcer = HermeneuticEnforcer()
            result = enforcer.validate_claim_multisource(claim=claim, sources=sources)

            if isinstance(result, dict):
                is_valid = result.get("valid", False)
                h_type = result.get("hermeneutic_type", "unknown")
                v_cat = result.get("validity_category", "unknown")
                reason = result.get("reason", "No reason")
                return is_valid, f"[{h_type.upper()}/{v_cat.upper()}] {reason}"

            return True, "Enforcer Format Unknown"

        except Exception as e:
            logger.error(f"MultiSource Enforcer Error: {e}")
            return True, f"ENFORCER ERROR (Ignored): {e}"

    async def verify_facts_parallel(
        self, 
        sentences: List[str], 
        results: List[Dict], 
        progress_callback=None
    ) -> List[Dict]:
        """Parallele Faktenprüfung."""
        sem = asyncio.Semaphore(5)
        completed = 0
        total = len(sentences)

        async def _bounded_check(sent):
            nonlocal completed

            async with sem:
                loop = asyncio.get_running_loop()

                matches = re.findall(r'\[(\d+)\]', sent)
                if not matches:
                    return None

                results_for_sentence = []

                # NEU v50.9: Multi-Source-Erkennung
                if len(matches) > 1:
                    # Satz zitiert mehrere Quellen → gemeinsam prüfen
                    all_sources = []
                    for m in matches:
                        idx = int(m) - 1
                        if 0 <= idx < len(results):
                            all_sources.append({
                                'content': results[idx].get('content', ''),
                                'metadata': results[idx].get('metadata', {}),
                                'source_id': m
                            })
                    if all_sources:
                        is_valid, reason = await loop.run_in_executor(
                            None,
                            partial(self.verify_fact_match_multisource, sent, all_sources)
                        )
                        results_for_sentence.append({
                            'sentence': sent,
                            'source_id': '+'.join(matches),
                            'valid': is_valid,
                            'reason': reason
                        })
                else:
                    # Satz zitiert eine Quelle → bisherige Logik
                    m = matches[0]
                    idx = int(m) - 1
                    if 0 <= idx < len(results):
                        source_content = results[idx].get('content', '')
                        source_meta = results[idx].get('metadata', {})
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

        tasks = [_bounded_check(sent) for sent in sentences]
        all_results = await asyncio.gather(*tasks)

        flat_log = []
        for res_list in all_results:
            if res_list:
                flat_log.extend(res_list)

        return flat_log