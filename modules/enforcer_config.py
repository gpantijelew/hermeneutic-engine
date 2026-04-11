# modules/enforcer_config.py
"""
Konfiguration für den Hermeneutic Enforcer (Fakten-Validierung).

PHILOSOPHIE:
Die Validierungs-Regeln sind kontextsensitiv – sie passen sich an die
Art der Frage (DISCOURSE vs. EXEGESIS) und die Datenlage (Quellenanzahl) an.

DESIGN-PRINZIP:
Bei Exegese mit wenig Quellen ist Zitation ein optionaler Flow;
wichtiger ist die inhaltliche Korrektheit. Bei Discourse ist Zitation
essentiell für die Zuschreibung von Positionen.

ÄNDERUNGSHISTORIE:
- v50.6: Vollständige Dokumentation der Regel-Keys, min_citations-Rationale
- v47: Initiale Version mit DISCOURSE/EXEGESIS-Unterscheidung
"""

from .types import QueryType


def get_enforcer_rules(query_type: QueryType, source_count: int) -> dict:
    """
    Liefert die Validierungs-Regeln basierend auf Query-Typ und Datenlage.
    
    Args:
        query_type: DISCOURSE (dialektisch) oder EXEGESIS (konzeptuell)
        source_count: Anzahl der gefundenen Quellen (aus Retrieval)
    
    Returns:
        dict mit folgenden Validierungs-Regeln:
        
        **require_citations** (bool):
            Müssen Aussagen mit [1], [2] etc. belegt sein?
            - EXEGESIS: Nur bei >1 Quelle (sonst ist Zitation sinnlos)
            - DISCOURSE: Immer (für Positions-Zuschreibung essentiell)
        
        **min_citations** (int):
            Mindestanzahl an Zitationen in der gesamten Antwort.
            - EXEGESIS: 0 (Permissiv – Substanz > Zitations-Quantität)
            - DISCOURSE: 1 (Mind. eine Position muss zugeschrieben werden)
        
        **allow_discourse_markers** (bool):
            Sind Diskurs-Marker ("Dagegen spricht...", "Im Gegensatz dazu...") erlaubt?
            - EXEGESIS: Nein (keine erfundenen Debatten!)
            - DISCOURSE: Ja (erwünscht für Positions-Darstellung)
        
        **strict_temporal_check** (bool):
            Verbiete erfundene Zeitstempel, Versionen, Daten?
            - Beide Modi: Ja (universelle epistemologische Regel)
    
    Beispiele:
        >>> get_enforcer_rules(QueryType.EXEGESIS, source_count=1)
        {
            'require_citations': False,  # 1 Quelle → Zitation sinnlos
            'min_citations': 0,
            'allow_discourse_markers': False,
            'strict_temporal_check': True
        }
        
        >>> get_enforcer_rules(QueryType.DISCOURSE, source_count=5)
        {
            'require_citations': True,   # Positionen zuschreiben!
            'min_citations': 1,
            'allow_discourse_markers': True,  # "Claude sagt X, GPT sagt Y"
            'strict_temporal_check': True
        }
    """
    
    if query_type == QueryType.EXEGESIS:
        return {
            # ZITATION BEI EXEGESIS:
            # - Bei 1 Quelle: Unnötig (wo soll man zitieren? Es gibt nur eine Stimme)
            # - Bei 2+ Quellen: Sinnvoll (für Transparenz, welche Quelle was sagt)
            "require_citations": source_count > 1,
            
            # PERMISSIVE MIN-CITATIONS:
            # Rationale: Bei Exegese ist die *inhaltliche Korrektheit* wichtiger
            # als die *Zitations-Quantität*. Eine substanzielle Erklärung mit
            # nur 1 Zitat ist besser als oberflächliches Zitieren ohne Interpretation.
            "min_citations": 0,
            
            # DISKURS-MARKER VERBOTEN:
            # Verhindert: "Dagegen spricht...", "Im Gegensatz dazu..." ohne echten Diskurs.
            # Der Enforcer soll solche Formulierungen als Fehler markieren, wenn
            # sie nicht durch mehrere widersprüchliche Quellen gedeckt sind.
            "allow_discourse_markers": False,
            
            # TEMPORAL CHECK (UNIVERSELL):
            # Erfundene Zeitstempel ("Version 2.5 vom März 2024...") sind
            # unabhängig vom Query-Typ epistemologisch inakzeptabel.
            "strict_temporal_check": True
        }
    
    else:  # QueryType.DISCOURSE
        return {
            # ZITATION BEI DISCOURSE:
            # Essentiell! Ohne Zitation sind Positions-Zuschreibungen unmöglich.
            # "Claude bevorzugt X" ist nutzlos ohne [1] als Beleg.
            "require_citations": True,
            
            # MINDESTENS 1 ZITAT:
            # Eine diskursive Antwort ohne jegliche Zitation ist wertlos.
            # Wir erwarten mind. *eine* Position, die belegt ist.
            "min_citations": 1,
            
            # DISKURS-MARKER ERLAUBT:
            # "Dagegen argumentiert...", "Im Gegensatz dazu..." sind hier
            # erwünscht und notwendig für die Darstellung von Positionen.
            "allow_discourse_markers": True,
            
            # TEMPORAL CHECK (UNIVERSELL):
            "strict_temporal_check": True
        }


# TODO v51: Erwäge zusätzliche Regel-Keys für feinere Kontrolle:
# - "max_quote_length": int (verhindert wortwörtliche Langzitate)
# - "require_speaker_attribution": bool (erzwinge "Laut Claude..." statt nur [1])
# - "allow_interpretation": bool (bei DISCOURSE: Darf Synthese eigene Schlüsse ziehen?)