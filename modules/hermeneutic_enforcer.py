# modules/hermeneutic_enforcer.py

import os
import json
import re
import google.generativeai as genai
from typing import List, Dict, Tuple

# SYSTEM PROMPT (v48.1 - Mit Zitat-Schutz)
HERMENEUTIC_PROMPT_TEMPLATE = """
Du bist ein hermeneutischer Validator.

AUFGABE: Prüfe, ob diese BEHAUPTUNG aus den QUELLEN ableitbar ist.

BEHAUPTUNG: "{claim}"

QUELLEN:
{sources_text}

KRITISCHE REGELN (HERMENEUTISCHER MODUS):

1. PARAPHRASEN sind VALIDE ✅
   - "Ich bin nichts" -> "Der Sprecher negiert seine Existenz" (Gültig)

2. META-AUSSAGEN sind VALIDE ✅
   - Quelle: "Não sou nada" -> "Die Wiederholung erzeugt Rhythmus" (Gültig)
   - Analysen von Stil, Struktur und Wirkung sind erlaubt.

3. LOGISCHE INFERENZEN sind VALIDE ✅
   - Schlussfolgerungen aus Fakten im Text sind erlaubt.

4. HALLUZINATIONEN sind INVALID ❌
   - Erfundene Fakten (Namen, Daten), die NIRGENDWO stehen.

5. FALSCHE ZITATE sind INVALID (WICHTIG!) ❌
   - Wenn die Behauptung sagt: "Der Autor schreibt: 'XYZ'" oder Anführungszeichen für ein direktes Zitat nutzt:
   - DANN muss der Text 'XYZ' auch wirklich in der Quelle stehen.
   - Beispiel FALSCH: Quelle="Ich bin müde" -> Behauptung="Er schreibt: 'Das Leben ist hart'" (Inhaltlich ähnlich, aber Zitat ist erfunden -> INVALID).

SPEZIALFALL FREMDSPRACHEN:
- Bei linguistischen Analysen (z.B. "Das Diminutiv 'шоколадки'..."):
  - Prüfe: Steht das WORT in der Quelle? Falls JA -> Meta-Aussage (valide) ✅

ANTWORT ALS JSON:
{{
  "valid": true,
  "classification": "paraphrase" | "meta" | "inference" | "hallucination",
  "reason": "Kurze Begründung (1 Satz)",
  "confidence": 0.0-1.0
}}

Jetzt validiere die Behauptung:
"""

class HermeneuticEnforcer:
    def __init__(self, model_name: str = "gemini-2.5-pro"):
        # Robustes Laden des API Keys (Google oder Gemini)
        api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")

        if not api_key:
            try:
                from dotenv import load_dotenv
                load_dotenv()
                api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
            except ImportError:
                pass

        if not api_key:
            raise ValueError("CRITICAL: Neither GOOGLE_API_KEY nor GEMINI_API_KEY found in environment.")

        genai.configure(api_key=api_key)

        # HIER: Striktes Befolgen der Anweisung "gemini-2.5-pro"
        self.model = genai.GenerativeModel(
            model_name=model_name,
            generation_config={"temperature": 0.0}
        )

    def _clean_json_response(self, text: str) -> dict:
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
                return {"valid": False, "classification": "error", "reason": "JSON Parsing Failed"}

        return {"valid": False, "classification": "error", "reason": "No JSON found"}

    def validate_claim(self, claim: str, sources: List[Dict], mode: str = "hermeneutic") -> Tuple[bool, str, str]:
        sources_text = ""
        for i, src in enumerate(sources, 1):
            content = src.get("content", "")
            sources_text += f"Quelle [{i}]: {content}\n"

        prompt = HERMENEUTIC_PROMPT_TEMPLATE.format(claim=claim, sources_text=sources_text)

        try:
            response = self.model.generate_content(prompt)
            result = self._clean_json_response(response.text)
            return (result.get("valid", False), result.get("classification", "unknown"), result.get("reason", "No reason provided"))
        except Exception as e:
            # Wir geben den Fehler zurück, damit er im Test sichtbar wird
            return False, "error", str(e)