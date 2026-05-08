# modules/hermeneutic_reranker.py
"""Hermeneutic Reranker: LLM-as-Judge für RAG-Systeme.

v51 (Phase 4): BATCH-TURBO
- Bewertung in Batches von 5 Chunks (5x weniger API Calls!)
- Sequentielle Abarbeitung (LM Studio sicher)
- Unzerstörbarer 2-Stufen-Fallback: Batch-Fehler → Einzelbewertung → 0.0
- Strikte JSON-Validierung mit C1..C5 IDs

ÄNDERUNGSHISTORIE:
- v51: Batch-Reranking implementiert (Phase 4)
- v50.9-local: Migration auf llm_wrapper
"""

import logging
import re
from typing import List, Dict, Tuple, Optional

from modules.llm_wrapper import llm_call, llm_call_json, llm_call_json_structured
from modules.llm_instructions import RERANKER_INSTRUCTION
from modules.config import RERANKER_BATCH_SIZE
from pydantic import BaseModel, Field
from typing import List

# --- JSON SCHEMA FÜR STRUCTURED OUTPUTS (Die Zwangsjacke) ---
class ChunkEvaluation(BaseModel):
    chunk_id: str = Field(description="Die ID des Chunks, z.B. C1, C2, C3")
    score: float = Field(description="Relevanz-Score zwischen 0.0 und 1.0", ge=0.0, le=1.0)

class RerankerBatchResult(BaseModel):
    evaluations: List[ChunkEvaluation] = Field(description="Liste der Bewertungsergebnisse für jeden Chunk")

logger = logging.getLogger(__name__)

# Batch-Konfiguration
# BATCH_SIZE wird jetzt aus config.py geladen (RERANKER_BATCH_SIZE)
class HermeneuticReranker:
    """Filtert semantische Treffer durch hermeneutische LLM-Validierung."""

    def __init__(self, threshold: float = 0.7):
        self.threshold = threshold
        logger.info("✅ HermeneuticReranker initialized (BATCH-TURBO v51).")

    def _detect_query_type(self, query: str) -> str:
        """Erkennt Query-Typ für angepasste Bewertung."""
        literary_signals = [
            'gedicht', 'übersetzung', 'musikalität', 'rhythmus', 'metapher',
            'poem', 'poetry', 'translation', 'verse', 'stanza',
            'поэзия', 'стих', 'перевод', 'poesia', 'verso', 'tradução',
            'essay', 'essai', 'эссе', 'ensaio', 'gattung', 'genre', 'жанр',
            'literarische analyse', 'literary analysis', 'литературный анализ',
            'stilistik', 'style', 'стиль', 'prosa', 'prose', 'проза',
            'definition', 'definiert', 'defines', 'text', 'texte', 'текст',
            'autor', 'author', 'автор', 'adorno', 'chesterton', 'valéry',
            'valery', 'шкловский', 'shklovskii', 'shklovsky', 'тынянов',
            'tynyanov', 'tynianov', 'pessoa', 'celan', 'ayer', 'voltaire'
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

    # =========================================================================
    # LEVEL 2 FALLBACK: Einzel-Bewertung (Unverändert)
    # =========================================================================
    def judge_relevance(self, query: str, chunk: str, chunk_meta: Dict, intent: str = None) -> float:
        """Bewertet einen einzelnen Chunk. Dient als Fallback, wenn Batching scheitert."""
        speaker = chunk_meta.get('metadata', {}).get('model_name', 'Unbekannt')
        chat_title = chunk_meta.get('chat_title', 'Unbekannt')
        
        if intent:
            query_type = intent.lower()
            if query_type in ["analytical_forensic", "meta_analytical"]: query_type = "analytical"
            if query_type not in ["literary", "analytical", "factual"]: query_type = "factual"
        else:
            query_type = self._detect_query_type(query)

        chunk_short = chunk[:800] + ("..." if len(chunk) > 800 else "")

        # Prompt für Einzel-Bewertung
        prompt = f"""FRAGE: "{query}"

TEXT-CHUNK (von {speaker}, Chat: "{chat_title}"): {chunk_short}

BEWERTUNGS-KONTEXT: Query-Typ ist {query_type.upper()}.
BEWERTUNGS-SKALA: 0.8-1.0 (Direkt), 0.6-0.8 (Kontext), 0.4-0.6 (Tangential), 0.0-0.4 (Irrelevant)

Bewerte die Relevanz (0.0-1.0): """

        try:
            reranker_temp = 0.1 if (intent and intent.lower() in ["analytical_forensic", "analytical", "meta_analytical"]) else 0.3
            from modules.config import DOMAIN_ANALYSIS
            score_text = llm_call(prompt, task="reranker", system_instruction=RERANKER_INSTRUCTION, temperature=reranker_temp, domain=DOMAIN_ANALYSIS)
            score_clean = re.sub(r'(\d+)[.,]\s+(\d+)', r'\1.\2', score_text.strip())
            match = re.search(r'(\d+[.,]\d+)', score_clean)
            if match:
                return max(0.0, min(1.0, float(match.group(1).replace(',', '.'))))
            return 0.5
        except Exception as e:
            logger.error(f"❌ Single-Reranker Fallback Fehler: {e}")
            return 0.0

    # =========================================================================
    # LEVEL 1: BATCH-BEWERTUNG (Der Turbo - VERTEX FIX)
    # =========================================================================
    def _judge_batch(self, query: str, batch_candidates: List[Dict], query_type: str, intent: str) -> Optional[List[Tuple[Dict, float]]]:
        """Bewertet Chunks via Structured Outputs (100% valides JSON garantiert)."""
        
        chunks_text = ""
        batch_map = {}
        
        # Chunks mit C1..Cx IDs formatieren
        for i, cand in enumerate(batch_candidates):
            cid = f"C{i+1}"
            batch_map[cid] = cand
            
            speaker = cand.get('metadata', {}).get('model_name', 'Unbekannt')
            chat_title = cand.get('chat_title', 'Unbekannt')
            content = cand.get('content', '')[:800]
            
            chunks_text += f"\n--- START CHUNK_{cid} (von {speaker}, Chat: \"{chat_title}\") ---\n"
            chunks_text += content
            chunks_text += f"\n--- ENDE CHUNK_{cid} ---\n"

        # Skala basierend auf Query-Typ anpassen
        scale_info = "0.8-1.0 (Direkt), 0.6-0.8 (Kontext), 0.4-0.6 (Tangential), 0.0-0.4 (Irrelevant)"
        if query_type == "literary":
            scale_info = "0.9-1.0 (Original), 0.7-0.9 (Theorie), 0.4-0.7 (Tangential), 0.0-0.4 (Irrelevant)"

        # WICHTIG: Keine "Nur JSON!"-Befehle mehr nötig. Das Schema erzwingt es.
        prompt = f"""FRAGE: "{query}"

BEWERTUNGS-KONTEXT: Query-Typ ist {query_type.upper()}.
BEWERTUNGS-SKALA: {scale_info}

ZU BEWERTENDE QUELLEN:{chunks_text}

AUFGABE: Bewerte die Relevanz JEDES Chunks für die FRAGE."""

        try:
            reranker_temp = 0.1 if (intent and intent.lower() in ["analytical_forensic", "analytical", "meta_analytical"]) else 0.3
            
            # NEU: Structured Output Call mit Pydantic Schema
            result_dict = llm_call_json_structured(
                prompt=prompt,
                response_schema=RerankerBatchResult,
                system_instruction=RERANKER_INSTRUCTION,
                temperature=reranker_temp,
                task="reranker"
            )

            if not result_dict or "evaluations" not in result_dict:
                logger.warning(f"⚠️ Structured Output leer/ungültig. Triggering Fallback.")
                return None

            # Scores zuordnen (sauberer Dict-Zugriff, kein String-Rating mehr)
            parsed_results = []
            found_ids = set()
            
            for item in result_dict.get("evaluations", []):
                chunk_id = item.get("chunk_id")
                score_val = item.get("score")
                
                if chunk_id in batch_map and isinstance(score_val, (int, float)):
                    cand = batch_map[chunk_id]
                    score = max(0.0, min(1.0, float(score_val)))
                    parsed_results.append((cand, score))
                    found_ids.add(chunk_id)

            # Strenge Prüfung: Hat das Modell alle Chunks bewertet?
            if len(found_ids) != len(batch_candidates):
                missing = set(batch_map.keys()) - found_ids
                logger.warning(f"⚠️ Structured Output unvollständig (fehlend: {missing}). Triggering Fallback.")
                return None

            return parsed_results

        except Exception as e:
            logger.error(f"❌ Structured Batch-Judge Fehler: {e}")
            return None

    # =========================================================================
    # MAIN METHOD: Rerank mit Parallel Processing (Phase 6.5 Turbo)
    # =========================================================================
    def rerank(self, query: str, candidates: List[Dict], max_results: int = 25, intent: str = None) -> Tuple[List[Dict], Dict]:
        """Filtert Kandidaten durch LLM-Judge (PARALLEL BATCH v52)."""
        if not candidates:
            return [], {"total": 0, "passed": 0, "rejected": 0, "query_type": "unknown"}

        # Query-Typ erkennen
        if intent:
            query_type = intent.lower()
            if query_type in ["analytical_forensic", "meta_analytical"]: 
                query_type = "analytical"
            if query_type not in ["literary", "analytical", "factual"]: 
                query_type = "factual"
        else:
            query_type = self._detect_query_type(query)

        logger.info(
            f"🔍 Reranker (PARALLEL-BATCH): "
            f"Prüfe {len(candidates)} Kandidaten (Typ: {query_type.upper()})..."
        )

        # 1. VIP-SCHUTZ: Gerettete Chunks sofort durchlassen
        filtered = []
        normal_candidates = []
        for cand in candidates:
            if cand.get("_is_rescued", False):
                cand["hermeneutic_score"] = 1.0
                filtered.append(cand)
            else:
                normal_candidates.append(cand)

        # 2. BATCHES VORBEREITEN
        batches = []
        for i in range(0, len(normal_candidates), RERANKER_BATCH_SIZE):
            batches.append(normal_candidates[i:i+RERANKER_BATCH_SIZE])

        # 3. PARALLELE AUSFÜHRUNG (ThreadPool — ROBUSTE VERSION)
        from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError

        total_batches = len(batches)
        successful_batches = 0
        failed_batches = 0
        FUTURE_TIMEOUT = 60  # Sekunden pro Batch — verhindert Hängen
        MAX_FAILURE_RATE = 0.5

        executor = None
        try:
            executor = ThreadPoolExecutor(max_workers=3)

            # Future-Objekte erstellen
            future_to_batch = {
                executor.submit(self._judge_batch, query, batch, query_type, intent): idx 
                for idx, batch in enumerate(batches)
            }

            processed = 0
            rejected_count = 0

            # Ergebnisse abholen, sobald ein Batch fertig ist
            for future in as_completed(future_to_batch, timeout=FUTURE_TIMEOUT * total_batches):
                batch_idx = future_to_batch[future]
                batch = batches[batch_idx]

                try:
                    # Timeout pro Future — verhindert endloses Warten
                    batch_result = future.result(timeout=FUTURE_TIMEOUT)

                    if batch_result is not None:
                        successful_batches += 1
                        for cand, score in batch_result:
                            cand["hermeneutic_score"] = score
                            if score >= self.threshold:
                                filtered.append(cand)
                            else:
                                rejected_count += 1
                    else:
                        failed_batches += 1
                        logger.warning(f"⚡ Batch {batch_idx} fehlgeschlagen. Nutze _final_score.")
                        for cand in batch:
                            score = cand.get('_final_score', 0.5)
                            cand["hermeneutic_score"] = score
                            if score >= self.threshold: filtered.append(cand)
                            else: rejected_count += 1

                except TimeoutError:
                    failed_batches += 1
                    logger.error(f"⏱️  Batch {batch_idx} Timeout nach {FUTURE_TIMEOUT}s")
                    for cand in batch:
                        score = cand.get('_final_score', 0.5)
                        cand["hermeneutic_score"] = score
                        if score >= self.threshold: filtered.append(cand)
                        else: rejected_count += 1

                except Exception as e:
                    failed_batches += 1
                    logger.error(f"❌ Parallel Batch Fehler: {e}")
                    for cand in batch:
                        score = cand.get('_final_score', 0.5)
                        cand["hermeneutic_score"] = score
                        if score >= self.threshold: filtered.append(cand)
                        else: rejected_count += 1

                # Progress-Logging
                processed += len(batch)
                if processed % 10 == 0 or processed == len(normal_candidates):
                    logger.info(f"   ... {processed}/{len(normal_candidates)} geprüft, "
                                f"{len(filtered)} bestanden "
                                f"({successful_batches}/{total_batches} Batches OK)")

            # Kritische Fehlerrate erkannt — voller Fallback
            if total_batches > 0 and (failed_batches / total_batches) > MAX_FAILURE_RATE:
                logger.critical(
                    f"🚨 KRITISCH: {failed_batches}/{total_batches} Batches fehlgeschlagen "
                    f"({failed_batches/total_batches*100:.0f}%). "
                    f"HermeneuticReranker ist instabil."
                )

        except Exception as e:
            logger.error(f"❌ ThreadPool komplett fehlgeschlagen: {e}")
            # Kompletter Fallback: Alle Candidates mit _final_score
            for cand in normal_candidates:
                score = cand.get('_final_score', 0.5)
                cand["hermeneutic_score"] = score
                if score >= self.threshold: filtered.append(cand)
                else: rejected_count += 1

        finally:
            # Sicherstellen, dass Executor heruntergefahren wird, ohne zu blockieren!
            if executor is not None:
                executor.shutdown(wait=False)
                logger.debug("✅ ThreadPool Executor sicher heruntergefahren")

        # Sortiere nach Score
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