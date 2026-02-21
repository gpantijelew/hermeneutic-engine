# modules/hermeneutic_enforcer.py
"""
Hermeneutic Enforcer - Epistemologischer Validierungs-Kern.

PHILOSOPHIE:
Unterscheidet zwischen zwei orthogonalen Dimensionen der Validierung:
1. HERMENEUTISCHE DIMENSION: Wie wird eine Aussage gemacht?
   - paraphrase, meta, inference, hallucination
2. VALIDIERUNGS-DIMENSION: Ist sie korrekt?
   - supported, contradiction, exaggeration, unsupported, temporal_fiction

Diese Zwei-Ebenen-Analyse ermöglicht präzise Fehlerdiagnosen:
"Die Aussage ist eine Paraphrase (hermeneutisch valide), aber übertrieben (faktisch invalid)."

ÄNDERUNGSHISTORIE:
- v50.10: Fix Indentation & Cleanup
- v50.6: Harmonisierung mit llm_instructions.py, Dict-Output, Beispiele, Legacy-Wrapper
- v48.1: Zitat-Schutz, hermeneutischer Modus
- v47: Initiale Version
"""

import os
import json
import re
import hashlib
import logging
from google import genai
from typing import Dict, Optional
from modules.config import MODEL_ENFORCER

logger = logging.getLogger(__name__)

# ========================================
# SYSTEM PROMPT (v50.6 - Harmonisiert)
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
- **contradiction**: Direkter sachlicher Widerspruch zur Quelle (Gegenteil wird behauptet)
- **exaggeration**: Übertreibung oder Verstärkung der Quelle (Kern stimmt, aber übertrieben)
- **unsupported**: Behauptung steht nicht in der Quelle (kein Widerspruch, aber auch kein Beleg)
- **temporal_fiction**: Erfundene Zeitstempel, Versionen, Daten (halluzinierte Metadaten)

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
→ {{"valid": false, "hermeneutic_type": "false_quote", "validity_category": "unsupported", "reason": "Zitat steht nicht im Text. Erfundenes Zitat.", "confidence": 1.0}}

**Beispiel 5:**
Behauptung: "Claude 2.5 erschien im März 2024."
Quelle: "Claude ist ein KI-Modell von Anthropic."
→ {{"valid": false, "hermeneutic_type": "hallucination", "validity_category": "temporal_fiction", "reason": "Zeitangabe nicht in Quelle. Halluziniertes Datum.", "confidence": 1.0}}

---
Jetzt validiere die Behauptung:
"""


class HermeneuticEnforcer:
    """
    Epistemologischer Validator mit Zwei-Ebenen-Analyse.

    Unterscheidet zwischen:
    - WIE eine Aussage gemacht wird (hermeneutic_type)
    - OB sie korrekt ist (validity_category)
    """

    # Statischer Cache (überlebt Re-Instanziierung)
    _global_cache = {}

    def __init__(self, model_name: str = MODEL_ENFORCER):
        """
        Initialisiert den Enforcer.

        Args:
            model_name: LLM-Model für Validierung (default: MODEL_ENFORCER)

        Raises:
            ValueError: Wenn kein API-Key gefunden wird
        """
        api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")

        if not api_key:
            try:
                from dotenv import load_dotenv
                load_dotenv()
                api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
            except ImportError:
                pass

        if not api_key:
            raise ValueError(
                "CRITICAL: Neither GOOGLE_API_KEY nor GEMINI_API_KEY found in environment. "
                "Set one of these variables to use the Hermeneutic Enforcer."
            )

        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name
        logger.info(f"✅ HermeneuticEnforcer initialized with model: {model_name}")

    def _generate_cache_key(self, claim: str, sources: list) -> str:
        """Erzeugt einen eindeutigen Hash für Claim + Quellen."""
        content_str = claim.strip()
        for src in sources:
            content_str += src.get("content", "").strip()
        return hashlib.md5(content_str.encode('utf-8')).hexdigest()

    def _clean_json_response(self, text: str) -> dict:
        """Extrahiert JSON aus LLM-Response (robust gegen Markdown-Fences)."""
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```', '', text)

        start = text.find('{')
        end = text.rfind('}') + 1

        if start != -1 and end != 0:
            json_str = text[start:end]
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                logger.error(f"JSON Parsing failed. Raw text: {text[:200]}...")
                return {
                    "valid": False,
                    "hermeneutic_type": "error",
                    "validity_category": "error",
                    "reason": "JSON Parsing Failed",
                    "confidence": 0.0
                }

        logger.error(f"No JSON found in response. Raw text: {text[:200]}...")
        return {
            "valid": False,
            "hermeneutic_type": "error",
            "validity_category": "error",
            "reason": "No JSON found in LLM response",
            "confidence": 0.0
        }

    def validate_claim(
        self,
        claim: str,
        sources: list,
        mode: str = "hermeneutic"
    ) -> Dict:
        """
        Validiert eine Behauptung gegen Quellen.

        NEU v50.6: Gibt Dict zurück statt Tuple (breaking change!).

        Args:
            claim: Die zu prüfende Behauptung
            sources: Liste von Dicts mit 'content' und optional 'metadata'
            mode: "hermeneutic" (default, einziger Modus)

        Returns:
            Dict mit Validierungs-Ergebnis
        """
        # 1. Cache Check
        cache_key = self._generate_cache_key(claim, sources)
        if cache_key in self._global_cache:
            logger.debug(f"⚡ [CACHE HIT] Enforcer spart API-Call für: {claim[:50]}...")
            return self._global_cache[cache_key]

        # 2. Prompt vorbereiten
        sources_text = ""
        for i, src in enumerate(sources, 1):
            content = src.get("content", "")
            sources_text += f"Quelle [{i}]: {content}\n\n"

        prompt = HERMENEUTIC_PROMPT_TEMPLATE.format(
            claim=claim,
            sources_text=sources_text
        )

        # 3. API Call
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config={"temperature": 0.0}
            )
            result_json = self._clean_json_response(response.text)

            result = {
                "valid": result_json.get("valid", False),
                "hermeneutic_type": result_json.get("hermeneutic_type", "unknown"),
                "validity_category": result_json.get("validity_category", "unknown"),
                "reason": result_json.get("reason", "No reason provided"),
                "confidence": result_json.get("confidence", 0.0)
            }

            # 4. Cache Result
            self._global_cache[cache_key] = result

            # 5. Log
            status_icon = "✅" if result["valid"] else "❌"
            logger.info(
                f"{status_icon} Enforcer: {claim[:50]}... → "
                f"{result['hermeneutic_type']}/{result['validity_category']} "
                f"(confidence: {result['confidence']:.2f})"
            )

            return result

        except Exception as e:
            logger.error(f"❌ Enforcer API Error: {e}", exc_info=True)
            return {
                "valid": False,
                "hermeneutic_type": "error",
                "validity_category": "error",
                "reason": f"API Error: {str(e)}",
                "confidence": 0.0
            }

    # ========================================
    # LEGACY COMPATIBILITY (v50.6)
    # ========================================

    def validate_claim_legacy(
        self,
        claim: str,
        sources: list,
        mode: str = "hermeneutic"
    ) -> tuple:
        """
        Legacy-Wrapper für alte Code-Stellen.

        DEPRECATED: Nutze validate_claim() (gibt Dict zurück).

        Returns:
            Tuple: (valid, classification, reason) - wie v48.1
        """
        result = self.validate_claim(claim, sources, mode)
        return (
            result["valid"],
            result["hermeneutic_type"],
            result["reason"]
        )