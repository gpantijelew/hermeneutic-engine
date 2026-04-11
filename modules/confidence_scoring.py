# modules/confidence_scoring.py - v51: Local Stack + Robustness Fixes
"""
Confidence Scoring - Relevanz-Bewertung für RAG-Ergebnisse.

Zweck:
- Berechnet Confidence-Scores (0–100) basierend auf Kosinus-Ähnlichkeit
  zwischen Query-Vektor und Dokument-Vektoren.
- Liefert normalisierte Scores zur Priorisierung von Retrieval-Ergebnissen.
"""

import numpy as np
import logging
from typing import List, Dict, Union

logger = logging.getLogger(__name__)


# Konstanten für Schwellwerte (zentral anpassbar)
MIN_SCORE_RANGE: float = 1e-2


def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """
    Berechnet die Kosinus-Ähnlichkeit zwischen zwei Vektoren.

    Args:
        vec_a: Erster Vektor (Query)
        vec_b: Zweiter Vektor (Dokument)

    Returns:
        Similarity-Score im Bereich [0, 1].
        - Theoretisch [-1, 1], hier auf [0, 1] clamp für Relevanz-Scoring.
        - Bei ungültigen Inputs oder Dimensionsmismatch: 0.0

    Mathematik:
        cos(θ) = (a · b) / (||a|| * ||b||)
    """
    # Typprüfung
    if not isinstance(vec_a, (list, np.ndarray)) or not isinstance(vec_b, (list, np.ndarray)):
        logger.warning(
            "cosine_similarity: Invalid input type. vec_a=%s, vec_b=%s",
            type(vec_a),
            type(vec_b)
        )
        return 0.0

    a = np.array(vec_a, dtype=float)
    b = np.array(vec_b, dtype=float)

    # Nicht-leer-Check
    if a.size == 0 or b.size == 0:
        logger.warning("cosine_similarity: Empty vector provided.")
        return 0.0

    # Dimensionsgleichheit
    if a.shape[0] != b.shape[0]:
        logger.warning(
            "cosine_similarity: Dimension mismatch. vec_a=%d, vec_b=%d",
            a.shape[0],
            b.shape[0]
        )
        return 0.0

    dot_product = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)

    # Zero-Division-Schutz
    if norm_a == 0 or norm_b == 0:
        logger.warning("cosine_similarity: Zero-norm vector detected.")
        return 0.0

    similarity = dot_product / (norm_a * norm_b)
    return float(max(0.0, min(1.0, similarity)))


def calculate_confidence_scores(
    query_vector: List[float],
    results: List[Dict]
) -> List[Dict]:
    """
    Fügt jedem Ergebnis einen 'confidence_score' (0–100) hinzu und sortiert die Liste.

    Args:
        query_vector: Embedding der User-Query als List[float].
        results: Liste von Retrieval-Ergebnissen (Dicts).
                 Jedes Dict muss ein Feld 'embedding' enthalten:
                   - Typ: list oder np.ndarray aus float/int
                   - Länge: identisch zu len(query_vector)

    Returns:
        Die Eingabe-Liste 'results' wird in-place modifiziert und sortiert zurückgegeben:
        - Jedes Element erhält '_raw_similarity' (float in [0, 1])
        - Jedes Element erhält 'confidence_score' (float in [0, 100])
        - Die Liste ist absteigend nach 'confidence_score' sortiert.

    Verhalten bei Edge-Cases:
        - Keine Ergebnisse: gibt leere Liste zurück.
        - Ungültige Embeddings oder Dimensionsmismatch: Score = 0.0 für dieses Ergebnis.
        - Sehr kleine Score-Spanne (<MIN_SCORE_RANGE): alle Scores auf 50.0 setzen.
    """
    if not results:
        logger.warning("No results for confidence scoring.")
        return []

    # PHASE 1: RAW SIMILARITY BERECHNUNG
    raw_scores: List[float] = []

    for res in results:
        doc_vector_raw = res.get("embedding")

        # Typ- und Formprüfung
        if not isinstance(doc_vector_raw, (list, np.ndarray)):
            logger.debug(
                "calculate_confidence_scores: Invalid embedding type. Expected list/ndarray, got %s",
                type(doc_vector_raw)
            )
            doc_vector = None
        else:
            try:
                doc_vector = np.array(doc_vector_raw, dtype=float)
            except Exception as e:
                logger.warning(
                    "calculate_confidence_scores: Failed to convert embedding to float array. %s",
                    e
                )
                doc_vector = None

        if doc_vector is not None and doc_vector.size == 0:
            logger.warning("calculate_confidence_scores: Empty embedding vector for result.")
            doc_vector = None

        # Dimensionsgleichheit zur Query
        query_len = len(query_vector)
        if doc_vector is not None and query_len > 0:
            if doc_vector.shape[0] != query_len:
                logger.warning(
                    "calculate_confidence_scores: Embedding dimension mismatch. query=%d, doc=%d",
                    query_len,
                    doc_vector.shape[0]
                )
                doc_vector = None

        # Similarity berechnen oder 0.0
        if doc_vector is not None and query_len > 0:
            similarity = cosine_similarity(query_vector, doc_vector.tolist())
            score = float(max(0.0, min(1.0, similarity)))
        else:
            score = 0.0

        raw_scores.append(score)
        res["_raw_similarity"] = score

    if not raw_scores:
        logger.error("calculate_confidence_scores: All embeddings invalid. No scores computed.")
        return results

    # PHASE 2: MIN-MAX-NORMALISIERUNG
    min_score = float(min(raw_scores))
    max_score = float(max(raw_scores))
    score_range = max_score - min_score

    logger.info(
        "Confidence scoring distribution: min=%.3f, max=%.3f, range=%.3f",
        min_score,
        max_score,
        score_range
    )

    if score_range < MIN_SCORE_RANGE:
        logger.warning(
            "Confidence scores nearly identical (range=%.4f). Using fallback score=50.0.",
            score_range
        )
        for res in results:
            res["confidence_score"] = 50.0
    else:
        for res in results:
            raw = float(res["_raw_similarity"])
            normalized = (raw - min_score) / score_range
            res["confidence_score"] = float(normalized * 100.0)

    # PHASE 3: SORTIERUNG (in-place)
    results.sort(key=lambda x: x["confidence_score"], reverse=True)

    logger.info(
        "Confidence scoring completed. Top=%.1f%%, Bottom=%.1f%%",
        results[0]["confidence_score"],
        results[-1]["confidence_score"]
    )

    return results


def get_color_for_confidence(score: float) -> str:
    """
    Gibt Streamlit-kompatiblen Farbcode zurück.

    Args:
        score: Confidence-Score (0–100)

    Returns:
        Farbname: "green", "orange" oder "red"

    Schwellenwerte:
        - ≥80%: Hochrelevant (grün)
        - 60–79%: Relevant (orange)
        - <60%: Niedrige Relevanz (rot)
    """
    if score >= 80:
        return "green"
    if score >= 60:
        return "orange"
    return "red"