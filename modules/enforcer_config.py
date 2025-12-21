from .types import QueryType

def get_enforcer_rules(query_type: QueryType, source_count: int) -> dict:
    """
    Liefert die Validierungs-Regeln basierend auf dem Modus.
    """
    if query_type == QueryType.EXEGESIS:
        return {
            # Bei Exegese mit wenig Quellen ist Zitation optionaler Flow, 
            # wichtiger ist inhaltliche Korrektheit.
            "require_citations": True if source_count > 1 else False,
            "min_citations": 0,
            "allow_discourse_markers": False, # Keine "Dagegen spricht..." ohne Grund
            "strict_temporal_check": True     # Keine erfundenen Daten!
        }

    else: # DISCOURSE (v47 Standard)
        return {
            "require_citations": True,
            "min_citations": 1,
            "allow_discourse_markers": True,
            "strict_temporal_check": True
        }