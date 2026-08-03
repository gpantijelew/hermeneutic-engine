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
    get_model_for_task,
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
from modules.synthesis_validator import run_three_phase_synthesis
from modules.stilistic_lab_pipeline import run_stilistic_lab
logger = logging.getLogger(__name__)

# Imbalance-Schwellwerte (Refactor 6/2026: konsolidiert aus check_imbalance_only + _calculate_imbalance)
_IMBALANCE_CRITICAL = 10
_IMBALANCE_INFO = 5



# ── SPRACH-BINDUNG für STILISIERUNG (Patch 2026-07-11) ───────────────────────
import re as _re_lang_patch

_CYRILLIC_RE_PATCH = _re_lang_patch.compile(r'[А-Яа-яЁё]')
_LATIN_RE_PATCH = _re_lang_patch.compile(r'[A-Za-zÄÖÜäöüß]')

_LANGUAGE_BINDINGS_PATCH = {
    "ru": (
        "SPRACH-BINDUNG (ABSOLUT):\n"
        "Der Originaltext ist auf Russisch. Dein Output MUSS auf Russisch sein.\n"
        "Übersetze NICHT. Behalte die russische Sprache throughout bei.\n"
        "Namen lateinischer Autoren (Eco, Sternhell etc.) können in lateinischer\n"
        "Originalform bleiben, wenn der Originaltext sie so nennt.\n"
        "Zitate aus dem Original bleiben in der Originalsprache.\n"
    ),
    "de": (
        "SPRACH-BINDUNG (ABSOLUT):\n"
        "Der Originaltext ist auf Deutsch. Dein Output MUSS auf Deutsch sein.\n"
        "Behalte die deutsche Sprache throughout bei.\n"
        "Fremdsprachige Zitate und Eigennamen bleiben in der Originalsprache.\n"
    ),
}


def _detect_language_patch(text: str) -> str:
    """Erkennt die dominanteste Sprache des Textes anhand des Skript-Anteils."""
    if not text or len(text) < 50:
        return "de"
    sample = text[:2000]
    cyrillic = len(_CYRILLIC_RE_PATCH.findall(sample))
    latin = len(_LATIN_RE_PATCH.findall(sample))
    total = cyrillic + latin
    if total == 0:
        return "de"
    if cyrillic / total > 0.30:
        return "ru"
    return "de"


def _get_language_binding(text: str) -> str:
    """Gibt die SPRACH-BINDUNG-Instruktion für den Input-Text zurück."""
    lang = _detect_language_patch(text)
    return _LANGUAGE_BINDINGS_PATCH.get(lang, _LANGUAGE_BINDINGS_PATCH["de"])


# ── Ende SPRACH-BINDUNG Patch ────────────────────────────────────────────────

def _compute_imbalance(counts):
    """Berechnet Imbalance-Severity aus Dokument-Haeufigkeiten.

    Bei weniger als 2 Dokumenten: keine Severity (kein Vergleich moeglich).
    Schwellwerte: ratio >= _IMBALANCE_CRITICAL = critical,
                  ratio >= _IMBALANCE_INFO = info.

    Returns:
        (ratio, severity) Tupel. ratio=1.0 bei weniger als 2 Dokumenten.
    """
    if len(counts) < 2:
        return 1.0, "none"
    max_c = max(counts)
    min_c = min(counts)
    ratio = max_c / min_c if min_c > 0 else 0
    severity = "none"
    if ratio >= _IMBALANCE_CRITICAL:
        severity = "critical"
    elif ratio >= _IMBALANCE_INFO:
        severity = "info"
    return ratio, severity
class CitationRAG:
    # ── v58: Deklaratives Set von Intents mit eigenen mode_instructions ──
    # Diese Intents nutzen ihr EIGENES YAML-Template statt ESSENCE_PARITY.
    # Neue Intents mit eigenem Template: hier hinzufügen. Fertig.
    STRUCTURE_OVERRIDES = {"STILISTIC", "STILISTIC_DEEPENING", "META_ANALYTICAL", "STILISTIC_LAB"}
    def __init__(
        self,
        vector_store: LocalVectorStore = None,
        model_name: str = get_model_for_task("synthesis"),
        router = None,
        reranker_factory = None,
        enforcer = None,
        llm_call_func = None,
    ):
        if vector_store is None:
            from modules.database import get_db_connection
            db = get_db_connection()
            vector_store = LocalVectorStore(db)
    # ======================================================================
    # === SYNTHESIS ENGINE ===
    # ======================================================================
    # Methoden: extract_quotes, extract_quotes_per_document,
    #           _build_context_text, _build_zitat_pool, _distill_style_per_document,
    #           _build_stil_profile_block, _group_sources_by_document,
    #           _build_synthesis_prompt, _execute_llm_call
    # Zustand:  self._extraction_failures (WRITE in extract_quotes_per_document),
    #           self.last_pipeline_trace (WRITE in _execute_llm_call),
    #           self.current_context (READ), self._semantic_intent (READ),
    #           self.prompt_manager (READ), self._llm_call_func (READ)
    # Zukunft:  Kern des kuenftigen SynthesisEngine-Moduls
    # ======================================================================
        self.vector_store = vector_store
        self.model_name = model_name
        self.router = router or HermeneuticRouter()
        self.synthesizer = EvidenceFirstSynthesizer(model_name)
        # UI-Zugriff für Imbalance-Daten
        self.last_imbalance_info = None
        self.last_pipeline_trace = None
        self.current_context = {"intent": "FACTUAL", "threshold": 0.65}
        self._extraction_failures = []  # v57: Trackt Quellen mit fehlgeschlagener Zitat-Extraktion
        # v59.3-fix (Kimi Audit C2): _semantic_intent initialisieren, bevor _ensure_router_context() läuft.
        self._semantic_intent = "FACTUAL"
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
    # ======================================================================
    # ZUSTANDSFLUSS-TABELLE (Patch: Kommentar-Anker, kein Code-Change)
    # ======================================================================
    # Diese Tabelle dokumentiert, welche self.*-Attribute wo gesetzt
    # und wo konsumiert werden. Sie ist die Landkarte fuer jeden
    # kuenftigen Edit — und die Voraussetzung fuer einen sicheren Split.
    #
    # LEGENDE:
    #   INIT  = in __init__ initialisiert
    #   WRITE = wird dort gesetzt (neuer Wert)
    #   READ  = wird dort gelesen (Wert verwendet)
    #
    # Attribut                    | INIT          | WRITE                                    | READ
    # ----------------------------|---------------|------------------------------------------|------------------------------------------
    # self.vector_store           | __init__      | —                                        | retrieve_with_rrf, _apply_essence_parity (Rescue Mission)
    # self.model_name             | __init__      | —                                        | __init__ (EvidenceFirstSynthesizer)
    # self.router                 | __init__      | —                                        | _ensure_router_context, retrieve_with_rrf, check_imbalance_only
    # self.synthesizer            | __init__      | —                                        | (legacy, nicht aktiv in generate_answer)
    # self.prompt_manager         | __init__      | —                                        | extract_quotes, _build_synthesis_prompt, _execute_llm_call, generate_ifs_supervision, generate_synthesis_best_of, generate_agentic_synthesis
    # self._llm_call_func        | __init__      | —                                        | extract_quotes, _execute_llm_call, generate_synthesis_best_of, generate_agentic_synthesis, expand_query_multilingual, _distill_style_per_document, _run_phase2_phase3, generate_ifs_supervision
    # self._enforcer              | __init__      | —                                        | verify_fact_match, verify_fact_match_multisource, _run_phase2_phase3
    # self._reranker_factory      | __init__      | —                                        | _score_and_rerank, check_imbalance_only
    # self._extraction_failures   | __init__=[]   | extract_quotes_per_document               | _execute_llm_call (in last_pipeline_trace)
    # self._original_results_cache| __init__=[]   | retrieve_with_rrf                        | (fuer Debug/Rettung, nicht aktiv in generate_answer)
    # self.current_context        | __init__      | _ensure_router_context, retrieve_with_rrf, check_imbalance_only | _ensure_router_context (READ+WRITE), _score_and_rerank, _execute_llm_call (in trace)
    # self.last_imbalance_info    | __init__=None | check_imbalance_only, _calculate_imbalance| _execute_llm_call (indirekt via _apply_essence_parity), UI (analysis_tab.py)
    # self.last_pipeline_trace    | __init__=None | _execute_llm_call, _run_phase2_phase3     | UI (analysis_tab.py, pipeline_trace.py)
    # self._semantic_intent       | _ensure_..    | _ensure_router_context                   | generate_answer (STRUCTURE_OVERRIDES), _apply_essence_parity, _build_synthesis_prompt
    #
    # WICHTIGE ABHAENGIGKEITEN (fuer Split-Planung):
    # — current_context wird von 3 Methoden GESCHRIEBEN und von 3 gelesen
    # — last_pipeline_trace wird von 2 Methoden GESCHRIEBEN und vom UI gelesen
    # — _extraction_failures wird von 1 Methode GESCHRIEBEN und in _execute_llm_call gelesen
    # — _semantic_intent wird von 1 Methode GESCHRIEBEN und von 3 gelesen
    # → Diese 4 Attribute sind die Kupplungspunkte bei einem Split.
    # ======================================================================
    def _extract_number_from_title(self, title: str) -> int:
        """Extrahiert die erste Zahl aus einem Titel für die Sortierung."""
        match = re.search(r'\d+', str(title))
        return int(match.group()) if match else 999
    def _parse_extraction_result(self, result: str) -> list:
        """Parst das LLM-Ergebnis der Zitat-Extraktion.
        
        Mehrstufige Strategie:
        1. Code-Fence-Stripping
        2. _parse_json_safe (4-Pass)
        3. Partial-JSON-Rettung (truncated arrays)
        4. Dict→List Normalisierung
        
        Returns:
            Liste von Dicts oder leere Liste bei Fehlschlag
        """
        if not result:
            return []
        
        # Code-Fences strippen (Modelle liefern oft ```json ... ```)
        cleaned = result.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines)
        
        from modules.llm_wrapper import _parse_json_safe
        quotes = _parse_json_safe(cleaned, fallback=[])
        # ── Fix H.5: Partial-JSON-Rettung ──
        if not quotes and cleaned.strip().startswith("["):
            import re
            last_obj = cleaned.rfind("}")
            if last_obj > 0:
                partial = cleaned[:last_obj + 1] + "]"
                logger.info(f"🔧 Partial-JSON-Rettung: Versuche Repair nach Position {last_obj}")
                try:
                    quotes = _parse_json_safe(partial, fallback=[])
                    if quotes and isinstance(quotes, list):
                        logger.info(f"✅ Partial-JSON-Rettung: {len(quotes)} Zitate gerettet")
                except Exception:
                    logger.warning("⚠️ Partial-JSON-Rettung fehlgeschlagen")
        # Robustheit: Einzelnes Dict → Liste packen
        if isinstance(quotes, dict):
            quotes = [quotes]
        
        if not isinstance(quotes, list):
            logger.warning(f"⚠️ Quote-Extraktion: Unerwartetes Format ({type(quotes)}). Fallback.")
            return []
        
        # Basis-Validierung: Jedes Zitat muss "quelle" und "text" haben
        valid_quotes = []
        for q in quotes:
            if isinstance(q, dict) and "quelle" in q and "text" in q:
                valid_quotes.append(q)
            else:
                logger.debug(f"⚠️ Überspringe invalides Zitat: {q}")
        
        return valid_quotes
    
    def extract_quotes(self, query: str, context_text: str) -> list:
        """Phase 1: Extrahiert verlässliche Zitate aus dem Kontext.
    
        Separater LLM-Call mit einfacher Aufgabe: erkennen + kopieren.
        Reduziert False-Quotes, weil das Modell nicht gleichzeitig
        synthetisieren UND zitieren muss.
        
        v57-Fix: 1-facher Retry bei JSON-Parse-Fehlschlag.
        Das Modell produziert gelegentlich malformed JSON (insb. bei
        kyrillischen Zitaten mit unescapten Anführungszeichen).
        Ein zweiter Call mit identischem Prompt liefert in >80% der
        Fälle valides JSON — die Fehler sind nicht-deterministisch.
    
        Returns:
        Liste von Dicts: [{"quelle": int, "text": str, "relevanz": str}]
        """
        try:
            # Prompt aus YAML holen
            sys_instr = self.prompt_manager.get_system_instruction("EXTRACTION")
            task_prompt = self.prompt_manager.get_mode_instruction(
                "EXTRACTION", query=query, context_text=context_text
            )
            
            # ── Erster Versuch ──
            result = self._llm_call_func(
                task_prompt,
                task="extraction",
                system_instruction=sys_instr,
                temperature=0.15,   # Sehr niedrig — wir wollen Kopieren, nicht Kreativität
                max_tokens=8192,   # Fix H.4: 4096 reicht nicht für 18-30 Zitate
            )
            
            if not result:
                logger.warning("⚠️ Quote-Extraktion leer. Fallback: keine vorgefilterten Zitate.")
                return []
            
            valid_quotes = self._parse_extraction_result(result)
            
            # ── v57-Fix: Retry bei Totalausfall ──
            # Wenn der erste Call 0 Zitate liefert (JSON-Parse-Fehler),
            # probieren wir einmal mit leicht erhöhter Temperatur.
            # Grund: Die Fehler sind nicht-deterministisch — ein zweiter
            # Call mit identischem Prompt liefert meist valides JSON.
            if not valid_quotes:
                logger.warning(
                    "🔄 Extraction-Retry: Erster Call lieferte 0 Zitate "
                    "(wahrscheinlich JSON-Parse-Fehler). Zweiter Versuch..."
                )
                import time
                time.sleep(0.5)  # Kurze Pause um API-Rate-Limits zu respektieren
                
                result = self._llm_call_func(
                    task_prompt,
                    task="extraction",
                    system_instruction=sys_instr,
                    temperature=0.2,   # Leicht erhöht — bricht eventuelle "festsitzende" Token-Sequenzen auf
                    max_tokens=8192,
                )
                
                if result:
                    valid_quotes = self._parse_extraction_result(result)
                    if valid_quotes:
                        logger.info(f"✅ Extraction-Retry erfolgreich: {len(valid_quotes)} Zitate gerettet")
                    else:
                        logger.warning("❌ Extraction-Retry fehlgeschlagen — auch 2. Call ohne parsebares JSON")
            
            logger.info(f"📌 Quote-Extraktion: {len(valid_quotes)} Zitate aus {len(context_text)//4} Token")
            return valid_quotes
        
        except Exception as e:
            logger.error(f"❌ Quote-Extraktion fehlgeschlagen: {e}")
            return []
    # =========================================================================
    # N.1: PRO-QUELLE-EXTRAKTION (Claude-R3, Architektur-Entscheidung)
    # =========================================================================
    def extract_quotes_per_document(
        self,
        query: str,
        doc_texts: dict,
    ) -> list:
        """Pro-Dokument-Extraktion statt eines 28K-Monolith-Calls.
        
        Architektur-Entscheidung (Claude-R3, 2026-05-16):
        Bei 28K Prompt-Tokens verliert das Modell den Überblick und
        stoppt nach ~323 Completion-Tokens (3 Zitate). Die Ursache
        ist Attention-Verlust, nicht Ungehorsam.
        
        Lösung: 6 kurze Calls à ~5K statt 1 Monolith-Call à 28K.
        Jeder Call hat volle Attention auf ein Dokument.
        Die "Min 2 pro Quelle"-Regel wird tatsächlich erzwingbar.
        6 × 5K Flash-Calls sind billiger als 1 × 28K Flash-Call.
        Latenz steigt um ~3-5 Sekunden — akzeptabel.
        
        Args:
            query: Die Analyse-Frage
            doc_texts: Dict von {doc_id: context_text}
                       doc_id ist die QUELLE-Nummer (1, 2, 3, ...)
        
        Returns:
            Liste von Dicts: [{"quelle": int, "text": str, "relevanz": str}]
        """
        all_quotes = []
        extraction_failures = []  # v57: Quellen mit fehlgeschlagener Extraktion tracken
        
        for doc_id, text in doc_texts.items():
            if not text or len(text.strip()) < 50:
                logger.debug(f"⏭️ Pro-Quelle: Überspringe Quelle [{doc_id}] (zu kurz)")
                extraction_failures.append({
                    "source_id": doc_id,
                    "reason": "too_short",
                    "context_chars": len(text) if text else 0,
                })
                continue
            
            # Kürze auf ~4000 Zeichen pro Dokument (Attention-Window optimieren)
            short_context = text[:4000] if len(text) > 4000 else text
            
            # Einzelner Extraktions-Call pro Dokument
            quotes = self.extract_quotes(query, short_context)
            
            # QUELLE-ID sicherstellen — Modell könnte falsche IDs liefern
            for q in quotes:
                q["quelle"] = doc_id  # Erzwinge korrekte Quelle-ID
            
            # Warnung wenn zu wenig Zitate pro Dokument
            if len(quotes) < 2:
                logger.warning(
                    f"⚠️ Pro-Quelle: Nur {len(quotes)} Zitat(e) aus Quelle [{doc_id}] "
                    f"(Ziel: ≥2). Kontext-Länge: {len(short_context)} Zeichen"
                )
                # v57: Extraktions-Fehler tracken
                if len(quotes) == 0:
                    extraction_failures.append({
                        "source_id": doc_id,
                        "reason": "json_parse_failed",
                        "context_chars": len(short_context),
                    })
            else:
                logger.info(f"✅ Pro-Quelle: {len(quotes)} Zitate aus Quelle [{doc_id}]")
            
            all_quotes.extend(quotes)
        
        # Deduplication: Identische Zitate aus verschiedenen Calls entfernen
        seen = set()
        deduped = []
        for q in all_quotes:
            key = (q.get("quelle", 0), q.get("text", "")[:100])  # (Quelle, erste 100 Zeichen)
            if key not in seen:
                seen.add(key)
                deduped.append(q)
        
        if len(deduped) < len(all_quotes):
            logger.info(
                f"🔄 Pro-Quelle Dedup: {len(all_quotes)} → {len(deduped)} "
                f"({len(all_quotes) - len(deduped)} Duplikate entfernt)"
            )
        
        logger.info(
            f"📌 Pro-Quelle-Extraktion: {len(deduped)} Zitate aus "
            f"{len(doc_texts)} Dokumenten"
        )
        
        # v57: Extraktions-Fehler im Instanz-Attribut speichern
        # (wird von der Pipeline für Synthese-Warnung + Trace verwendet)
        self._extraction_failures = extraction_failures
        if extraction_failures:
            failed_ids = [f"[{f['source_id']}]" for f in extraction_failures]
            logger.warning(
                f"🚨 Extraktions-Fehler: {len(extraction_failures)} Quelle(n) ohne Zitate: "
                f"{', '.join(failed_ids)}"
            )
        
        return deduped
    # ======================================================================
    # === AGENTIC PIPELINE ===
    # ======================================================================
    # Methoden: generate_synthesis_best_of, generate_agentic_synthesis
    # Zustand:  self.prompt_manager (READ), self._llm_call_func (READ)
    #           Keine self.*-WRITES — zustandslos!
    # Zukunft:  Kandidat fuer eigenes AgenticPipeline-Modul (sauber trennbar)
    # ======================================================================
    def generate_synthesis_best_of(
        self,
        iteration_texts: List[str],
        intent: str = "SYNTHESIS_BEST_OF",
        source_intent: Optional[str] = None,
        temperature: float = 0.55,
        mode_labels: Optional[Dict[int, str]] = None,
    ) -> str:
        """
        Direkte Full-Context-Synthese ohne RAG-Pipeline.
        Kein Chunking, kein Retrieval, kein Trimming.
        Alle Iterationen werden als Ganzes in den Kontext geladen.
        Args:
            iteration_texts: Liste der vollständigen Iterationstexte
            intent: Intent-Name (SYNTHESIS_BEST_OF oder SYNTHESIS_BEST_OF_STILISTIC)
            temperature: LLM-Temperatur
            mode_labels: Optional Dict {1: "STILISTIC", 2: "META_ANALYTICAL", ...}
                        Wenn gesetzt, werden Modus-Tags in die Iterations-Header injiziert.
        """
        # FIX: system_instruction vom agentic intent (Rolle),
        # mode_instruction vom source_intent (was zu tun ist — STILISIERUNG etc.)
        sys_instr = self.prompt_manager.get_system_instruction(intent)
        mode_intent = source_intent if source_intent else intent
        mode_instr = self.prompt_manager.get_mode_instruction(mode_intent)
        
        # FIX: SPRACH-BINDUNG — Sprache des Originals erkennen und injizieren
        # Verhindert ungewollte Übersetzung (z.B. Russisch → Deutsch)
        if iteration_texts:
            lang_binding = _get_language_binding(iteration_texts[0])
            mode_instr = mode_instr.rstrip() + "\n\n" + lang_binding
        context = "\n\n".join(
            f"=== ITERATION {i} [{mode_labels.get(i, '')}] ===\n{text}" if mode_labels and mode_labels.get(i) else f"=== ITERATION {i} ===\n{text}"
            for i, text in enumerate(iteration_texts, 1)
        )
        prompt = f"{mode_instr}\n\nITERATIONEN:\n{context}\n\nMEISTERTEXT:"
        # Dynamisches Token-Limit: Stilisierung braucht mehr Raum für Ghostwriting
        # FIX: max_tokens basiert auf mode_intent (nicht intent), da STILISIERUNG
        # die mode_instruction ist, nicht die system_instruction
        max_tokens = MAX_TOKENS_STILISIERUNG if mode_intent == "STILISIERUNG" else 8192
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
        # FIX: source_intent wird durchgereicht — STILISIERUNG-Prompts werden geladen
        draft = self.generate_synthesis_best_of(
            iteration_texts,
            intent="AGENT_DRAFTER",
            source_intent=source_intent,
        )
        logger.info(f"✅ Agentic Schritt 1 (DRAFTER): {len(draft)} Zeichen")
        if not draft:
            return "", {"error": "DRAFTER lieferte leeren Text"}
        # --- Schritt 2: Kritik (Ohne JSON-Modus, um API-Limits zu umgehen) ---
        # FIX: STILISIERUNG_CRITIC nutzen, falls vorhanden (prüft STILISIERUNGS-Regeln)
        is_stilisierung = (source_intent == "STILISIERUNG")
        critic_sys_intent = "AGENT_CRITIC"
        critic_mode_intent = "STILISIERUNG_CRITIC" if is_stilisierung else "AGENT_CRITIC"
        critic_sys = self.prompt_manager.get_system_instruction(critic_sys_intent)
        critic_mode_instr = self.prompt_manager.get_mode_instruction(critic_mode_intent)
        # Fallback: falls STILISIERUNG_CRITIC nicht im YAML, nutze AGENT_CRITIC
        if not critic_mode_instr.strip():
            critic_mode_instr = self.prompt_manager.get_mode_instruction("AGENT_CRITIC")
        # SPRACH-BINDUNG für CRITIC
        lang_binding = _get_language_binding(draft) if draft else ""
        critic_prompt = f"{critic_mode_instr}\n\n{lang_binding}\n\nENTWURF ZUR PRÜFUNG:\n\n{draft}"
        raw_critique = self._llm_call_func(
            prompt=critic_prompt,
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
        # FIX: mode_instruction vom source_intent (STILISIERUNG), system_instruction vom AGENT_EDITOR
        # FIX: "n Stellen" dynamisch statt hardcodiert "3"
        editor_sys = self.prompt_manager.get_system_instruction("AGENT_EDITOR")
        editor_mode_intent = source_intent if source_intent else "AGENT_EDITOR"
        editor_mode_instr = self.prompt_manager.get_mode_instruction(editor_mode_intent)
        # SPRACH-BINDUNG für EDITOR
        lang_binding = _get_language_binding(draft) if draft else ""
        n_critique = min(len(critique[:3]), 3)
        stellen_wort = f"{n_critique} Stelle{'n' if n_critique != 1 else ''}"
        edit_prompt = (
            f"{editor_mode_instr}\n\n{lang_binding}\n\n"
            f"ENTWURF:\n\n{draft}\n\n"
            f"KRITIKPUNKTE (nur diese {stellen_wort} ändern):\n"
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
    # ======================================================================
    # === RAG RETRIEVER ===
    # ======================================================================
    # Methoden: retrieve_with_rrf, check_imbalance_only, expand_query_multilingual,
    #           extract_keywords
    # Zustand:  self.current_context (WRITE), self._original_results_cache (WRITE),
    #           self.last_imbalance_info (WRITE), self.vector_store (READ),
    #           self.router (READ), self._reranker_factory (READ)
    # Zukunft:  Kandidat fuer eigenes Modul (VectorRepository + SearchService)
    # ======================================================================
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
        ratio, severity = _compute_imbalance(list(surviving_docs.values()))
        # v51.1 Fix 2026-06-21: max_c/min_c lokal berechnen (waren undefined).
        # Vorher: NameError bei Aufruf aus dem Analyse-Tab.
        # _compute_imbalance() gibt nur (ratio, severity) zurück, nicht max_c/min_c.
        _counts = list(surviving_docs.values())
        imbalance_info = SimpleNamespace(
            severity=severity,
            ratio=ratio,
            doc_distribution=dict(surviving_docs),
            max_chunks=max(_counts) if _counts else 0,
            min_chunks=min(_counts) if _counts else 0,
            top_results=top_results,
            pre_rerank_pool=top_candidates,
        )
        # Speichere für späteren Zugriff
        self.last_imbalance_info = imbalance_info
        logger.info(f"📊 Imbalance-Check: {severity.upper()} (Ratio: {ratio:.1f}:1)")
        return imbalance_info
    # ======================================================================
    # === UTILITIES ===
    # ======================================================================
    # Methoden: _extract_number_from_title, _parse_extraction_result,
    #           clean_citation_format, _get_chat_title, extract_date_from_metadata
    # Zustand:  Keine self.*-Zugaenge — reine Funktionen (koennten @staticmethod sein)
    # Zukunft:  In utils-Modul auslagern
    # ======================================================================
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
    # =========================================================================
    # SMALL-CORPUS-THRESHOLD: Ab dieser Chunk-Anzahl wird der
    # Small-Corpus-Guard aktiviert (Reranker-Skip, Essence-Parity-Skip)
    # =========================================================================
    SMALL_CORPUS_THRESHOLD = 8  # ≤8 Chunks total = Small Corpus
    # ======================================================================
    # === MAIN PIPELINE (ORCHESTRATOR) ===
    # ======================================================================
    # Methoden: generate_answer (Der Dirigent), _ensure_router_context,
    #           _extract_chat_ids, _score_and_rerank, _calculate_imbalance,
    #           _apply_essence_parity, _trim_to_token_budget, _run_phase2_phase3
    # Zustand:  KOORDINIERT ALLE self.*-Attribute (Dirigent)
    #           self.current_context (WRITE via _ensure_router_context),
    #           self._semantic_intent (WRITE via _ensure_router_context),
    #           self.last_imbalance_info (WRITE via _calculate_imbalance),
    #           self.last_pipeline_trace (WRITE via _execute_llm_call)
    # Zukunft:  Bleibt als RAGOrchestrator — aber delegiert an obige Sektionen
    # ======================================================================
    def generate_answer(self, query: str, results: List[Dict], dry_run: bool = False, pre_reranked=None, selected_doc_ids: List[str] = None) -> Tuple[str, List[Dict], str]:
        """ v50.9: ESSENCE PARITY - Intelligente Essenz-Extraktion. v51: Refactored for clarity."""
        if not results:
            return "Ich habe keine relevanten Informationen in den Dokumenten gefunden.", [], "unknown"
        # ── v57.1: Pipeline-Timer ──
        _pipeline_start = time.time()
        logger.info(
            f"⏱️ PIPELINE-START: {datetime.now().strftime('%H:%M:%S')} "
            f"| Query: {query[:80]}{'...' if len(query) > 80 else ''}"
        )
        # --- Schritt 1: Kontext & Intent sicherstellen ---
        intent, semantic_intent = self._ensure_router_context(query)
        # ── STILISTIC_LAB: Frühe Abzweigung (vor Reranking/Essence-Parity) ──
        # Die Lab-Pipeline braucht Volltexte, keine Chunks. Sie hat ihre eigene
        # Etappe-1-Analyse und Globale Synthese. Kein RAG-Overhead nötig.
        if semantic_intent == "STILISTIC_LAB":
            logger.info("🔬 STILISTIC_LAB: Frühe Abzweigung — starte Lab-Pipeline direkt")
            # Adapter: Chunks → Volltext-Dict pro Dokument
            doc_chunks_map = defaultdict(list)
            for res in results:
                cid = res.get('chat_id', '')
                if cid:
                    doc_chunks_map[cid].append(res)
            # Baue source_texts Dict: {label: volltext}
            source_texts = {}
            for idx, (cid, chunks) in enumerate(doc_chunks_map.items(), 1):
                first_meta = chunks[0].get('metadata', {})
                title = first_meta.get('chat_title') or self._get_chat_title(cid)
                label = f"QUELLE {idx}: {title}"
                full_text = "\n\n".join(
                    c.get('content', '') for c in sorted(
                        chunks,
                        key=lambda x: x.get('metadata', {}).get('chunk_index', 0)
                    )
                )
                if full_text.strip():
                    source_texts[label] = full_text
            if len(source_texts) < 2:
                logger.warning(f"⚠️ STILISTIC_LAB: Nur {len(source_texts)} Quelle(n)")
                return (
                    f"STILISTIC_LAB benötigt mindestens 2 Quellen. Gefunden: {len(source_texts)}.",
                    [], "STILISTIC_LAB"
                )
            try:
                lab_result = run_stilistic_lab(
                    source_texts=source_texts,
                    user_question=query,
                    progress_callback=None,
                )
                globale_synthese = lab_result.get("globale_synthese", "(Keine Synthese)")
                self.last_pipeline_trace = {
                    "intent": "STILISTIC_LAB",
                    "semantic_intent": "STILISTIC_LAB",
                    "lab_source_count": len(source_texts),
                    "lab_valid_sources": lab_result.get("metadata", {}).get("valid_sources", 0),
                    "timestamp": __import__('time').time(),
                }
                logger.info(f"✅ STILISTIC_LAB abgeschlossen")
                return globale_synthese, [], "STILISTIC_LAB"
            except Exception as e:
                logger.error(f"❌ STILISTIC_LAB fehlgeschlagen: {e}")
                return f"❌ STILISTIC_LAB-Fehler: {e}", [], "STILISTIC_LAB"
        # --- Schritt 2: Chat IDs extrahieren ---
        # Fix C: Wenn UI die ausgewählten IDs liefert, diese verwenden
        # (andernfalls fallen Dokumente mit 0 Retrieval-Chunks durchs Raster)
        if selected_doc_ids and len(selected_doc_ids) <= 10:
            chat_id = selected_doc_ids
            logger.info(f"📋 Fix C: {len(chat_id)} Doc-IDs aus UI-Selection (überschreibt _extract_chat_ids)")
        else:
            chat_id = self._extract_chat_ids(results)
        # ── SMALL-CORPUS-GUARD ──
        # Bei sehr wenigen Chunks (z.B. 2 kurze Texte à 1 Chunk) sind
        # Reranker, Essence Parity und Rescue Mission kontraproduktiv:
        # - Reranker: 2/2 Chunks zu filtern ist trivial, verschwendet LLM-Call
        # - Essence Parity: Budget 60 für 2 Chunks → 97% ungenutzt, Rescue rennt ins Leere
        # - Phase 3: 86 Token Output für 11 Fehler → Korrektur verhungert
        # Lösung: Small-Corpus-Pfad umgeht alle Filter und gibt ALLES in den Kontext.
        is_small_corpus = len(results) <= self.SMALL_CORPUS_THRESHOLD
        if is_small_corpus:
            logger.info(
                f"🧊 SMALL-CORPUS-GUARD aktiv: {len(results)} Chunks ≤ {self.SMALL_CORPUS_THRESHOLD} "
                f"→ Reranker + Essence Parity übersprungen, alle Chunks direkt in Synthese"
            )
        # --- Schritt 3: Scoring & Reranking (MIT CRASH-CATCHER) ---
        # SMALL-CORPUS: Reranker überspringen — bei ≤8 Chunks nicht nötig
        if is_small_corpus:
            # Direkte Übernahme aller Chunks ohne Reranking
            for res in results:
                if '_final_score' not in res:
                    res['_final_score'] = res.get('score', 0.0) + res.get('_keyword_boost', 0.0)
            top_results = sorted(results, key=lambda x: x.get('_final_score', 0), reverse=True)
            top_candidates = results
            rerank_stats = {
                "total": len(results),
                "passed": len(top_results),
                "rejected": 0,
                "avg_score": sum(r.get('_final_score', 0) for r in top_results) / len(top_results) if top_results else 0,
                "query_type": "small_corpus_skip",
                "reranker_failed": False,
                "reranker_error": "",
            }
            rejected_chunks = []
            logger.info(f"🧊 Small-Corpus: {len(top_results)} Chunks direkt übernommen (Reranker übersprungen)")
        else:
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
        # SMALL-CORPUS: Essence Parity überspringen — alle Chunks direkt nutzen
        doc_metadata = []
        is_essence_parity = False
        if is_small_corpus and chat_id and isinstance(chat_id, list):
            # Small-Corpus-Pfad: Alle Chunks direkt, kein Budget-Management
            # doc_metadata manuell aufbauen (wird sonst von _apply_essence_parity geliefert)
            doc_groups = defaultdict(list)
            for res in top_results:
                cid = res.get('chat_id', 'unknown')
                doc_groups[cid].append(res)
            
            for cid in chat_id:
                chunks = doc_groups.get(cid, [])
                if chunks:
                    doc_title = chunks[0].get('metadata', {}).get('chat_title') or self._get_chat_title(cid)
                    dates = [self.extract_date_from_metadata(c) for c in chunks]
                    valid_dates = [d for d in dates if d != datetime.min]
                    rep_date = min(valid_dates) if valid_dates else datetime.min
                    doc_metadata.append({
                        'title': doc_title, 'chat_id': cid,
                        'chunks_available': len(chunks),
                        'chunks_selected': len(chunks),
                        'date': rep_date
                    })
                    # source_id zuweisen (für _build_context_text)
                    doc_idx = chat_id.index(cid) + 1 if cid in chat_id else 0
                    for chunk in chunks:
                        chunk['source_id'] = doc_idx
            
            # v57.8: STILISTIC_DEEPENING-Ausnahme
            if self._semantic_intent in self.STRUCTURE_OVERRIDES:
                intent = self._semantic_intent
                logger.info(f"🧊 Small-Corpus + {self._semantic_intent}: intent bleibt {self._semantic_intent}")
            else:
                intent = "ESSENCE_PARITY"  # Synthese-Prompt bleibt gleich
            is_essence_parity = True
            # FIX v57.3: doc_metadata konsistent sortieren — nach Score,
            # damit [1] in doc_metadata = [1] in context_text (sorted_doc_ids)
            if doc_metadata and top_results:
                # Build score-based ordering from top_results
                cid_score_order = {}
                for res in top_results:
                    cid = res.get('chat_id', '')
                    if cid not in cid_score_order:
                        score = res.get('_final_score', res.get('hermeneutic_score', 0))
                        cid_score_order[cid] = score
                # Sort doc_metadata by score (descending = same as top_results_sorted)
                doc_metadata.sort(key=lambda d: cid_score_order.get(d.get('chat_id', ''), 0), reverse=True)
            # Log: Quellen-Zuordnung dokumentieren
            for idx, d in enumerate(doc_metadata, 1):
                logger.info(f"  📋 [{idx}] = {d.get('title', 'Unbekannt')}")
            logger.info(f"🧊 Small-Corpus: {len(doc_metadata)} Docs direkt in Synthese (Essence Parity übersprungen)")
        elif chat_id and isinstance(chat_id, list) and len(chat_id) <= 10:
            logger.debug(">>> BAKE 2: Betrete Essence Parity...")
            top_results, doc_metadata, intent = self._apply_essence_parity(
                query, top_results, results, chat_id, intent
            )
            is_essence_parity = True
        # --- NOTBREMSE ---
        if not top_results:
            return "Ich habe in den ausgewählten Dokumenten keine passenden Textstellen gefunden.", [], "NO_DATA"
        # --- Schritt 6: Token Trimming ---
        logger.info("🏁 DEBUG BAKE 3: Vor Token-Trimming") # NEU
        top_results_sorted = self._trim_to_token_budget(
               top_results,
               max_tokens=TRIM_TOKEN_BUDGET
        )
        logger.info(f"📅 Chunks für Token-Trimming: {len(top_results_sorted)} Stücke")
        # Debug-Log: Zeige Datums-Reihenfolge
        for i, res in enumerate(top_results_sorted[:5]):
            date = self.extract_date_from_metadata(res)
            title = res.get('metadata', {}).get('title', 'Unknown')
            logger.debug(f"  #{i+1}: {title} → {date.strftime('%d.%m.%Y') if date != datetime.min else 'o.D.'}")
        # --- Schritt 7: Context Text aufbauen ---
        context_text = self._build_context_text(top_results_sorted)
        
        # --- Schritt 7.5 NEU: Pro-Quelle-Extraktion (N.1) + Verify-Gate (N.2) ---
        logger.info("🔍 Starte Phase 1: Pro-Quelle Zitat-Extraktion...")
        
        # N.1: Dokumententexte pro QUELLE-Nummer sammeln
        doc_texts_for_extraction = {}
        for res in top_results_sorted:
            sid = res.get('source_id', 0)
            if sid:
                if sid not in doc_texts_for_extraction:
                    doc_texts_for_extraction[sid] = ""
                doc_texts_for_extraction[sid] += res.get('content', '') + "\n"
        
        # Pro-Quelle-Extraktion statt Monolith-Call
        extracted_quotes = self.extract_quotes_per_document(query, doc_texts_for_extraction)
        
        # N.2: Fuzzy-Verify-Gate — Zitate behalten, die im Quelltext existieren
        # (Claude-R3: "C2/C3-Check vor Synthese = 5-Zeilen-Filter")
        # v51.2 Fix 2026-06-27: Fuzzy-Match statt exaktem String-Vergleich.
        # Grund: Bei kanonischen Autoren (Puschkin, Shakespeare) zitiert das
        # LLM aus dem Gedächtnis — mit leicht abweichender Formatierung
        # (Zeilenumbrüche, Leerzeichen, Interpunktion). Der exakte Vergleich
        # verwirft diese Zitate, obwohl der Inhalt korrekt ist.
        # Fix: Normalisierung vor dem Vergleich (NFC, Zeilenumbrüche → Leerzeichen,
        # doppelte Leerzeichen → einfache, Strip) + Teilstring-Match (erste 80 Zeichen).
        import unicodedata

        def _normalize_for_fuzzy(s: str) -> str:
            """Normalisiert String für Fuzzy-Match."""
            if not s:
                return ""
            # NFC-Normalisierung (z.B. komponierte vs. dekomponierte Diakritika)
            s = unicodedata.normalize("NFC", s)
            # Zeilenumbrüche → Leerzeichen
            s = s.replace("\n", " ").replace("\r", " ").replace("\u00a0", " ")
            # Doppelte Leerzeichen → einfache (ohne re-Modul — String-Methode)
            while "  " in s:
                s = s.replace("  ", " ")
            # Strip
            return s.strip()

        verified_quotes = []
        for q in extracted_quotes:
            qtext = q.get("text", "")
            qsrc = q.get("quelle", 0)
            src_text = doc_texts_for_extraction.get(qsrc, "")
            if qtext and src_text:
                # Normalisiere beide Strings
                qtext_norm = _normalize_for_fuzzy(qtext)
                src_text_norm = _normalize_for_fuzzy(src_text)
                # Versuch 1: exakter Match (normalisiert)
                if qtext_norm in src_text_norm:
                    verified_quotes.append(q)
                # Versuch 2: Teilstring-Match (erste 80 Zeichen — erlaubt
                # längere Zitate, die am Anfang exakt stimmen, aber am Ende
                # vom LLM gekürzt/erweitert wurden)
                elif len(qtext_norm) > 80 and qtext_norm[:80] in src_text_norm:
                    verified_quotes.append(q)
                # Versuch 3: letzter Teil (falls Zitat mit "..." beginnt)
                elif len(qtext_norm) > 80 and qtext_norm[-80:] in src_text_norm:
                    verified_quotes.append(q)
                else:
                    logger.info(
                        f"🚫 Verify-Gate: Zitat aus [{qsrc}] NICHT im Quelltext gefunden → verworfen: "
                        f"\"{qtext[:60]}...\""
                    )
            else:
                logger.info(
                    f"🚫 Verify-Gate: Zitat aus [{qsrc}] NICHT im Quelltext gefunden → verworfen: "
                    f"\"{qtext[:60]}...\""
                )
        
        if len(verified_quotes) < len(extracted_quotes):
            logger.info(
                f"🔐 Verify-Gate: {len(extracted_quotes)} → {len(verified_quotes)} Zitate "
                f"({len(extracted_quotes) - len(verified_quotes)} fabrizierte/ungenau entfernt)"
            )
        
        extracted_quotes = verified_quotes
        
        # --- Schritt 7.5: STILISTIC Mode — Stil-Distillation (Phase 0.5) ---
        stil_profiles = None
        if semantic_intent in ("STILISTIC", "STILISTIC_DEEPENING"):
            # Dokument-Texte für Pro-Quelle-Distillation zusammenstellen
            doc_texts_for_distillation = {}
            for i, doc in enumerate(doc_metadata, 1):
                # Alle Chunks dieses Dokuments zusammenführen
                doc_content = "\n\n".join(
                    chunk.get('content', '') 
                    for chunk in top_results_sorted 
                    if chunk.get('chat_id') == doc.get('chat_id', '')
                )
                if doc_content:
                    doc_texts_for_distillation[i] = doc_content
            
            if doc_texts_for_distillation:
                logger.info(f"🎭 STILISTIC: Starte Stil-Distillation für {len(doc_texts_for_distillation)} Dokumente...")
                stil_profiles = self._distill_style_per_document(query, doc_texts_for_distillation)
            else:
                logger.warning("⚠️ STILISTIC: Keine Dokument-Texte für Distillation verfügbar")
        
        # --- Schritt 8: Prompt bauen ---
        prompt, mode_display, dynamic_sys_instruct = self._build_synthesis_prompt(
            query, doc_metadata, intent, semantic_intent, context_text, extracted_quotes,
            stil_profiles=stil_profiles
        )
        # --- Finale Diagnostik ---
        final_doc_distribution = defaultdict(int)
        for res in top_results_sorted:
            title = res.get('metadata', {}).get('title', 'Unknown')
            final_doc_distribution[title] += 1
        logger.info(f"📊 Finale Kontext-Verteilung ({len(top_results_sorted)} Chunks total):")
        # Sortiere nach Dokument-Nummer für korrekte Chronologie-Anzeige
        for doc_title, count in sorted(final_doc_distribution.items(), key=lambda x: self._extract_number_from_title(x[0])):
            percentage = (count / len(top_results_sorted)) * 100
            logger.info(f"  📄 {doc_title}: {count} Chunks ({percentage:.1f}%)")
        
        # --- NEU: Phase 2 - Synthese mit extrahierten Zitaten ---
        # extracted_quotes wird in _execute_llm_call gesetzt und später hier verwendet
        # Dieser Block wird nach dem LLM-Call in _execute_llm_call ausgeführt
        # --- 🔴 NEU: DRY RUN CHECK ---
        if dry_run:
            logger.info("Dry Run: Überspringe LLM-Generierung (nur Metriken gesammelt).")
            return "", top_results_sorted, intent
        # --- Schritt 9: LLM Generierung & Pipeline Trace ---
        final_text, top_results_sorted, intent, extracted_quotes = self._execute_llm_call(
            query, prompt, dynamic_sys_instruct, intent, semantic_intent, 
            top_results, top_results_sorted, rerank_stats, rejected_chunks,
            extracted_quotes, is_small_corpus=is_small_corpus
        )
        
        # --- NEU: extracted_quotes in Metadaten speichern ---
        for chunk in top_results_sorted:
            chunk['extracted_quotes'] = extracted_quotes
        # ── DREI-PHASEN-SYNTHESE: Phase 2 (Check) + Phase 3 (Korrektur) ──
        # Prüft ZITAT-Tags VOR der User-sichtbaren Umwandlung,
        # da die Checks die <ZITAT>-Tags als Struktur-Marker brauchen.
        if semantic_intent in ("ANALYTICAL_FORENSIC", "ANALYTICAL", "META_ANALYTICAL", "LITERARY", "STILISTIC", "STILISTIC_DEEPENING"):
            final_text = self._run_phase2_phase3(
                final_text, top_results_sorted, doc_metadata, extracted_quotes,
                is_small_corpus=is_small_corpus
            )
        # Mache die Zitat-Tags für den User lesbar
        import re
        final_text = re.sub(
            r'<ZITAT quelle="(\d+)">(.*?)</ZITAT>', 
            r'*„\2"* [\1]', 
            final_text, 
            flags=re.DOTALL
        )
        # WARNUNG-Tags für User sichtbar machen
        final_text = re.sub(
            r'<WARNUNG typ="([^"]+)" grund="([^"]+)">(.*?)</WARNUNG>',
            r'⚠️ *\3* (\2)',
            final_text,
            flags=re.DOTALL
        )
        # ── v57.1: Pipeline-Timer — Ende ──
        _pipeline_elapsed = time.time() - _pipeline_start
        _mins, _secs = divmod(_pipeline_elapsed, 60)
        logger.info(
            f"⏱️ PIPELINE-ENDE: {datetime.now().strftime('%H:%M:%S')} "
            f"| Dauer: {int(_mins)}:{_secs:05.2f} ({_pipeline_elapsed:.1f}s) "
            f"| Intent: {intent}"
        )
        return final_text, top_results_sorted, intent
    # =========================================================================
    # 2. PRIVATE HILFSMETHODEN (Die Musiker)
    # =========================================================================
    def _run_phase2_phase3(
        self,
        draft: str,
        top_results_sorted: List[Dict],
        doc_metadata: List[Dict],
        extracted_quotes: list,
        is_small_corpus: bool = False,
    ) -> str:
        """
        Drei-Phasen-Synthese: Phase 2 (Mechanischer Check) + Phase 3 (Korrektur).
        
        Architektur-Entscheidung (Gemini-Freigabe, 2026-05-16):
        - Phase 2: Deterministischer Check (kein LLM, nur Code)
        - Phase 3: Gezielte Korrektur (kurzer Prompt, temp=0.0, flash)
        - 1 Runde, nicht verhandelbar
        - <WARNUNG>-Tags für unkorrigierbare Abschnitte
        - Skip-Optimierung bei 0 Fehlern
        """
        try:
            # Quelltexte pro source_id zusammenstellen
            source_texts = {}
            for res in top_results_sorted:
                sid = res.get('source_id', 0)
                if sid:
                    if sid not in source_texts:
                        source_texts[sid] = ""
                    source_texts[sid] += res.get('content', '') + "\n"
            
            num_sources = len(source_texts)
            
            if num_sources == 0:
                logger.warning("⚠️ Phase 2: Keine Quelltexte → Validierung übersprungen")
                return draft
            
            # doc_metadata um source_id anreichern
            # doc_metadata kommt aus _apply_essence_parity und hat title/chat_id,
            # aber evtl. keine source_id. Wir ordnen über chat_id → source_id Mapping.
            chat_to_source = {}
            for res in top_results_sorted:
                cid = res.get('chat_id', '')
                sid = res.get('source_id', 0)
                if cid and sid:
                    chat_to_source[cid] = sid
            
            enriched_metadata = []
            for doc in doc_metadata:
                enriched_doc = dict(doc)
                # source_id aus chat_id ableiten
                doc_chat_id = doc.get('chat_id', '')
                if 'source_id' not in enriched_doc and doc_chat_id in chat_to_source:
                    enriched_doc['source_id'] = chat_to_source[doc_chat_id]
                enriched_metadata.append(enriched_doc)
            
            # FIX v57: is_small_corpus-Parameter robust übergeben
            # Ältere synthesis_validator-Versionen akzeptieren diesen Parameter nicht.
            try:
                final_text, phase_report = run_three_phase_synthesis(
                    draft=draft,
                    num_sources=num_sources,
                    source_texts=source_texts,
                    doc_metadata=enriched_metadata,
                    extracted_quotes=extracted_quotes,
                    llm_call_func=self._llm_call_func,
                    is_small_corpus=is_small_corpus,
                )
            except TypeError as e:
                if "is_small_corpus" in str(e):
                    logger.warning(
                        "⚠️ synthesis_validator.py veraltet — is_small_corpus nicht unterstützt. "
                        "Fallback ohne Parameter. Bitte synthesis_validator.py aktualisieren!"
                    )
                    final_text, phase_report = run_three_phase_synthesis(
                        draft=draft,
                        num_sources=num_sources,
                        source_texts=source_texts,
                        doc_metadata=enriched_metadata,
                        extracted_quotes=extracted_quotes,
                        llm_call_func=self._llm_call_func,
                    )
                else:
                    raise
            
            # Phase-Report in Pipeline-Trace speichern
            if hasattr(self, 'last_pipeline_trace') and self.last_pipeline_trace:
                self.last_pipeline_trace["phase2_errors"] = phase_report["phase2_errors"]
                self.last_pipeline_trace["phase2_warnings"] = phase_report["phase2_warnings"]
                self.last_pipeline_trace["phase3_applied"] = phase_report["phase3_applied"]
            
            return final_text
            
        except Exception as e:
            logger.error(f"❌ Drei-Phasen-Synthese fehlgeschlagen: {e} → Original beibehalten")
            return draft
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
        # v58: _router_intent entfernt — STRUCTURE_OVERRIDES + self._semantic_intent steuern die Logik
        self._semantic_intent = semantic_intent
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
            ratio, severity = _compute_imbalance(list(surviving_docs.values()))
            # v51.1 Fix 2026-06-21: max_c/min_c lokal berechnen (siehe check_imbalance_only).
            _counts = list(surviving_docs.values())
            self.last_imbalance_info = SimpleNamespace(
                severity=severity, ratio=ratio, doc_distribution=dict(surviving_docs),
                max_chunks=max(_counts) if _counts else 0,
                min_chunks=min(_counts) if _counts else 0
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
        # ── Phase 0: Proaktive Rescue — fehlende Dokumente aus DB holen ──
        # Wenn ein Dokument 0 Chunks im Reranking-Ergebnis hat, 
        # suchen wir gezielt in der Vektor-DB danach (wie Mechanismus 1).
        missing_docs = [cid for cid in chat_id if cid not in docs_map]
        if missing_docs:
            logger.warning(
                f"🚨 {len(missing_docs)} Dokument(e) fehlen komplett im Reranking-Ergebnis. "
                f"Starte proaktive Rescue..."
            )
            for missing_cid in missing_docs:
                rescue_results, _ = self.vector_store.hybrid_search(
                    query=query,
                    limit=RESCUE_FETCH_LIMIT,
                    allowed_chat_ids=[missing_cid],
                )
                if rescue_results:
                    for res in rescue_results:
                        res["_is_rescued"] = True
                        res["_keyword_boost"] = res.get("_keyword_boost", 0) + 0.2
                    docs_map[missing_cid] = rescue_results
                    top_results.extend(rescue_results)
                    logger.info(
                        f"  🚑 Proaktive Rescue: {len(rescue_results)} Chunks aus DB "
                        f"für Dokument {missing_cid[-8:]}"
                    )
                else:
                    logger.error(
                        f"  ❌ Proaktive Rescue fehlgeschlagen: "
                        f"Keine Chunks in DB für Dokument {missing_cid[-8:]} — "
                        f"Dokument wird in der Synthese fehlen!"
                    )
        # Logarithmische Skalierung: Mehr Docs → mehr Budget, aber degressiv
        # 5 Docs → 60 (unverändert), 10 Docs → 90, 15 Docs → 104
        if len(chat_id) <= 5:
            total_budget = ESSENCE_TOTAL_BUDGET
        else:
            total_budget = int(
                ESSENCE_TOTAL_BUDGET * (1 + 0.5 * math.log2(len(chat_id) / 5))
            )
        logger.info(f"⚖️ Logarithmisches Budget: {total_budget} Chunks für {len(chat_id)} Dokumente")
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
        # ── Logarithmische Budget-Verteilung (wie in _trim_to_token_budget) ──
        log_weights = {}
        for cid in chat_id:
            available = len(docs_map.get(cid, []))
            log_weights[cid] = math.log2(available + 1)
        total_log_weight = sum(log_weights.values()) if log_weights else 1.0
        doc_allocations = {}
        for cid in chat_id:
            fair_share = int(total_budget * (log_weights[cid] / total_log_weight))
            doc_allocations[cid] = max(fair_share, doc_minimums.get(cid, 2))
            logger.info(
                f"  📊 {cid[-8:]}: log_weight={log_weights[cid]:.2f} "
                f"→ fair_share={fair_share} → allocation={doc_allocations[cid]} "
                f"(available: {len(docs_map.get(cid, []))})"
            )
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
            # Wenn IMMER NOCH leer: Direkte ChromaDB-Rettung (Fix B)
            if not doc_chunks:
                logger.warning(
                    f"  🚨 Dokument {cid[-8:]} hat 0 Chunks in Pipeline! "
                    f"Starte direkte ChromaDB-Rettung..."
                )
                try:
                    rescue_results, _ = self.vector_store.hybrid_search(
                        query=query,
                        limit=RESCUE_FETCH_LIMIT,
                        allowed_chat_ids=[cid],
                    )
                    if rescue_results:
                        rescue_results.sort(
                            key=lambda x: x.get('score', 0), reverse=True
                        )
                        doc_chunks = rescue_results[:3]  # Mindestrepräsentation
                        for res in doc_chunks:
                            res['_is_rescued'] = True
                            res['_keyword_boost'] = res.get('_keyword_boost', 0) + 0.2
                        logger.info(
                            f"  🚑 ChromaDB-Rettung erfolgreich: "
                            f"{len(doc_chunks)} Chunks für {cid[-8:]}"
                        )
                    else:
                        logger.error(
                            f"  ❌ Dokument {cid[-8:]} existiert NICHT in ChromaDB!"
                        )
                except Exception as e:
                    logger.error(
                        f"  ❌ ChromaDB-Rettung fehlgeschlagen für {cid[-8:]}: {e}"
                    )
                # Endgültiger Fallback: Wenn selbst ChromaDB nichts liefert
                if not doc_chunks:
                    doc_title = self._get_chat_title(cid)
                    doc_metadata.append({
                        'title': doc_title, 'chat_id': cid, 'chunks_available': 0,
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
        # Phase 5: Sammle Ergebnisse mit logarithmischer Allokation
        essence_results = []
        for cid in chat_id:
            selected = final_selection[cid]
            
            # Logarithmische Allokation als Obergrenze verwenden
            max_allowed = doc_allocations.get(cid, 6)
            if len(selected) > max_allowed:
                logger.warning(
                    f"  ✂️ Dokument {cid[-8:]}: {len(selected)} → "
                    f"{max_allowed} Chunks (logarithmische Allokation)"
                )
                selected = selected[:max_allowed]
                final_selection[cid] = selected
            
            if selected:
                essence_results.extend(selected)
                doc_title = selected[0].get('metadata', {}).get('chat_title') or self._get_chat_title(cid)
                avg_score = sum(c.get('hermeneutic_score', c.get('_final_score', 0)) for c in selected) / len(selected)
                logger.info(f"  📄 {doc_title}: {len(docs_map.get(cid, []))} verfügbar → {len(selected)} ausgewählt (Ø {avg_score:.2f})")
                
                dates = [self.extract_date_from_metadata(c) for c in selected]
                valid_dates = [d for d in dates if d != datetime.min]
                rep_date = min(valid_dates) if valid_dates else datetime.min
                doc_metadata.append({
                    'title': doc_title, 'chat_id': cid, 'chunks_available': len(docs_map.get(cid, [])),
                    'chunks_selected': len(selected), 'date': rep_date
                })
            else:
                doc_title = self._get_chat_title(cid)
                logger.error(f"  ❌ {doc_title}: 0 Chunks!")
                doc_metadata.append({
                    'title': doc_title, 'chat_id': cid, 'chunks_available': 0,
                    'chunks_selected': 0, 'date': datetime.min
                })
        # v57.8: STILISTIC_DEEPENING bekommt eigene mode_instructions,
        # nicht ESSENCE_PARITY. Die Essenz-Extraktion läuft normal,
        # aber die Ausgabestruktur kommt von STILISTIC_DEEPENING.
        if self._semantic_intent in self.STRUCTURE_OVERRIDES:
            new_intent = self._semantic_intent
            logger.info(f"✅ Essenz-Extraktion: {len(essence_results)} Chunks aus {len(chat_id)} Dokumenten ({self._semantic_intent}: intent bleibt {self._semantic_intent})")
        else:
            new_intent = "ESSENCE_PARITY"
            logger.info(f"✅ Essenz-Extraktion: {len(essence_results)} Chunks aus {len(chat_id)} Dokumenten")
        return essence_results, doc_metadata, new_intent
    def _build_context_text(self, top_results_sorted: List[Dict]) -> str:
        
        # ── DOKUMENTEN-GRUPPIERUNG statt Chunk-Nummerierung ──
        # Chunks nach chat_id gruppieren → Dokument-Nummer zuweisen
        doc_groups = defaultdict(list)
        for res in top_results_sorted:
            cid = res.get('chat_id', 'unknown')
            doc_groups[cid].append(res)
        # Deterministische Reihenfolge: nach erstem Chunk sortiert
        sorted_doc_ids = sorted(
            doc_groups.keys(),
            key=lambda cid: top_results_sorted.index(next(r for r in top_results_sorted if r.get('chat_id') == cid))
        )
        # Jedem Chunk die DOKUMENT-Nummer als source_id zuweisen
        context_text = ""
        for doc_idx, cid in enumerate(sorted_doc_ids, 1):
            chunks = doc_groups[cid]
            # Header nur einmal pro Dokument
            first_meta = chunks[0].get('metadata', {})
            title = first_meta.get('chat_title', 'Dokument')
            speaker = first_meta.get('model_name') or first_meta.get('speaker') or first_meta.get('author') or 'Quelle'
            date_obj = self.extract_date_from_metadata(chunks[0])
            date_str = date_obj.strftime("%d.%m.%Y") if date_obj != datetime.min else "o.D."
            # ── Fix F: Doc-Type-Annotation im QUELLE-Header ──
            # Default: ANALYSE (die meisten Dokumente in der DB sind Sekundäranalysen)
            # Nur bei Primärquellen-Schlüsselwörtern wird PRIMÄRQUELLE gesetzt
            _primary_keywords = ["brief", "tagebuch", "tagebuchnotiz", "notiz", "protokoll",
                                 "aufzeichnung", "manuskript", "vorlesung", "briefwechsel",
                                 "korrespondenz", "stundennotiz", "sitzungsprotokoll"]
            _title_lower = title.lower()
            # Dokumente, die "Analyse", "Gutachten" etc. im Titel haben → offensichtlich ANALYSE
            # Dokumente mit Primärquellen-Schlüsselwörtern → PRIMÄRQUELLE
            # Alles andere → ANALYSE (safe default)
            _analysis_keywords = ["analyse", "gutachten", "supervision", "handoff",
                                  "fallstudie", "interpretation", "kommentar", "kritik"]
            if any(kw in _title_lower for kw in _analysis_keywords):
                doc_type_label = "ANALYSE"
            elif any(kw in _title_lower for kw in _primary_keywords):
                doc_type_label = "PRIMÄRQUELLE"
            else:
                doc_type_label = "ANALYSE"  # ← SAFE DEFAULT: Lieber fälschlich als ANALYSE
                                            # labeln als als Primärquelle, weil das Frame-Flip
                                            # von ANALYSE→PRIMÄRQUELLE katastrophal ist,
                                            # umgekehrt aber harmlos.
            context_text += f"QUELLE [{doc_idx}] — {doc_type_label}: \"{title}\"\n({speaker} | Datum: {date_str}):\n"
            for chunk in chunks:
                chunk['source_id'] = doc_idx  # ← DOKUMENT-Nummer, nicht Chunk-Nummer!
                context_text += f"{chunk.get('content', '')}\n\n"
        return context_text
    def _build_zitat_pool(self, extracted_quotes: list) -> str:
        """Baut den ZITAT-POOL mit nummerierten Einträgen."""
        if not extracted_quotes:
            return "Keine Zitate extrahiert."
        
        lines = []
        for i, q in enumerate(extracted_quotes, 1):
            src = q.get("quelle", "?")
            text = q.get("text", "")
            lines.append(f"[Z{i}] Quelle [{src}]: \"{text}\"")
        
        return "\n".join(lines)
    # =========================================================================
    # STILISTIC MODE: Stil-Distillation (Phase 0.5)
    # =========================================================================
    def _distill_style_per_document(self, query: str, doc_texts: dict) -> dict:
        """Zweistufige Stil-Analyse — Phase 0.5: Stil-Distillation pro Dokument.
        
        Architektur-Entscheidung (Claude-R3 + User-Konsultation, 2026-05-20):
        Stilistische Beobachtung ist holistisch, Vergleich ist selektiv.
        In einem Pass gewinnt immer der thematische Frame (kognitiver Modus-Konflikt).
        
        Lösung: Separater LLM-Call pro Dokument mit moderater Temperatur (0.6),
        der ein strukturiertes Stil-Profil mit 6 Kategorien erzeugt.
        Die Profile werden dann in den Synthese-Prompt injiziert,
        BEVOR der ZITAT-POOL kommt (stilistischer Frame vor Zitat-Evidence).
        
        Args:
            query: Die Analyse-Frage
            doc_texts: Dict von {doc_id: context_text}
                       doc_id ist die QUELLE-Nummer (1, 2, 3, ...)
        
        Returns:
            Dict von {doc_id: stil_profile_text}
        """
        stil_profiles = {}
        
        for doc_id, text in doc_texts.items():
            if not text or len(text.strip()) < 50:
                logger.debug(f"⏭️ Stil-Distillation: Überspringe Quelle [{doc_id}] (zu kurz)")
                continue
            
            # Kürze auf ~4000 Zeichen (Attention-Window)
            short_text = text[:4000] if len(text) > 4000 else text
            
            # Distillation-Prompt (5 Kategorien à 40-60 Wörter = 200-300 Wörter)
            # FIX v57.1: v57 sagte "240-360 Wörter" — das Modell lieferte ~50 Wörter.
            # Ursachen: (a) "max" vs. "min" Ambiguität, (b) Flash-Modelle komprimieren
            # aggressiv, (c) keine MINDEST-Länge pro Kategorie erzwungen.
            # FIX: (a) "MINDESTENS" statt "maximal", (b) Wortzahl pro Kategorie
            # verdoppelt, (c) Beispiel-Output zeigt die erwartete Länge, (d) max_tokens
            # von 2048 → 4096, (e) System-Instruction wiederholt Längenpflicht.
            distillation_prompt = (
                f"FRAGE: {query}\n\n"
                f"QUELLE [{doc_id}]:\n{short_text}\n\n"
                f"Erstelle ein STIL-PROFIL für Quelle [{doc_id}] mit exakt 5 Kategorien.\n\n"
                f"LÄNGEN-VORGABE (ZWINGEND):\n"
                f"- Jede Kategorie: BEFUND (1-2 Sätze, 25-40 Woerter) + BELEG (1 Zitat, 10-20 Woerter)\n"
                f"- Halte dich exakt an das BEFUND/BELEG-Format. Keine Abweichung.\n"
                f"- STIMME, ADRESSAT, TRADITION: nur im STIL-FAZIT (1-2 Saetze), nicht als eigene Kategorie.\n\n"
                f"BEISPIEL (alle 5 Kategorien im Soll-Format):\n1. SYNTAX UND PERIODENBAU:\nBEFUND: Parataktische Reihung, selten Subordination — erzeugt Stoßkraft.\nBELEG: \"Er kam, sah und siegte — ohne jeden Nebensatz.\"\n2. LEXIK UND WORTFELDER:\nBEFUND: Abstrakta dominieren, lateinische Lehnwoerter — verleiht akademische Autoritaet.\nBELEG: \"Die Konstitution des transzendenten Subjekts\"\n3. TEXTUROBERFLÄCHE UND MATERIALITÄT:\nBEFUND: Ausrufezeichen als rhythmische Eingriffe (3× pro Absatz) — durchbrechen den Fluss.\nBELEG: \"Aber – das ist das Entscheidende!\"\n4. RHYTHMUS UND KADENZ:\nBEFUND: Beschleunigung durch Aneinanderreihung, Verzoegerung durch Einschub — erzeugt Spannungsbogen.\nBELEG: \"nicht nur... sondern auch... und zugleich\"\n5. FIGUREN ALS SYNTAXPHÄNOMENE:\nBEFUND: Anapher als dominantestes Mittel — steigert zur Beschwörung.\nBELEG: \"Die einen... Die anderen...\"\n\n"
                f"Figuren in Kategorie 5: Benennen, zitieren, Funktion beschreiben.\n\n"
                f"Format:\n"
                f"### STIL-PROFIL QUELLE [{doc_id}]\n\n"
                f"1. SYNTAX UND PERIODENBAU\n"
                f"Was ist der häufigste Satztyp? Zähle Hauptsätze vs. Nebensätze.\n"
                f"Beschreibe Satzlängenvariation. Wie enden die Sätze — Vollschluss oder Offenheit?\n"
                f"Hypotaxe oder Parataxe? Satzbögen oder abgebrochene Sätze?\n"
                f"BEFUND: [Beobachtung] — [Funktion]\nBELEG: \"\"\n\n"
                f"2. LEXIK UND WORTFELDER\n"
                f"Welche Wortebene dominiert: Abstrakta oder Konkreta? Latinismen oder Germanismen?\n"
                f"Fachvokabular oder Allgemeinsprache? Nenne drei Schlüsselwörter. Welche semantischen Felder?\n"
                f"BEFUND: [Beobachtung] — [Funktion]\nBELEG: \"\"\n\n"
                f"3. TEXTUROBERFLÄCHE UND MATERIALITÄT\n"
                f"Welche Satzzeichen dominieren? Klammern, Gedankenstriche, Ausrufezeichen — zähle, benenne, zitiere.\n"
                f"Wie sieht der Text aus? Absatzstruktur: Steigerung? Brüche? Registerwechsel?\n"
                f"Satzmelodie: Wo klingt der Satz? Rhythmus der Betonung? Vokalwechsel, Alliteration?\n"
                f"BEFUND: [Beobachtung] — [Funktion]\nBELEG: \"\"\n\n"
                f"4. RHYTHMUS UND KADENZ\n"
                f"Wo beschleunigt der Text? Wo verlangsamt er? Beschreibe die Bewegung.\n"
                f"Wie schließen die Sätze — hart oder weich? Rhythmusmuster, das durchbrochen wird?\n"
                f"BEFUND: [Beobachtung] — [Funktion]\nBELEG: \"\"\n\n"
                f"5. FIGUREN ALS SYNTAXPHÄNOMENE\n"
                f"Finde eine Anapher, Ellipse, Antithese, Parallelismus oder Chiasmus.\n"
                f"Nenne den Namen, zitiere die Stelle. Welche Funktion erfüllt sie im Argument?\n"
                f"BEFUND: [Name der Figur] — [Funktion]\nBELEG: \"\"\n\n"
                f"FREIER RAUM: Wenn du eine Beobachtung machst, die in keine der 5 Kategorien passt —\n"
                f"notiere sie hier. Überraschungen sind wertvoller als Ordnung.\n\n"
                f"STIL-FAZIT: [Sprachliches Merkmal] — daher/weshalb [Wirkung].\n"f"Beispiel: \"Kurze Hauptsatzdominanz mit Imperativ — daher wirkt der Stil wie ein Befehl.\"\n"f"1-2 Saetze. Abgeleitet aus den Beobachtungen oben. Synthese aus den Beobachtungen oben.\n"
                f"\nWICHTIG: Schreibe ALLE 5 Kategorien aus. Halte nicht nach 1-2 Kategorien an.\n"
                f"Jede Kategorie braucht BEFUND + BELEG. Das sind mindestens 200 Woerter insgesamt.\n"
            )
            
            try:
                # Separater Call mit moderater Temperatur für ausführliche Beobachtung
                profile_text = self._llm_call_func(
                    distillation_prompt,
                    task="stilistic_distillation",  # Nutzt konfiguriertes Distillation-Modell (Flash-Tier)
                    system_instruction=(
                        "Du bist ein Annotator. Beobachte zuerst, deute dann. "
                        "Jeder BEFUND beginnt mit einer Beobachtung (was im Text STEHT), "
                        "dann darf die Funktion folgen (was es BEWIRKT). "
                        "Beobachtung zuerst, Funktion danach — das ist die Regel.\n"
                        "Beobachte konkret und ausfuehrlich, belege praezise. Ein BEFUND-Satz, ein BELEG-Zitat pro Kategorie.\n"
                        "LÄNGEN-PFLICHT: Du MUSS alle 5 Kategorien AUSFUEHRLICH bearbeiten. Stoppe NICHT vor Kategorie 5. "
                        "Gesamt MINDESTENS 40 Woerter pro Kategorie, gerne mehr."
                    ),
                    temperature=0.6,  # v58: Flash braucht mehr Waerme fuer Ausfuehrlichkeit (0.4 -> Komprimierung)
                    max_tokens=2048,  # v58: 1536 -> 2048 Sicherheitsmarge
                )
                
                if profile_text and len(profile_text.strip()) > 50:
                    stil_profiles[doc_id] = profile_text.strip()
                    word_count = len(profile_text.split())
                    logger.info(
                        f"✅ Stil-Distillation: Profil für Quelle [{doc_id}] erstellt "
                        f"({len(profile_text)} Zeichen, ~{word_count} Wörter)"
                    )
                    # FIX v57.1: Warnung bei zu kurzem Profil
                    if word_count < 80:
                        logger.warning(
                            f"⚠️ Stil-Distillation: Quelle [{doc_id}] Profil zu kurz "
                            f"(~{word_count} Wörter, Ziel: >=150). "
                            f"Synthese wird möglicherweise dünn."
                        )
                else:
                    logger.warning(f"⚠️ Stil-Distillation: Quelle [{doc_id}] lieferte leeres/profil")
                    
            except Exception as e:
                logger.error(f"❌ Stil-Distillation fehlgeschlagen für Quelle [{doc_id}]: {e}")
        
        logger.info(f"🎭 Stil-Distillation: {len(stil_profiles)}/{len(doc_texts)} Profile erstellt")
        return stil_profiles
    def _build_stil_profile_block(self, stil_profiles: dict, doc_metadata: list) -> str:
        """Formatiert die Stil-Profile für die Injektion in den Synthese-Prompt.
        
        Die Profile werden VOR dem ZITAT-POOL injiziert, damit der stilistische
        Frame bereits etabliert ist, bevor das Modell die Zitate sieht.
        """
        if not stil_profiles:
            return ""
        
        # Titel-Mapping für die Profil-Header
        title_map = {}
        if doc_metadata:
            for i, doc in enumerate(doc_metadata, 1):
                title_map[i] = doc.get('title', f'Dokument {i}')
        
        lines = [
            f"\n\n"
            f"============================================================\n"
            f"STIL-PROFILE ({len(stil_profiles)} Dokumente) — VORAB-BEOBACHTUNGEN\n"
            f"============================================================\n"
            f"ACHTUNG: Diese Profile sind VORSCHAUEN, keine Primärquellen!\n"
            f"Analysiere und zitiere NUR die ORIGINALQUELLEN unten.\n"
            f"Beschreibe den Stil des ORIGINALTEXTES, nicht den der Profile.\n"
            f"============================================================\n",
        ]
        for doc_id in sorted(stil_profiles.keys()):
            title = title_map.get(doc_id, f'Dokument {doc_id}')
            lines.append(f"\n------------------------------------------------------------")
            lines.append(f"VORAB-BEOBACHTUNG Profil [{doc_id}] — {title} — NICHT zitieren!")
            lines.append("Dies ist eine VORSCHAU, keine Primärquelle.")
            lines.append("Analysiere und zitiere NUR den ORIGINALTEXT unten.")
            lines.append("------------------------------------------------------------")
            lines.append(stil_profiles[doc_id])
            lines.append("------------------------------------------------------------\n")
        lines.append("\n============================================================\n")
        lines.append("AB HIER: ORIGINALQUELLEN — Deine Analyse-Grundlage\n")
        lines.append("Zitiere NUR aus diesen Texten, NIEMALS aus Profilen.\n")
        lines.append("============================================================\n")
        return "\n".join(lines)
    def _group_sources_by_document(self, results: list) -> list:
        """Gruppiert Chunks nach Dokument (title) für den Enforcer.
        Verwendet dieselbe Dokument-Nummerierung wie _build_context_text."""
        from collections import OrderedDict
        
        # Nach title gruppieren, Reihenfolge bewahren
        doc_groups = OrderedDict()
        for chunk in results:
            meta = chunk.get('metadata', {})
            title = meta.get('chat_title', meta.get('title', 'Unbekannt'))
            if title not in doc_groups:
                doc_groups[title] = []
            doc_groups[title].append(chunk)
        
        # Pro Dokument: einen Eintrag mit konkateniertem Inhalt
        grouped = []
        for doc_num, (title, chunks) in enumerate(doc_groups.items(), 1):
            # Alle Chunk-Inhalte zusammenfügen
            combined_content = "\n\n".join(
                chunk.get('content', '') for chunk in chunks
            )
            # Metadaten vom ersten Chunk übernehmen
            first_meta = chunks[0].get('metadata', {})
            
            grouped.append({
                'content': combined_content,
                'source_id': str(doc_num),  # Dokument-Nummer, nicht Chunk-Nummer!
                'metadata': first_meta
            })
        
        logger.info(f"📊 Enforcer-Quellen: {len(results)} Chunks → {len(grouped)} Dokumente gruppiert")
        return grouped
    def _build_synthesis_prompt(
        self, query: str, doc_metadata: List[Dict], intent: str, semantic_intent: str, context_text: str,
        extracted_quotes: list = None,   # <-- NEU, Default=None für Abwärtskompatibilität
        stil_profiles: dict = None      # <-- NEU v57+STILISTIC: Stil-Profile aus Phase 0.5
    ) -> Tuple[str, str, str]:
        """Baut den finalen Synthese-Prompt und die System-Instruction zusammen (v52: YAML-basiert)."""
        
        # 1. Formatierungs-Variablen sammeln (VOR structure_template!)
        doc_count = len(doc_metadata) if doc_metadata else 1
        # ── Compact-Mode: Drei Stufen (Claude-Option D) ──
        if doc_count <= 5:
            compact_mode = False
            max_words_per_doc = 150
        elif doc_count <= 8:
            compact_mode = "partial"
            max_words_per_doc = 100
        else:
            compact_mode = "full"
            max_words_per_doc = 70
        # 2. Struktur-Template dynamisch aufbauen
        # FIX v57: STILISTIC bekommt sein EIGENES Template — nicht das FORENSIC-Template!
        structure_template = ""
        if doc_metadata:
            for i, doc_info in enumerate(doc_metadata):
                structure_template += f"\n### QUELLE [{i+1}]: {doc_info['title']}\n"
                # ── STILISTIC-Template: Eigene Struktur, unabhängig von compact_mode ──
                if semantic_intent == "STILISTIC":
                    structure_template += (
                        f"1. SYNTAX UND PERIODENBAU:\n"
                        f"   BEFUND: [Beobachtung] — [Funktion]\n"
                        f"   BELEG: \"[Zitat, max. 20 Wörter]\"\n"
                        f"2. LEXIK UND WORTFELDER:\n"
                        f"   BEFUND: [Beobachtung] — [Funktion]\n"
                        f"   BELEG: \"[Zitat, max. 20 Wörter]\"\n"
                        f"3. TEXTUROBERFLÄCHE UND MATERIALITÄT:\n"
                        f"   BEFUND: [Beobachtung] — [Funktion]\n"
                        f"   BELEG: \"[Zitat, max. 20 Wörter]\"\n"
                        f"4. RHYTHMUS UND KADENZ:\n"
                        f"   BEFUND: [Beobachtung] — [Funktion]\n"
                        f"   BELEG: \"[Zitat, max. 20 Wörter]\"\n"
                        f"5. FIGUREN ALS SYNTAXPHÄNOMENE:\n"
                        f"   BEFUND: [Beobachtung] — [Funktion]\n"
                        f"   BELEG: \"[Zitat, max. 20 Wörter]\"\n"
                        f"   FREIER RAUM: [Überraschende Beobachtung]\n"
                        f"STIL-FAZIT: [Sprachliches Merkmal] — daher/weshalb [Wirkung]. 1-2 Sätze.\n"f"Aus den Beobachtungen abgeleitet.\n"
                    )
                elif semantic_intent == "STILISTIC_DEEPENING":
                    structure_template += (
                        f"AUSGANGSBEFUND: [1-2 zentrale Stil-Befunde, max. 40 Wörter]\n"
                        f"\n"
                        f"FUNKTIONALE INTERPRETATION:\n"
                        f"1. FUNKTION IM KONTEXT:\n"
                        f"   Schreibe 2-3 Sätze als fließenden Text. Erkläre die Wirkung, die der Befund im Text erzeugt.\n"
                        f"2. STRATEGIE DER MITTELWAHL:\n"
                        f"   Schreibe 1-2 Sätze als fließenden Text. Deute die Wahl als bewusste Strategie.\n"
                        f"3. TRADITION UND BRUCH:\n"
                        f"   Nenne die Tradition, an die der Befund anschließt. Beschreibe, wo sie durchbrochen wird.\n"
                        f"   Erkläre den funktionalen Gewinn des Bruchs. 2-3 Sätze.\n"
                        f"\n"
                        f"OPERATIVES URTEIL:\n"
                        f"1 Satz: ‹Merkmal› funktioniert als ‹Funktion›, weil ‹Grund›.\n"
                    )
                elif compact_mode == "full":
                    structure_template += f"1. BEFUND [{max_words_per_doc} Wörter]\n2. FAZIT [{max_words_per_doc} Wörter]\n"
                elif compact_mode == "partial":
                    structure_template += f"0. DOKUMENTTYP [1 Satz]\n1. BEFUND [{max_words_per_doc} Wörter]\n2. MOTIV [{max_words_per_doc} Wörter]\n3. KONSEQUENZ [{max_words_per_doc} Wörter]\n4. FAZIT [{max_words_per_doc} Wörter]\n"
                else:
                    structure_template += f"[4-6 Sätze mit 3-4 Zitaten]\n"
        format_kwargs = {
            "structure_template": structure_template,
            "compact_mode": bool(compact_mode),
            "max_words_per_doc": max_words_per_doc,
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
        # NEU: ZITAT-POOL mit Whitelist-Regel
        quote_block = ""
        if extracted_quotes:
            zitat_pool = self._build_zitat_pool(extracted_quotes)
            quote_block = (
                f"\n\n=== ZITAT-POOL ({doc_count} Quellen: [1]–[{doc_count}]) ===\n"
                f"WICHTIG: Es gibt exakt {doc_count} Quellen [1]–[{doc_count}]. "
                f"Zahlen wie [22] oder [26] im Quelltext sind INTERNE Referenzen "
                f"des Originaldokuments — KEINE Zitationsmarker!\n\n"
                f"{zitat_pool}\n\n"
                "ZITAT-POOL-REGEL:\n"
                "• <ZITAT quelle=\"X\">-Tags dürfen AUSSCHLIEßLICH Text enthalten, der WÖRTLICH oben im Pool steht.\n"
                "• Zitate dürfen NUR Quellen [1]–[N] referenzieren. Andere Zahlen sind INTERNE Referenzen!\n"
                "• ATTRIBUTIONS-ZWANG: Wenn ein Phrase im Pool als quelle=2 markiert ist, "
                "MUSS sie in deiner Synthese als [2] erscheinen — niemals als [4] oder [6]. "
                "Die Quelle-Zuweisung im ZITAT-POOL ist verbindlich.\n"
                "• Wenn du paraphrasierst: schreibe OHNE <ZITAT>-Tags: ...wie in Quelle [X] beschrieben.\n"
                "• FALSCH: <ZITAT quelle=\"1\">Sicherheitsarchitektur</ZITAT> — dieser Begriff steht nicht im Pool.\n"
                "• RICHTIG: <ZITAT quelle=\"1\">Der Begriff Zensur wird durch Sicherheitsarchitektur ersetzt</ZITAT> — falls dieser Text im Pool steht.\n"
                "• Ein Verweis OHNE Zitat ist immer besser als ein erfundenes Zitat.\n"
                "=== ENDE ZITAT-POOL ===\n"
            )
        
        # v57: Extraktions-Fehler-Warnung in den Prompt injizieren
        # Wenn Quellen im Zitat-Pool fehlen, warnt das Modell,
        # dass es für diese Quellen keine verifizierten Zitate verwenden soll
        extraction_failures = getattr(self, '_extraction_failures', [])
        if extraction_failures:
            failed_ids = [str(f['source_id']) for f in extraction_failures if f['reason'] == 'json_parse_failed']
            if failed_ids:
                failed_str = ", ".join(f"[{sid}]" for sid in failed_ids)
                extraction_warning = (
                    f"\n\n⚠️ EXTRAKTIONSWARNUNG: Für Quelle(n) {failed_str} "
                    f"konnten keine verifizierten Zitate extrahiert werden "
                    f"(JSON-Parsing-Fehler im Extraktions-Call). "
                    f"Der Quelltext IST im Kontext vorhanden, aber du DARFST für "
                    f"diese Quelle(n) KEINE <ZITAT>-Tags verwenden — nur Paraphrasen "
                    f"ohne Zitat-Tag. Schreibe stattdessen z.B.: "
                    f"„Wie in Quelle [{failed_ids[0]}] dargelegt...\" "
                    f"ohne <ZITAT>-Markup.\n"
                )
                quote_block += extraction_warning
        
        # Bestehenden Prompt um den Zitat-Block erweitern
        prompt = self.prompt_manager.build_task_prompt(
            query, mode_display, base_instruction, context_text
        )
        
        # Zitat-Block VOR dem eigentlichen Task in den Prompt einfügen
        if quote_block:
            # Finde die Stelle nach den Quellen, vor der Aufgabenstellung
            prompt = quote_block + prompt
        # ── STILISTIC: Stil-Profile VOR dem ZITAT-POOL injizieren ──
        # Stilistischer Frame muss etabliert sein, bevor das Modell
        # die Zitate sieht — sonst gewinnt der thematische Frame.
        if stil_profiles and semantic_intent == "STILISTIC":
            stil_block = self._build_stil_profile_block(stil_profiles, doc_metadata)
            if stil_block:
                # STIL-PROFILE ganz am Anfang des Prompts (vor allem anderen)
                prompt = stil_block + prompt
                logger.info(f"🎭 Stil-Profile injiziert: {len(stil_profiles)} Profile VOR Zitat-Pool")
        # ── Fix J.2: Titel-Mapping-Injektion (unabhängig vom ZITAT-POOL) ──
        # Explizite Titel-Tabelle direkt vor der AUFGABE — das Modell sieht
        # die Mapping-Tabelle, bevor es zu schreiben beginnt.
        # Löst: Dokumentnamen [4]-[6] werden als "Dokument" statt korrektem Titel
        if doc_metadata:
            title_map = "\n\nQUELLEN-VERZEICHNIS (verbindlich):\n"
            for i, doc in enumerate(doc_metadata, 1):
                title_map += f"[{i}] = \"{doc['title']}\"\n"
            title_map += "Verwende diese Titel EXAKT in deinen Überschriften.\n"
            # VOR der AUFGABE einfügen (Recency-Bias)
            task_marker = "\nAUFGABE:"
            if task_marker in prompt:
                prompt = prompt.replace(task_marker, title_map + task_marker, 1)
            else:
                prompt = title_map + prompt
        # ── Compact-Mode: Stufen-spezifische Instruktion ──
        # FIX v57.1: STILISTIC bekommt seine EIGENE compact_instruction!
        # Vorher: compact_mode=partial erzwang FORENSIC-Format (DOKUMENTTYP/BEFUND/MOTIV)
        # auch bei STILISTIC → Modell sah zwei widersprüchliche Struktur-Anweisungen.
        # FIX v57.3: STILISTIC-compact_instruction verwendet BEFUND/BELEG (5 Kategorien)
        # ARCHITEKTUR/MIKRO-STIL/STIL-FAZIT — konsistent mit dem structure_template.
        if semantic_intent == "STILISTIC":
            # STILISTIC-eigene Compact-Anweisung (konsistent mit structure_template)
            if compact_mode == "partial":
                compact_instruction = (
                    f"\n\n⚠️ COMPACT-MODE PARTIAL — STILISTISCH ({doc_count} Dokumente).\n"
                    f"Für JEDES Dokument:\n"
                    f"### QUELLE [N]: [Titel]\n"
                    f"1. SYNTAX UND PERIODENBAU: BEFUND + BELEG\n"
                    f"2. LEXIK UND WORTFELDER: BEFUND + BELEG\n"
                    f"3. TEXTUROBERFLÄCHE UND MATERIALITÄT: BEFUND + BELEG\n"
                    f"4. RHYTHMUS UND KADENZ: BEFUND + BELEG\n"
                    f"5. FIGUREN ALS SYNTAXPHÄNOMENE: BEFUND + BELEG\n"
                    f"FREIER RAUM: Überraschende Beobachtung.\n"
                    f"STIL-FAZIT: [Sprachliches Merkmal] — daher/weshalb [Wirkung]. 1-2 Sätze.\n"f"Aus Beobachtungen abgeleitet.\n"
                    f"Beobachte SPRACHE, nicht Rhetorik. BEFUND = 1 Satz Beobachtung. BELEG = 1 Zitat. "
                    f"Analysiere die ORIGINALQUELLEN, NICHT die obigen Profile. "
                    f"GLOBALE SYNTHESE: STILISTISCHE KONVERGENZEN / "
                    f"STILISTISCHE DIVERZENZEN / SPRACHLICHE WAHLVERWANDTSCHAFT / STRUKTURELLES FAZIT."
                )
                prompt = prompt + compact_instruction
            elif compact_mode == "full":
                compact_instruction = (
                    f"\n\n⚠️ COMPACT-MODE FULL — STILISTISCH ({doc_count} Dokumente).\n"
                    f"Für JEDES Dokument:\n"
                    f"### QUELLE [N]: [Titel]\n"
                    f"1. SYNTAX UND PERIODENBAU: BEFUND + BELEG\n"
                    f"2. LEXIK UND WORTFELDER: BEFUND + BELEG\n"
                    f"3. TEXTUROBERFLÄCHE UND MATERIALITÄT: BEFUND + BELEG\n"
                    f"4. RHYTHMUS UND KADENZ: BEFUND + BELEG\n"
                    f"5. FIGUREN ALS SYNTAXPHÄNOMENE: BEFUND + BELEG\n"
                    f"FREIER RAUM: Überraschende Beobachtung.\n"
                    f"STIL-FAZIT: [Sprachliches Merkmal] — daher/weshalb [Wirkung]. 1-2 Sätze.\n"f"Aus Beobachtungen abgeleitet.\n"
                    f"Beobachte SPRACHE, nicht Rhetorik. BEFUND = 1 Satz. BELEG = 1 Zitat. "
                    f"Analysiere ORIGINALQUELLEN, NICHT obige Profile. "
                    f"GLOBALE SYNTHESE wie oben."
                )
                prompt = prompt + compact_instruction
        elif semantic_intent == "STILISTIC_DEEPENING":
            # STILISTIC_DEEPENING-eigene Compact-Anweisung (konsistent mit structure_template)
            if compact_mode == "partial":
                compact_instruction = (
                    f"\n\n⚠️ COMPACT-MODE PARTIAL — STILISTIC DEEPENING ({doc_count} Dokumente).\n"
                    f"Für JEDES Dokument:\n"
                    f"### QUELLE [N]: [Titel]\n"
                    f"AUSGANGSBEFUND: [1-2 zentrale Stil-Befunde, max. 40 Wörter]\n"
                    f"\n"
                    f"FUNKTIONALE INTERPRETATION:\n"
                    f"1. FUNKTION IM KONTEXT: [2-3 Sätze als fließender Text]\n"
                    f"2. STRATEGIE DER MITTELWAHL: [1-2 Sätze als fließender Text]\n"
                    f"3. TRADITION UND BRUCH: [2-3 Sätze]\n"
                    f"\n"
                    f"OPERATIVES URTEIL: 1 Satz: ‹Merkmal› funktioniert als ‹Funktion›, weil ‹Grund›.\n"
                    f"\n"
                    f"GLOBALE SYNTHESE: FUNKTIONALE KONVERGENZEN / "
                    f"FUNKTIONALE DIVERZENZEN / WAHLVERWANDTSCHAFT DER FUNKTIONEN / STRUKTURELLES FAZIT."
                )
                prompt = prompt + compact_instruction
            elif compact_mode == "full":
                compact_instruction = (
                    f"\n\n⚠️ COMPACT-MODE FULL — STILISTIC DEEPENING ({doc_count} Dokumente).\n"
                    f"Für JEDES Dokument:\n"
                    f"### QUELLE [N]: [Titel]\n"
                    f"AUSGANGSBEFUND: [max. 40 Wörter]\n"
                    f"FUNKTIONALE INTERPRETATION: [3-5 Sätze]\n"
                    f"OPERATIVES URTEIL: [1 Satz]\n"
                    f"\n"
                    f"GLOBALE SYNTHESE wie oben."
                )
                prompt = prompt + compact_instruction
            # Bei compact_mode=False (≤5 Dokumente): structure_template via YAML reicht
        else:
            # FORENSIC/ANALYTICAL-compact_instruction (unverändert)
            if compact_mode == "partial":
                compact_instruction = (
                    f"\n\n⚠️ COMPACT-MODE PARTIAL ({doc_count} Dokumente).\n"
                    f"Für JEDES Dokument NUR:\n"
                    f"### QUELLE [N]: [Titel]\n"
                    f"0. DOKUMENTTYP: [1 Satz]\n"
                    f"1. BEFUND (max. {max_words_per_doc} Wörter)\n"
                    f"2. MOTIV (max. {max_words_per_doc} Wörter)\n"
                    f"3. KONSEQUENZ (max. {max_words_per_doc} Wörter)\n"
                    f"4. FAZIT (max. {max_words_per_doc} Wörter)\n"
                    f"WEGLASSEN: RHETORISCHE STRATEGIE.\n"
                    f"GLOBALE SYNTHESE unverändert."
                )
                prompt = prompt + compact_instruction
            elif compact_mode == "full":
                compact_instruction = (
                    f"\n\n⚠️ COMPACT-MODE FULL ({doc_count} Dokumente).\n"
                    f"Für JEDES Dokument NUR:\n"
                    f"### QUELLE [N]: [Titel]\n"
                    f"1. BEFUND (max. {max_words_per_doc} Wörter)\n"
                    f"2. FAZIT (max. {max_words_per_doc} Wörter)\n"
                    f"KEIN: DOKUMENTTYP, RHETORISCHE STRATEGIE, FUNKTIONALES MOTIV, DISKURSIVE KONSEQUENZ.\n"
                    f"GLOBALE SYNTHESE unverändert."
                )
                prompt = prompt + compact_instruction
        # 6. System-Instruction aus YAML holen (inkl. injizierter QUELLENREGEL)
        dynamic_sys_instruct = self.prompt_manager.get_system_instruction(semantic_intent)
        return prompt, mode_display, dynamic_sys_instruct
    def _execute_llm_call(
        self, query: str, prompt: str, dynamic_sys_instruct: str, intent: str, 
        semantic_intent: str, top_results: List[Dict], top_results_sorted: List[Dict], 
        rerank_stats: Dict, rejected_chunks: List[Dict], extracted_quotes: list = None,
        is_small_corpus: bool = False
    ) -> Tuple[str, List[Dict], str, List[Dict]]:
        """Führt den LLM Call mit Retries durch und baut den Pipeline Trace."""
        
        logger.info(f"🔢 Token-Audit POST-TRIM: chunks_real= {sum(len(c.get('content','')) // 4 for c in top_results_sorted)} | n_chunks={len(top_results_sorted)}")
        # extracted_quotes wird als Parameter übergeben, nicht intern erzeugt
        max_retries = 3
        for attempt in range(max_retries):
            try:
                synthesis_temp = 0.4 if semantic_intent in (
                      "ANALYTICAL_FORENSIC", "META_ANALYTICAL", "STILISTIC", "STILISTIC_DEEPENING"
                ) else 0.7
                # Fix D: Dynamisches Token-Limit für ESSENCE_PARITY mit >5 Docs
                dynamic_max_tokens = MAX_TOKENS_PER_CALL
                if is_small_corpus:
                    # SMALL-CORPUS: Bei wenigen Chunks braucht das Modell weniger
                    # Input, aber genauso viel Output-Space für eine vollständige Analyse
                    dynamic_max_tokens = MAX_TOKENS_PER_CALL  # 8192 reicht
                    # ANALYTICAL-Temperatur: 0.4 statt 0.7 für präzisere Vergleiche
                    if semantic_intent == "ANALYTICAL":
                        synthesis_temp = 0.4
                        logger.info(f"🧊 Small-Corpus: temp={synthesis_temp} für präzisen Vergleich")
                elif intent in ("ESSENCE_PARITY", "STILISTIC_DEEPENING"):
                    doc_count = len(set(r.get('chat_id') for r in top_results_sorted))
                    if doc_count > 5:
                        # Pro zusätzlichem Doc ~1500 Tokens mehr (6→9592, 8→12592, 10→15592)
                        dynamic_max_tokens = min(
                            MAX_TOKENS_PER_CALL + (doc_count - 5) * 1500,
                            16384
                        )
                        logger.info(f"📈 Fix D: Token-Limit erhöht auf {dynamic_max_tokens} ({doc_count} Docs)")
                logger.info(f"🚀 Starte Synthese-Call (Versuch {attempt+1}, max_tokens={dynamic_max_tokens}, temp={synthesis_temp})...")
                from modules.config import DOMAIN_PROFILES, DOMAIN_ANALYSIS
                _profile = DOMAIN_PROFILES.get(DOMAIN_ANALYSIS, {})
                result = self._llm_call_func(
                    prompt,
                    task="synthesis",
                    system_instruction=dynamic_sys_instruct,
                    temperature=synthesis_temp,
                    max_tokens=dynamic_max_tokens,
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
                from modules.config import get_model_for_task, DOMAIN_PROFILES, DOMAIN_ANALYSIS
                _profile = DOMAIN_PROFILES.get(DOMAIN_ANALYSIS, {})
                save_analysis(
                    analysis_id=_analysis_id,
                    query=query,
                    answer_text=final_text,
                    intent=intent,
                    semantic_intent=semantic_intent,
                    analysis_domain=DOMAIN_ANALYSIS,
                    model=get_model_for_task("synthesis"),
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
                    "extraction_failures": getattr(self, '_extraction_failures', []),  # v57
                    "timestamp":        __import__('time').time()
                }
                return final_text, top_results_sorted, intent, extracted_quotes
            except Exception as e:
                logger.error(f"⚠️ API Versuch {attempt+1} fehlgeschlagen: {e}")
                if attempt < max_retries - 1:
                    time.sleep((attempt + 1) * 2)
                    continue
                return f"❌ Fehler: {e}", top_results_sorted, intent, []
        return "❌ LLM nicht verfügbar.", top_results_sorted, intent, []
    # ======================================================================
    # === VALIDATION ORCHESTRATOR ===
    # ======================================================================
    # Methoden: split_thought_and_speech, validate_citations,
    #           verify_fact_match, verify_fact_match_multisource
    # Zustand:  self._enforcer (READ)
    #           Keine self.*-WRITES — zustandslos!
    # Zukunft:  Kandidat fuer eigenes ValidationOrchestrator-Modul (sauber trennbar)
    # ======================================================================
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
        """Struktureller Citation-Check - unterstützt [X] und <ZITAT quelle="X">."""
        warnings = []
        # 1. Prüfe klassische [X] Zitate
        bracket_matches = re.findall(r"\[(\d+)\]", answer)
        
        # 2. Prüfe neue <ZITAT quelle="X"> Tags
        zitat_matches = re.findall(r'<ZITAT quelle="(\d+)">', answer)
        
        # 3. Kombiniere alle Zitate
        all_matches = bracket_matches + zitat_matches
        if not all_matches:
            warnings.append("⚠️ Warnung: Keine Zitationen gefunden.")
            return warnings
        # 4. Validiere alle Quellennummern
        for m in all_matches:
            try:
                idx = int(m)
                if idx < 1 or idx > num_sources:
                    warnings.append(f"⚠️ Ungültige Zitation: [{idx}]")
            except ValueError:
                warnings.append(f"⚠️ Ungültiges Zitatformat: {m}")
        return warnings
    def verify_fact_match(
        self, claim: str, source_text: str, source_meta: Dict, extracted_quotes: list = None
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
            result = enforcer.validate_claim(claim=claim, sources=sources, domain=DOMAIN_ANALYSIS, extracted_quotes=extracted_quotes)
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
            # v59.3-fix (Kimi Audit C1): Unbekanntes Format = UNBESTÄTIGT.
            # Vorher: return True → falsch-positive Bestätigung bei Format-Fehlern.
            return False, "Enforcer Format Unknown (unvalidated)"
        except Exception as e:
            logger.error(f"Enforcer Error: {e}")
            # v59.3-fix (Kimi Audit C1): Wenn die Validierung fehlschlägt, ist der Fakt UNBESTÄTIGT.
            # Vorher: return True → falsch-positive Bestätigung. Jetzt: return False.
            return False, f"ENFORCER ERROR (Validation failed): {e}"
    def verify_fact_match_multisource(
        self, claim: str, sources: List[Dict], extracted_quotes: list = None
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
            # v59.3-fix (Kimi Audit C1): Unbekanntes Format = UNBESTÄTIGT.
            return False, "Enforcer Format Unknown (unvalidated)"
        except Exception as e:
            logger.error(f"MultiSource Enforcer Error: {e}")
            # v59.3-fix (Kimi Audit C1): return False statt True bei Enforcer-Fehler.
            return False, f"ENFORCER ERROR (Validation failed): {e}"
    async def verify_facts_parallel(
        self, sentences: List[str], results: List[Dict], progress_callback=None, extracted_quotes: list = None
    ) -> List[Dict]:
        """Parallele Faktenprüfung."""
        sem = asyncio.Semaphore(5)
        completed = 0
        total = len(sentences)
        async def _bounded_check(sent):
            nonlocal completed
            async with sem:
                loop = asyncio.get_running_loop()
                # Zitierte Quellen-Nummern extrahieren
                matches = re.findall(r"\[(\d+)\]", sent)
                if not matches:
                    completed += 1
                    if progress_callback:
                        progress_callback(completed / total)
                    return None
                results_for_sentence = []  # ← IMMER initialisieren
                # ── Structural Marker Filter ──
                # Überschriften wie "0. DOKUMENTTYP:", "1. BEFUND:" etc.
                # nicht als Claims validieren — spart LLM-Calls und vermeidet Rauschen
                if self._enforcer and hasattr(self._enforcer, '_is_structural_marker'):
                    if self._enforcer._is_structural_marker(sent):
                        completed += 1
                        if progress_callback:
                            progress_callback(completed / total)
                        return None
                # ── source_id-basierte Lookup ──
                unique_doc_nums = list(set(int(m) for m in matches))
                # Alle Chunks aus ALLEN zitierten Dokumenten sammeln
                all_enforcer_sources = []
                for doc_num in unique_doc_nums:
                    matching_chunks = [
                        r for r in results
                        if r.get('source_id') == doc_num
                    ]
                    if not matching_chunks:
                        logger.warning(
                            f"⚠️ Keine Chunks mit source_id={doc_num} "
                            f"gefunden für Zitat [{doc_num}]"
                        )
                        continue
                    for chunk in matching_chunks:
                        all_enforcer_sources.append({
                            "content": chunk.get("content", ""),
                            "metadata": chunk.get("metadata", {}),
                            "source_id": str(doc_num),
                        })
                if not all_enforcer_sources:
                    completed += 1
                    if progress_callback:
                        progress_callback(completed / total)
                    return None
                # ── EIN einziger Aufruf mit ALLEN Quellen ──
                # Egal ob 1 oder 5 Dokumente zitiert werden — 
                # der Enforcer bekommt ALLES auf einmal
                is_valid, reason = await loop.run_in_executor(
                    None,
                    partial(
                        self.verify_fact_match_multisource,
                        sent,
                        all_enforcer_sources
                    ),
                )
                results_for_sentence.append(
                    {
                        "sentence": sent,
                        "source_id": "+".join(str(n) for n in sorted(unique_doc_nums)),
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
    # ======================================================================
    # === IFS SUPERVISOR ===
    # ======================================================================
    # Methoden: generate_ifs_supervision
    # Zustand:  self.prompt_manager (READ), self._llm_call_func (READ)
    #           Keine self.*-WRITES — zustandslos!
    # Zukunft:  Kandidat fuer eigenes IFSExecutionEngine-Modul (sauber trennbar)
    # ======================================================================
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
