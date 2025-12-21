import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import os
import sys
import time
import traceback
from dotenv import load_dotenv

# Pfad-Hack (damit Module gefunden werden)
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Eigene Module
from modules.vector_store import FirestoreVectorStore
from modules.citation_rag import CitationRAG
from system_prompts import GEMINI_3_SYSTEM_INSTRUCTION

# Datenbank-Funktionen (WICHTIG: Die waren weg!)
from modules.database import (
    get_firestore_client,
    create_chat_in_firestore,
    save_message,
    generate_and_update_title,
    delete_chat,
    get_chat_list,
    load_chat_history,
    rename_chat,
    load_global_settings,
    save_global_settings
)

# Hilfsfunktionen für Export (falls du sie in app.py hast, sonst ignorieren)
# from modules.utils.export_utils import generate_markdown, generate_json, generate_excel 

# Logging setup
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# .env laden
load_dotenv()

class CitationRAG:
    def __init__(self, vector_store: FirestoreVectorStore = None, model_name: str = "gemini-2.0-flash-lite-001"):
        self.vector_store = vector_store
        self.model_name = model_name
        self.classifier = QueryClassifier()
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

    def generate_answer(self, query: str, results: List[Dict]) -> Tuple[str, List[Dict], str]:
        """
        Generiert Antwort (Fusion v48: Reranking + Classifier + Mode-Switch).
        Returns: (Antwort-Text, Quellen-Liste, Modus-String)
        """
        if not results:
            return "Ich habe keine relevanten Informationen in den Dokumenten gefunden.", [], "none"

        # 1. Basis-Scoring
        for res in results:
            base_score = res.get('score', 0.0)
            kw_boost = res.get('_keyword_boost', 0.0)
            res['_final_score'] = base_score + kw_boost

        results.sort(key=lambda x: x.get('_final_score', 0), reverse=True)

        # 2. Hermeneutic Reranking (Erst filtern, dann klassifizieren!)
        top_candidates = results[:100]
        reranker = HermeneuticReranker(threshold=0.7)
        top_results, rerank_stats = reranker.rerank(query, top_candidates, max_results=60)

        # Fallback bei zu wenig Treffern
        if len(top_results) < 20:
            logger.warning("⚠️ Zu wenig Treffer nach Reranking. Senke Schwellwert auf 0.5...")
            reranker_relaxed = HermeneuticReranker(threshold=0.5)
            top_results, rerank_stats = reranker_relaxed.rerank(query, top_candidates, max_results=60)

        # 3. Klassifizierung (JETZT erst, wo wir die Top-Ergebnisse haben)
        mode = self.classifier.classify(query, top_results)
        logger.info(f"🧠 RAG Modus: {mode.value.upper()}")

        # 4. Kontext aufbereiten (Gruppiert nach Speaker, dann chronologisch)
        # Wir nutzen diese Struktur für BEIDE Modi, da sie sauber ist.
        sources_by_speaker = defaultdict(list)
        for i, res in enumerate(top_results):
            meta = res.get('metadata', {})
            speaker = meta.get('model_name') or meta.get('speaker') or 'KI'
            res['source_id'] = i + 1
            sources_by_speaker[speaker].append(res)

        # Sortiere jede Speaker-Gruppe chronologisch
        for speaker, sources in sources_by_speaker.items():
            sources.sort(key=lambda x: x.get('metadata', {}).get('date') or '9999-99-99')

        # Baue Kontext-String
        context_text = ""
        for speaker, sources in sorted(sources_by_speaker.items()):
            context_text += f"\n### {speaker.upper()}\n"
            for res in sources:
                meta = res.get('metadata', {})
                sid = res['source_id']
                version = meta.get('version')
                date = meta.get('date')

                source_label = f"{speaker}"
                if version: source_label += f" v{version}"
                if date: source_label += f" ({date})"

                context_text += f"QUELLE [{sid}] von {source_label}:\n{res.get('content')}\n\n"

        # 5. Prompt-Weiche (Switch)
        if mode == QueryType.EXEGESIS:
            # --- MODUS A: EXEGESE ---
            system_instruction = EXEGESIS_SYNTHESIS_PROMPT

            # Einfacherer User-Prompt für Exegese
            prompt = f"""
FRAGE: "{query}"

QUELLEN:
{context_text}

AUFGABE:
Analysiere die Quellen direkt und beantworte die Frage präzise.
Vermeide Meta-Diskussionen über die Modelle, wenn nicht danach gefragt wurde.
Konzentriere dich auf Inhalte, Definitionen und Erklärungen.

Zitieren Sie Aussagen mit [x].
"""
        else:
            # --- MODUS B: DISKURS (v47 Standard) ---
            system_instruction = SYNTHESIS_INSTRUCTION

            # Komplexer User-Prompt für Diskurs
            prompt = f"""
FRAGE: "{query}"

QUELLEN (Gruppiert nach Modell, chronologisch sortiert):
{context_text}

AUFGABE:
Beantworte die Frage mit hermeneutischer Tiefe und achte besonders auf ZEITLICHE ENTWICKLUNG und MODELL-VERGLEICHE.

ANALYSE-DIMENSIONEN:
1. **Pro-Modell-Chronologie** (PRIORITÄT):
   - Analysiere JEDEN Modell-Block separat.
   - Beschreibe die Entwicklungslinie.
   - Nenne Version + Datum explizit.

2. **Cross-Modell-Vergleich**:
   - Vergleiche die Modelle: Konsens vs. Divergenz.

3. **Hermeneutische Tiefe**:
   - Explizit vs. Implizit.
   - Paradoxien & Metaebene.

4. **Synthetisches Fazit**:
   - Muster, Konvergenz oder Divergenz?

FORMALIEN:
- Zitiere präzise mit Nummer: [1], [2].
- Nutze Markdown.
"""

        # 6. Generierung mit Retry-Logik
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Wir nutzen gemini-2.5-pro für maximale Intelligenz
                model = genai.GenerativeModel(
                    model_name="gemini-2.5-pro",
                    system_instruction=system_instruction
                )
                response = model.generate_content(prompt)
                final_text = self.clean_citation_format(response.text)

                # WICHTIG: 3 Werte zurückgeben
                return final_text, top_results, mode.value

            except Exception as e:
                error_msg = str(e)
                if "429" in error_msg or "Resource exhausted" in error_msg:
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 10
                        logger.warning(f"⏳ Rate Limit. Warte {wait_time}s...")
                        time.sleep(wait_time)
                        continue
                    else:
                        return f"❌ API-Limit erreicht.\nDetails: {e}", top_results, "error"
                else:
                    return f"Fehler bei der Generierung: {e}", top_results, "error"

        return "❌ Maximale Versuche erreicht.", top_results, "error"

    def split_thought_and_speech(self, text: str) -> Tuple[str, str]:
        if not text: return "", ""
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
                  system_instruction=ENFORCER_INSTRUCTION
        )
        prompt = f"""
    BEHAUPTUNG: "{claim}"\nQUELLE: "{source_text[:2000]}"\nAntworte als JSON (auf Deutsch): {{"valid": true/false, "reason": "..."}}"""
        try:
            res = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
            data = json.loads(res.text)
            return data.get("valid", False), data.get("reason", "Keine Begründung")
        except:
            return True, "Nicht prüfbar"