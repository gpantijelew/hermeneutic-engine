# modules/hermeneutic_enforcer.py — v50.9: LM Studio Drop-in
"""
Hermeneutic Enforcer - Epistemologischer Validierungs-Kern.

PHILOSOPHIE:
Unterscheidet zwischen zwei orthogonalen Dimensionen der Validierung:
1. HERMENEUTISCHE DIMENSION: Wie wird eine Aussage gemacht?
   - paraphrase, meta, inference, hallucination
2. VALIDIERUNGS-DIMENSION: Ist sie korrekt?
   - supported, contradiction, exaggeration, unsupported, temporal_fiction

MIGRATION v50.9:
- Gemini API → llm_wrapper.llm_call_json()
- Keine API-Key-Abhängigkeit mehr
- Identische öffentliche Schnittstelle

ÄNDERUNGSHISTORIE:
- v50.9: Migration Gemini → LM Studio via llm_wrapper
- v50.6: Harmonisierung mit llm_instructions.py, Dict-Output, Beispiele
- v48.1: Zitat-Schutz, hermeneutischer Modus
- v47:   Initiale Version
"""

import json
import re
import hashlib
import logging
from typing import Dict, Optional
from modules.config import MODEL_ENFORCER
from modules.llm_wrapper import llm_call_json

logger = logging.getLogger(__name__)

# ========================================
# SYSTEM PROMPTS (vollständig unverändert)
# ========================================
HERMENEUTIC_PROMPT_TEMPLATE = """
Du bist ein hermeneutischer Validator mit doppelter Analyse-Dimension.

AUFGABE: Prüfe, ob diese BEHAUPTUNG aus den QUELLEN ableitbar ist.

BEHAUPTUNG: "{claim}"

QUELLEN:
{sources_text}

---

## ZWEI-EBENEN-ANALYSE (KRITISCH):

### 1. HERMENEUTISCHE DIMENSION (Wie wird gesagt?)

**VALIDE FORMEN:**
- **Paraphrase**: Umformulierung mit gleicher Bedeutung
  - Beispiel: "Ich bin nichts" → "Der Sprecher negiert seine Existenz" ✅
- **Meta-Aussage**: Analyse von Stil, Struktur, Wirkung
  - Beispiel: Quelle="Não sou nada" → "Die Wiederholung erzeugt Rhythmus" ✅
- **Inferenz**: Logische Schlussfolgerung aus Fakten im Text
  - Beispiel: Quelle="Es regnet" → "Der Boden wird nass" ✅

**INVALIDE FORMEN:**
- **Halluzination**: Erfundene Fakten (Namen, Daten, Ereignisse), die NIRGENDWO stehen
- **Falsches Zitat**: Behauptung nutzt Anführungszeichen, aber Text steht nicht in Quelle
  - Beispiel: Quelle="Ich bin müde" → Behauptung="Er schreibt: 'Das Leben ist hart'" ❌

### 2. VALIDIERUNGS-DIMENSION (Ist es korrekt?)

**KATEGORIEN:**
- **supported**: Behauptung wird direkt und wörtlich von der Quelle gestützt
- **contradiction**: Direkter sachlicher Widerspruch zur Quelle
- **exaggeration**: Übertreibung oder Verstärkung der Quelle
- **unsupported**: Behauptung steht nicht in der Quelle
- **temporal_fiction**: Erfundene Zeitstempel, Versionen, Daten

---

## SPEZIALFALL: FREMDSPRACHEN
Bei linguistischen Analysen (z.B. "Das Diminutiv 'шоколадки'..."):
- Prüfe: Steht das WORT in der Quelle? Falls JA → Meta-Aussage (valide) ✅

---

## AUSGABE-FORMAT (STRIKT):
Antworte NUR als JSON mit ALLEN Feldern:
{{
  "valid": true/false,
  "hermeneutic_type": "paraphrase" | "meta" | "inference" | "hallucination" | "false_quote",
  "validity_category": "supported" | "contradiction" | "exaggeration" | "unsupported" | "temporal_fiction",
  "reason": "Kurze, präzise Begründung (1-2 Sätze)",
  "confidence": 0.0-1.0
}}

---

## ENTSCHEIDUNGS-MATRIX:
| valid | hermeneutic_type | validity_category | Bedeutung |
|-------|------------------|-------------------|-----------|
| true  | paraphrase       | supported         | Korrekte Umformulierung |
| true  | meta             | supported         | Valide Stil-Analyse |
| true  | inference        | supported         | Logische Schlussfolgerung |
| false | inference        | exaggeration      | Schlussfolgerung übertrieben |
| false | paraphrase       | unsupported       | Paraphrase unbelegter Aussage |
| false | hallucination    | unsupported       | Erfundener Fakt |
| false | false_quote      | unsupported       | Zitat steht nicht im Text |
| false | paraphrase       | temporal_fiction  | Datum/Version erfunden |

---

## BEISPIELE:

**Beispiel 1:**
Behauptung: "Claude ist schneller als GPT."
Quelle: "Claude zeigt leichte Performance-Vorteile gegenüber GPT-4."
→ {{"valid": true, "hermeneutic_type": "paraphrase", "validity_category": "supported", "reason": "Quelle bestätigt Performance-Vorteil.", "confidence": 0.95}}

**Beispiel 2:**
Behauptung: "Claude ist 10x schneller als GPT."
Quelle: "Claude zeigt leichte Performance-Vorteile gegenüber GPT-4."
→ {{"valid": false, "hermeneutic_type": "inference", "validity_category": "exaggeration", "reason": "Quelle sagt 'leichte Vorteile', nicht '10x'. Übertreibung.", "confidence": 0.98}}

**Beispiel 3:**
Behauptung: "Claude kostet 5$/Mio Tokens."
Quelle: "Claude bietet flexible Pricing-Optionen."
→ {{"valid": false, "hermeneutic_type": "hallucination", "validity_category": "unsupported", "reason": "Preisangabe steht nicht in der Quelle.", "confidence": 0.99}}

**Beispiel 4:**
Behauptung: "Der Autor schreibt: 'Das Leben ist hart.'"
Quelle: "Ich bin müde."
→ {{"valid": false, "hermeneutic_type": "false_quote", "validity_category": "unsupported", "reason": "Zitat steht nicht im Text.", "confidence": 1.0}}

**Beispiel 5:**
Behauptung: "Claude 2.5 erschien im März 2024."
Quelle: "Claude ist ein KI-Modell von Anthropic."
→ {{"valid": false, "hermeneutic_type": "hallucination", "validity_category": "temporal_fiction", "reason": "Zeitangabe nicht in Quelle.", "confidence": 1.0}}

---
Jetzt validiere die Behauptung:
"""

MULTISOURCE_PROMPT_TEMPLATE = """
Du bist ein hermeneutischer Validator für Multi-Quellen-Aussagen.

AUFGABE: Prüfe, ob diese BEHAUPTUNG aus den QUELLEN kollektiv ableitbar ist.

BEHAUPTUNG: "{claim}"

QUELLEN (der Satz zitiert aus mehreren):
{sources_text}

---

## MULTI-QUELLEN-REGEL (KRITISCH):
Ein Satz ist VALID, wenn:
- Jedes wörtliche Zitat in MINDESTENS EINER der genannten Quellen vorkommt
- Die Gesamtaussage eine valide Paraphrase oder Inferenz aus der Summe ist

Ein Satz ist INVALID, wenn:
- Ein wörtliches Zitat in KEINER der genannten Quellen vorkommt
- Die Gesamtaussage dem Inhalt aller Quellen widerspricht

## AUSGABE-FORMAT (STRIKT):
Antworte NUR als JSON:
{{
  "valid": true/false,
  "hermeneutic_type": "multi_source_synthesis" | "hallucination" | "false_quote",
  "validity_category": "supported" | "unsupported" | "contradiction",
  "reason": "Kurze Begründung: Welche Zitate sind belegt, welche nicht?",
  "confidence": 0.0-1.0
}}

Jetzt validiere:
"""

# ========================================
# ERROR FALLBACK (für beide Methoden)
# ========================================
_ERROR_RESULT = {
    "valid": False,
    "hermeneutic_type": "error",
    "validity_category": "error",
    "reason": "LLM-Aufruf fehlgeschlagen",
    "confidence": 0.0
}


class HermeneuticEnforcer:
    """
    Epistemologischer Validator mit Zwei-Ebenen-Analyse.
    Vollständig identische öffentliche Schnittstelle zu v50.6.
    Intern: llm_wrapper statt Gemini API.
    """

    # Statischer Cache (überlebt Re-Instanziierung)
    _global_cache = {}

    def __init__(self, model_name: str = MODEL_ENFORCER):
        """
        Initialisiert den Enforcer.
        model_name wird für Logging behalten,
        das aktive Modell kommt aus config.py/get_llm_client().
        """
        self.model_name = model_name
        logger.info(
            f"✅ HermeneuticEnforcer initialisiert "
            f"(Backend: LM Studio, Modell-Config: {model_name})"
        )

    def _generate_cache_key(self, claim: str, sources: list) -> str:
        """Erzeugt eindeutigen Hash für Claim + Quellen."""
        content_str = claim.strip()
        for src in sources:
            content_str += src.get("content", "").strip()
        return hashlib.md5(content_str.encode('utf-8')).hexdigest()

    def _clean_json_response(self, text: str) -> dict:
        """
        Rückwärtskompatibilität — wird intern nicht mehr verwendet.
        llm_call_json() übernimmt das Parsing.
        """
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```', '', text)
        start = text.find('{')
        end = text.rfind('}') + 1
        if start != -1 and end != 0:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass
        return dict(_ERROR_RESULT)

    def validate_claim(
        self,
        claim: str,
        sources: list,
        mode: str = "hermeneutic"
    ) -> Dict:
        """
        Validiert eine Behauptung gegen Quellen.
        Identische Signatur und Rückgabestruktur zu v50.6.
        """
        # 1. Cache Check
        cache_key = self._generate_cache_key(claim, sources)
        if cache_key in self._global_cache:
            logger.debug(
                f"⚡ [CACHE HIT] Enforcer: {claim[:50]}..."
            )
            return self._global_cache[cache_key]

        # 2. Prompt aufbauen
        sources_text = ""
        for i, src in enumerate(sources, 1):
            sources_text += f"Quelle [{i}]: {src.get('content', '')}\n\n"

        prompt = HERMENEUTIC_PROMPT_TEMPLATE.format(
            claim=claim,
            sources_text=sources_text
        )

        # 3. LLM-Aufruf via Wrapper
        result_json = llm_call_json(
            prompt=prompt,
            task="enforcer",
            temperature=0.0,  # Determinismus für Validierung
            fallback=dict(_ERROR_RESULT)
        )

        result = {
            "valid":              result_json.get("valid", False),
            "hermeneutic_type":   result_json.get("hermeneutic_type", "unknown"),
            "validity_category":  result_json.get("validity_category", "unknown"),
            "reason":             result_json.get("reason", "No reason provided"),
            "confidence":         result_json.get("confidence", 0.0)
        }

        # 4. Cache
        self._global_cache[cache_key] = result

        # 5. Log
        icon = "✅" if result["valid"] else "❌"
        logger.info(
            f"{icon} Enforcer: {claim[:50]}... → "
            f"{result['hermeneutic_type']}/{result['validity_category']} "
            f"(confidence: {result['confidence']:.2f})"
        )

        return result

    def validate_claim_legacy(
        self,
        claim: str,
        sources: list,
        mode: str = "hermeneutic"
    ) -> tuple:
        """
        Legacy-Wrapper. Vollständig unverändert.
        DEPRECATED: Nutze validate_claim().
        """
        result = self.validate_claim(claim, sources, mode)
        return (
            result["valid"],
            result["hermeneutic_type"],
            result["reason"]
        )

    def validate_claim_multisource(
        self,
        claim: str,
        sources: list
    ) -> Dict:
        """
        Validiert einen Satz der bewusst aus mehreren Quellen zitiert.
        Identische Signatur zu v50.9.
        """
        cache_key = self._generate_cache_key(claim, sources)
        if cache_key in self._global_cache:
            return self._global_cache[cache_key]

        sources_text = ""
        for i, src in enumerate(sources, 1):
            sid = src.get('source_id', str(i))
            sources_text += f"Quelle [{sid}]: {src.get('content', '')}\n\n"

        prompt = MULTISOURCE_PROMPT_TEMPLATE.format(
            claim=claim,
            sources_text=sources_text
        )

        result_json = llm_call_json(
            prompt=prompt,
            task="enforcer",
            temperature=0.0,
            fallback={
                "valid": True,
                "hermeneutic_type": "error",
                "validity_category": "unavailable",
                "reason": "ENFORCER UNAVAILABLE — Zitat nicht validiert",
                "confidence": 0.0
            }
        )

        result = {
            "valid":             result_json.get("valid", False),
            "hermeneutic_type":  result_json.get(
                "hermeneutic_type", "multi_source_synthesis"
            ),
            "validity_category": result_json.get("validity_category", "unknown"),
            "reason":            result_json.get("reason", "No reason provided"),
            "confidence":        result_json.get("confidence", 0.0)
        }

        self._global_cache[cache_key] = result
        icon = "✅" if result["valid"] else "❌"
        logger.info(
            f"{icon} MultiEnforcer: {claim[:50]}... → "
            f"{result['hermeneutic_type']}/{result['validity_category']}"
        )
        return result