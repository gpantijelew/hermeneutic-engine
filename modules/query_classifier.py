# modules/query_classifier.py
"""
Hermeneutischer Query-Classifier für die Reconstruction Engine.

PHILOSOPHIE:
Unterscheidet zwischen zwei fundamentalen Fragemodi:
- DISCOURSE: Dialektische Vielstimmigkeit (Was sagen verschiedene Perspektiven?)
- EXEGESIS: Konzeptuelle Auslegung (Was bedeutet dieses Konzept?)

Diese Unterscheidung folgt der hermeneutischen Tradition (Dilthey, Gadamer):
Verstehen vs. Erklären als zwei Modi des Weltzugangs.

ÄNDERUNGSHISTORIE:
- v50.6: Verbesserte Dokumentation, epistemologische Begründungen
- v47: Initiale Version mit Pattern-Matching + Speaker-Density
"""

import re
from typing import List, Dict, Any
from .types import QueryType


class QueryClassifier:
    """
    Entscheidet, ob eine Anfrage diskursiv (Vergleich) oder exegetisch (Erklärung)
    behandelt werden soll.

    ENTSCHEIDUNGS-LOGIK:
    1. Explizite Keywords (User-Intention hat Vorrang)
    2. Speaker-Density aus Daten (implizite Diskursivität)
    3. Konservativer Fallback (EXEGESIS als sicherer Default)
    """

    # ========================================
    # PATTERN-DEFINITIONEN
    # ========================================
    # TODO v51: Externalisiere als JSON-Config für leichtere Wartbarkeit

    DISCOURSE_PATTERNS = [
        # Explizite Vergleichswörter
        r"vergleich",
        r"unterschied",
        r"gegenüberstellung",
        r"vs\.",
        r"versus",
        r"anders als",
        # Diskurs-Marker
        r"diskutiere",
        r"positionen",
        r"meinungen",
        r"konsens",
        r"divergenz",
        r"kontroverse",
        # Kollektive Pluralformen
        r"wie sehen.*modelle",
        r"was sagen.*systeme",
    ]

    EXEGESIS_PATTERNS = [
        # Konzept-Fragen
        r"was ist",
        r"was bedeutet",
        r"was wäre",
        r"definier",
        r"bedeutung von",
        # Erklär-Marker
        r"erkläre",
        r"erläutere",
        r"wie funktioniert",
        r"warum",
        r"wieso",
        r"weshalb",
        # Analyse-Marker
        r"analyse",
        r"interpretier",
        r"hintergrund",
        r"kontext",
        r"einordnung",
    ]

    def classify(self, query: str, chunks: List[Dict[str, Any]]) -> QueryType:
        """
        Klassifiziert die Query basierend auf Text und gefundenen Chunks.

        Args:
            query: Die User-Frage (natürlichsprachig)
            chunks: Liste der reranked Chunks mit Metadata
                    Erwartet: 'metadata' mit 'speaker' oder 'model_name'

        Returns:
            QueryType.DISCOURSE oder QueryType.EXEGESIS

        Entscheidungs-Matrix:
            A) Explizite Vergleichsfrage → DISCOURSE (trumps everything)
            B) Explizite Erklärfrage → EXEGESIS (auch bei vielen Sprechern)
            C) Viele Sprecher (≥3) → DISCOURSE (implizite Diskursivität)
            D) Wenige Sprecher (≤2) → EXEGESIS (kein echter Diskurs möglich)
            E) Fallback → EXEGESIS (epistemologisch konservativ)
        """
        query_lower = query.lower()

        # ========================================
        # 1. SPEAKER-DENSITY ANALYSE
        # ========================================
        speakers = set()
        for chunk in chunks:
            meta = chunk.get("metadata", {})
            # Fallback-Chain: speaker → model_name → None
            spk = meta.get("speaker") or meta.get("model_name")
            if spk:
                speakers.add(spk)

        unique_speaker_count = len(speakers)

        # ========================================
        # 2. KEYWORD-MATCHING
        # ========================================
        has_discourse_kw = any(
            re.search(pattern, query_lower) for pattern in self.DISCOURSE_PATTERNS
        )

        has_exegesis_kw = any(
            re.search(pattern, query_lower) for pattern in self.EXEGESIS_PATTERNS
        )

        # ========================================
        # 3. ENTSCHEIDUNGS-LOGIK
        # ========================================

        # Fall A: Explizite Vergleichsfrage → IMMER Discourse
        # Rationale: User-Intention trumps Datenlage
        if has_discourse_kw:
            return QueryType.DISCOURSE

        # Fall B: Explizite Erklärfrage → IMMER Exegesis
        # Rationale: Selbst bei vielen Sprechern – wenn User "Was ist X?" fragt,
        # will er eine Definition, keine Debatte.
        if has_exegesis_kw:
            return QueryType.EXEGESIS

        # Fall C: Implizit durch Datenlage – viele Sprecher
        # Rationale: ≥3 Sprecher implizieren eine diskursive Landschaft,
        # auch wenn der User nicht explizit nach Vergleich fragt.
        if unique_speaker_count >= 3:
            return QueryType.DISCOURSE

        # Fall D: Wenig Sprecher → Exegesis
        # Rationale: Bei ≤2 Sprechern ist kein echter Diskurs möglich,
        # die Antwort sollte die vorhandenen Stimmen synthetisieren, nicht vergleichen.
        if unique_speaker_count <= 2:
            return QueryType.EXEGESIS

        # Fall E: Fallback (Sicherheit first)
        # Rationale: EXEGESIS ist epistemologisch konservativer als DISCOURSE.
        # Risiken:
        # - DISCOURSE als Default → könnte nicht-existente Debatten halluzinieren
        # - EXEGESIS als Default → könnte nuancierte Unterschiede übersehen
        # Wir wählen das kleinere Übel: Lieber eine Erklärung ohne Diskurs-Marker
        # als ein erfundener Vergleich ohne Substanz.
        return QueryType.EXEGESIS
