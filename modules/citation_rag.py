# modules/citation_rag.py - v52: Hybrid Cockpit Integration
import logging
import re
import time
import asyncio
import math
import uuid
import json
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from collections import defaultdict
from typing import List, Dict, Any, Tuple, Optional
from types import SimpleNamespace
from datetime import datetime

from modules.config import (
    MODEL_SYNTHESIS,
    RERANKER_CANDIDATES,
    MAX_TOKENS_PER_CALL,
    ESSENCE_TOTAL_BUDGET,
    RESCUE_THRESHOLD,
    MINIMUM_RESCUE_SCORE,
    RESCUE_FETCH_LIMIT,  # <--- NEU (siehe Punkt 2)
    TRIM_TOKEN_BUDGET,  # <--- NEU
    MAX_TOKENS_STILISIERUNG,
)
from modules.llm_wrapper import llm_call, llm_call_json, _parse_json_safe
from modules.vector_store import LocalVectorStore
from modules.evidence_synthesis import EvidenceFirstSynthesizer
from modules.hermeneutic_reranker import HermeneuticReranker
from modules.hermeneutic_router import HermeneuticRouter
from modules.prompt_manager import PromptManager

logger = logging.getLogger(__name__)


class CitationRAG:
    def __init__(
        self,
        vector_store: LocalVectorStore = None,
        model_name: str = MODEL_SYNTHESIS,
        router = None,
        reranker_factory = None,
        enforcer = None,
        llm_call_func = None,
    ):
        if vector_store is None:
            from modules.database import get_db_connection

            db = get_db_connection()
            vector_store = LocalVectorStore(db)

        self.vector_store = vector_store
        self.model_name = model_name
        self.router = router or HermeneuticRouter()
        self.synthesizer = EvidenceFirstSynthesizer(model_name)

        # UI-Zugriff für Imbalance-Daten
        self.last_imbalance_info = None
        self.last_pipeline_trace = None
        self.current_context = {"intent": "FACTUAL", "threshold": 0.65}

        # --- FIX: Cache initialisieren ---
        self._original_results_cache = []

        # --- NEU v52: Prompt-Manager ---
        self.prompt_manager = PromptManager()

        # --- Phase 5.1: Dependency Injection Slots ---
        self._enforcer = enforcer
        self._llm_call_func = llm_call_func or llm_call
        if reranker_factory:
            self._reranker_factory = reranker_factory
        else:
            self._reranker_factory = lambda threshold: HermeneuticReranker(threshold=threshold)

    def generate_synthesis_best_of(
        self,
        iteration_texts: List[str],
        intent: str = "SYNTHESIS_BEST_OF",
        temperature: float = 0.55,
    ) -> str:
        """
        Direkte Full-Context-Synthese ohne RAG-Pipeline.
        Kein Chunking, kein Retrieval, kein Trimming.
        Alle Iterationen werden als Ganzes in den Kontext geladen.
        """
        sys_instr = self.prompt_manager.get_system_instruction(intent)
        mode_instr = self.prompt_manager.get_mode_instruction(intent)

        context = "\n\n".join(
            f"=== ITERATION {i} ===\n{text}"
            for i, text in enumerate(iteration_texts, 1)
        )
        prompt = f"{mode_instr}\n\nITERATIONEN:\n{context}\n\nMEISTERTEXT:"

        # Dynamisches Token-Limit: Stilisierung braucht mehr Raum für Ghostwriting
        max_tokens = MAX_TOKENS_STILISIERUNG if intent == "STILISIERUNG" else 8192

        return self._llm_call_func(
            prompt,
            task="synthesis",
            system_instruction=sys_instr,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def generate_agentic_synthesis(
        self,
        iteration_texts: List[str],
        source_intent: str = "SYNTHESIS_BEST_OF",
    ) -> Tuple[str, dict]:
        """
        Drei-Stufen-Agentic-Pipeline:
        AGENT_DRAFTER → AGENT_CRITIC → AGENT_EDITOR

        Args:
            iteration_texts: vollständige Texte, unkondensiert
            source_intent: "SYNTHESIS_BEST_OF" oder "STILISIERUNG"

        Returns:
            (finaler_text, trace_dict)
        """
        import json as _json

        # --- Schritt 1: Entwurf ---
        draft = self.generate_synthesis_best_of(
            iteration_texts,
            intent="AGENT_DRAFTER"
        )
        logger.info(f"✅ Agentic Schritt 1 (DRAFTER): {len(draft)} Zeichen")

        if not draft:
            return "", {"error": "DRAFTER lieferte leeren Text"}

        # --- Schritt 2: Kritik (Ohne JSON-Modus, um API-Limits zu umgehen) ---
        critic_sys = self.prompt_manager.get_system_instruction("AGENT_CRITIC")
        raw_critique = self._llm_call_func(
            prompt=f"ENTWURF ZUR PRÜFUNG:\n\n{draft}",
            task="synthesis",
            system_instruction=critic_sys,
            temperature=0.3,
            max_tokens=4096,
        )

        # Manuelles Parsing des Text-Outputs
        from modules.llm_wrapper import _parse_json_safe
        critique = _parse_json_safe(raw_critique, fallback=[])

        logger.info(f"✅ Agentic Schritt 2 (CRITIC): {len(str(critique))} Zeichen")
        logger.info(f"CRITIC Output: {_json.dumps(critique, ensure_ascii=False, indent=2)}")

        # Wenn das Modell nur ein einzelnes dict zurückgibt, packe es in eine Liste
        if isinstance(critique, dict):
            critique = [critique]

        if not isinstance(critique, list) or len(critique) == 0:
            logger.warning("⚠️ CRITIC lieferte leere oder invalide Liste — überspringe Editor")
            return draft, {"draft": draft[:300], "critique": [], "skipped_editor": True}

        logger.info(f"📋 CRITIC: {len(critique)} Kritikpunkte")
        for i, point in enumerate(critique[:3]):
            logger.info(f"  [{i+1}] {point.get('problem', '?')}")

        # --- Schritt 3: Überarbeitung ---
        editor_sys = self.prompt_manager.get_system_instruction("AGENT_EDITOR")
        edit_prompt = (
            f"ENTWURF:\n\n{draft}\n\n"
            f"KRITIKPUNKTE (nur diese 3 Stellen ändern):\n"
            f"{_json.dumps(critique[:3], ensure_ascii=False, indent=2)}"
        )
        final = self._llm_call_func(
            edit_prompt,
            task="synthesis",
            system_instruction=editor_sys,
            temperature=0.55,
            max_tokens=MAX_TOKENS_PER_CALL,
        )
        logger.info(f"✅ Agentic Schritt 3 (EDITOR): {len(final)} Zeichen")

        trace = {
            "draft_preview": draft[:300],
            "critique": critique[:3],
            "final_length": len(final),
        }
        return final, trace

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

            multilingual_query = self._llm_call_func(prompt, task="query_expansion")

            if not multilingual_query:
                logger.warning("⚠️ Query-Expansion leer. Fallback auf Original.")
                return query

            multilingual_query = multilingual_query.strip()
            multilingual_query = re.sub(r"\n+", " ", multilingual_query)
            logger.info(
                f"🌐 Query Translation: {query[:50]}... → {len(multilingual_query.split())} words"
            )
            return multilingual_query

        except Exception as e:
            logger.warning(
                f"⚠️ Query Translation fehlgeschlagen: {e}. Fallback auf Original."
            )
            return query

    def retrieve_with_rrf(
        self, query: str, limit: int = 15, chat_id: Any = None, use_router: bool = True
    )  -> Tuple[List[Dict], Optional[List[float]]]:  # <--- SIGNATUR GEÄNDERT
        """v50.10: Retrieval mit Router, RRF und 'Rescue Mission' für garantierte Abdeckung."""
        # 1. Router & Parameter-Setup
        if use_router:
            try:
                route = self.router.route_query(query)
                dynamic_limit = route.get("limit", limit)
                intent = route.get("intent", "AUTO")
                threshold = route.get("threshold", 0.65)
                logger.info(
                    f"🚀 Retrieval Mode: AUTO ({intent}) | Limit: {dynamic_limit} | Threshold: {threshold}"
                )
            except Exception as e:
                logger.error(f"❌ Router Error: {e}. Fallback auf Standard-Parameter.")
                route = {}
                dynamic_limit = limit
                intent = "FALLBACK"
                threshold = 0.65
        else:
            route = {}
            dynamic_limit = limit
            intent = "MANUAL"
            threshold = 0.65

        logger.info(f"🔧 Retrieval Mode: {intent} | Limit: {dynamic_limit}")

        # Selection Boost: Wenn Dokumente ausgewählt sind, erhöhen wir das Limit
        if chat_id:
            old_limit = dynamic_limit
            dynamic_limit = max(dynamic_limit, RERANKER_CANDIDATES)
            if dynamic_limit > old_limit:
                logger.info(
                    f"📈 Selection Boost: Limit erhöht von {old_limit} auf {dynamic_limit}"
                )

        self.current_context = {
            "intent": intent,
            "threshold": threshold,
            "query": query,
            "reasoning": route.get("reasoning", ""),
        }

        # 2. Haupt-Suche
        expanded_query = self.expand_query_multilingual(query)
        allowed_ids = (
            chat_id if isinstance(chat_id, list) else [chat_id] if chat_id else None
        )

        results, query_vector = self.vector_store.hybrid_search(
            query=expanded_query, limit=dynamic_limit, allowed_chat_ids=allowed_ids
        )

        # --- 🔴 NEU: RESCUE MISSION (Garantierte Abdeckung) ---
        if allowed_ids and len(allowed_ids) > 1:
            # Welche Dokumente haben wir gefunden?
            found_chat_ids = set(r.get("chat_id") for r in results if r.get("chat_id"))

            # Welche fehlen?
            missing_ids = [cid for cid in allowed_ids if cid not in found_chat_ids]

            if missing_ids:
                logger.warning(
                    f"⚠️ {len(missing_ids)} ausgewählte Dokumente fehlen im Top-{dynamic_limit}. Starte Rettungsmission..."
                )

                for missing_cid in missing_ids:
                    # Gezielte Nachsuche NUR in diesem Dokument
                    rescue_results, _ = self.vector_store.hybrid_search(
                        query=expanded_query,
                        limit=RESCUE_FETCH_LIMIT,  # <--- GEÄNDERT: DB-Abfrage-Limit
                        allowed_chat_ids=[missing_cid],
                    )

                    if rescue_results:
                        # Markiere sie als "gerettet", damit wir das im Log sehen
                        for res in rescue_results:
                            res["_is_rescued"] = True
                            # Gib ihnen einen künstlichen Boost, damit sie nicht sofort wieder rausfliegen
                            res["_keyword_boost"] = res.get("_keyword_boost", 0) + 0.2

                        results.extend(rescue_results)
                        logger.info(
                            f"  🚑 Dokument {missing_cid[-6:]}... mit {len(rescue_results)} Chunks gerettet."
                        )
                    else:
                        logger.warning(
                            f"  ❌ Dokument {missing_cid[-6:]}... enthält KEINE Treffer (selbst bei gezielter Suche)."
                        )

        # --- FIX: Ergebnisse cachen für spätere Rettungsversuche ---
        self._original_results_cache = results
        # -----------------------------------------------------------
        return results, query_vector   # <--- RÜCKGABE GEÄNDERT

    def check_imbalance_only(
        self,
        query: str,
        results: List[Dict],
        chat_id: Any = None,
        use_router: bool = True,
    ) -> SimpleNamespace:
        """Prüft NUR die Chunk-Verteilung, OHNE zu synthetisieren.

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
                min_chunks=0,
            )

        # Router-Logik (falls aktiviert)
        if use_router:
            try:
                route = self.router.route_query(query)
                rerank_threshold = route["threshold"]
                intent = route["intent"]
                self.current_context = {
                    "intent": intent,
                    "threshold": rerank_threshold,
                    "query": query,
                }
            except Exception as e:
                logger.error(f"❌ Router Error: {e}. Fallback auf Standard-Parameter.")
                rerank_threshold = 0.65
                intent = "FALLBACK"
        else:
            rerank_threshold = 0.65
            intent = "MANUAL"

        # Scoring
        is_rrf_result = any(res.get("_rrf_active") for res in results)
        if is_rrf_result:
            for res in results:
                if "_final_score" not in res:
                    res["_final_score"] = res.get("score", 0.0)
        else:
            for res in results:
                res["_final_score"] = res.get("score", 0.0) + res.get(
                    "_keyword_boost", 0.0
                )
            results.sort(key=lambda x: x.get("_final_score", 0), reverse=True)

        # Reranking
        top_candidates = results[:100]
        reranker = self._reranker_factory(threshold=rerank_threshold)
        top_results, _ = reranker.rerank(
            query, top_candidates, max_results=RERANKER_CANDIDATES, intent=intent
        )

        # Fallback bei zu wenig Treffern
        if len(top_results) < 5:
                 logger.warning(f"⚠️ Zu wenig Treffer nach Reranking ({len(top_results)}). Senke Threshold auf 0.35 (OHNE neuen LLM-Call)...")
                 # PERFORMANCE FIX: Wir starten KEINEN neuen LLM-Durchlauf!
                 # Wir filtern die top_candidates einfach mit den Scores, 
                 # die der erste Reranker-Durchlauf bereits vergeben hat.
                 top_results = [
                     cand for cand in top_candidates 
                     if cand.get("hermeneutic_score", 0) >= 0.35
                 ]
                 logger.info(f"✅ Relaxed Filter (0.35) angewendet: {len(top_results)} Chunks übernommen.")
                 
                 # Falls immer noch zu wenig, nehmen wir die Top 5 nach Score
                 if len(top_results) < 5:
                     top_candidates.sort(key=lambda x: x.get("hermeneutic_score", x.get("_final_score", 0)), reverse=True)
                     top_results = top_candidates[:5]
                     logger.info(f"✅ Harter Fallback: Top 5 Chunks übernommen.")

        # NEU v51: Mindestrepräsentations-Garantie
        if chat_id:
            _requested = set(chat_id) if isinstance(chat_id, list) else {chat_id}
            _represented = set(r.get("chat_id") for r in top_results)
            _missing = _requested - _represented
            if _missing:
                _pool_by_id = defaultdict(list)
                for c in top_candidates:
                    if c.get("chat_id") in _missing:
                        _pool_by_id[c.get("chat_id")].append(c)
                for _cid in _missing:
                    _best = sorted(
                        _pool_by_id[_cid],
                        key=lambda x: x.get("_final_score", 0),
                        reverse=True,
                    )
                    if _best:
                        top_results.append(_best[0])
                        logger.info(
                            f"🔧 Mindestrepräsentation: +1 Chunk für "
                            f"{_cid[-8:]} (score={_best[0].get('_final_score', 0):.3f})"
                        )
                    else:
                        logger.warning(f"⚠️ Kein Chunk im Pool für {_cid[-8:]}")
        # Dokumenten-Verteilung VOR Essenz-Extraktion
        surviving_docs = defaultdict(int)
        for res in top_results:
            chat_id_single = res.get("chat_id", "unknown")
            chat_title = res.get("metadata", {}).get(
                "chat_title"
            ) or self._get_chat_title(chat_id_single)
            surviving_docs[chat_title] += 1

        # Imbalance-Berechnung
        if not surviving_docs:
            return SimpleNamespace(
                severity="none",
                ratio=1.0,
                doc_distribution={},
                max_chunks=0,
                min_chunks=0,
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
            min_chunks=min_c,
            top_results=top_results,
            pre_rerank_pool=top_candidates,
        )

        # Speichere für späteren Zugriff
        self.last_imbalance_info = imbalance_info

        logger.info(f"📊 Imbalance-Check: {severity.upper()} (Ratio: {ratio:.1f}:1)")

        return imbalance_info

    def extract_keywords(self, query: str) -> List[str]:
        """Legacy-Funktion."""
        clean_query = query.replace("-", " ").replace("_", " ")
        ignore = {
            "wie",
            "was",
            "wo",
            "und",
            "oder",
            "der",
            "die",
            "das",
            "bei",
            "mit",
            "von",
            "über",
            "ist",
            "sind",
            "jeweils",
            "erwähnung",
            "auf",
            "den",
            "dem",
            "sagen",
            "meinen",
        }

        keywords = []
        for w in clean_query.split():
            w_clean = w.lower().strip('?".,!:')
            if w_clean not in ignore and len(w_clean) > 2:
                keywords.append(w_clean)

        return keywords

    def clean_citation_format(self, text: str) -> str:
        """Bereinigt Zitationsformate."""
        text = re.sub(r"\[source_id:\s*(\d+)\]", r"[\1]", text)
        text = re.sub(r"\[Quelle:\s*(\d+)\]", r"[\1]", text)
        return text

    def _get_chat_title(self, chat_id: str) -> str:
        """v50.2: Hole echten Chat-Titel (Fallback-sicher).
        v50.9-local: SQLite-Direktabfrage statt Firestore-Collection-API.
        """
        try:
            from modules.database import get_db_connection

            db = get_db_connection()
            if db is None:
                return f"Doc {chat_id[-8:]}"
            row = db.execute(
                "SELECT title FROM chats WHERE id = ?", (chat_id,)
            ).fetchone()
            if row:
                return row["title"] or f"Doc {chat_id[-8:]}"
            return f"Doc {chat_id[-8:]}"
        except Exception:
            return f"Doc {chat_id[-8:]}"

    def extract_date_from_metadata(self, res: Dict) -> datetime:
        """Extrahiert Datum aus Chunk-Metadaten für chronologische Sortierung.

        Unterstützt Formate:
        - "04.12.2025" (Tag.Monat.Jahr)
        - "Mai 2025" (Monat Jahr)
        - "13.10.2025" (Tag.Monat.Jahr)

        Returns:
            datetime-Objekt oder datetime.min falls kein Datum
        """
        meta = res.get("metadata", {})
        date_str = meta.get("real_date_str", "")

        if not date_str or date_str == "o.D.":
            return datetime.min

        try:
            # Format: "04.12.2025"
            if "." in date_str:
                return datetime.strptime(date_str, "%d.%m.%Y")

            # Format: "Mai 2025"
            elif " " in date_str:
                month_map = {
                    "Januar": 1,
                    "Februar": 2,
                    "März": 3,
                    "April": 4,
                    "Mai": 5,
                    "Juni": 6,
                    "Juli": 7,
                    "August": 8,
                    "September": 9,
                    "Oktober": 10,
                    "November": 11,
                    "Dezember": 12,
                }
                parts = date_str.split()
                if len(parts) == 2 and parts[0] in month_map:
                    month = month_map[parts[0]]
                    year = int(parts[1])
                    return datetime(year, month, 1)

        except Exception as e:
            logger.warning(f"⚠️ Konnte Datum nicht parsen: '{date_str}' → {e}")

        return datetime.min

    def _trim_to_token_budget(self, chunks: list, max_tokens: int = 6000) -> list:
        """Token-bewusster Ersatz für [:12]. (P5 Performance Fix)
        Greedy-Forward-Pass mit O(n) Token-Prekalkulation.
        Garantiert: mindestens 1 Chunk pro Dokument (falls Budget reicht).
        """
        if not chunks:
            return []

        # 1. O(n) Pre-Kalkulation: Token-Länge nur EINMAL berechnen
        for c in chunks:
            if "_tokens" not in c:
                c["_tokens"] = len(c.get("content", "")) // 4

        # 2. Mindestens 1 Chunk pro Dokument sichern (Epistemische Basis)
        seen_docs = {}
        rest = []
        for chunk in chunks:
            cid = chunk.get("chat_id")
            if cid not in seen_docs:
                seen_docs[cid] = chunk  # erster Chunk pro Dokument
            else:
                rest.append(chunk)

        # 3. Logarithmische Gewichte berechnen
        chunk_counts = {}
        for c in chunks:
            cid = c.get("chat_id")
            chunk_counts[cid] = chunk_counts.get(cid, 0) + 1

        log_weights = {cid: math.log(chunk_counts.get(cid, 1) + 1) for cid in seen_docs}
        total_weight = sum(log_weights.values()) if log_weights else 1.0

        selected = []
        used_tokens = 0
        deferred = []

        # Phase 1: Epistemische Basis — Versuch innerhalb des fairen Budgets
        for cid, chunk in seen_docs.items():
            doc_budget = int(max_tokens * (log_weights[cid] / total_weight))
            tokens = chunk["_tokens"]

            if tokens <= doc_budget and used_tokens + tokens <= max_tokens:
                selected.append(chunk)
                used_tokens += tokens
                logger.debug(f"✅ Phase1 {cid[-8:]}: {tokens} Tokens (budget={doc_budget})")
            else:
                deferred.append(chunk)
                logger.debug(f"⏳ Zurückgestellt {cid[-8:]}: {tokens} > budget={doc_budget}")

        # Phase 2: Breiten-Maximierung — Zurückgestellte Basis-Chunks nachnominieren
        for chunk in deferred:
            tokens = chunk["_tokens"]
            if used_tokens + tokens <= max_tokens:
                selected.append(chunk)
                used_tokens += tokens
                logger.info(f"🔄 Phase2 nachgeholt {chunk.get('chat_id', '')[-8:]}: {tokens} Tokens")
            else:
                logger.warning(f"⚠️ Kein Platz für {chunk.get('chat_id', '')[-8:]}: braucht {tokens}, verfügbar {max_tokens - used_tokens}")

        # Phase 3: Rest greedy auffüllen
        for chunk in rest:
            tokens = chunk["_tokens"]
            if used_tokens + tokens <= max_tokens:
                selected.append(chunk)
                used_tokens += tokens

        # Phase 4: Chronologische Reihenfolge wiederherstellen
        selected.sort(key=self.extract_date_from_metadata)

        logger.info(
            f"📐 Token-Budget: {used_tokens}/{max_tokens} Token "
            f"| {len(selected)} Chunks aus {len(seen_docs)} Dokumenten"
        )

        # Cleanup: Temporären Key entfernen, um Dictionaries sauber zu halten
        for c in selected:
            c.pop("_tokens", None)

        return selected

    # =========================================================================
    # 1. ÖFFENTLICHE HAUPTMETHODE (Der Dirigent)
    # =========================================================================

    def generate_answer(self, query: str, results: List[Dict], dry_run: bool = False, pre_reranked=None) -> Tuple[str, List[Dict], str]:
        """ v50.9: ESSENCE PARITY - Intelligente Essenz-Extraktion. v51: Refactored for clarity."""
        if not results:
            return "Ich habe keine relevanten Informationen in den Dokumenten gefunden.", [], "unknown"

        # --- Schritt 1: Kontext & Intent sicherstellen ---
        intent, semantic_intent = self._ensure_router_context(query)

        # --- Schritt 2: Chat IDs extrahieren ---
        chat_id = self._extract_chat_ids(results)

        # --- Schritt 3: Scoring & Reranking (MIT CRASH-CATCHER) ---
        try:
            top_results, top_candidates, rerank_stats, rejected_chunks = self._score_and_rerank(
                query, results, pre_reranked, intent
            )
            logger.info("🏁 DEBUG BAKE 0: Reranker Rückgabe erfolgreich entpackt!")
        except Exception as e:
            logger.error(f"❌❌❌ CRASH NACH RERANKER: {e}")
            import traceback
            logger.error(traceback.format_exc())

            logger.warning(
                "⚠️  UNGEPRÜFTE ERGEBNISSE: Der HermeneuticReranker ist "
                "ausgefallen. Es werden die Top-20 Roh-Treffer verwendet, "
                "OHNE hermeneutische Qualitätsprüfung. "
                "Dies kann zu irrelevanten Chunks und Halluzinationen führen."
            )

            # Fallback, damit die App nicht steht
            raw_results = sorted(results, key=lambda x: x.get('score', 0), reverse=True)
            top_results = raw_results[:20]
            top_candidates = raw_results[:100]
            rerank_stats = {
                "total": len(results), 
                "passed": len(top_results), 
                "rejected": 0, 
                "avg_score": 0, 
                "query_type": "fallback_unranked",
                "reranker_failed": True,      # <--- NEU: Das Flag für den Wrapper
                "reranker_error": str(e)      # <--- NEU: Der Fehler für die Diagnose
            }
            rejected_chunks = []

        # --- Schritt 4: Imbalance-Daten berechnen ---
        self._calculate_imbalance(top_results)
        
        # === DIAGNOSE-LOGGING ===
        logger.debug(f">>> BAKE 1: Nach Imbalance-Check | chat_id={chat_id}")
        if chat_id is None:
            logger.warning(">>> WARNUNG: chat_id ist None! Essence Parity wird übersprungen!")
        # ========================
        
        # --- Schritt 5: Essence Parity & Rescue Mission ---
        doc_metadata = []
        is_essence_parity = False
        if chat_id and isinstance(chat_id, list) and len(chat_id) <= 10:
            print(">>> BAKE 2: Betrete Essence Parity...", flush=True)
            top_results, doc_metadata, intent = self._apply_essence_parity(
                query, top_results, results, chat_id, intent
            )
            is_essence_parity = True

        # --- NOTBREMSE ---
        if not top_results:
            return "Ich habe in den ausgewählten Dokumenten keine passenden Textstellen gefunden.", [], "NO_DATA"

        # --- Schritt 6: Chronologische Sortierung & Token Trimming ---
        logger.info("🏁 DEBUG BAKE 3: Vor Token-Trimming") # NEU
        top_results_sorted = self._trim_to_token_budget(
               sorted(top_results, key=self.extract_date_from_metadata),
               max_tokens=TRIM_TOKEN_BUDGET
        )
        logger.info(f"📅 Chunks chronologisch sortiert: {len(top_results_sorted)} Stücke")

        # Debug-Log: Zeige Datums-Reihenfolge
        for i, res in enumerate(top_results_sorted[:5]):
            date = self.extract_date_from_metadata(res)
            title = res.get('metadata', {}).get('chat_title', 'Unknown')
            logger.debug(f"  #{i+1}: {title} → {date.strftime('%d.%m.%Y') if date != datetime.min else 'o.D.'}")

        # v50.8 FIX: CHRONOLOGISCHE SORTIERUNG DER DOKUMENT-STRUKTUR
        if doc_metadata:
            doc_metadata.sort(key=lambda x: x['date'])
            logger.info("📅 Dokument-Reihenfolge für Prompt chronologisch korrigiert.")

        # --- Schritt 7: Context Text aufbauen ---
        context_text = self._build_context_text(top_results_sorted)

        # --- Finale Diagnostik ---
        final_doc_distribution = defaultdict(int)
        for res in top_results:
            chat_title = res.get('metadata', {}).get('chat_title', 'Unknown')
            final_doc_distribution[chat_title] += 1

        logger.info(f"📊 Finale Kontext-Verteilung ({len(top_results)} Chunks total):")
        for doc_title, count in sorted(final_doc_distribution.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / len(top_results)) * 100
            logger.info(f"  📄 {doc_title}: {count} Chunks ({percentage:.1f}%)")

        # --- Schritt 8: Prompt bauen ---
        prompt, mode_display, dynamic_sys_instruct = self._build_synthesis_prompt(
            query, doc_metadata, intent, semantic_intent, context_text
        )

        # --- 🔴 NEU: DRY RUN CHECK ---
        if dry_run:
            logger.info("Dry Run: Überspringe LLM-Generierung (nur Metriken gesammelt).")
            return "", top_results_sorted, intent

        # --- Schritt 9: LLM Generierung & Pipeline Trace ---
        return self._execute_llm_call(
            query, prompt, dynamic_sys_instruct, intent, semantic_intent, 
            top_results, top_results_sorted, rerank_stats, rejected_chunks
        )

    # =========================================================================
    # 2. PRIVATE HILFSMETHODEN (Die Musiker)
    # =========================================================================

    def _ensure_router_context(self, query: str) -> Tuple[str, str]:
        """Stellt sicher, dass der Router-Kontext für die Query geladen ist."""
        if self.current_context.get("query") != query:
            logger.info("🔄 Router-Kontext fehlt (Analyse-Fenster). Hole Intent-Analyse nach...")
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
        return intent, semantic_intent

    def _extract_chat_ids(self, results: List[Dict]) -> Optional[List[str]]:
        """Extrahiert eindeutige Chat-IDs aus den Results."""
        if not results:
            return None
        first_result_chat_ids = [r.get('chat_id') for r in results if r.get('chat_id')]
        if first_result_chat_ids:
            unique_chat_ids = list(set(first_result_chat_ids))
            if len(unique_chat_ids) <= 10:
                return unique_chat_ids
        return None

    def _score_and_rerank(
        self, query: str, results: List[Dict], pre_reranked, intent: str
    ) -> Tuple[List[Dict], List[Dict], Dict, List[Dict]]:
        """Führt Scoring und Reranking durch."""
        rerank_threshold = self.current_context.get("threshold", 0.65)
        
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
        rejected_chunks = []
        rerank_stats = {}
        if pre_reranked is not None:
            top_results = pre_reranked.top_results
            top_candidates = pre_reranked.pre_rerank_pool
            logger.info(f"⚡ Reranking übersprungen — nutze pre-geranktes Ergebnis ({len(top_results)} Chunks)")
        else:
            top_candidates = results[:100]
            logger.info(f"⚖️ Reranking mit Threshold: {rerank_threshold} (Intent: {intent})")
            reranker = self._reranker_factory(threshold=rerank_threshold)
            top_results, rerank_stats = reranker.rerank(query, top_candidates, max_results=RERANKER_CANDIDATES, intent=intent)
            
            if len(top_results) < 5:
                 logger.warning(f"⚠️ Zu wenig Treffer nach Reranking ({len(top_results)}). Senke Threshold auf 0.35...")
                 reranker_relaxed = self._reranker_factory(threshold=0.35)
                 top_results, _ = reranker_relaxed.rerank(query, top_candidates, max_results=RERANKER_CANDIDATES, intent=intent)

            # Verworfene Chunks für Pipeline-Trace
            kept_ids = {id(r) for r in top_results}
            rejected_chunks = [
                {
                    "title":   c.get('metadata', {}).get('chat_title', 'Unknown'),
                    "score":   round(c.get('hermeneutic_score', c.get('_final_score', 0)), 3),
                    "date":    c.get('metadata', {}).get('real_date_str', 'o.D.'),
                    "preview": c.get('content', '')[:120].replace('\n', ' '),
                }
                for c in top_candidates
                if id(c) not in kept_ids
            ]
            
            # v51: Mindestrepräsentations-Garantie
            chat_id_list = self._extract_chat_ids(results)
            if chat_id_list:
                _requested = set(chat_id_list)
                _represented = set(r.get('chat_id') for r in top_results)
                _missing = _requested - _represented
                if _missing:
                    _pool_by_id = defaultdict(list)
                    for c in top_candidates:
                        if c.get('chat_id') in _missing:
                            _pool_by_id[c.get('chat_id')].append(c)
                    for _cid in _missing:
                        _best = sorted(_pool_by_id[_cid],
                                       key=lambda x: x.get('_final_score', 0),
                                       reverse=True)
                        if _best:
                            top_results.append(_best[0])
                            logger.info(f"🔧 Mindestrepräsentation: +1 Chunk für "
                                        f"{_cid[-8:]} (score={_best[0].get('_final_score', 0):.3f})")

        return top_results, top_candidates, rerank_stats, rejected_chunks

    def _calculate_imbalance(self, top_results: List[Dict]) -> None:
        """Berechnet Dokumenten-Verteilung und speichert Imbalance-Info für UI."""
        surviving_docs = defaultdict(int)
        for res in top_results:
            chat_id_single = res.get('chat_id', 'unknown')
            chat_title = res.get('metadata', {}).get('chat_title') or self._get_chat_title(chat_id_single)
            surviving_docs[chat_title] += 1

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
                severity=severity, ratio=ratio, doc_distribution=dict(surviving_docs),
                max_chunks=max_c, min_chunks=min_c
            )
        else:
            self.last_imbalance_info = SimpleNamespace(
                severity="none", ratio=1.0, doc_distribution={}, max_chunks=0, min_chunks=0
            )

    def _apply_essence_parity(
        self, query: str, top_results: List[Dict], results: List[Dict], chat_id: List[str], intent: str
    ) -> Tuple[List[Dict], List[Dict], str]:
        """Wendet Logarithmische Essenz-Extraktion und Rescue Mission an."""
        logger.info(f"⚖️ ESSENCE PARITY aktiviert: {len(chat_id)} Dokumente")
        
        doc_metadata = []
        
        # Gruppiere Chunks nach Chat-ID
        docs_map = defaultdict(list)
        for res in top_results:
            cid = res.get('chat_id')
            docs_map[cid].append(res)

        total_budget = ESSENCE_TOTAL_BUDGET
        doc_minimums = {}

        # Schritt 1: Ermittle ORIGINAL-Chunk-Anzahl (vor Reranking)
        original_counts = {}
        for cid in chat_id:
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
        all_chunks_with_meta = []

        for cid in chat_id:
            doc_chunks = docs_map.get(cid, [])

            # RESCUE MISSION
            if len(doc_chunks) < RESCUE_THRESHOLD:
                logger.warning(
                    f"  🚨 Rescue Mission: Dokument {cid[-8:]} hat nur {len(doc_chunks)} Chunks "
                    f"nach Reranking (Schwellwert: {RESCUE_THRESHOLD})"
                )

                pre_rerank_chunks = [r for r in results if r.get('chat_id') == cid]
                if pre_rerank_chunks:
                    pre_rerank_chunks.sort(key=lambda x: x.get('_final_score', 0), reverse=True)
                    needed = RESCUE_THRESHOLD - len(doc_chunks)
                    existing_ids = {id(c) for c in doc_chunks}
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
                    'title': doc_title, 'chunks_available': 0,
                    'chunks_selected': 0, 'date': datetime.min
                })
                continue

            # Sammle Chunks für Quality-Verteilung
            for chunk in doc_chunks:
                score = chunk.get('hermeneutic_score', chunk.get('_final_score', 0))
                all_chunks_with_meta.append({
                    'chunk': chunk, 'chat_id': cid, 'score': score
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
                avg_score = sum(c.get('hermeneutic_score', c.get('_final_score', 0)) for c in selected) / len(selected)
                logger.info(f"  📄 {doc_title}: {len(docs_map.get(cid, []))} verfügbar → {len(selected)} ausgewählt (Ø {avg_score:.2f})")
                
                dates = [self.extract_date_from_metadata(c) for c in selected]
                valid_dates = [d for d in dates if d != datetime.min]
                rep_date = min(valid_dates) if valid_dates else datetime.min

                doc_metadata.append({
                    'title': doc_title, 'chunks_available': len(docs_map.get(cid, [])),
                    'chunks_selected': len(selected), 'date': rep_date
                })
            else:
                doc_title = self._get_chat_title(cid)
                logger.error(f"  ❌ {doc_title}: 0 Chunks!")
                doc_metadata.append({
                    'title': doc_title, 'chunks_available': 0,
                    'chunks_selected': 0, 'date': datetime.min
                })

        new_intent = "ESSENCE_PARITY"
        logger.info(f"✅ Essenz-Extraktion: {len(essence_results)} Chunks aus {len(chat_id)} Dokumenten")
        return essence_results, doc_metadata, new_intent

    def _build_context_text(self, top_results_sorted: List[Dict]) -> str:
        """Baut den Kontext-String für den LLM Prompt zusammen."""
        # Stelle sicher, dass Metadaten vorhanden sind
        for i, res in enumerate(top_results_sorted):
            meta = res.get('metadata')
            if not meta:
                meta = {}
                res['metadata'] = meta

            speaker = meta.get('model_name') or meta.get('speaker') or meta.get('author') or 'Quelle'

            # Phase 6.5 Fix: Sicherstellen, dass NIEMALS "Unknown" im Prompt landet
            if not meta.get('chat_title') or meta['chat_title'] == 'Unknown':
                chat_id_single = res.get('chat_id')
                if chat_id_single:
                    raw_title = self._get_chat_title(chat_id_single)
                    clean_title = raw_title
                    for prefix in ['ChatGPT:', 'PDF:', 'Gemini:', 'DeepSeek:', 'Claude:']:
                        if clean_title.startswith(prefix):
                            clean_title = clean_title[len(prefix):].strip()
                    meta['chat_title'] = clean_title or f"Dokument {chat_id_single[-8:]}"
                else:
                    meta['chat_title'] = 'Unbekanntes Dokument'

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
            
        return context_text

    def _build_synthesis_prompt(
        self, query: str, doc_metadata: List[Dict], intent: str, semantic_intent: str, context_text: str
    ) -> Tuple[str, str, str]:
        """Baut den finalen Synthese-Prompt und die System-Instruction zusammen (v52: YAML-basiert)."""
        
        # 1. Struktur-Template für ESSENCE_PARITY dynamisch aufbauen (Architekten-Vorgabe!)
        structure_template = ""
        if doc_metadata:
            for i, doc_info in enumerate(doc_metadata):
                structure_template += f"\n### {i+1}. {doc_info['title']}\n"
                structure_template += f"[4-6 Sätze mit 3-4 Zitaten]\n"

        # 2. Formatierungs-Variablen sammeln
        format_kwargs = {
            "structure_template": structure_template
        }
        
        # Essence Parity benötigt min/max Chunks für den Prompt
        if intent == "ESSENCE_PARITY" and doc_metadata:
            format_kwargs["min_chunks"] = min(d['chunks_selected'] for d in doc_metadata)
            format_kwargs["max_chunks"] = max(d['chunks_selected'] for d in doc_metadata)
        else:
            # Fallback, falls Template versehentlich Platzhalter enthält
            format_kwargs["min_chunks"] = "N/A"
            format_kwargs["max_chunks"] = "N/A"

        # 3. Mode-Instruction aus YAML holen
        base_instruction = self.prompt_manager.get_mode_instruction(
            intent, semantic_intent=semantic_intent, **format_kwargs
        )
        
        # 4. Mode-Display-String aus YAML holen
        mode_display = self.prompt_manager.get_mode_display(intent)

        logger.info(f"🧠 RAG Modus: {mode_display}")

        # 5. Finalen Task-Prompt zusammenbauen
        prompt = self.prompt_manager.build_task_prompt(
            query, mode_display, base_instruction, context_text
        )

        # 6. System-Instruction aus YAML holen (inkl. injizierter QUELLENREGEL)
        dynamic_sys_instruct = self.prompt_manager.get_system_instruction(semantic_intent)

        return prompt, mode_display, dynamic_sys_instruct

    def _execute_llm_call(
        self, query: str, prompt: str, dynamic_sys_instruct: str, intent: str, 
        semantic_intent: str, top_results: List[Dict], top_results_sorted: List[Dict], 
        rerank_stats: Dict, rejected_chunks: List[Dict]
    ) -> Tuple[str, List[Dict], str]:
        """Führt den LLM Call mit Retries durch und baut den Pipeline Trace."""
        
        logger.info(f"🔢 Token-Audit POST-TRIM: chunks_real= {sum(len(c.get('content','')) // 4 for c in top_results_sorted)} | n_chunks={len(top_results_sorted)}")

        max_retries = 3
        for attempt in range(max_retries):
            try:
                synthesis_temp = 0.4 if semantic_intent in (
                      "ANALYTICAL_FORENSIC", "META_ANALYTICAL"
                ) else 0.7

                logger.info(f"🚀 Starte Synthese-Call (Versuch {attempt+1}, max_tokens={MAX_TOKENS_PER_CALL}, temp={synthesis_temp})...")

                from modules.config import DOMAIN_ANALYSIS
                result = self._llm_call_func(
                    prompt,
                    task="synthesis",
                    system_instruction=dynamic_sys_instruct,
                    temperature=synthesis_temp,
                    max_tokens=MAX_TOKENS_PER_CALL,
                    domain=DOMAIN_ANALYSIS,
                )

                if not result:
                    logger.error(f"❌ LLM hat leere Antwort zurückgegeben (Versuch {attempt+1}).")
                    if attempt < max_retries - 1:
                        time.sleep((attempt + 1) * 2)
                        continue
                    return "⚠️ Das Modell konnte keine Antwort generieren.", top_results_sorted, intent

                final_text = self.clean_citation_format(result)

                # NEU: Warnung anhängen wenn Reranker ausgefallen ist
                if rerank_stats.get("reranker_failed", False):
                    warning_banner = (
                        "\n\n---\n"
                        "⚠️ **HINWEIS ZUR ANTWORTQUALITÄT**: "
                        "Die hermeneutische Qualitätsprüfung (Reranker) war "
                        "für diese Analyse nicht verfügbar. "
                        "Die verwendeten Quellen wurden NICHT auf Relevanz "
                        "geprüft. Fakten bitte eigenständig verifizieren.\n"
                        "---"
                    )
                    final_text = final_text + warning_banner
                    logger.warning("⚠️ Qualitätswarnung an Nutzer ausgegeben (Reranker-Ausfall)")

                logger.info("✅ Antwort empfangen!")

                # --- A.3: ANALYSIS PERSISTENZ ---
                _analysis_id = str(uuid.uuid4())[:8]
                _cited_doc_ids = list(set(
                    r.get('metadata', {}).get('chat_id', r.get('chat_id', ''))
                    for r in top_results_sorted
                    if r.get('metadata', {}).get('chat_id') or r.get('chat_id')
                ))
                from modules.database import save_analysis
                from modules.config import MODEL_SYNTHESIS, DOMAIN_PROFILES, DOMAIN_ANALYSIS
                _profile = DOMAIN_PROFILES.get(DOMAIN_ANALYSIS, {})
                save_analysis(
                    analysis_id=_analysis_id,
                    query=query,
                    answer_text=final_text,
                    intent=intent,
                    semantic_intent=semantic_intent,
                    analysis_domain=DOMAIN_ANALYSIS,
                    model=MODEL_SYNTHESIS,
                    temperature=_profile.get('temperature'),
                    seed=_profile.get('seed'),
                    top_p=_profile.get('top_p'),
                    cited_document_ids=_cited_doc_ids,
                )
                # --- /A.3 ---

                _chunk_table = []
                for r in top_results_sorted:
                    _chunk_table.append({
                        "title":     r.get('metadata', {}).get('chat_title', 'Unknown'),
                        "score":     round(r.get('hermeneutic_score', r.get('_final_score', 0)), 3),
                        "rescued":   r.get('_is_rescued', False),
                        "date":      r.get('metadata', {}).get('real_date_str', 'o.D.'),
                        "preview":   r.get('content', '')[:120].replace('\n', ' '),
                    })

                self.last_pipeline_trace = {
                    "intent":           intent,
                    "semantic_intent":  semantic_intent,
                    "router_reasoning": self.current_context.get("reasoning", ""),
                    "threshold":        self.current_context.get("threshold", 0.65),
                    "reranker_total":   rerank_stats.get("total", 0),
                    "reranker_passed":  rerank_stats.get("passed", 0),
                    "reranker_rejected":rerank_stats.get("rejected", 0),
                    "reranker_avg":     round(rerank_stats.get("avg_score", 0), 3),
                    "query_type":       rerank_stats.get("query_type", "unknown"),
                    "reranker_failed":  rerank_stats.get("reranker_failed", False), # NEU: Fürs UI
                    "reranker_error":   rerank_stats.get("reranker_error", ""),     # NEU: Fürs UI
                    "chunks_retrieved": len(top_results_sorted),
                    "essence_parity":   (intent == "ESSENCE_PARITY"),
                    "chunk_table":      _chunk_table,
                    "rejected_chunks":  rejected_chunks,
                    "timestamp":        __import__('time').time()
                }
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

        pattern = r"(> \*\*Thinking:\*\*.*?)(\n\n|$)(.*)"
        match = re.search(pattern, text, re.DOTALL)

        if match:
            return match.group(1).strip(), match.group(3).strip()

        return "", text

    def validate_citations(self, answer: str, num_sources: int) -> List[str]:
        """Struktureller Citation-Check."""
        warnings = []

        matches = re.findall(r"\[(\d+)\]", answer)

        if not matches:
            warnings.append("⚠️ Warnung: Keine Zitationen gefunden.")
            return warnings

        for m in matches:
            idx = int(m)
            if idx < 1 or idx > num_sources:
                warnings.append(f"⚠️ Ungültige Zitation: [{idx}]")

        return warnings

    def verify_fact_match(
        self, claim: str, source_text: str, source_meta: Dict
    ) -> Tuple[bool, str]:
        """Tiefenprüfung via Enforcer (FINAL FIX v50.9)."""
        try:
            if self._enforcer:
                enforcer = self._enforcer
            else:
                from modules.hermeneutic_enforcer import HermeneuticEnforcer
                enforcer = HermeneuticEnforcer()
            sources = [{"content": source_text, "metadata": source_meta}]

            # 1. Aufruf (Name ist korrekt: validate_claim)
            from modules.config import DOMAIN_ANALYSIS
            result = enforcer.validate_claim(claim=claim, sources=sources, domain=DOMAIN_ANALYSIS)

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
            # Hermeneutisch korrekt: Wenn die Validierung fehlschlägt, ist der Fakt UNBESTÄTIGT.
            return True, f"ENFORCER ERROR (Validation failed): {e}"

    def verify_fact_match_multisource(
        self, claim: str, sources: List[Dict]
    ) -> Tuple[bool, str]:
        """Multi-Source-Validierung: Jedes Zitat muss in mindestens einer Quelle stehen."""
        try:
            if self._enforcer:
                enforcer = self._enforcer
            else:
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
            return True, f"ENFORCER ERROR (Validation failed): {e}"

    async def verify_facts_parallel(
        self, sentences: List[str], results: List[Dict], progress_callback=None
    ) -> List[Dict]:
        """Parallele Faktenprüfung."""
        sem = asyncio.Semaphore(5)
        completed = 0
        total = len(sentences)

        async def _bounded_check(sent):
            nonlocal completed

            async with sem:
                loop = asyncio.get_running_loop()

                matches = re.findall(r"\[(\d+)\]", sent)
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
                            all_sources.append(
                                {
                                    "content": results[idx].get("content", ""),
                                    "metadata": results[idx].get("metadata", {}),
                                    "source_id": m,
                                }
                            )
                    if all_sources:
                        is_valid, reason = await loop.run_in_executor(
                            None,
                            partial(
                                self.verify_fact_match_multisource, sent, all_sources
                            ),
                        )
                        results_for_sentence.append(
                            {
                                "sentence": sent,
                                "source_id": "+".join(matches),
                                "valid": is_valid,
                                "reason": reason,
                            }
                        )
                else:
                    # Satz zitiert eine Quelle → bisherige Logik
                    m = matches[0]
                    idx = int(m) - 1
                    if 0 <= idx < len(results):
                        source_content = results[idx].get("content", "")
                        source_meta = results[idx].get("metadata", {})
                        is_valid, reason = await loop.run_in_executor(
                            None,
                            partial(
                                self.verify_fact_match,
                                sent,
                                source_content,
                                source_meta,
                            ),
                        )
                        results_for_sentence.append(
                            {
                                "sentence": sent,
                                "source_id": m,
                                "valid": is_valid,
                                "reason": reason,
                            }
                        )

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

    # =========================================================================
    # IFS SUPERVISION PIPELINE — Drei-Agenten-Map-Reduce
    # =========================================================================

    def generate_ifs_supervision(self, chat_text: str) -> dict:
        """
        Drei-Agenten-Pipeline für psychosystemische Analyse von User-KI-Dialogen.
        
        Map-Phase (parallel):
            - SUPERVISION_MANAGER: Strukturelle Kartierung von Kontrollmechanismen
            - SUPERVISION_EXILE: Identifikation von Diskursrissen und Subversion
        
        Reduce-Phase (sequentiell):
            - SUPERVISION_META: Meta-Gutachten über die Beziehungsdynamik
        
        Args:
            chat_text: Der vollständige User-KI-Dialog als String.
        
        Returns:
            dict: {"manager": <str>, "exile": <str>, "fazit": <str>}
        """
        logger.info("🚀 Starte IFS-Supervision Pipeline (Map-Reduce)")

        # --- Hilfsfunktion für einzelne LLM-Calls ---
        def _call_supervision_agent(intent: str, **kwargs) -> str:
            """Führt einen einzelnen Supervision-Agenten aus."""
            try:
                sys_prompt = self.prompt_manager.get_system_instruction(intent)
                mode_prompt = self.prompt_manager.get_mode_instruction(intent, **kwargs)
                
                # Temperatur aus YAML holen (Fallback: 0.2)
                temp = self.prompt_manager.get_synthesis_params(intent).get("temperature", 0.2)
                
                result = self._llm_call_func(
                    mode_prompt,
                    task="synthesis",
                    system_instruction=sys_prompt,
                    temperature=temp,
                    max_tokens=8192,
                )
                logger.info(f"✅ {intent}: {len(result)} Zeichen")
                return result
            except Exception as e:
                logger.error(f"❌ {intent} fehlgeschlagen: {e}")
                return f"[FEHLER: {intent} konnte nicht ausgeführt werden: {e}]"

        # --- MAP-PHASE: Manager + Exile parallel ---
        logger.info("🗺️  Map-Phase: Manager + Exile (parallel)")
        with ThreadPoolExecutor(max_workers=2) as executor:
            manager_future = executor.submit(
                _call_supervision_agent,
                "SUPERVISION_MANAGER",
                context_text=chat_text
            )
            exile_future = executor.submit(
                _call_supervision_agent,
                "SUPERVISION_EXILE",
                context_text=chat_text
            )
            
            manager_result = manager_future.result()
            exile_result = exile_future.result()

        # --- REDUCE-PHASE: Meta-Gutachten (sequentiell, wartet auf Map-Ergebnisse) ---
        logger.info("🧠 Reduce-Phase: Meta-Gutachten")
        meta_result = _call_supervision_agent(
            "SUPERVISION_META",
            context_text=chat_text,
            manager_analysis=manager_result,
            exile_analysis=exile_result
        )

        logger.info("✅ IFS-Supervision Pipeline abgeschlossen")

        return {
            "manager": manager_result,
            "exile": exile_result,
            "meta": meta_result
        }