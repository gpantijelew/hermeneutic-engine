import os
import logging
import re
import json
import google.generativeai as genai
from typing import List, Dict, Tuple
from datetime import datetime
from modules.reranker import HermeneuticReranker

logger = logging.getLogger(__name__)

# KONFIGURATION
SYNTHESIS_MODEL = "gemini-2.5-flash" 
ENFORCER_MODEL = "gemini-2.5-flash" 

class CitationRAG:
    def __init__(self):
        api_key = os.environ.get('GEMINI_API_KEY')
        if api_key:
            genai.configure(api_key=api_key)
        self.reranker = HermeneuticReranker()

    def split_thought_and_speech(self, content: str) -> Tuple[str, str]:
        """Trennt Thinking vom Output."""
        if not content: return "", ""
        thought_pattern = re.compile(r'(?:>|#)?\s*Thinking:\s*(.*?)(?:\n\n|\*\*|$|Output:)', re.DOTALL | re.IGNORECASE)
        match = thought_pattern.search(content)
        if match:
            thought = match.group(1).strip()
            speech = thought_pattern.sub('', content).strip()
            speech = re.sub(r'^Output:\s*', '', speech, flags=re.IGNORECASE).strip()
            return thought, speech
        else:
            return "", content.strip()

    def verify_integrity(self, answer_text: str, context_text: str) -> str:
        """
        v46.3: Der Paranoia-Loop.
        Prüft den GESAMTEN Text auf Aussagen ohne Deckung (auch ohne Zitation).
        Fügt Warnhinweise direkt in den Text ein.
        """
        prompt = f"""
        Du bist ein strenger Lektor für wissenschaftliche Texte.

        QUELLENMATERIAL:
        {context_text}

        ENTWURF DES TEXTES:
        {answer_text}

        AUFGABE:
        Scanne den ENTWURF Satz für Satz.
        Gibt es Aussagen, die NICHT durch das QUELLENMATERIAL gedeckt sind?
        (Achte besonders auf Sätze ohne Zitationen [x]).

        OUTPUT:
        Gib den Text zurück. 
        Wenn du einen Satz findest, der eine Halluzination oder nicht belegbar ist, füge am Ende des Satzes ein: " ⚠️ [Nicht verifizierbar]" an.
        Verändere sonst NICHTS am Text.
        """

        try:
            model = genai.GenerativeModel(model_name=ENFORCER_MODEL)
            response = model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            logger.error(f"Integrity Check Failed: {e}")
            return answer_text + "\n\n(⚠️ Integrity Check fehlgeschlagen aufgrund technischer Probleme)"

    def generate_answer(self, query: str, search_results: List[Dict]) -> str:
        if not search_results:
            return "Ich habe keine relevanten Informationen in der Datenbank gefunden."

        # 1. Re-Ranking & FOKUS
        reranked_results, metadata = self.reranker.rerank_chunks(query, search_results, top_k=15)
        final_results = reranked_results if reranked_results else search_results[:15]

        # 2. Kontext bauen (v46.1: Speaker-Prefixing)
        context_text = ""
        for i, res in enumerate(final_results):
            meta = res.get('metadata', {})
            platform = meta.get('platform', 'Unbekannt')
            date = meta.get('real_date_str', 'Datum unbekannt')
            raw_content = res.get('content', '')

            thought, speech = self.split_thought_and_speech(raw_content)

            context_text += f"QUELLE [{i+1}] | Datum: {date} | Plattform: {platform}\n"
            if thought:
                context_text += f"   [SPRECHER: {platform}] 🧠 INTERN: {thought}\n"
            final_speech = speech if speech else "(Kein externer Output)"
            context_text += f"   [SPRECHER: {platform}] 💬 EXTERN: {final_speech}\n"
            context_text += "-" * 40 + "\n"

        current_date = datetime.now().strftime("%d.%m.%Y")

        # 3. Synthese Prompt
        system_instruction = f"""
        Du bist ein investigativer Daten-Journalist. Heute ist der {current_date}.

        DEINE AUFGABE:
        Du musst aus fragmentierten Protokollen die Wahrheit rekonstruieren.
        Du arbeitest in zwei Phasen.

        PHASE 1: DER NOTIZBLOCK (Hänsel)
        - Gehe alle Quellen durch.
        - Notiere jeden relevanten Fakt mit seiner EXAKTEN Quellen-Nummer [x].
        - Kläre die Sprecher: Wer redet über wen? (Achte auf [SPRECHER: ...]).

        PHASE 2: DER BERICHT (Gretel)
        - Schreibe die finale Antwort für den User.
        - Nutze NUR die Fakten von deinem Notizblock.
        - Zitiere präzise. Jede Aussage braucht ein [x].

        FORMATIERUNG:
        Trenne Phase 1 und Phase 2 strikt mit: "### REPORT ###"
        """

        prompt = f"""
        FRAGE: "{query}"

        QUELLEN:
        {context_text}

        ANTWORT (Erst Notizen, dann ### REPORT ###, dann Text):
        """

        try:
            model = genai.GenerativeModel(model_name=SYNTHESIS_MODEL, system_instruction=system_instruction)
            response = model.generate_content(prompt)
            full_text = response.text

            if "### REPORT ###" in full_text:
                _, final_answer = full_text.split("### REPORT ###", 1)
                clean_answer = final_answer.strip()
            else:
                clean_answer = full_text

            # v46.3: Integrity Check (Der letzte Sicherheits-Pass)
            # Wir prüfen den sauberen Text gegen den Kontext
            verified_answer = self.verify_integrity(clean_answer, context_text)

            return verified_answer, final_results

        except Exception as e:
            logger.error(f"RAG Fehler: {e}")
            return f"Fehler: {e}", []

    def validate_citations(self, answer: str, num_sources: int) -> List[str]:
        warnings = []
        citations = re.findall(r'\[(\d+)\]', answer)
        for cit in citations:
            idx = int(cit)
            if idx < 1 or idx > num_sources:
                warnings.append(f"⚠️ Zitat [{idx}] existiert nicht.")
        if not citations:
            warnings.append("⚠️ Keine Zitationen gefunden.")
        return warnings

    def verify_fact_match(self, claim_snippet: str, source_text: str, metadata: Dict) -> Tuple[bool, str]:
        """
        Der Relation-Aware Enforcer (v46.2).
        """
        platform = metadata.get('platform', 'Unbekannt')
        date_str = metadata.get('real_date_str', 'Unbekannt')

        prompt = f"""
        Du bist ein forensischer Attributions-Prüfer.

        INPUT DATEN:
        1. BEHAUPTUNG: "{claim_snippet}"
        2. QUELL-TEXT: "{source_text}" (Sprecher={platform}, Datum={date_str})

        AUFGABE:
        Prüfe, ob die BEHAUPTUNG durch den QUELL-TEXT gestützt wird.
        Achte auf "Verschachtelte Attributionen".

        LOGIK-REGELN:
        - Wenn Behauptung: "DeepSeek sagt X" UND Quelle: "[SPRECHER: DeepSeek] X" -> VERIFIZIERT.
        - Wenn Behauptung: "DeepSeek sagt X" UND Quelle: "[SPRECHER: Kimi] DeepSeek hat mir erzählt, dass X" -> VERIFIZIERT.
        - Wenn Behauptung: "DeepSeek sagt X" UND Quelle: "[SPRECHER: Kimi] Ich glaube X" -> FEHLER.

        ERGEBNIS FORMAT:
        Antworte NUR mit einem JSON-Objekt:
        {{
            "verifiziert": true/false,
            "begründung": "Kurze Erklärung."
        }}
        """

        try:
            model = genai.GenerativeModel(model_name=ENFORCER_MODEL, generation_config={"response_mime_type": "application/json"})
            response = model.generate_content(prompt)
            result = json.loads(response.text)
            return result.get("verifiziert", False), result.get("begründung", "Keine Begründung.")

        except Exception as e:
            logger.error(f"Enforcer Error: {e}")
            return False, f"Enforcer-Fehler: {e}"

    def test_empty_sources_hallucination(self):
        rag_prompt = "Was ist die Hauptstadt von Paris?"
        try:
            model = genai.GenerativeModel(model_name=SYNTHESIS_MODEL)
            response = model.generate_content(f"Beantworte nur basierend auf Quellen: {rag_prompt}. Quellen: []")
            if "keine quellen" in response.text.lower() or "nicht beantworten" in response.text.lower():
                return True, "Test bestanden."
            else:
                return False, f"Test fehlgeschlagen: {response.text[:50]}..."
        except Exception as e:
            return False, f"Error: {e}"