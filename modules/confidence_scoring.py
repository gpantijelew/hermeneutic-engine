# modules/confidence_scoring.py
import numpy as np
from typing import List, Dict

def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """Berechnet die Kosinus-Ähnlichkeit zwischen zwei Vektoren (0.0 bis 1.0)."""
    if not vec_a or not vec_b: return 0.0

    a = np.array(vec_a)
    b = np.array(vec_b)

    dot_product = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)

    if norm_a == 0 or norm_b == 0: return 0.0

    return dot_product / (norm_a * norm_b)

def calculate_confidence_scores(query_vector: List[float], results: List[Dict]) -> List[Dict]:
    """
    Fügt jedem Ergebnis einen 'confidence_score' (0-100) hinzu.
    """
    scored_results = []

    for res in results:
        doc_vector = res.get('embedding_vector') # Wir müssen sicherstellen, dass wir den Vektor haben

        if doc_vector and query_vector:
            similarity = cosine_similarity(query_vector, doc_vector)
            # Normalisieren: Cosine ist -1 bis 1, aber bei Text Embeddings meist 0 bis 1.
            # Wir machen daraus Prozent.
            score = max(0.0, similarity) * 100
        else:
            score = 0.0

        res['confidence_score'] = score
        scored_results.append(res)

    # Sortieren nach Score (höchster zuerst)
    scored_results.sort(key=lambda x: x['confidence_score'], reverse=True)
    return scored_results

def get_color_for_score(score: float) -> str:
    if score >= 85: return "green"
    if score >= 70: return "orange"
    return "red"