# modules/confidence_scoring.py - v50.7: AUDIT-FIX (Feldname + Normalisierung)
"""
Confidence Scoring - Relevanz-Bewertung für RAG-Ergebnisse.

PHILOSOPHIE:
Berechnet Confidence-Scores (0-100%) basierend auf Kosinus-Ähnlichkeit
zwischen Query-Vektor und Dokument-Vektoren.

NEU v50.7 (AUDIT-FIXES):
1. Feldname-Korrektur: 'embedding' statt 'embedding_vector' (Firestore-kompatibel)
2. Min-Max-Normalisierung: Maximiert Differenzierung auch bei engen Score-Bereichen
3. Robustes Handling von Firestore Vector-Objekten
4. Diagnostik-Logging für Score-Verteilung

ÄNDERUNGSHISTORIE:
- v50.7: Vollständige Überarbeitung (Audit-Fixes)
- v47: Initiale Version
"""

import numpy as np
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """
    Berechnet die Kosinus-Ähnlichkeit zwischen zwei Vektoren (0.0 bis 1.0).
    
    Args:
        vec_a: Erster Vektor (Query)
        vec_b: Zweiter Vektor (Dokument)
    
    Returns:
        Similarity-Score zwischen 0.0 (orthogonal) und 1.0 (identisch)
        Bei ungültigen Inputs: 0.0
    
    Mathematik:
        cos(θ) = (a · b) / (||a|| * ||b||)
    """
    if not vec_a or not vec_b:
        return 0.0
    
    a = np.array(vec_a)
    b = np.array(vec_b)
    
    dot_product = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    
    # Zero-Division-Schutz
    if norm_a == 0 or norm_b == 0:
        return 0.0
    
    return float(dot_product / (norm_a * norm_b))


def calculate_confidence_scores(
    query_vector: List[float], 
    results: List[Dict]
) -> List[Dict]:
    """
    Fügt jedem Ergebnis einen 'confidence_score' (0-100) hinzu.
    
    NEU v50.7: Min-Max-Normalisierung für bessere Differenzierung.
    
    Args:
        query_vector: Embedding der User-Query
        results: Liste von Retrieval-Ergebnissen (Dicts)
                 Erwartet: 'embedding' (Firestore-Feld!)
    
    Returns:
        Sortierte Liste (höchster Score zuerst) mit neuem Feld:
        - 'confidence_score': Normalisierter Score (0-100)
        - '_raw_similarity': Original Kosinus-Ähnlichkeit (für Debugging)
    
    Normalisierungs-Strategie:
        1. Alle Scores liegen eng beieinander (z.B. 0.65-0.75)?
           → Min-Max-Normalisierung spreizt sie auf 0-100
        2. Alle Scores quasi identisch (<0.01 Varianz)?
           → Fallback auf 50.0 (keine Differenzierung möglich)
        3. Kein valider Vektor?
           → Score = 0.0
    
    Beispiel:
        Vor Normalisierung: [0.75, 0.70, 0.65]
        Nach Normalisierung: [100.0, 50.0, 0.0]
        → Chunk mit 0.75 ist nun klar als "bester" erkennbar
    """
    if not results:
        logger.warning("⚠️ Keine Ergebnisse für Confidence-Scoring erhalten.")
        return []
    
    # ========================================
    # PHASE 1: RAW SIMILARITY BERECHNUNG
    # ========================================
    raw_scores = []
    
    for res in results:
        # FIX v50.7: Firestore speichert als 'embedding', nicht 'embedding_vector'!
        doc_vector = res.get('embedding')
        
        # Firestore Vector-Objekt → List konvertieren
        if doc_vector and hasattr(doc_vector, '__iter__'):
            try:
                # Firestore Vector kann als Iterable fungieren
                doc_vector = list(doc_vector)
            except (TypeError, ValueError) as e:
                logger.warning(f"⚠️ Konnte Embedding nicht konvertieren: {e}")
                doc_vector = None
        
        # Berechne Similarity
        if doc_vector and query_vector:
            similarity = cosine_similarity(query_vector, doc_vector)
            score = max(0.0, similarity)  # Clamp auf [0, 1]
        else:
            score = 0.0
        
        raw_scores.append(score)
        res['_raw_similarity'] = score
    
    # ========================================
    # PHASE 2: MIN-MAX-NORMALISIERUNG
    # ========================================
    if not raw_scores:
        logger.error("❌ Alle Embeddings waren ungültig. Keine Scores berechnet.")
        return results
    
    min_score = min(raw_scores)
    max_score = max(raw_scores)
    score_range = max_score - min_score
    
    logger.info(
        f"📊 Score-Verteilung: "
        f"Min={min_score:.3f}, Max={max_score:.3f}, Range={score_range:.3f}"
    )
    
    # Fallback: Alle Scores quasi identisch?
    if score_range < 0.01:
        logger.warning(
            "⚠️ Alle Scores sind nahezu identisch (<0.01 Varianz). "
            "Keine sinnvolle Differenzierung möglich. Fallback auf 50.0."
        )
        for res in results:
            res['confidence_score'] = 50.0
    else:
        # Normalisierung: [min_score, max_score] → [0, 100]
        for res in results:
            raw = res['_raw_similarity']
            normalized = (raw - min_score) / score_range
            res['confidence_score'] = normalized * 100
    
    # ========================================
    # PHASE 3: SORTIERUNG
    # ========================================
    results.sort(key=lambda x: x['confidence_score'], reverse=True)
    
    logger.info(
        f"✅ Confidence-Scoring abgeschlossen. "
        f"Top-Score: {results[0]['confidence_score']:.1f}%, "
        f"Bottom-Score: {results[-1]['confidence_score']:.1f}%"
    )
    
    return results


# ========================================
# UTILITY: COLOR MAPPING (für UI)
# ========================================
def get_color_for_confidence(score: float) -> str:
    """
    Gibt Streamlit-kompatiblen Farbcode zurück.
    
    Args:
        score: Confidence-Score (0-100)
    
    Returns:
        Farbname: "green", "orange", oder "red"
    
    Verwendung in Streamlit:
        st.markdown(f":{get_color_for_confidence(score)}[Score: {score:.1f}%]")
    
    Schwellenwerte:
        - ≥80%: Hochrelevant (grün)
        - 60-79%: Relevant (orange)
        - <60%: Niedrige Relevanz (rot)
    """
    if score >= 80:
        return "green"
    if score >= 60:
        return "orange"
    return "red"