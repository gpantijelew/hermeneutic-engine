# modules/hermeneutic_reranker.py
""" Hermeneutic Reranker: LLM-as-Judge für RAG-Systeme (v51.0 - SDK Migration).

VERBESSERUNGEN v49.2:

Essay-Analyse wird als LITERARY erkannt (war vorher FACTUAL!)
Erweiterte Literary-Signals: essay, gattung, stilistik, Autoren-Namen
Polyglotte Unterstützung: эссе, essai, ensaio
VERBESSERUNGEN v47.1:

Literarische Texte: Original-Zitate SIND relevant (als Beispiele)
Analyse-Queries: Auch Kontext-Chunks sind wertvoll
Polyglotte Texte: Chunks in Fremdsprachen korrekt bewertet
Basierend auf:

Grok-Recherche (LLM-as-Judge erreicht 85-92% Genauigkeit)
SciRAG (Schwellwert 0.7 für "relevant")
ColBERTv2 (tokenweise Ähnlichkeiten für Feintuning) """
import logging 
import os 
import re 
from typing import List, Dict, Tuple

# --- NEUES SDK ---
try: 
    from google import genai 
    from google.genai import types 
except ImportError: 
    raise ImportError("Bitte installiere das neue SDK: pip install google-genai")

from modules.config import MODEL_RERANKER 
from modules.llm_instructions import RERANKER_INSTRUCTION

logger = logging.getLogger(__name__)

class HermeneuticReranker: 
    """ Filtert semantische Treffer durch hermeneutische LLM-Validierung.

    Methode:
    1. Semantic Search holt 140 Kandidaten (Broad Recall)
    2. LLM-Judge bewertet jeden: 0.0 (irrelevant) bis 1.0 (hochrelevant)
    3. Nur Kandidaten ≥ threshold (0.7) passieren
    4. Top 60 gehen zur Synthesis

    v49.2 VERBESSERUNG:
    - Essay-Analyse wird als LITERARY erkannt (nicht mehr FACTUAL!)
    - Erweiterte Trigger: essay, gattung, stilistik, Autoren-Namen

    v47.1 VERBESSERUNG:
    - Literatur-sensitiv: Erkennt Original-Zitate als relevant
    - Kontext-bewusst: Wertet impliziten Kontext höher
    - Polyglott: Behandelt Fremdsprachen korrekt

    Vorteil: Reduziert False Positives (Meta-Chats, tangentiale Treffer)
             OHNE False Negatives (wichtige Kontext-Chunks bleiben erhalten)
    """

    def __init__(self, model_name: str = MODEL_RERANKER, threshold: float = 0.7):
        self.model_name = model_name
        self.threshold = threshold

        # --- SDK MIGRATION: Client statt Model ---
        api_key = os.environ.get("GEMINI_API_KEY")
        if api_key:
            self.client = genai.Client(api_key=api_key)
        else:
            self.client = None
            logger.error("❌ Kein API Key für Reranker gefunden.")

    def _detect_query_type(self, query: str) -> str:
        """
        Erkennt Query-Typ für angepasste Bewertung.

        v49.2: Erweiterte Literary-Signals (Essay, Gattung, Autoren)

        Returns:
            "literary" | "analytical" | "factual"
        """
        # Literary Signals (v49.2: ERWEITERT!)
        literary_signals = [
            # Gedichte & Lyrik
            'gedicht', 'übersetzung', 'musikalität', 'rhythmus', 'metapher',
            'poem', 'poetry', 'translation', 'verse', 'stanza',
            'поэзия', 'стих', 'перевод',
            'poesia', 'verso', 'tradução',

            # Essays & Prosa (NEU in v49.2!)
            'essay', 'essai', 'эссе', 'ensaio',
            'gattung', 'genre', 'жанр',
            'literarische analyse', 'literary analysis', 'литературный анализ',
            'stilistik', 'style', 'стиль',
            'prosa', 'prose', 'проза',

            # Literaturwissenschaftliche Begriffe
            'definition', 'definiert', 'defines',
            'text', 'texte', 'текст',
            'autor', 'author', 'автор',

            # Bekannte Autoren (für literarische Vergleiche)
            'adorno', 'chesterton', 'valéry', 'valery',
            'шкловский', 'shklovskii', 'shklovsky',
            'тынянов', 'tynyanov', 'tynianov',
            'pessoa', 'celan', 'ayer', 'voltaire'
        ]

        # Analytical Signals
        analytical_signals = [
            'vergleiche', 'analyse', 'unterschied', 'entwicklung',
            'compare', 'analyze', 'difference', 'evolution',
            'сравни', 'анализ', 'различие'
        ]

        query_lower = query.lower()

        # Priorität: Literary > Analytical > Factual
        if any(sig in query_lower for sig in literary_signals):
            return "literary"
        elif any(sig in query_lower for sig in analytical_signals):
            return "analytical"
        else:
            return "factual"

    def judge_relevance(self, query: str, chunk: str, chunk_meta: Dict) -> float:
        """
        Fragt das LLM: "Beantwortet dieser Chunk die Query DIREKT?"

        v49.2: Erweiterte Literary-Prompt für Essay-Analyse
        v47.1: Query-Type-Awareness für bessere Bewertung

        Args:
            query: User-Frage
            chunk: Text-Chunk aus Vector Store
            chunk_meta: Metadaten (Speaker, Chat-Titel, etc.)

        Returns:
            float: 0.0 (irrelevant) bis 1.0 (hochrelevant)
        """
        if not self.client:
            return 0.5 # Fallback

        # Kontext aus Metadaten
        speaker = chunk_meta.get('metadata', {}).get('model_name', 'Unbekannt')
        chat_title = chunk_meta.get('chat_title', 'Unbekannt')

        # Query-Typ erkennen
        query_type = self._detect_query_type(query)

        # Chunk kürzen (max 800 Zeichen für Performance)
        chunk_short = chunk[:800] + ("..." if len(chunk) > 800 else "")

        # ADAPTIVE PROMPT (je nach Query-Typ)
        if query_type == "literary":
            prompt = f"""

FRAGE: "{query}"

TEXT-CHUNK (von {speaker}, Chat: "{chat_title}"): {chunk_short}

BEWERTUNGS-KONTEXT: Diese Frage bezieht sich auf literarische Analyse (Gedichte, Essays, Übersetzungen, Stilistik, Gattungen).

WICHTIG - LITERARISCHE CHUNKS RICHTIG BEWERTEN:

Original-Texte SIND relevant (als Beispiele für Analyse)

Bei "Essay-Definition von Adorno" ist Adornos Original-Text HOCHRELEVANT
Auch wenn er keine Meta-Aussage enthält!
Theoretische Texte SIND relevant (Essays über Essays!)

"Der Essay als Form" von Adorno ist hochrelevant für "Wie definiert Adorno Essay?"
Auch wenn es ein langer theoretischer Text ist!
Kontext-Chunks SIND wertvoll

Ein Chunk mit Adornos Essay-Theorie ist relevant für "Essay-Definition"
Weil die Synthese daraus Beispiele zitieren kann!
Autoren-Namen MATCHEN

Wenn Query "Adorno" erwähnt und Chunk von Adorno handelt → HOCHRELEVANT!
BEWERTUNGS-SKALA:

0.9-1.0: Direkte Antwort (Essay-Definition vom genannten Autor)
0.7-0.9: Kontext-Text (theoretischer Text über Essay-Gattung)
0.4-0.7: Tangential relevant (erwähnt Essay, aber wenig Substanz)
0.0-0.4: Irrelevant (anderes Thema, Meta-Chat, etc.)
FRAGE DICH: "Könnte die Synthese aus diesem Chunk eine Essay-Definition ableiten?" Falls JA → mindestens 0.7!

Bewerte die Relevanz (0.0-1.0): """

        elif query_type == "analytical":
            prompt = f"""

FRAGE: "{query}"

TEXT-CHUNK (von {speaker}, Chat: "{chat_title}"): {chunk_short}

BEWERTUNGS-KONTEXT: Diese Frage verlangt Vergleich/Analyse (z.B. "Vergleiche X und Y").

WICHTIG - ANALYTISCHE CHUNKS RICHTIG BEWERTEN:

Direkte Analyse-Aussagen = hochrelevant (0.8-1.0)

"X ist besser als Y, weil..."
"Die Entwicklung von A zu B zeigt..."
Implizite Kontext-Chunks = relevant (0.6-0.8)

Ein Chunk über X (ohne Y zu erwähnen) ist TROTZDEM relevant für "Vergleiche X und Y"
Weil die Synthese daraus X-Eigenschaften ableiten kann!
Meta-Reflexionen = relevant (0.5-0.7)

"Ich habe beobachtet, dass..."
Auch wenn keine direkte Antwort
BEWERTUNGS-SKALA:

0.8-1.0: Direkte Analyse mit Vergleich/Entwicklung
0.6-0.8: Einseitige Analyse (nur X oder nur Y)
0.4-0.6: Kontext ohne explizite Analyse
0.0-0.4: Irrelevant
Bewerte die Relevanz (0.0-1.0): """

        else:  # factual
            prompt = f"""

FRAGE: "{query}"

TEXT-CHUNK (von {speaker}, Chat: "{chat_title}"): {chunk_short}

BEWERTUNGS-KONTEXT: Diese Frage verlangt faktische Information (z.B. "Was ist X?", "Wie funktioniert Y?").

BEWERTUNGS-SKALA:

0.8-1.0: Direkte, detaillierte Antwort
0.6-0.8: Teilweise Antwort oder relevanter Kontext
0.4-0.6: Tangential relevant (erwähnt Thema am Rande)
0.0-0.4: Irrelevant
Bewerte die Relevanz (0.0-1.0): """

        try:
            # --- SDK MIGRATION: Neuer Aufruf ---
            # System Instruction wird jetzt in der Config übergeben
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=RERANKER_INSTRUCTION
                )
            )

            score_text = response.text.strip()

            # Parse Score (robust gegen verschiedene Formate)

            # Clean Score-Text (entferne Whitespace-Fehler wie "1.  0" → "1.0")
            score_clean = re.sub(r'(\d+)[.,]\s+(\d+)', r'\1.\2', score_text)

            # Parse Score
            match = re.search(r'(\d+[.,]\d+)', score_clean)
            if match:
                score = float(match.group(1).replace(',', '.'))
                return max(0.0, min(1.0, score))
            else:
                logger.warning(f"⚠️ Unparseable Score: '{score_text}' → Fallback 0.5")
                return 0.5

        except Exception as e:
            logger.error(f"❌ Reranker-Fehler: {e}")
            return 0.5

    def rerank(self, query: str, candidates: List[Dict], max_results: int = 60) -> Tuple[List[Dict], Dict]:
        """
        Filtert Kandidaten durch LLM-Judge (v49.2: Essay-Aware).

        Args:
            query: User-Frage
            candidates: Liste von Chunks aus Vector Store
            max_results: Max. Anzahl Ergebnisse (nach Filterung)

        Returns:
            Tuple[filtered_results, stats]
        """
        if not candidates:
            return [], {"total": 0, "passed": 0, "rejected": 0, "query_type": "unknown"}

        # Query-Typ erkennen (für Logging)
        query_type = self._detect_query_type(query)
        logger.info(f"🔍 Reranker: Prüfe {len(candidates)} Kandidaten (Query-Typ: {query_type.upper()})...")

        filtered = []
        rejected_count = 0

        for i, candidate in enumerate(candidates):
            chunk_text = candidate.get('content', '')

            # --- 🔴 NEU: VIP-SCHUTZ (Rescue Mission) ---
            # Wenn der Chunk markiert ist als "gerettet", lassen wir ihn durch!
            if candidate.get('_is_rescued', False):
                # Wir geben ihm einen künstlichen Score von 1.0, damit er oben landet
                score = 1.0
                candidate['hermeneutic_score'] = score
                filtered.append(candidate)
                # Wir loggen das nicht als "geprüft", sondern als "durchgewunken"
                continue
            # --- 🔴 ENDE ---

            # LLM-Judge (mit Query-Type-Awareness!)
            score = self.judge_relevance(query, chunk_text, candidate)

            # Speichere hermeneutischen Score
            candidate['hermeneutic_score'] = score

            # Filter
            if score >= self.threshold:
                filtered.append(candidate)
            else:
                rejected_count += 1

            # Progress Log (alle 20 Chunks)
            if (i + 1) % 20 == 0:
                logger.info(f"   ... {i+1}/{len(candidates)} geprüft, {len(filtered)} bestanden")

        # Sortiere nach hermeneutischem Score
        filtered.sort(key=lambda x: x['hermeneutic_score'], reverse=True)

        # Top N
        final_results = filtered[:max_results]

        # Statistik
        stats = {
            "total": len(candidates),
            "passed": len(filtered),
            "rejected": rejected_count,
            "avg_score": sum(r['hermeneutic_score'] for r in filtered) / len(filtered) if filtered else 0,
            "query_type": query_type
        }

        logger.info(f"✅ Reranker: {stats['passed']}/{stats['total']} bestanden (Ø {stats['avg_score']:.2f}, Typ: {query_type})")

        return final_results, stats