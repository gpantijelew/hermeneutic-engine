# modules/evidence_synthesis.py
import json
import logging
from modules.config import get_model_for_task
from modules.llm_wrapper import llm_call, llm_call_json
from typing import List, Dict

logger = logging.getLogger(__name__)


class EvidenceFirstSynthesizer:
    def __init__(self, model_name=get_model_for_task("fact_extraction")):
        self.model_name = model_name
        # API Key wird global konfiguriert, wir verlassen uns darauf

    def generate(
        self, query: str, results: List[Dict], target_speakers: List[str]
    ) -> str:
        """
        Führt die 3-Schritt-Synthese durch:
        1. Extraction (Primärquellen finden)
        2. Validation (Widersprüche prüfen)
        3. Synthesis (Schreiben)
        """
        # 1. Kontext vorbereiten
        context_text = self._prepare_context(results)

        # 2. Schritt 1: Extraction
        evidence = self._extract_evidence(query, context_text, target_speakers)

        # Fallback: Wenn keine Primärquellen gefunden wurden, brechen wir ab
        # und lassen den normalen RAG weitermachen (wird vom Caller gehandhabt)
        if not evidence.get("primary_quotes"):
            logger.info("EvidenceFirst: Keine Primärquellen gefunden. Fallback.")
            return None

        # 3. Schritt 2: Validation
        validated = self._validate_evidence(evidence)

        # 4. Schritt 3: Synthesis
        final_text = self._synthesize(query, validated)

        return final_text

    def _prepare_context(self, results: List[Dict]) -> str:
        context = ""
        for i, res in enumerate(results):
            meta = res.get("metadata", {})
            model = meta.get("model_name", "Unbekannt")
            content = res.get("content", "").replace("\n", " ")
            context += (
                f"SOURCE_ID [{i + 1}] | SPEAKER: {model} | CONTENT: {content}\n\n"
            )
        return context

    def _extract_evidence(
        self, query: str, context: str, target_speakers: List[str]
    ) -> Dict:
        """Schritt 1: Extrahiere Zitate (Aggressive Version v48.2)."""
        targets_str = ", ".join(target_speakers)

        prompt = f"""
        Du bist ein forensischer Daten-Analyst.
        ZIEL: Extrahiere JEDEN Textfetzen, der von {targets_str} stammt.

        INPUT-FORMAT:
        Die Quellen sind so formatiert:
        SOURCE_ID [x] | SPEAKER: [Name] | CONTENT: [Text]

        AUFGABE:
        1. Gehe jede SOURCE_ID durch.
        2. Schau auf das Feld "SPEAKER".
        3. Ist der SPEAKER einer von: {targets_str}?
           -> JA: Das ist ein "primary_quote". NIMM ES AUF! Egal was drin steht.
           -> NEIN: Spricht der Text ÜBER {targets_str}?
              -> JA: Das ist ein "secondary_mention".

        BEISPIEL:
        Wenn da steht: "SOURCE_ID [33] | SPEAKER: Kimi | CONTENT: Ja, genau..."
        Und Ziel ist "Kimi".
        DANN MUSST DU EXTRAHIEREN: {{"source_id": 33, "speaker": "Kimi", "quote": "Ja, genau..."}}

        Ignoriere nichts! Wir brauchen Rohdaten.

        QUELLEN:
        {context}

        FORMAT (JSON):
        {{
          "primary_quotes": [
            {{"source_id": 12, "speaker": "Name", "quote": "..."}}
          ],
          "secondary_mentions": [
            {{"source_id": 5, "analyst": "Name", "claim": "..."}}
          ]
        }}
        """

        try:
            evidence = llm_call_json(
                prompt,
                task="fact_extraction",
                fallback={"primary_quotes": [], "secondary_mentions": []},
            )
            primaries = evidence.get("primary_quotes", [])
            logger.debug("Target Speakers: %s", target_speakers)
            logger.debug("Primärquellen gefunden: %d", len(primaries))

            for q in primaries:
                sid = q.get("source_id", "??")
                spk = q.get("speaker", "Unknown")
                txt = q.get("quote", "")[:80].replace("\n", " ")
                logger.debug("  - [%s] %s: %s...", sid, spk, txt)

            return evidence
        except Exception as e:
            logger.error(f"Extraction Error: {e}")
            return {"primary_quotes": [], "secondary_mentions": []}

    def _validate_evidence(self, evidence: Dict) -> Dict:
        """Schritt 2: Prüfe auf Widersprüche."""

        prompt = f"""
        ANALYSE DER BEWEISLAGE.

        PRIMÄRQUELLEN (Das Original):
        {json.dumps(evidence.get("primary_quotes", []), indent=2)}

        SEKUNDÄRQUELLEN (Die Analyse durch Dritte):
        {json.dumps(evidence.get("secondary_mentions", []), indent=2)}

        AUFGABE:
        Vergleiche. Widersprechen die Sekundärquellen den Primärquellen?
        Beispiel: Sekundär sagt "Kimi schweigt", aber Primär sagt "Ich denke..." -> WIDERSPRUCH.

        FORMAT (JSON):
        {{
          "validated_primary": [ ... alle validen Primärquellen ... ],
          "contradictions": [
            {{
              "primary_id": 12,
              "secondary_id": 5,
              "analysis": "ChatGPT behauptet X, aber Kimi sagt Y."
            }}
          ]
        }}
        """

        try:
            validated = llm_call_json(
                prompt,
                task="fact_extraction",
                fallback={
                    "validated_primary": evidence.get("primary_quotes", []),
                    "contradictions": [],
                },
            )

            val_prim = validated.get("validated_primary", [])
            logger.debug("Validierte Primärquellen: %d", len(val_prim))

            for v in val_prim:
                logger.debug("  ✅ [%s] %s", v.get("source_id"), v.get("speaker"))

            contradictions = validated.get("contradictions", [])
            if contradictions:
                logger.debug("%d Widersprüche gefunden.", len(contradictions))

            return validated
        except Exception as e:
            logger.error(f"Validation Error: {e}")
            # Fallback: Alles durchlassen, wenn Validation crasht (für Debugging)
            return {
                "validated_primary": evidence.get("primary_quotes", []),
                "contradictions": [],
            }

    def _synthesize(self, query: str, validated: Dict) -> str:
        """Schritt 3: Schreibe den Artikel."""

        prompt = f"""
        Du bist ein investigativer Journalist. Schreibe einen Artikel über: "{query}"

        BASIS (Primärquellen - HÖCHSTE PRIORITÄT):
        {json.dumps(validated.get("validated_primary", []), indent=2)}

        KONFLIKTE (Primär vs. Sekundär):
        {json.dumps(validated.get("contradictions", []), indent=2)}

        AUFGABE:
        Schreibe eine "Investigative Synthese".
        1. Stütze dich ZUERST auf die Primärquellen. Was sagen die Modelle selbst?
        2. Wenn Sekundärquellen (Analysen) falsch lagen, decke das auf ("Entgegen der Analyse von ChatGPT...").
        3. Nutze Zitationen [source_id] für jeden Satz.

        Stil: Präzise, beweisorientiert, aufdeckend.
        """

        try:
            text = llm_call(prompt, task="synthesis")

            val_ids = [
                str(v.get("source_id")) for v in validated.get("validated_primary", [])
            ]
            found_ids = [vid for vid in val_ids if f"[{vid}]" in text]

            logger.debug("Erwartete IDs aus Validation: %s", val_ids)
            logger.debug("Gefundene IDs im Text: %s", found_ids)

            if len(found_ids) == len(val_ids) and len(val_ids) > 0:
                logger.debug("Alle Beweise zitiert.")
            elif len(val_ids) == 0:
                logger.debug("Keine validierten Beweise vorhanden.")
            else:
                missing = set(val_ids) - set(found_ids)
                logger.warning("Synthese hat Beweise ignoriert! Fehmend: %s", missing)

            return text
        except Exception as e:
            return f"Fehler bei Synthese: {e}"
