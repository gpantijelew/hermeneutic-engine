import re
from typing import List, Dict, Any
from .types import QueryType

class QueryClassifier:
    """
    Entscheidet, ob eine Anfrage diskursiv (Vergleich) oder exegetisch (Erklärung) 
    behandelt werden soll.
    """

    # Regex-Patterns für Intention
    DISCOURSE_PATTERNS = [
        r"vergleich", r"unterschied", r"diskutiere", r"positionen", 
        r"konsens", r"divergenz", r"gegenüberstellung", r"vs\.", 
        r"anders als", r"gemeinsamkeit"
    ]

    EXEGESIS_PATTERNS = [
        r"was ist", r"was wäre", r"erkläre", r"wie funktioniert", 
        r"warum", r"bedeutung", r"definier", r"hintergrund", 
        r"analyse", r"interpretier"
    ]

    def classify(self, query: str, chunks: List[Dict[str, Any]]) -> QueryType:
        """
        Klassifiziert die Query basierend auf Text und gefundenen Chunks.

        Args:
            query: Die User-Frage.
            chunks: Liste der reranked Chunks (muss 'metadata' mit 'speaker' enthalten).
        """
        query_lower = query.lower()

        # 1. Analyse der Speaker-Dichte
        speakers = set()
        for chunk in chunks:
            meta = chunk.get("metadata", {})
            # Fallback auf 'model_name' oder 'speaker'
            spk = meta.get("speaker") or meta.get("model_name")
            if spk:
                speakers.add(spk)

        unique_speaker_count = len(speakers)

        # 2. Keyword-Matching
        has_discourse_kw = any(re.search(p, query_lower) for p in self.DISCOURSE_PATTERNS)
        has_exegesis_kw = any(re.search(p, query_lower) for p in self.EXEGESIS_PATTERNS)

        # 3. Entscheidungs-Logik (Decision Matrix)

        # Fall A: Explizite Vergleichsfrage -> IMMER Discourse
        if has_discourse_kw:
            return QueryType.DISCOURSE

        # Fall B: Explizite Erklärfrage -> Eher Exegesis, außer extrem viele Speaker
        if has_exegesis_kw:
            # Selbst wenn wir 5 Speaker haben: Wenn der User fragt "Was ist X?", 
            # will er eine Definition, keine Debatte.
            return QueryType.EXEGESIS

        # Fall C: Implizit durch Datenlage (Heuristik aus Briefing)
        if unique_speaker_count >= 3:
            return QueryType.DISCOURSE

        # Fall D: Wenig Speaker -> Exegesis
        if unique_speaker_count <= 2:
            return QueryType.EXEGESIS

        # Fall E: Fallback (Sicherheit first)
        return QueryType.EXEGESIS