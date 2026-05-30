# modules/hermeneutic_enforcer.py — v53: 
"""
Hermeneutic Enforcer - Epistemologischer Validierungs-Kern.

PHILOSOPHIE:
Unterscheidet zwischen zwei orthogonalen Dimensionen der Validierung:
1. HERMENEUTISCHE DIMENSION: Wie wird eine Aussage gemacht?
2. VALIDIERUNGS-DIMENSION: Ist sie korrekt?

ÄNDERUNGSHISTORIE:
- v53:   YAML-Migration (PromptManager), Typ-Sicherheit, Log-Spam-Reduktion
- v50.9: Migration Gemini → LM Studio via llm_wrapper
"""

import hashlib
import logging
import random
import re
import uuid
from collections import OrderedDict
from typing import Dict, Optional

from modules.config import (
    get_model_for_task,
    DOMAIN_ANALYSIS,
    ENFORCER_SAMPLING_RATE_HIGH,
    ENFORCER_SAMPLING_RATE_LOW,
    ENFORCER_CALIBRATION_TARGET,
    ENFORCER_VERSION,
)
from modules.llm_wrapper import llm_call_json
from modules.prompt_manager import PromptManager

logger = logging.getLogger(__name__)

# ========================================
# ERROR FALLBACK
# ========================================
_ERROR_RESULT = {
    "valid": False,
    "hermeneutic_type": "error",
    "validity_category": "error",
    "reason": "LLM-Aufruf fehlgeschlagen",
    "confidence": 0.0,
}

class HermeneuticEnforcer:
    """
    Epistemologischer Validator mit Zwei-Ebenen-Analyse.
    """
    _global_cache_max = 500
    _global_cache: OrderedDict = OrderedDict()
    _init_logged = False  # Verhindert Log-Spam

    def _cache_set(self, key, value):
        self._global_cache[key] = value
        if len(self._global_cache) > self._global_cache_max:
            self._global_cache.popitem(last=False)

    def _cache_get(self, key):
        return self._global_cache.get(key)

    def __init__(self, model_name: str = None):
        if model_name is None:
            model_name = get_model_for_task("enforcer")
        self.model_name = model_name
        self.pm = PromptManager()

        if not HermeneuticEnforcer._init_logged:
            logger.info(
                f"✅ HermeneuticEnforcer initialisiert "
                f"(Backend: llm_wrapper, Modell-Config: {model_name})"
            )
            HermeneuticEnforcer._init_logged = True

    def _is_structural_marker(self, claim: str) -> bool:
        """Prüft, ob ein Claim ein struktureller Marker ist, der nicht validiert werden soll."""
        stripped = claim.strip()
        
        # Überschriften: ### QUELLE [N]: Titel
        if re.match(r'^#{1,3}\s+QUELLE\s*\[\d+\]', stripped):
            return True
        
        # Feld-Nummerierungen: "0. DOKUMENTTYP:", "1. BEFUND:", "2. RHETORISCHE STRATEGIE:", etc.
        if re.match(r'^\d+\.\s+(DOKUMENTTYP|BEFUND|RHETORISCHE\s+STRATEGIE|MOTIV|FUNKTIONALES\s+MOTIV|KONSEQUENZ|DISKURSIVE\s+KONSEQUENZ|FAZIT|METHODISCHER\s+ANSATZ|ZENTRALE\s+ERKENNTNIS|ARGUMENTATIVE\s+STRATEGIE|BLINDE\s+FLECKEN|STÄRKEN)', stripped):
            return True
        
        # Globale Synthese Überschriften
        if re.match(r'^#{1,2}\s+GLOBALE\s+SYNTHESE', stripped):
            return True
        if re.match(r'^(ENTWICKLUNGSLINIE|KONVERGENZEN|DIVERZENZEN|STRUKTURELLES\s+FAZIT):', stripped):
            return True
        
        return False

    def _fuzzy_match_ratio(self, text: str, source: str) -> float:
        """Berechnet die Ähnlichkeit zwischen Text und Quelle (0.0 bis 1.0).
        Verwendet Sequenz-Matching statt Levenshtein, um keine neue Dependency zu brauchen."""
        from difflib import SequenceMatcher
        return SequenceMatcher(None, text.lower().strip(), source.lower().strip()).ratio()

    def _find_best_fuzzy_match(self, quote_text: str, sources: list) -> tuple:
        """Findet die beste Übereinstimmung eines Zitats in den Quellen.
        Returns: (best_ratio, best_source_idx)"""
        best_ratio = 0.0
        best_source = -1
        
        # Zitat-Text bereinigen (Tags entfernen)
        clean = re.sub(r'<ZITAT[^>]*>|</ZITAT>', '', quote_text).strip()
        clean = clean.strip('"').strip("'").strip(""").strip(""").strip()
        
        for idx, source in enumerate(sources):
            ratio = self._fuzzy_match_ratio(clean, source)
            if ratio > best_ratio:
                best_ratio = ratio
                best_source = idx
        
        return best_ratio, best_source

    def _generate_cache_key(self, claim: str, sources: list) -> str:
        content_str = claim.strip()
        for src in sources:
            content_str += src.get("content", "").strip()
        return hashlib.md5(content_str.encode("utf-8")).hexdigest()

    def validate_claim(self, claim: str, sources: list, mode: str = "hermeneutic", domain: Optional[str] = None, extracted_quotes: list = None) -> Dict:
        cache_key = self._generate_cache_key(claim, sources)
        if self._cache_get(cache_key) is not None:
            logger.debug(f"⚡ [CACHE HIT] Enforcer: {claim[:50]}...")
            return self._cache_get(cache_key)

        # Prüfe <ZITAT>-Tags gegen Extraktions-Block, falls verfügbar
        zitat_warnings = []
        if extracted_quotes is not None:
            zitat_warnings = self.verify_zitat_tags(claim, extracted_quotes, len(sources))

        sources_text = ""
        for i, src in enumerate(sources, 1):
            meta = src.get('metadata', {})
            chat_title = meta.get('chat_title', '')
            date = meta.get('real_date_str', '') or meta.get('date', '')
            
            header_parts = []
            if chat_title:
                header_parts.append(f"Titel: {chat_title}")
            if date:
                header_parts.append(f"Datum: {date}")
            header = f" ({', '.join(header_parts)})" if header_parts else ""
            
            sources_text += f"Quelle [{i}]{header}: {src.get('content', '')}\n\n"

        prompt_template = self.pm.get_enforcer_prompt()
        if not prompt_template:
            logger.error("❌ Enforcer-Prompt nicht in YAML gefunden!")
            return dict(_ERROR_RESULT)

        prompt = prompt_template.format(claim=claim, sources_text=sources_text)

        result_json = llm_call_json(
            prompt=prompt,
            task="enforcer",
            temperature=0.0,
            max_tokens=4096,
            fallback=dict(_ERROR_RESULT),
            domain=DOMAIN_ANALYSIS,
        )

        # Typ-Sicherheit (GLMs exzellenter Beitrag)
        if isinstance(result_json, list) and len(result_json) > 0:
            result_json = result_json[0]
        if not isinstance(result_json, dict):
            result_json = dict(_ERROR_RESULT)

        result = {
            "valid": bool(result_json.get("valid", False)),
            "hermeneutic_type": str(result_json.get("hermeneutic_type", "unknown")),
            "validity_category": str(result_json.get("validity_category", "unknown")),
            "reason": str(result_json.get("reason", "No reason provided")),
            "confidence": float(result_json.get("confidence", 0.0)),
        }

        # Wenn Zitat-Warnungen vorhanden, integriere sie ins Ergebnis
        if zitat_warnings:
            if result["valid"]:
                result["valid"] = False  # Zitat-Warnungen überschreiben Validität
                result["validity_category"] = "unverified_quotes"
            
            # Füge Zitat-Warnungen zur Reason hinzu
            zitat_reason = " | ".join(zitat_warnings)
            if result["reason"]:
                result["reason"] = f"{result['reason']} | {zitat_reason}"
            else:
                result["reason"] = zitat_reason

        # Nach der Enforcer-Validierung: Fuzzy-Match-Upgrade
        # ── FUZZY-UPGRADE (defensive safety net) ──
        # DIAGNOSE (2026-05-12): wird nie getriggert.
        # Ursache: Bei hoher Ähnlichkeit setzt das LLM bereits
        # hermeneutic_type="paraphrase" (valid=True) — der Upgrade-Pfad
        # ist damit logisch nicht erreichbar.
        # BEHALTEN als Schutz gegen zukünftige Modellwechsel,
        # die false_quote bei hoher Ähnlichkeit zurückgeben könnten.
        if result.get("hermeneutic_type") == "false_quote":
            sources_list = [src.get("content", "") for src in sources]
            best_ratio, best_idx = self._find_best_fuzzy_match(claim, sources_list)
            
            if best_ratio >= 0.85:
                # Upgrade: false_quote → paraphrase
                result["hermeneutic_type"] = "paraphrase"
                result["validity_category"] = "supported"
                result["valid"] = True
                result["reason"] = f"Paraphrase (Ähnlichkeit: {best_ratio:.0%} mit Quelle [{best_idx+1}]). {result.get('reason', '')}"
                logger.info(f"🔄 Fuzzy-Upgrade: false_quote → paraphrase (Ratio: {best_ratio:.2f})")

        self._cache_set(cache_key, result)
        self._maybe_sample_for_review(claim, sources, result)
        # --- /A.7 ---

        return result

    def verify_zitat_tags(self, synthesis_text: str, extracted_quotes: list, num_sources: int) -> list:
        """Prüft <ZITAT>-Tags gegen den Extraktions-Block und Quellennummern.
    
        Returns:
            Liste von Warnungs-Strings. Leere Liste = alles OK.
        """
        warnings = []
        
        # 1. Alle <ZITAT>-Tags finden
        pattern = r'<ZITAT quelle="(\d+)">(.*?)</ZITAT>'
        cited = re.findall(pattern, synthesis_text, re.DOTALL)
        
        if not cited:
            return warnings  # Keine ZITAT-Tags verwendet → nichts zu prüfen
        
        # 2. Quellennummern prüfen
        for source_id_str, quote_text in cited:
            try:
                source_id = int(source_id_str)
            except ValueError:
                warnings.append(f"❌ INVALID SOURCE: quelle=\"{source_id_str}\" ist keine Zahl")
                continue
        
            if source_id < 1 or source_id > num_sources:
                warnings.append(
                    f"❌ INVALID CITATION: quelle=\"{source_id}\" — "
                    f"nur [1]–[{num_sources}] gültig"
                )
                continue
        
        # 3. Steht das Zitat im Extraktions-Block? (Fix E: Fuzzy-Match statt exakt)
        quote_clean = quote_text.strip()
        
        # Zuerst exakter Check (schnell, häufiger Fall)
        in_extraction = any(
            q.get("text", "").strip() == quote_clean
            for q in extracted_quotes
            if q.get("quelle") == source_id
        )
        
        # Fix E: Wenn exakter Check fehlschlägt, Fuzzy-Match versuchen
        if not in_extraction and extracted_quotes:
            from difflib import SequenceMatcher
            best_ratio = 0.0
            for q in extracted_quotes:
                if q.get("quelle") == source_id:
                    ratio = SequenceMatcher(
                        None,
                        quote_clean.lower(),
                        q.get("text", "").strip().lower()
                    ).ratio()
                    best_ratio = max(best_ratio, ratio)
            
            # Fuzzy-Match-Schwelle: 0.85 = kleine Abweichungen tolerieren
            if best_ratio >= 0.85:
                in_extraction = True
                logger.info(
                    f"🔄 Fix E: ZITAT-Verify Fuzzy-Upgrade "
                    f"(Ratio: {best_ratio:.2f}, Quelle [{source_id}])"
                )
        
        if not in_extraction and extracted_quotes:
            warnings.append(
                f"⚠️ UNVERIFIED QUOTE [{source_id}]: "
                f"\"{quote_clean[:80]}...\" nicht im ZITAT-POOL (nicht wörtlich extrahiert)"
            )
    
        return warnings

    def _maybe_sample_for_review(self, claim: str, sources: list, result: Dict) -> None:
        """A.7: Samplet Claims für Human-in-the-Loop Review (non-blocking)."""
        try:
            # 1. Claim-Hash (claim + source_id)
            first_src = sources[0]
            source_id = first_src.get("source_id", "") or first_src.get("metadata", {}).get("chat_id", "")
            claim_hash = hashlib.sha256(
                (claim.strip().lower() + str(source_id)).encode()
            ).hexdigest()[:16]

            # 2. Deduplizierung: Prüfe ob Hash für aktuelle Version existiert
            from modules.database import get_db_connection
            db = get_db_connection()
            if db is None:
                return
            existing = db.execute(
                "SELECT 1 FROM enforcer_reviews WHERE claim_hash = ? AND enforcer_version = ? LIMIT 1",
                (claim_hash, ENFORCER_VERSION),
            ).fetchone()
            if existing:
                return  # Bereits gesampelt für diese Version

            # 3. Rate ermitteln
            from modules.database import get_human_review_count
            reviewed = get_human_review_count()
            rate = ENFORCER_SAMPLING_RATE_HIGH if reviewed < ENFORCER_CALIBRATION_TARGET else ENFORCER_SAMPLING_RATE_LOW

            # 4. Würfeln
            if random.randint(1, rate) != 1:
                return

            # 5. Source-Content + Hash
            source_content = first_src.get("content", "")
            source_content_hash = hashlib.sha256(source_content.encode()).hexdigest()

            # 6. Insert
            from modules.database import insert_enforcer_review
            review_id = str(uuid.uuid4())[:8]
            insert_enforcer_review(
                id=review_id,
                claim_hash=claim_hash,
                claim_text=claim,
                source_id=str(source_id) or "unknown",
                source_content=source_content,
                source_content_hash=source_content_hash,
                enforcer_version=ENFORCER_VERSION,
                enforcer_valid=result.get("valid", False),
                enforcer_reason=result.get("reason", ""),
                enforcer_confidence=result.get("confidence", None),
            )
            logger.info(f"🔬 A.7: Claim gesampelt für Human-Review (rate=1/{rate}, id={review_id})")
        except Exception as e:
            logger.warning(f"⚠️ A.7 Sampling fehlgeschlagen (non-critical): {e}")

    def validate_claim_legacy(self, claim: str, sources: list, mode: str = "hermeneutic") -> tuple:
        result = self.validate_claim(claim, sources, mode)
        return (result["valid"], result["hermeneutic_type"], result["reason"])

    def validate_claim_multisource(self, claim: str, sources: list, extracted_quotes: list = None) -> Dict:
        cache_key = self._generate_cache_key(claim, sources)
        if self._cache_get(cache_key) is not None:
            return self._cache_get(cache_key)

        # Prüfe <ZITAT>-Tags gegen Extraktions-Block, falls verfügbar
        zitat_warnings = []
        if extracted_quotes is not None:
            zitat_warnings = self.verify_zitat_tags(claim, extracted_quotes, len(sources))

        sources_text = ""
        for i, src in enumerate(sources, 1):
            sid = src.get("source_id", str(i))
            meta = src.get('metadata', {})
            chat_title = meta.get('chat_title', '')
            date = meta.get('real_date_str', '') or meta.get('date', '')
            
            header_parts = []
            if chat_title:
                header_parts.append(f"Titel: {chat_title}")
            if date:
                header_parts.append(f"Datum: {date}")
            header = f" ({', '.join(header_parts)})" if header_parts else ""
            
            sources_text += f"Quelle [{sid}]{header}: {src.get('content', '')}\n\n"

        prompt_template = self.pm.get_multisource_enforcer_prompt()
        if not prompt_template:
            logger.error("❌ Multi-Enforcer-Prompt nicht in YAML gefunden!")
            return dict(_ERROR_RESULT)

        prompt = prompt_template.format(claim=claim, sources_text=sources_text)

        from modules.config import DOMAIN_ANALYSIS
        result_json = llm_call_json(
            prompt=prompt,
            task="enforcer",
            temperature=0.0,
            max_tokens=4096,
            fallback={
                "valid": False,
                "hermeneutic_type": "error",
                "validity_category": "unavailable",
                "reason": "ENFORCER UNAVAILABLE — Zitat nicht validiert",
                "confidence": 0.0,
            },
            domain=DOMAIN_ANALYSIS,
        )

        if isinstance(result_json, list) and len(result_json) > 0:
            result_json = result_json[0]
        if not isinstance(result_json, dict):
            result_json = dict(_ERROR_RESULT)

        result = {
            "valid": bool(result_json.get("valid", False)),
            "hermeneutic_type": str(result_json.get("hermeneutic_type", "multi_source_synthesis")),
            "validity_category": str(result_json.get("validity_category", "unknown")),
            "reason": str(result_json.get("reason", "No reason provided")),
            "confidence": float(result_json.get("confidence", 0.0)),
        }

        # Wenn Zitat-Warnungen vorhanden, integriere sie ins Ergebnis
        if zitat_warnings:
            if result["valid"]:
                result["valid"] = False  # Zitat-Warnungen überschreiben Validität
                result["validity_category"] = "unverified_quotes"
            
            # Füge Zitat-Warnungen zur Reason hinzu
            zitat_reason = " | ".join(zitat_warnings)
            if result["reason"]:
                result["reason"] = f"{result['reason']} | {zitat_reason}"
            else:
                result["reason"] = zitat_reason

        self._cache_set(cache_key, result)
        icon = "✅" if result["valid"] else "❌"
        logger.info(
            f"{icon} MultiEnforcer: {claim[:50]}... → "
            f"{result['hermeneutic_type']}/{result['validity_category']}"
        )
        return result