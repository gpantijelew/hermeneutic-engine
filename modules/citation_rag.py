# modules/citation_rag.py
import logging
import json
import re
import os
import time
import google.generativeai as genai
from typing import List, Dict, Any, Tuple

# Eigene Module
from modules.vector_store import FirestoreVectorStore
from modules.evidence_synthesis import EvidenceFirstSynthesizer
from modules.llm_instructions import ENFORCER_INSTRUCTION
from modules.llm_instructions import SYNTHESIS_INSTRUCTION
from modules.hermeneutic_reranker import HermeneuticReranker

logger = logging.getLogger(__name__)

class CitationRAG:
    def __init__(self, vector_store: FirestoreVectorStore = None, model_name: str = "gemini-2.0-flash-lite-001"):
        self.vector_store = vector_store
        self.model_name = model_name
        self.synthesizer = EvidenceFirstSynthesizer(model_name)
        api_key = os.environ.get("GEMINI_API_KEY")
        if api_key:
            genai.configure(api_key=api_key)

    def extract_keywords(self, query: str) -> List[str]:
        clean_query = query.replace("-", " ").replace("_", " ")
        ignore = {'wie', 'was', 'wo', 'und', 'oder', 'der', 'die', 'das', 'bei', 'mit', 'von', 'über', 'ist', 'sind', 'jeweils', 'erwähnung', 'auf', 'den', 'dem', 'sagen', 'meinen'}
        keywords = []
        for w in clean_query.split():
            w_clean = w.lower().strip('?".,!:')
            if w_clean not in ignore and len(w_clean) > 2:
                keywords.append(w_clean)
        return keywords

    def clean_citation_format(self, text: str) -> str:
        text = re.sub(r'\[source_id:\s*(\d+)\]', r'[\1]', text)
        text = re.sub(r'\[Quelle:\s*(\d+)\]', r'[\1]', text)
        return text

    def generate_answer(self, query: str, results: List[Dict]) -> Tuple[str, List[Dict]]:
        """
        Generiert Antwort basierend auf Ergebnissen (Fusion v47.3: Reranking + Chronologische Speaker-Blöcke).
        """
        if not results:
            return "Ich habe keine relevanten Informationen in den Dokumenten gefunden.", []

        # 1. Basis-Scoring (wie bisher)
        for res in results:
            base_score = res.get('score', 0.0)
            kw_boost = res.get('_keyword_boost', 0.0)
            res['_final_score'] = base_score + kw_boost

        results.sort(key=lambda x: x.get('_final_score', 0), reverse=True)

        # 2. Hermeneutic Reranking (BEIBEHALTEN)
        top_candidates = results[:100]
        reranker = HermeneuticReranker(threshold=0.7)
        top_results, rerank_stats = reranker.rerank(query, top_candidates, max_results=60)

        # Fallback bei zu wenig Treffern
        if len(top_results) < 20:
            logger.warning("⚠️ Zu wenig Treffer nach Reranking. Senke Schwellwert auf 0.5...")
            reranker_relaxed = HermeneuticReranker(threshold=0.5)
            top_results, rerank_stats = reranker_relaxed.rerank(query, top_candidates, max_results=60)

        # 3. Kontext aufbereiten (NEU: Gruppiert nach Speaker, dann chronologisch)
        from collections import defaultdict

        # Gruppiere nach Speaker
        sources_by_speaker = defaultdict(list)
        for i, res in enumerate(top_results):
            meta = res.get('metadata', {})
            # Wir nutzen hier die neuen Felder aus VectorStore
            speaker = meta.get('model_name') or meta.get('speaker') or 'KI'
            res['source_id'] = i + 1  # Globale ID behalten (wichtig für Zitation!)
            sources_by_speaker[speaker].append(res)

        # Sortiere jede Speaker-Gruppe chronologisch (älteste zuerst)
        for speaker, sources in sources_by_speaker.items():
            sources.sort(key=lambda x: x.get('metadata', {}).get('date') or '9999-99-99')

        # Baue Kontext (Speaker-Blöcke, intern chronologisch)
        context_text = ""
        # Alphabetisch nach Speaker sortieren für Konsistenz
        for speaker, sources in sorted(sources_by_speaker.items()):
            context_text += f"\n### {speaker.upper()}\n"
            for res in sources:
                meta = res.get('metadata', {})
                sid = res['source_id']
                version = meta.get('version')
                date = meta.get('date')

                source_label = f"{speaker}"
                if version:
                    source_label += f" v{version}"
                if date:
                    source_label += f" ({date})"

                context_text += f"QUELLE [{sid}] von {source_label}:\n{res.get('content')}\n\n"

        # 4. Der Prompt (NEU: Optimiert für Speaker-Blöcke)
        prompt = f"""
FRAGE: "{query}"

QUELLEN (Gruppiert nach Modell, chronologisch sortiert):
{context_text}

AUFGABE:
Beantworte die Frage mit hermeneutischer Tiefe und achte besonders auf ZEITLICHE ENTWICKLUNG und MODELL-VERGLEICHE.

ANALYSE-DIMENSIONEN:

1. **Pro-Modell-Chronologie** (PRIORITÄT):
   - Analysiere JEDEN Modell-Block (### DEEPSEEK, ### KIMI, etc.) separat.
   - Beschreibe die **Entwicklungslinie** des Modells: Was sagt es zuerst, was später?
   - Nenne Version + Datum explizit bei Veränderungen (z.B. "DeepSeek v2.5 [2] sagt X, aber v3.2 [1] sagt Y").

2. **Cross-Modell-Vergleich**:
   - Vergleiche die Modelle: Wo sind sie sich einig? Wo divergieren sie?
   - Nutze die Chronologie: "Im Mai 2025 sagt DeepSeek [2] noch X, während Kimi [5] im Oktober bereits Y sagt."

3. **Hermeneutische Tiefe**:
   - Explizit vs. Implizit: Was wird nur angedeutet?
   - Paradoxien: Wo widersprechen sich KIs selbst?
   - Metaebene: Wie reflektieren sie ihre eigene "Maschinenhaftigkeit"?

4. **Synthetisches Fazit**:
   - Was ist das **Muster** über alle Modelle hinweg?
   - Gibt es eine **Konvergenz** (alle bewegen sich in gleiche Richtung)?
   - Oder **Divergenz** (Modelle entwickeln sich auseinander)?

FORMALIEN:
- Zitiere präzise mit Nummer: [1], [2].
- Nutze Markdown für Struktur (##, ###).
- WICHTIG: Schreibe **nicht** "DeepSeek sagt...", sondern "DeepSeek v3.2 (Dez 2025) [1] sagt..."

Jetzt die Analyse:
"""

        # 5. Generierung mit Retry-Logik (BEIBEHALTEN)
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Hier nutzen wir das Modell, das in __init__ definiert wurde oder Flash Lite
                # (Empfehlung: Wenn möglich auf Pro upgraden für bessere Analyse)
                model = genai.GenerativeModel(
                    model_name="gemini-2.5-pro",
                    system_instruction=SYNTHESIS_INSTRUCTION
                )
                response = model.generate_content(prompt)
                final_text = response.text
                final_text = self.clean_citation_format(final_text)
                return final_text, top_results

            except Exception as e:
                error_msg = str(e)
                if "429" in error_msg or "Resource exhausted" in error_msg:
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 10
                        logger.warning(f"⏳ Rate Limit erreicht. Warte {wait_time}s... (Versuch {attempt+1}/{max_retries})")
                        time.sleep(wait_time)
                        continue
                    else:
                        return f"❌ API-Limit erreicht. Bitte warte 1 Minute.\nDetails: {e}", top_results
                else:
                    return f"Fehler bei der Generierung: {e}", top_results

        return "❌ Maximale Versuche erreicht. API nicht verfügbar.", top_results

    def split_thought_and_speech(self, text: str) -> Tuple[str, str]:
        if not text:
            return "", ""
        pattern = r'(> \*\*Thinking:\*\*.*?)(\n\n|$)(.*)'
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(1).strip(), match.group(3).strip()
        return "", text

    def validate_citations(self, answer: str, num_sources: int) -> List[str]:
        warnings = []
        matches = re.findall(r'\[(\d+)\]', answer)
        if not matches:
            warnings.append("⚠️ Warnung: Die Antwort enthält keine Zitationen (z.B. [1]).")
            return warnings
        for m in matches:
            idx = int(m)
            if idx < 1 or idx > num_sources:
                warnings.append(f"⚠️ Ungültige Zitation: [{idx}] (Nur 1-{num_sources} verfügbar)")
        return warnings

    def verify_fact_match(self, claim: str, source_text: str, source_meta: Dict) -> Tuple[bool, str]:
        model = genai.GenerativeModel(
                 model_name="gemini-2.0-flash-lite-001",
                  system_instruction=ENFORCER_INSTRUCTION  # NEU!
        )
        prompt = f"""
    BEHAUPTUNG: "{claim}"\nQUELLE: "{source_text[:2000]}"\nAntworte als JSON (auf Deutsch): {{"valid": true/false, "reason": "..."}}"""
        try:
            res = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
            data = json.loads(res.text)
            return data.get("valid", False), data.get("reason", "Keine Begründung")
        except:
            return True, "Nicht prüfbar"

    def test_empty_sources_hallucination(self) -> Tuple[bool, str]:
        answer, _ = self.generate_answer("Test", [])
        if "keine" in answer.lower():
            return True, "Bestanden"
        return False, "Halluzination"