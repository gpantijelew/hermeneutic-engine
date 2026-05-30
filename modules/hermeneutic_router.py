# modules/hermeneutic_router.py
"""
Hermeneutic Router - Adaptive RAG-Strategie-Entscheidung.

PHILOSOPHIE:
Entscheidet VOR dem Retrieval über die Such-Parameter basierend auf Query-Intent.

TAXONOMIE (orthogonal zu QueryType aus query_classifier.py):
- FACTUAL: Präzise Fakten, Definitionen → Enge Suche, hohe Präzision
- LITERARY: Gedichte, Essays, Metaphern → Weite Suche, niedrige Schwelle
- ANALYTICAL: Vergleiche, Entwicklungen → Mittlere Suche, Balance
- STILISTIC: Stilanalyse, Rhetorik, Kadenz → Weite Suche + Breite (Phase 0.5)
- STILISTIC_DEEPENING: Vorliegende Stil-Befunde vertiefen → Maximale Breite + Analyse

WICHTIG: Router-Intent und QueryType sind KOMPLEMENTÄR:
┌──────────────┬──────────┬───────────┬────────────┬────────────┬─────────────────────┐
│              │ FACTUAL  │ LITERARY  │ ANALYTICAL │ STILISTIC  │ STILISTIC_DEEPENING │
├──────────────┼──────────┼───────────┼────────────┼────────────┼─────────────────────┤
│ DISCOURSE    │    ✓     │     ✓     │     ✓      │     ✓      │          ✓          │
│ EXEGESIS     │    ✓     │     ✓     │     ✓      │     ✓      │          ✓          │
└──────────────┴──────────┴───────────┴────────────┴────────────┴─────────────────────┘

Beispiel:
- "Vergleiche Heideggers frühe vs. späte Werke"
  → Router: ANALYTICAL (Vergleich braucht viele Belege)
  → Classifier: DISCOURSE (zwei "Sprecher": früh/spät)

- "Was ist Dasein?"
  → Router: FACTUAL (Definition braucht Präzision)
  → Classifier: EXEGESIS (Konzept-Erklärung, keine Diskursivität)

- "Vergleiche den Stil Lenins und Herzens — Kadenz, Register, Gestus"
  → Router: STILISTIC (Stilvergleich braucht breite Abdeckung + Phase 0.5 Distillation)
  → Classifier: DISCOURSE (zwei "Stimmen": Lenin/Herzen)

ÄNDERUNGSHISTORIE:
- v57: STILISTIC-Intent hinzugefügt (Stilanalyse, Rhetorik, Kadenz, Wahlverwandtschaft)
- v50.9-local: Migration auf llm_wrapper (kein genai-Import mehr)
- v50.7: Migration auf neues google.genai SDK
- v50.6: Klarere Taxonomie-Dokumentation, orthogonale Beziehung zu QueryType
- v50: Initiale Version (Adaptive RAG)
"""

import logging
from enum import Enum
from typing import Dict, Any

from modules.llm_wrapper import llm_call_json

logger = logging.getLogger(__name__)


class QueryIntent(Enum):
    """
    Intent-Taxonomie für Retrieval-Strategie.

    FACTUAL: Definitionen, Fakten, "Was ist X?"
        → retrieval_limit: ~15, threshold: 0.75 (eng & präzise)

    LITERARY: Gedichte, Essays, Stil, Atmosphäre
        → retrieval_limit: ~40, threshold: 0.45 (weit & inklusiv)

    ANALYTICAL: Vergleiche, Entwicklungen, "X vs. Y"
        → retrieval_limit: ~30, threshold: 0.6 (Balance)

    ANALYTICAL_FORENSIC: Dekonstruktion, Motivanalyse, Widersprüche
        → retrieval_limit: ~35, threshold: 0.45 (Balance + Breite)

    STILISTIC: Stilanalyse, Rhetorik, Kadenz, Register, Wahlverwandtschaft
        → retrieval_limit: ~35, threshold: 0.45 (Breite für stilistische Muster)

    STILISTIC_DEEPENING: Vorliegende Stil-Befunde vertiefen, über Befunde hinausgehen
        → retrieval_limit: ~40, threshold: 0.4 (Maximale Breite + Analyse-Kontext)
    """

    FACTUAL = "factual"
    LITERARY = "literary"
    ANALYTICAL = "analytical"
    ANALYTICAL_FORENSIC = "analytical_forensic"
    STILISTIC = "stilistic"
    STILISTIC_DEEPENING = "stilistic_deepening"
    META_ANALYTICAL = "meta_analytical"
    SYNTHESIS_BEST_OF = "synthesis_best_of"
    STILISIERUNG = "stilisierung"
    IFS_CONTROL = "ifs_control"
    IFS_FIGHT = "ifs_fight"
    IFS_FEAR = "ifs_fear"

class HermeneuticRouter:
    """
    Entscheidet VOR dem Retrieval über die Strategie.

    ROLLE IN DER PIPELINE:
    1. Router analysiert Query → FACTUAL/LITERARY/ANALYTICAL/ANALYTICAL_FORENSIC/STILISTIC/STILISTIC_DEEPENING
    2. Retrieval mit adaptiven Parametern (limit, threshold)
    3. Query-Classifier analysiert Results → DISCOURSE/EXEGESIS
    4. Synthesis mit passendem Prompt (beide Infos kombiniert)
    """

    def __init__(self):
        """
        Initialisiert den Router.
        v50.9-local: Kein eigener Client mehr – llm_wrapper übernimmt.
        """
        logger.info("✅ HermeneuticRouter initialized (llm_wrapper backend).")

    def route_query(self, query: str) -> Dict[str, Any]:
        """
        Analysiert die Query und gibt Retrieval-Parameter zurück.

        Args:
            query: User-Frage (natürlichsprachig)

        Returns:
            Dict mit:
            - intent (str): FACTUAL, LITERARY, ANALYTICAL, ANALYTICAL_FORENSIC, STILISTIC, STILISTIC_DEEPENING, META_ANALYTICAL
            - limit (int): Anzahl Chunks aus DB (15-40)
            - threshold (float): Reranker-Schwelle (0.45-0.75)
            - reasoning (str): Begründung der Entscheidung

        Bei Fehler: Fallback auf sichere Defaults
        """
        prompt = f"""Du bist der Router für eine hermeneutische Suchmaschine.

USER QUERY: "{query}"

AUFGABE:
Klassifiziere die Intention und bestimme die Such-Parameter.

KATEGORIEN:

**FACTUAL**: Definitionen, Fakten, "Was ist X?", "Wann passierte Y?"
→ Braucht: Präzision, wenige hochrelevante Treffer
→ Parameter: retrieval_limit=15, rerank_threshold=0.75

**LITERARY**: Gedichte, Essays, Stil, Atmosphäre, "Ich"-Erzähler, Metaphorik,
Bedeutung, Deutung, literarisches Gewissen, Tradition, Verstehen
→ Braucht: Weiten Kontext, viele Nuancen
→ Parameter: retrieval_limit=40, rerank_threshold=0.45
ERKENNUNGSMERKMALE (mindestens eines muss zutreffen):
- Query enthält: "Bedeutung", "deuten", "Deutung", "bedeuten", "literarisches Gewissen",
  "Tradition", "literarische Tradition", "Verstehen", "Sinn", "Sinngehalt",
  "wie ist das zu verstehen", "was bedeutet das", "was meint"
- Query fragt nach dem WAS der Bedeutung, nicht nach dem WIE der Form:
  "Was bedeutet diese Metapher?", "Welchen Sinn hat...?",
  "Welcher Tradition gehört dieser Text an?"
- Query bittet um Auslegung oder Vertiefung eines vorliegenden Befunds:
  "Deute die Texte", "Was bedeuten die sprachlichen Mittel?",
  "Eine Analyse liegt vor — was bedeuten die Befunde?"
ABGRENZUNG zu STILISTIC:
STILISTIC beschreibt, WIE Texte sprechen (ohne zu deuten).
LITERARY beschreibt, WAS die sprachlichen Mittel BEDEUTEN.
Wenn die Frage nach Bedeutung, Deutung oder Sinn fragt → LITERARY.
Wenn die Frage nach Struktur, Gestus, Register fragt → STILISTIC.

**ANALYTICAL**: Vergleiche ("X vs. Y"), Entwicklungen ("von A nach B"), Diskurse
→ Braucht: Viele Belege für beide Seiten, Balance
→ Parameter: retrieval_limit=30, rerank_threshold=0.6

**ANALYTICAL_FORENSIC**: Dekonstruktion, Motivanalyse, Widersprüche aufdecken,
"Warum hat X seine Meinung geändert?", "Welche Interessen stecken hinter?",
"Was verschweigt der Text?", Selbstzeugnisse kritisch hinterfragen
→ Braucht: Viele Belege, breite Abdeckung für kritische Analyse
→ Parameter: retrieval_limit=35, rerank_threshold=0.45

**STILISTIC**: Stilanalyse, Stilvergleich, rhetorische Strukturen,
"Wie spricht X?", "Vergleiche den Stil von A und B", Kadenz, Register,
Gestus, Wortwahl, Wahlverwandtschaft,
Augenlektüre vs. Vorlese-Lektüre, Satzmuster, Prosodie
→ Braucht: Viele Belege für stilistische Muster, breite Abdeckung
→ Parameter: retrieval_limit=35, rerank_threshold=0.45
ERKENNUNGSMERKMALE (mindestens eines muss zutreffen):
- Query enthält: "Stil", "stilistisch", "Rhetorik", "Kadenz", "Register",
  "Gestus", "Wortwahl", "Diktion", "Satzmelodie",
  "Wahlverwandtschaft", "Vorgänger", "Augenlektüre",
  "Vorlese-Lektüre", "Prosodie", "Satzbau", "Stimme"
- Query fragt nach dem WIE des Sprechens, nicht nach dem WAS:
  "Wie spricht Lenin?", "Welchen Gestus hat dieser Text?",
  "Vergleiche den Stil von..."
- Query vergleicht Autoren auf der Ebene der SPRACHE, nicht der Argumentation:
  "Stil Lenins vs. Herzens", "Satzrhythmus vergleichen"
ABGRENZUNG zu ANALYTICAL:
ANALYTICAL vergleicht Inhalte, Argumente, Entwicklungen.
STILISTIC vergleicht SPRACHLICHE Mittel, Gestus, Register, Kadenz.
ABGRENZUNG zu LITERARY:
LITERARY deutet die Bedeutung von Texten — einzeln oder im Vergleich.
STILISTIC beschreibt, WIE Texte sprechen (ohne zu deuten).
LITERARY beschreibt, WAS die sprachlichen Mittel BEDEUTEN.
Wenn die Frage nach Bedeutung, Deutung oder literarischem Gewissen fragt → LITERARY.
Wenn die Frage nach Struktur, Gestus, Register fragt → STILISTIC.

**STILISTIC_DEEPENING**: Vertiefung einer vorliegenden Stil-Analyse,
"Gehe tiefer in die Stil-Analyse", "Was bedeuten diese Stil-Befunde funktional?",
"Interpretiere die stilistischen Beobachtungen", "Autopsie der Stil-Befunde",
Jede Query, die eine VORLIEGENDE Stil-Analyse nicht nur zusammenfassen,
sondern FUNKTIONAL INTERPRETIEREN will — vom Befund zur Bedeutung,
von der Leiche zur Autopsie.
→ Braucht: Viele Belege + vorliegende Stil-Analyse, Balance
→ Parameter: retrieval_limit=30, rerank_threshold=0.5
ERKENNUNGSMERKMALE (mindestens eines muss zutreffen):
- Query enthält: "vertiefen", "deepening", "Autopsie", "funktional interpretieren",
  "was bedeuten diese Befunde", "über die Beobachtung hinaus", "tiefer gehen",
  "Zusammenhänge zwischen den Stil-Befunden"
- Query bezieht sich auf ERGEBNISSE einer vorherigen Stil-Analyse:
  "Was folgt aus diesen Beobachtungen?", "Welche Funktion hat dieser Stil?"
- Query fordert SYNTHese einzelner Beobachtungen zu einem funktionalen Gesamturteil
ABGRENZUNG zu STILISTIC:
STILISTIC beschreibt und vergleicht stilistische Merkmale (Befunde).
STILISTIC_DEEPENING interpretiert die Befunde funktional (Autopsie).
Faustregel: Liefert die Query bereits Stil-Befunde mit und fragt nach deren BEDEUTUNG? → DEEPENING.
Fragt sie nach den Befunden selbst? → STILISTIC.

**META_ANALYTICAL**: Der User fragt nach der METHODIK eines Analyse-Protokolls,
nach der Arbeitsweise oder den blinden Flecken eines ANALYSTEN.
Der User will wissen, WIE analysiert wird, nicht WAS analysiert wird.
→ Braucht: Breite Abdeckung des Protokolls, Fokus auf Methodik
→ Parameter: retrieval_limit=30, rerank_threshold=0.5
ERKENNUNGSMERKMALE (mindestens eines muss zutreffen):
- Query enthält: "Methodik", "Vorgehen", "Arbeitsweise", "Ansatz",
  "Herangehensweise", "Analysemethode", "methodisch"
- Query fragt nach dem Autor des Protokolls oder dem Analysten:
  "wie hat der Analyst...", "wie geht der Autor vor...",
  "mit welcher Methode..."
- Query zielt auf den Analyserahmen, nicht den Inhalt:
  "Wie ist diese Analyse aufgebaut?", "Was ist das für ein Verfahren?",
  "Welche Theorie steckt dahinter?"
ABGRENZUNG zu ANALYTICAL_FORENSIC:
ANALYTICAL_FORENSIC dekonstruiert einen TEXT oder DISKURS.
META_ANALYTICAL dekonstruiert eine ANALYSE oder ein PROTOKOLL.
Faustregel: Ist das Dokument selbst eine Analyse? → META_ANALYTICAL.

**STILISTIC_DEEPENING**: Der User hat eine vorliegende Stil-Analyse und
möchte die Befunde vertiefen — darüber hinausgehen, was die Analyse bereits
identifiziert hat. Die Analyse hat beschrieben, WIE die Texte sprechen;
der User will wissen, was die Sprache IN dieser Struktur TUT.
→ Braucht: Breite Abdeckung der Primärtexte + der vorliegenden Analyse
→ Parameter: retrieval_limit=40, rerank_threshold=0.4
ERKENNUNGSMERKMALE (mindestens eines muss zutreffen):
- Query erwähnt eine vorliegende Analyse/Stil-Analyse UND bittet um Vertiefung:
  "Die Stil-Analyse liegt vor — gehe weiter", "Vertiefe die Befunde",
  "Was hat die Analyse nicht gesehen?"
- Query enthält: "vertiefen", "deepening", "darüber hinaus", "weitergehen",
  "Befunde vertiefen", "was noch nicht gesehen", "was fehlt",
  "Strukturbefunde vertiefen"
- Query nimmt Stil-Befunde als Ausgangspunkt, nicht als Ziel:
  "Die Analyse hat X beschrieben — was passiert DARIN?",
  "Was tun die Texte MIT den Mitteln, die die Analyse benennt?"
ABGRENZUNG zu STILISTIC:
STILISTIC beschreibt Strukturen erstmalig (keine vorliegende Analyse).
STILISTIC_DEEPENING nimmt vorliegende Befunde und geht darüber hinaus.
Wenn noch keine Analyse vorliegt → STILISTIC.
Wenn eine Analyse vorliegt und vertieft werden soll → STILISTIC_DEEPENING.
ABGRENZUNG zu LITERARY:
LITERARY deutet die Bedeutung von Texten (Sinn, Tradition, Verstehen).
STILISTIC_DEEPENING vertieft Strukturbefunde — es bleibt beim WIE,
fragt aber, was die Sprache IN der Struktur tut.
Wenn die Frage nach Bedeutung/Sinn fragt → LITERARY.
Wenn die Frage Befunde vertiefen will → STILISTIC_DEEPENING.
ABGRENZUNG zu META_ANALYTICAL:
META_ANALYTICAL analysiert die METHODIK eines Analysten.
STILISTIC_DEEPENING nutzt vorliegende Befunde als Ausgangspunkt
für eine tiefergehende Analyse der Primärtexte.
Wenn die Frage die Methode kritisiert → META_ANALYTICAL.
Wenn die Frage die Befunde vertieft → STILISTIC_DEEPENING.

OUTPUT (JSON):
{{
    "intent": "FACTUAL" | "LITERARY" | "ANALYTICAL" | "ANALYTICAL_FORENSIC" | "STILISTIC" | "STILISTIC_DEEPENING" | "META_ANALYTICAL",
    "retrieval_limit": int,
    "rerank_threshold": float,
    "reasoning": "Kurze Begründung (1 Satz)"
}}

WICHTIG:
- Antworte NUR mit dem JSON-Objekt, ohne Markdown-Backticks oder Präambel!
- Wähle EINE Kategorie (die dominante)
"""

        fallback = {
            "intent": "FACTUAL",
            "retrieval_limit": 20,
            "rerank_threshold": 0.65,
            "reasoning": "Router Error - Fallback zu sicheren Defaults",
        }

        try:
            result = llm_call_json(prompt, task="router", fallback=fallback)

            # FIX v50.1: Handle Listen gracefully
            if isinstance(result, list):
                if len(result) > 0:
                    result = result[0]
                else:
                    raise ValueError("Empty JSON list returned by Router")

            # Validierung & Normalisierung
            intent_str = result.get("intent", "FACTUAL").upper()
            limit = result.get("retrieval_limit", 20)
            threshold = result.get("rerank_threshold", 0.65)
            reasoning = result.get("reasoning", "Default reasoning")

            # Sanity Checks
            if limit < 5 or limit > 100:
                logger.warning(
                    f"⚠️ Router gab unplausibles Limit: {limit}. Normalisiere auf 20."
                )
                limit = 20

            if threshold < 0.0 or threshold > 1.0:
                logger.warning(
                    f"⚠️ Router gab unplausible Threshold: {threshold}. Normalisiere auf 0.65."
                )
                threshold = 0.65

            logger.info(
                f"🧭 Router Decision: {intent_str} "
                f"(k={limit}, thresh={threshold:.2f}) - {reasoning}"
            )

            return {
                "intent": intent_str,
                "limit": limit,
                "threshold": threshold,
                "reasoning": reasoning,
            }

        except Exception as e:
            logger.error(f"❌ Router failed: {e}. Falling back to FACTUAL defaults.")
            return {
                "intent": "FACTUAL",
                "limit": 20,
                "threshold": 0.65,
                "reasoning": "Router Error - Fallback zu sicheren Defaults",
            }
