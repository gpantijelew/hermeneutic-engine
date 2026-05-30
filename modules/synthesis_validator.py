# modules/synthesis_validator.py — Drei-Phasen-Synthese: Phase 2 (Check) + Phase 3 (Korrektur)
"""
Architektur-Entscheidung (Gemini-Freigabe, 2026-05-16):
- Phase 2: Deterministischer, mechanischer Check des Synthese-Drafts
- Phase 3: Gezielte Korrektur mit kurzem Prompt (temp=0.0, flash-Modell)
- 1 Runde Korrektur, nicht verhandelbar (80/20-Regel)
- <WARNUNG>-Tag für unkorrigierbare Abschnitte (Transparenz)
- Skip-Optimierung: Bei 0 Fehlern → Phase 3 überspringen

Checks C1-C6:
- C1: Zitat-Range (1 ≤ quelle ≤ N)
- C2: Substring-Existenz im Quelldokument
- C3: Fuzzy-Fallback (SequenceMatcher ≥ 0.85)
- C4: Dokumentnamen matchen QUELLEN-VERZEICHNIS
- C5: Verwaiste Referenzen ([N] ohne ZITAT-Tag)
- C6: Ungültige nackte Referenzen ([N] mit N außerhalb [1]–[N])

Phase 1.5: Truncation-Detection
- Erkennt ob Synthese unvollständig (fehlende QUELLE-Abschnitte)
- Löst Continuation-Call aus (flash, temp=0.3)
"""

import re
import logging
from difflib import SequenceMatcher
from typing import List, Dict, Tuple, Optional

logger = logging.getLogger(__name__)

# ── Schwellenwerte ──
FUZZY_THRESHOLD = 0.85  # Wie bei Fix E im Enforcer


class ValidationError:
    """Ein einzelner Validierungsfehler aus Phase 2."""
    
    def __init__(self, code: str, severity: str, source_id: int, 
                 quote_text: str = "", expected: str = "", message: str = ""):
        self.code = code          # C1, C2, C3, C4, C5
        self.severity = severity  # "error" | "warning"
        self.source_id = source_id
        self.quote_text = quote_text
        self.expected = expected
        self.message = message
    
    def __repr__(self):
        return f"[{self.code}] {self.severity.upper()}: {self.message}"


class SynthesisValidator:
    """
    Phase 2 + Phase 3 der Drei-Phasen-Synthese.
    
    Phase 2: Mechanischer Check (deterministisch, kein LLM)
    Phase 3: Gezielte Korrektur (kurzer Prompt, temp=0.0, flash-Modell)
    """
    
    def __init__(self, llm_call_func=None):
        """
        Args:
            llm_call_func: Die LLM-Call-Funktion (z.B. llm_wrapper.llm_call)
        """
        self._llm_call_func = llm_call_func
    
    # =========================================================================
    # PHASE 2: MECHANISCHER CHECK
    # =========================================================================
    
    def validate_draft(
        self,
        draft: str,
        num_sources: int,
        source_texts: Dict[int, str],
        doc_metadata: List[Dict],
        extracted_quotes: Optional[List[Dict]] = None,
    ) -> Tuple[str, List[ValidationError]]:
        """
        Führt Checks C1-C5 auf den Synthese-Draft durch.
        
        Args:
            draft: Der Synthese-Entwurf mit <ZITAT quelle="X">text</ZITAT>-Tags
            num_sources: Anzahl der Quellen (N)
            source_texts: Dict source_id → concat-Text aller Chunks dieser Quelle
            doc_metadata: Liste von {title, source_id} für Dokumentnamen-Check
            extracted_quotes: Optional: Pool-Zitate für erweiterte Prüfung
            
        Returns:
            (corrected_draft, errors) — corrected_draft enthält <WARNUNG>-Tags
            bei unkorrigierbaren Fehlern, errors ist die Liste aller gefundenen Fehler
        """
        errors = []
        
        # ── C1 + C2 + C3: ZITAT-Tags prüfen ──
        zitat_errors = self._check_zitat_tags(
            draft, num_sources, source_texts, extracted_quotes
        )
        errors.extend(zitat_errors)
        
        # ── C4: Dokumentnamen prüfen ──
        name_errors = self._check_document_names(draft, doc_metadata)
        errors.extend(name_errors)
        
        # ── C5 + C6: Verwaiste + ungültige Referenzen ──
        orphan_errors = self._check_orphan_references(draft, num_sources, source_texts)
        errors.extend(orphan_errors)
        
        # ── <WARNUNG>-Tags für unkorrigierbare Abschnitte einfügen ──
        corrected_draft = self._insert_warning_tags(draft, errors)
        
        error_count = len([e for e in errors if e.severity == "error"])
        warning_count = len([e for e in errors if e.severity == "warning"])
        logger.info(
            f"🔍 Phase 2 Check: {error_count} Fehler, {warning_count} Warnungen "
            f"bei {num_sources} Quellen"
        )
        
        return corrected_draft, errors
    
    def _check_zitat_tags(
        self,
        draft: str,
        num_sources: int,
        source_texts: Dict[int, str],
        extracted_quotes: Optional[List[Dict]] = None,
    ) -> List[ValidationError]:
        """C1: Zitat-Range + C2: Substring-Existenz + C3: Fuzzy-Fallback."""
        errors = []
        
        # Alle <ZITAT quelle="X">text</ZITAT> extrahieren
        zitat_pattern = re.compile(
            r'<ZITAT quelle="(\d+)">(.*?)</ZITAT>', 
            re.DOTALL
        )
        
        for match in zitat_pattern.finditer(draft):
            source_id = int(match.group(1))
            quote_text = match.group(2).strip()
            
            # ── C1: Range-Check ──
            if source_id < 1 or source_id > num_sources:
                errors.append(ValidationError(
                    code="C1",
                    severity="error",
                    source_id=source_id,
                    quote_text=quote_text,
                    message=f"ZITAT [{source_id}]: Quellen-ID außerhalb des "
                            f"gültigen Bereichs [1]–[{num_sources}]"
                ))
                continue  # Keine weiteren Checks für dieses Zitat
            
            # ── C2: Substring-Existenz ──
            source_text = source_texts.get(source_id, "")
            if not source_text:
                errors.append(ValidationError(
                    code="C2",
                    severity="warning",
                    source_id=source_id,
                    quote_text=quote_text,
                    message=f"ZITAT [{source_id}]: Kein Quelltext verfügbar "
                            f"für Validierung"
                ))
                continue
            
            # Exakter Substring-Check (case-sensitive, aber whitespace-normalisiert)
            normalized_quote = self._normalize_whitespace(quote_text)
            normalized_source = self._normalize_whitespace(source_text)
            
            if normalized_quote in normalized_source:
                continue  # ✅ Zitat verifiziert
            
            # ── C3: Fuzzy-Fallback ──
            best_ratio = self._find_best_fuzzy_ratio(quote_text, source_text)
            
            if best_ratio >= FUZZY_THRESHOLD:
                logger.debug(
                    f"  C3 Fuzzy-Pass: ZITAT [{source_id}] "
                    f"Ähnlichkeit={best_ratio:.2f}"
                )
                continue  # ✅ Zitat fuzzy-verifiziert
            
            # ── Zitat NICHT verifiziert ──
            errors.append(ValidationError(
                code="C2",
                severity="error",
                source_id=source_id,
                quote_text=quote_text,
                message=f"ZITAT [{source_id}]: „{quote_text[:60]}...\" "
                        f"NICHT in Quelle [{source_id}] gefunden "
                        f"(Fuzzy-Ratio={best_ratio:.2f})"
            ))
        
        return errors
    
    def _check_document_names(
        self,
        draft: str,
        doc_metadata: List[Dict],
    ) -> List[ValidationError]:
        """C4: Prüft ob QUELLE-Überschriften die korrekten Dokumentnamen verwenden."""
        errors = []
        
        if not doc_metadata:
            return errors
        
        # Erwartete Titel pro source_id
        expected_titles = {}
        for doc in doc_metadata:
            sid = doc.get('source_id', 0)
            title = doc.get('title', '')
            if sid and title:
                expected_titles[sid] = title
        
        # Finde QUELLE-Überschriften im Draft
        # Pattern: ### QUELLE [N]: Irgendetwas
        heading_pattern = re.compile(
            r'###\s+QUELLE\s+\[(\d+)\]:\s*(.+?)(?:\n|$)'
        )
        
        for match in heading_pattern.finditer(draft):
            source_id = int(match.group(1))
            found_title = match.group(2).strip()
            expected = expected_titles.get(source_id, "")
            
            if not expected:
                continue  # Kein erwarteter Titel → kein Check möglich
            
            if found_title != expected:
                # Fuzzy-Check: Vielleicht nur leicht abweichend
                ratio = SequenceMatcher(
                    None, 
                    found_title.lower(), 
                    expected.lower()
                ).ratio()
                
                if ratio < FUZZY_THRESHOLD:
                    errors.append(ValidationError(
                        code="C4",
                        severity="error",
                        source_id=source_id,
                        quote_text=found_title,
                        expected=expected,
                        message=f"QUELLE [{source_id}]-Überschrift: "
                                f"„{found_title}\" → Korrekter Titel: „{expected}\""
                    ))
        
        return errors
    
    def _check_orphan_references(
        self,
        draft: str,
        num_sources: int,
        source_texts: Dict[int, str],
    ) -> List[ValidationError]:
        """C5 + C6: Findet [N]-Referenzen ohne <ZITAT>-Tag.
        
        C5: Gültige nackte [N] (1 ≤ N ≤ num_sources) → Warnung (Paraphrase OK)
        C6: Ungültige nackte [N] (N > num_sources oder N < 1) → ERROR
        
        Fix K.1: Nackte [N] mit N > num_sources waren vorher `continue`,
               weil C1 assumed dass sie in ZITAT-Tags stehen. Aber das LLM
               verwendet nackte [N] statt <ZITAT>-Tags — die fallen durch ALLE Checks!
               Fix K.2: Nackte [N] in Anführungszeichen → ERROR (falsches Zitat-Format)
        """
        errors = []
        
        # Alle [N] Referenzen finden, die NICHT innerhalb eines <ZITAT>-Tags stehen
        # Strategie: Entferne alle ZITAT-Tags, dann suche nach [N]-Referenzen
        draft_without_zitats = re.sub(
            r'<ZITAT quelle="\d+">.*?</ZITAT>', '', draft, flags=re.DOTALL
        )
        
        ref_pattern = re.compile(r'\[(\d+)\]')
        seen_c5 = set()  # Track already-reported C5 warnings
        seen_c6 = set()  # Track already-reported C6 errors
        
        for match in ref_pattern.finditer(draft_without_zitats):
            ref_id = int(match.group(1))
            
            # ── Fix K.2: Nackte [N] in Anführungszeichen → ERROR ──
            # Pattern: „text [N]" oder „text[N]" — das ist ein Zitat ohne ZITAT-Tag!
            # Das LLM hat vergessen, <ZITAT quelle="N"> zu verwenden.
            start_pos = match.start()
            end_pos = match.end()
            # Schaue 60 Zeichen zurück und 20 Zeichen vor
            context_before = draft_without_zitats[max(0, start_pos-60):start_pos]
            context_after = draft_without_zitats[end_pos:min(len(draft_without_zitats), end_pos+20)]
            surrounding = context_before + '[' + str(ref_id) + ']' + context_after
            
            # Prüfe ob [N] in Anführungszeichen steht (deutsch: „..." oder englisch: "...")
            in_quotes = False
            quote_text = ""
            if '„' in context_before:
                # Finde das öffnende „
                quote_start = context_before.rfind('„')
                text_before_bracket = context_before[quote_start+1:]
                if '"' in context_after or '‖' in context_after:
                    in_quotes = True
                    # Extrahiere den zitierten Text
                    quote_text = text_before_bracket + '[' + str(ref_id) + ']' + context_after.split('"')[0]
            elif '"' in context_before and context_before.count('"') % 2 == 1:
                # Ungerade Anzahl " → ein öffnendes "
                in_quotes = True
                quote_start = context_before.rfind('"')
                text_before_bracket = context_before[quote_start+1:]
                quote_text = text_before_bracket + '[' + str(ref_id) + ']'
                if '"' in context_after:
                    quote_text += context_after.split('"')[0]
            
            if ref_id < 1 or ref_id > num_sources:
                # ── Fix K.1: UNGÜLTIGE nackte Referenz → ERROR ──
                # C1 deckt nur ZITAT-Tags ab. Nackte [15], [7], [9] etc.
                # fielen vorher durch ALLE Checks!
                if ref_id not in seen_c6:
                    seen_c6.add(ref_id)
                    errors.append(ValidationError(
                        code="C6",
                        severity="error",
                        source_id=ref_id,
                        quote_text=quote_text if in_quotes else '',
                        message=f"Referenz [{ref_id}] außerhalb des gültigen Bereichs "
                                f"[1]–[{num_sources}] — NACKTE Referenz ohne <ZITAT>-Tag. "
                                f"LÖSUNG: Entfernen oder als Paraphrase umformulieren."
                    ))
            elif in_quotes and quote_text:
                # ── Fix K.2: Nacktes Zitat in Anführungszeichen → ERROR ──
                # Das LLM hat „text [N]" statt <ZITAT quelle="N">text</ZITAT> geschrieben
                # Prüfe ob der zitierte Text in der Quelle existiert
                source_text = source_texts.get(ref_id, "")
                if source_text:
                    # Entferne die [N]-Referenz aus dem Zitat für den Vergleich
                    clean_quote = re.sub(r'\[\d+\]', '', quote_text).strip()
                    if clean_quote:
                        normalized_quote = self._normalize_whitespace(clean_quote)
                        normalized_source = self._normalize_whitespace(source_text)
                        if normalized_quote not in normalized_source:
                            # Fuzzy-Check
                            fuzzy_ratio = self._find_best_fuzzy_ratio(clean_quote, source_text)
                            if fuzzy_ratio < FUZZY_THRESHOLD:
                                if ref_id not in seen_c6:
                                    seen_c6.add(ref_id)
                                    errors.append(ValidationError(
                                        code="C6",
                                        severity="error",
                                        source_id=ref_id,
                                        quote_text=quote_text[:80],
                                        message=(f"Nacktes Zitat [{ref_id}]: "
                                                 f"'{quote_text[:60]}...' NICHT in Quelle "
                                                 f"[{ref_id}] gefunden (Fuzzy={fuzzy_ratio:.2f}). "
                                                 f"LÖSUNG: Als Paraphrase ohne Anführungszeichen.")
                                    ))
                        # else: Zitat existiert in Quelle → nur C5 Warning
                
                # Zusätzlich: C5 Warning für gültige nackte Zitate
                if ref_id not in seen_c5:
                    seen_c5.add(ref_id)
                    errors.append(ValidationError(
                        code="C5",
                        severity="warning",
                        source_id=ref_id,
                        message=f"Referenz [{ref_id}] im Text ohne <ZITAT>-Tag "
                                f"(möglicherweise Paraphrase — OK)"
                    ))
            else:
                # Normale nackte Referenz → nur Warnung
                if ref_id not in seen_c5:
                    seen_c5.add(ref_id)
                    errors.append(ValidationError(
                        code="C5",
                        severity="warning",
                        source_id=ref_id,
                        message=f"Referenz [{ref_id}] im Text ohne <ZITAT>-Tag "
                                f"(möglicherweise Paraphrase — OK)"
                    ))
        
        return errors
    
    def _insert_warning_tags(
        self,
        draft: str,
        errors: List[ValidationError],
    ) -> str:
        """
        Fügt <WARNUNG>-Tags für Abschnitte mit mehreren unverifizierten Zitaten ein.
        Gemini: „Transparenz ist die höchste Tugend eines forensischen Systems."
        """
        # Finde Absätze mit >1 unverifizierten Zitat-Fehlern
        error_sources_per_paragraph = {}
        
        c2_errors = [e for e in errors if e.code == "C2" and e.severity == "error"]
        if not c2_errors:
            return draft
        
        # Finde den Absatz für jeden C2-Fehler
        paragraphs = draft.split('\n\n')
        for error in c2_errors:
            quote_snippet = error.quote_text[:40]
            for i, para in enumerate(paragraphs):
                if quote_snippet in para:
                    if i not in error_sources_per_paragraph:
                        error_sources_per_paragraph[i] = []
                    error_sources_per_paragraph[i].append(error)
                    break
        
        # Absätze mit ≥2 C2-Fehlern → <WARNUNG>-Tag
        result_paragraphs = list(paragraphs)
        for para_idx, para_errors in error_sources_per_paragraph.items():
            if len(para_errors) >= 2:
                source_ids = sorted(set(e.source_id for e in para_errors))
                warning_tag = (
                    f'<WARNUNG typ="unverifizierbar" '
                    f'grund="Mehrere Zitate in diesem Absatz konnten nicht '
                    f'validiert werden (Quellen {source_ids}).">'
                    f'Dieser Absatz basiert möglicherweise auf nicht '
                    f'verifizierten Behauptungen.</WARNUNG>\n\n'
                )
                result_paragraphs[para_idx] = warning_tag + result_paragraphs[para_idx]
        
        return '\n\n'.join(result_paragraphs)
    
    # =========================================================================
    # PHASE 3: KORREKTUR
    # =========================================================================
    
    def build_correction_prompt(
        self,
        draft: str,
        errors: List[ValidationError],
        doc_metadata: List[Dict],
    ) -> str:
        """
        Baut den Phase-3-Korrektur-Prompt.
        
        KURZ: Nur Draft + Fehler-Protokoll. Keine 200KB Dokumente.
        Kein ZITAT-POOL. Kein Kontext. Nur: „Ersetze X durch Y."
        """
        # Nur Fehler (keine Warnungen) ins Protokoll aufnehmen
        correction_errors = [e for e in errors if e.severity == "error"]
        
        if not correction_errors:
            return ""  # Kein Korrektur-Prompt nötig
        
        # Fehler-Protokoll bauen
        protocol_lines = []
        for i, error in enumerate(correction_errors, 1):
            if error.code == "C1":
                protocol_lines.append(
                    f"[F{i}] ZITAT [{error.source_id}]: Quellen-ID ungültig "
                    f"(erlaubt: [1]–[N]). "
                    f"LÖSUNG: Entferne das <ZITAT>-Tag, schreibe als Paraphrase: "
                    f"„Quelle argumentiert, dass...\""
                )
            elif error.code == "C2":
                protocol_lines.append(
                    f"[F{i}] ZITAT [{error.source_id}]: „{error.quote_text[:80]}\" "
                    f"→ Nicht in Quelle gefunden. "
                    f"LÖSUNG: Entferne das <ZITAT>-Tag, schreibe stattdessen: "
                    f"„Quelle [{error.source_id}] argumentiert, dass...\""
                )
            elif error.code == "C4":
                protocol_lines.append(
                    f"[F{i}] QUELLE [{error.source_id}]-Überschrift: "
                    f"„{error.quote_text}\" → Korrekt: „{error.expected}\""
                )
            elif error.code == "C6":
                protocol_lines.append(
                    f"[F{i}] NACKTE Referenz [{error.source_id}]: "
                    f"{error.message}"
                )
        
        # Titel-Referenz für C4-Korrekturen
        title_reference = ""
        if any(e.code == "C4" for e in correction_errors):
            title_lines = ["KORREKTE DOKUMENTTITEL:"]
            for doc in doc_metadata:
                sid = doc.get('source_id', 0)
                title = doc.get('title', '')
                if sid and title:
                    title_lines.append(f"  [{sid}] = \"{title}\"")
            title_reference = "\n".join(title_lines) + "\n\n"
        
        protocol = "\n".join(protocol_lines)
        
        correction_prompt = f"""KORREKTUR-AUFGABE:
Dein Synthese-Entwurf enthält überprüfte Fehler. Korrigiere NUR diese.

ENTWURF:
{draft}

{title_reference}FEHLER-PROTOKOLL ({len(correction_errors)} Fehler):
{protocol}

REGELN:
- GIB DEN GESAMTEN KORRIGIERTEN ENTWURF ZURÜCK — nicht nur die Korrekturen!
- Ändre NUR die markierten Fehler, alles andere bleibt UNVERÄNDERT
- Erfinde KEINE neuen Zitate
- Wenn ein Zitat nicht verifiziert ist → als Paraphrase ohne <ZITAT>-Tag
- WICHTIG: Dein Output muss den GESAMTEN Text enthalten, nicht nur Fragmente

KORRIGIERTER ENTWURF (VOLLSTÄNDIG):"""
        
        return correction_prompt
    
    def run_correction(
        self,
        draft: str,
        errors: List[ValidationError],
        doc_metadata: List[Dict],
        max_tokens: int = 2048,
    ) -> Tuple[str, bool]:
        """
        Führt Phase 3 durch: Korrektur-LLM-Call.
        
        Args:
            draft: Der Synthese-Draft (mit <WARNUNG>-Tags)
            errors: Die Fehler aus Phase 2
            doc_metadata: Dokument-Metadaten für Titel-Referenz
            max_tokens: Max Tokens für Korrektur (default 2048)
            
        Returns:
            (corrected_text, correction_applied)
            - correction_applied = False wenn keine Fehler → Skip-Optimierung
            
        SICHERHEITS-REGEL (Fix L.1):
        Wenn die Korrektur kürzer als 50% des Originals ist, wird sie
        ABGELEHNT und das Original (mit <WARNUNG>-Tags) beibehalten.
        Grund: flash-Modelle geben oft nur die Korrektur-Stellen zurück,
        nicht den gesamten Text → katastrophaler Datenverlust.
        """
        # Skip-Optimierung: Bei 0 Fehlern → Phase 3 überspringen
        correction_errors = [e for e in errors if e.severity == "error"]
        if not correction_errors:
            logger.info("✅ Phase 2: 0 Fehler → Phase 3 übersprungen (Skip-Optimierung)")
            return draft, False
        
        if not self._llm_call_func:
            logger.warning("⚠️ Keine LLM-Call-Funktion → Korrektur übersprungen")
            return draft, False
        
        # Korrektur-Prompt bauen
        correction_prompt = self.build_correction_prompt(draft, errors, doc_metadata)
        
        if not correction_prompt:
            return draft, False
        
        logger.info(
            f"🔧 Phase 3: Starte Korrektur für {len(correction_errors)} Fehler "
            f"(Prompt-Größe: ~{len(correction_prompt)//4} Tokens)"
        )
        
        try:
            from modules.config import get_model_for_task, DOMAIN_PROFILES, DOMAIN_ANALYSIS
            
            correction_model = get_model_for_task("correction")
            
            # Lade Korrektur-System-Instruction aus YAML (wenn verfügbar)
            correction_sys_instruct = (
                "Du bist ein präziser Korrektur-Assistent. "
                "Du korrigierst NUR die explizit markierten Fehler. "
                "Du erfindest KEINE neuen Zitate. "
                "Du änderst KEINEN anderen Text."
            )
            try:
                from modules.prompt_manager import PromptManager
                pm = PromptManager()
                yaml_instruct = pm._data.get("correction_protocol", {}).get("system_instruction", "")
                if yaml_instruct:
                    correction_sys_instruct = yaml_instruct
            except Exception:
                pass  # Fallback auf Hardcoded
            
            # Gemini-Empfehlung: temp=0.0, keine Kreativität bei mechanischer Aufgabe
            result = self._llm_call_func(
                correction_prompt,
                task="correction",
                system_instruction=correction_sys_instruct,
                temperature=0.0,  # Gemini: „Kein Grund für irgendeine Kreativität"
                max_tokens=max_tokens,
                domain=DOMAIN_ANALYSIS,
            )
            
            if not result:
                logger.warning("⚠️ Korrektur-LLM gab leere Antwort → Original beibehalten")
                return draft, False
            
            # Bereinige eventuelle Artefakte
            corrected = result.strip()
            
            # Entferne evtl. generierte Markdown-Code-Blöcke
            if corrected.startswith("```"):
                corrected = re.sub(r'^```\w*\n?', '', corrected)
                corrected = re.sub(r'\n?```$', '', corrected)
                corrected = corrected.strip()
            
            # ── Fix L.1 + L.3: LENGTH-SAFETY-CHECK ──
            # Fix L.1: Wenn die Korrektur kürzer als 80% des Originals ist,
            # hat das Modell den Text abgeschnitten (nur Korrektur-Stellen
            # oder unvollständigen Text zurückgegeben).
            # Fix L.3 (v57): Zusätzlich prüfen, ob die letzte QUELLE [N]
            # noch vorhanden ist — verhindert halbe Synthesen.
            draft_len = len(draft)
            corrected_len = len(corrected)
            ratio = corrected_len / draft_len if draft_len > 0 else 0
            
            # Fix L.3: Quellen-Vollständigkeits-Check
            # Der korrigierte Text MUSS die letzte QUELLE [N]-Überschrift enthalten.
            # Wenn sie fehlt, hat das Modell den Text abgeschnitten.
            last_source_id = None
            if doc_metadata:
                last_source_id = len(doc_metadata)  # N = Anzahl der Quellen
            source_complete = True
            if last_source_id and last_source_id > 0:
                last_source_marker = f"QUELLE [{last_source_id}]"
                if last_source_marker not in corrected:
                    source_complete = False
                    logger.warning(
                        f"⚠️ Phase 3: Letzte Quelle [{last_source_id}] fehlt im korrigierten Text — "
                        f"Modell hat den Text abgeschnitten."
                    )
            
            # Längen-Check: 80% Schwelle (v57: angehoben von 50%)
            # Ein korrigierter Text mit ≥80% Länge und vollständigen Quellen
            # ist akzeptabel. <80% oder fehlende letzte Quelle → ablehnen.
            if ratio < 0.8 or not source_complete:
                rejection_reason = []
                if ratio < 0.8:
                    rejection_reason.append(
                        f"Output zu kurz ({corrected_len} vs {draft_len} Zeichen, Ratio={ratio:.1%})"
                    )
                if not source_complete:
                    rejection_reason.append(
                        f"Letzte QUELLE [{last_source_id}] fehlt — Text unvollständig"
                    )
                logger.warning(
                    f"⚠️ Phase 3: Korrektur ABGELEHNT — {'; '.join(rejection_reason)}. "
                    f"Original mit <WARNUNG>-Tags beibehalten."
                )
                return draft, False
            
            logger.info(
                f"✅ Phase 3: Korrektur angewendet "
                f"({corrected_len} Zeichen, Ratio={ratio:.1%})"
            )
            return corrected, True
            
        except Exception as e:
            logger.error(f"❌ Phase 3 Korrektur fehlgeschlagen: {e} → Original beibehalten")
            return draft, False
    
    # =========================================================================
    # PHASE 1.5: TRUNCATION-DETECTION
    # =========================================================================
    
    @staticmethod
    def detect_truncation(
        draft: str,
        num_sources: int,
        doc_metadata: List[Dict],
    ) -> Tuple[bool, List[int], str]:
        """
        Erkennt ob eine Synthese unvollständig ist.
        
        Kriterien:
        1. Weniger QUELLE-Abschnitte als erwartet
        2. Letzter Abschnitt bricht mitten im Satz ab
        3. Kein GLOBALE SYNTHESE-Abschnitt
        
        Returns:
            (is_truncated, missing_sources, last_complete_text)
        """
        # Finde alle QUELLE-Abschnitte
        quelle_pattern = re.compile(r'###\s+QUELLE\s+\[(\d+)\]')
        found_sources = set()
        for match in quelle_pattern.finditer(draft):
            found_sources.add(int(match.group(1)))
        
        expected_sources = set(range(1, num_sources + 1))
        missing_sources = sorted(expected_sources - found_sources)
        
        # Prüfe ob der Text mitten im Satz abbricht
        ends_mid_sentence = False
        if draft:
            last_char = draft.rstrip()[-1] if draft.rstrip() else ''
            # Ein vollständiger Text endet normalerweise mit Satzzeichen
            if last_char not in '.!?:;»"\n' and missing_sources:
                ends_mid_sentence = True
        
        is_truncated = len(missing_sources) > 0 or ends_mid_sentence
        
        if is_truncated:
            logger.info(
                f"✂️ Phase 1.5 Truncation-Detection: "
                f"{'ABGEBROCHEN' if ends_mid_sentence else 'UNVOLLSTÄNDIG'}. "
                f"Fehlende Quellen: {missing_sources}. "
                f"Gefunden: {sorted(found_sources)}/{num_sources}"
            )
        
        # Finde den letzten vollständigen Absatz
        last_complete_text = draft
        if ends_mid_sentence and '\n\n' in draft:
            paragraphs = draft.rsplit('\n\n', 1)
            if len(paragraphs) > 1:
                last_complete_text = paragraphs[0]
        
        return is_truncated, missing_sources, last_complete_text
    
    def run_continuation(
        self,
        truncated_draft: str,
        missing_sources: List[int],
        doc_metadata: List[Dict],
        context_text: str = "",
        max_tokens: int = 8192,
        max_attempts: int = 3,
    ) -> Tuple[str, bool]:
        """
        Phase 1.5: Continuation-Call bei truncierter Synthese.
        
        Nutzt flash-Modell (schnell, günstig) mit moderater Temperatur,
        damit der Fortsetzungstext inhaltlich konsistent bleibt.
        
        Fix M.1: Loop-Continuation — wenn nach dem Continuation-Call
        noch Quellen fehlen, wird erneut fortgesetzt (bis max_attempts).
        Fix M.2: Kontext-Limit von 10K → 30K Zeichen erhöht.
        Fix M.3: Explicit-Output-Regel im Prompt.
        """
        if not missing_sources or not self._llm_call_func:
            return truncated_draft, False
        
        current_draft = truncated_draft
        total_added = 0
        
        for attempt in range(1, max_attempts + 1):
            # Finde verbleibende fehlende Quellen
            quelle_pattern = re.compile(r'###\s+QUELLE\s+\[(\d+)\]')
            found = set()
            for m in quelle_pattern.finditer(current_draft):
                found.add(int(m.group(1)))
            still_missing = sorted(set(missing_sources) - found)
            
            if not still_missing:
                logger.info(
                    f"✅ Phase 1.5 Loop: Alle Quellen vorhanden nach {attempt-1} "
                    f"Continuation(s), +{total_added} Zeichen"
                )
                break
            
            logger.info(
                f"🔄 Phase 1.5 Continuation (Versuch {attempt}/{max_attempts}): "
                f"{len(still_missing)} Quellen fehlen noch ({still_missing})"
            )
            
            # Baue QUELLEN-VERZEICHNIS für noch fehlende Quellen
            missing_titles = []
            for doc in doc_metadata:
                sid = doc.get('source_id', 0)
                title = doc.get('title', '')
                if sid in still_missing and title:
                    missing_titles.append(f"[{sid}] = \"{title}\"")
            
            title_block = "\n".join(missing_titles) if missing_titles else ""
            
            # Letzte 800 Zeichen als Anschluss-Punkt (erhöht von 500)
            last_section = current_draft[-800:] if len(current_draft) > 800 else current_draft
            
            continuation_prompt = f"""FORTSETZUNG EINER ABGEBROCHENEN SYNTHESE:

Der folgende Synthese-Text wurde vorzeitig abgebrochen. Setze ihn NAHTLOS fort.

LETZTER ABSCHNITT (Anschluss-Punkt):
...{last_section}

FEHLENDE QUELLEN-ABSCHNITTE:
{title_block}

REGELN:
- Setze NAHTLOS an der Abbruchstelle fort
- Schreibe JEDEN fehlenden QUELLE-Abschnitt VOLLSTÄNDIG (0. 1. 2. 3. Format)
- Verwende <ZITAT quelle="N">text</ZITAT>-Tags für Zitate
- Schreibe am Ende einen GLOBALE SYNTHESE-Abschnitt
- KEINE Einleitung, KEINE Wiederholung — nur die Fortsetzung
- WICHTIG: Schreibe AUSFÜHRLICH — jeder QUELLE-Abschnitt muss mindestens 200 Wörter haben
- KEINE Kurzzusammenfassung — VOLLSTÄNDIGE Analyse pro Quelle

FORTSETZUNG:"""
            
            # Fix M.2: Kontext-Limit erhöht von 10K → 30K
            # Das Modell braucht genug Kontext um über die fehlenden Quellen zu schreiben
            if context_text:
                context_limit = 30000
                context_suffix = context_text[-context_limit:] if len(context_text) > context_limit else context_text
                continuation_prompt += f"\n\nKONTEXT (Auszug für fehlende Quellen):\n{context_suffix}"
            
            try:
                from modules.config import get_model_for_task, DOMAIN_PROFILES, DOMAIN_ANALYSIS
                
                result = self._llm_call_func(
                    continuation_prompt,
                    task="correction",  # flash-Modell
                    system_instruction=(
                        "Du bist ein ausführlicher Fortsetzungs-Assistent. "
                        "Du setzt einen abgebrochenen Text nahtlos und VOLLSTÄNDIG fort. "
                        "Du schreibst AUSFÜHRLICHE QUELLE-Abschnitte (mindestens 200 Wörter pro Quelle). "
                        "Du verwendest <ZITAT quelle=\"N\">-Tags für Zitate. "
                        "Du erfindest KEINE Zitate — nur Paraphrasen wenn nötig. "
                        "Du schreibst ALLE fehlenden QUELLE-Abschnitte, nicht nur den ersten."
                    ),
                    temperature=0.4,  # Etwas höher für längere Outputs
                    max_tokens=max_tokens,
                    domain=DOMAIN_ANALYSIS,
                )
                
                if not result:
                    logger.warning(f"⚠️ Continuation-Versuch {attempt} gab leere Antwort")
                    continue
                
                continuation = result.strip()
                total_added += len(continuation)
                
                # Nahtlose Verknüpfung
                current_draft = current_draft + "\n\n" + continuation
                
                logger.info(
                    f"  ✅ Continuation-Versuch {attempt}: +{len(continuation)} Zeichen"
                )
                
            except Exception as e:
                logger.error(f"❌ Continuation-Versuch {attempt} fehlgeschlagen: {e}")
                continue
        
        # Prüfe ob mindestens einige Quellen ergänzt wurden
        quelle_pattern = re.compile(r'###\s+QUELLE\s+\[(\d+)\]')
        final_found = set()
        for m in quelle_pattern.finditer(current_draft):
            final_found.add(int(m.group(1)))
        remaining_missing = sorted(set(missing_sources) - final_found)
        
        if total_added > 0:
            logger.info(
                f"✅ Phase 1.5 Continuation abgeschlossen: +{total_added} Zeichen insgesamt, "
                f"{len(final_found & set(missing_sources))} von {len(missing_sources)} "
                f"fehlenden Quellen ergänzt. "
                f"{('Noch fehlend: ' + str(remaining_missing)) if remaining_missing else 'Alle Quellen vorhanden!'}"
            )
            return current_draft, True
        else:
            logger.warning("⚠️ Phase 1.5: Keine Continuation erfolgreich → Truncation bleibt")
            return truncated_draft, False
    
    # =========================================================================
    # HILFSMETHODEN
    # =========================================================================
    
    @staticmethod
    def _normalize_whitespace(text: str) -> str:
        """Normalisiert Whitespace für zuverlässigen Substring-Vergleich."""
        return ' '.join(text.split())
    
    @staticmethod
    def _find_best_fuzzy_ratio(quote: str, source: str) -> float:
        """
        Findet die beste Fuzzy-Ratio zwischen Zitat und Quelldokument.
        Nutzt Sliding-Window über den Quelltext, da das Zitat einen
        zusammenhängenden Ausschnitt repräsentiert.
        """
        quote_lower = quote.lower()
        source_lower = source.lower()
        
        # Bei sehr kurzem Zitat → direkter Vergleich
        if len(quote_lower) < 20:
            return SequenceMatcher(None, quote_lower, source_lower).ratio()
        
        # Sliding-Window: Vergleiche Zitat mit gleichlangen Ausschnitten
        # aus dem Quelldokument (Schrittweite = 10% der Zitat-Länge)
        quote_len = len(quote_lower)
        step = max(quote_len // 10, 20)
        best_ratio = 0.0
        
        # Begrenze die Suche auf die ersten 50000 Zeichen (Performance)
        search_source = source_lower[:1536]
        
        for start in range(0, len(search_source) - quote_len + 1, step):
            window = search_source[start:start + quote_len]
            ratio = SequenceMatcher(None, quote_lower, window).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                if best_ratio >= FUZZY_THRESHOLD:
                    return best_ratio  # Early exit
        
        # Letztes Fenster
        if len(search_source) > quote_len:
            window = search_source[-quote_len:]
            ratio = SequenceMatcher(None, quote_lower, window).ratio()
            best_ratio = max(best_ratio, ratio)
        
        return best_ratio


# =========================================================================
# CONVENIENCE FUNKTION (Integration in citation_rag.py)
# =========================================================================

def run_three_phase_synthesis(
    draft: str,
    num_sources: int,
    source_texts: Dict[int, str],
    doc_metadata: List[Dict],
    extracted_quotes: Optional[List[Dict]] = None,
    llm_call_func=None,
    is_small_corpus: bool = False,
) -> Tuple[str, Dict]:
    """
    Convenience-Funktion: Führt Phase 2 + Phase 3 durch.
    
    Args:
        draft: Der Synthese-Entwurf (Phase 1 Output)
        num_sources: Anzahl der Quellen
        source_texts: Dict source_id → concat-Text aller Chunks
        doc_metadata: Liste von {title, source_id}
        extracted_quotes: Optional: Pool-Zitate
        llm_call_func: LLM-Call-Funktion für Phase 3
        
    Returns:
        (final_text, phase_report)
        phase_report: {
            "phase2_errors": int,
            "phase2_warnings": int, 
            "phase3_applied": bool,
            "errors": List[ValidationError]
        }
    """
    validator = SynthesisValidator(llm_call_func=llm_call_func)
    
    logger.warning(
        f"🏁 Drei-Phasen-Start: Draft={len(draft)} Zeichen, "
        f"{num_sources} Quellen, LLM={'vorhanden' if llm_call_func else 'FEHLT'}"
    )
    
    # ── Phase 1.5: Truncation-Detection ──
    # Bevor wir validieren, prüfen ob die Synthese überhaupt vollständig ist
    is_truncated, missing_sources, clean_draft = SynthesisValidator.detect_truncation(
        draft=draft,
        num_sources=num_sources,
        doc_metadata=doc_metadata,
    )
    logger.warning(
        f"✂️ Phase 1.5 Ergebnis: truncated={is_truncated}, "
        f"missing={missing_sources}, draft_len={len(draft)}"
    )
    
    # Context-Text für Continuation sammeln (ALLE Quellen, nicht nur fehlende!)
    # Fix M.4: Früher nur fehlende Quellen → Kontext war zu dünn.
    # Jetzt alle Quellen beifügen, damit das Continuation-Modell den vollen
    # Kontext hat (wie das ursprüngliche Synthese-Modell).
    context_text_for_continuation = ""
    if source_texts:
        # Erst die fehlenden Quellen (wichtigster Kontext)
        for sid in missing_sources:
            text = source_texts.get(sid, "")
            if text:
                context_text_for_continuation += text[-10000:] + "\n"
        # Dann die bereits vorhandenen Quellen (für Konsistenz)
        quelle_pattern = re.compile(r'###\s+QUELLE\s+\[(\d+)\]')
        found_sids = set()
        for m in quelle_pattern.finditer(draft):
            found_sids.add(int(m.group(1)))
        for sid in sorted(found_sids):
            if sid not in missing_sources:
                text = source_texts.get(sid, "")
                if text:
                    context_text_for_continuation += text[-5000:] + "\n"
    
    # Continuation-Call wenn trunciert
    continuation_applied = False
    if is_truncated and missing_sources:
        draft, continuation_applied = validator.run_continuation(
            truncated_draft=clean_draft,
            missing_sources=missing_sources,
            doc_metadata=doc_metadata,
            context_text=context_text_for_continuation,
        )
    
    # Phase 2: Mechanischer Check
    checked_draft, errors = validator.validate_draft(
        draft=draft,
        num_sources=num_sources,
        source_texts=source_texts,
        doc_metadata=doc_metadata,
        extracted_quotes=extracted_quotes,
    )
    
    error_count = len([e for e in errors if e.severity == "error"])
    warning_count = len([e for e in errors if e.severity == "warning"])
    
    # ── SMALL-CORPUS-GUARD: Phase 3 überspringen bei kleinen Corpora ──
    # Bei ≤8 Chunks total ist die Synthese oft sehr kurz (~1000 Zeichen),
    # und Phase 3 produziert dann nur ~86 Token Output für 11 Fehler.
    # Die Korrektur verhungert und zerstört den Draft. Besser: Phase 2-
    # Warnungen direkt in den Text einfügen, aber kein LLM-Korrektur-Call.
    if is_small_corpus:
        logger.info(
            f"🧊 Small-Corpus: Phase 3 übersprungen ({error_count} Fehler, "
            f"{warning_count} Warnungen — stattdessen WARNUNG-Tags beibehalten)"
        )
        final_text = checked_draft
        correction_applied = False
    else:
        # Phase 3: Korrektur (nur wenn Fehler vorhanden)
        # max_tokens dynamisch: Muss groß genug sein für den GESAMTEN korrigierten Text!
        # Fix L.2: Alte Formel (len//2) war zu knapp. Neue Formel: ~2/3 der geschätzten
        # Token-Anzahl des Drafts (ca. 3 Zeichen/Token), Minimum 4096.
        estimated_draft_tokens = max(len(checked_draft) // 3, 2048)
        correction_max_tokens = min(estimated_draft_tokens * 2, 16384)
        
        final_text, correction_applied = validator.run_correction(
            draft=checked_draft,
            errors=errors,
            doc_metadata=doc_metadata,
            max_tokens=correction_max_tokens,
        )
    
    phase_report = {
        "phase2_errors": error_count,
        "phase2_warnings": warning_count,
        "phase3_applied": correction_applied,
        "phase15_truncated": is_truncated,
        "phase15_continuation": continuation_applied,
        "phase15_missing_sources": missing_sources if is_truncated else [],
        "errors": errors,
    }
    
    truncation_info = (
        f", Truncation={'behoben' if continuation_applied else 'erkannt' if is_truncated else 'nein'}"
    ) if is_truncated else ""
    
    logger.info(
        f"📊 Drei-Phasen-Report: Phase2={error_count}F/{warning_count}W, "
        f"Phase3={'angewendet' if correction_applied else 'übersprungen'}"
        f"{truncation_info}"
    )
    
    return final_text, phase_report
