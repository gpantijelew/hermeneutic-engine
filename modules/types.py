# modules/types.py
"""
Domain-Typen für die Reconstruction Engine.

DESIGN-PHILOSOPHIE:
Diese Datei enthält NUR globale, domänen-spezifische Typen,
die von mehreren Modulen geteilt werden.

ABGRENZUNG:
- Technische Type-Hints (List, Dict, etc.) → bleiben in `typing`
- Modul-spezifische Enums (z.B. QueryIntent) → bleiben im jeweiligen Modul
- Datenklassen (z.B. ImbalanceInfo) → bleiben lokal, falls nur 1 Nutzer

RATIONALE:
`types.py` verhindert Circular Imports und dient als Single Source of Truth
für konzeptuelle Kategorien der Hermeneutik (z.B. DISCOURSE vs. EXEGESIS).

ÄNDERUNGSHISTORIE:
- v50.6: Dokumentation erweitert
- v48: EXEGESIS-Modus hinzugefügt
- v47: Initiale Version mit DISCOURSE
"""
from enum import Enum

class QueryType(Enum):
    """
    Fundamentale Modi der hermeneutischen Analyse.
    
    DISCOURSE: Dialektische Vielstimmigkeit (≥3 Sprecher, Vergleich)
    EXEGESIS: Konzeptuelle Auslegung (Erklärung, Definition)
    
    Diese Unterscheidung folgt Dilthey/Gadamer: Verstehen vs. Erklären.
    
    Verwendung:
        - query_classifier.py: Entscheidet basierend auf Query + Chunks
        - enforcer_config.py: Passt Validierungs-Regeln an Query-Typ an
    """
    DISCOURSE = "discourse"
    EXEGESIS = "exegesis"