import logging
import json
import os
import google.generativeai as genai
from enum import Enum
from typing import Dict, Any
from modules.config import MODEL_ROUTER

logger = logging.getLogger(__name__)

class QueryIntent(Enum):
    FACTUAL = "factual"       # Präzise Fakten, Definitionen
    LITERARY = "literary"     # Gedichte, Essays, Metaphern
    ANALYTICAL = "analytical" # Vergleiche, Entwicklungen

class HermeneuticRouter:
    """
    Entscheidet VOR dem Retrieval über die Strategie.
    Ziel: Adaptive RAG (v50).
    """
    def __init__(self):
        # --- FIX: Selbstständige Authentifizierung ---
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            logger.error("❌ HermeneuticRouter: Kein GEMINI_API_KEY in den Environment-Variables gefunden!")
        else:
            try:
                genai.configure(api_key=api_key)
            except Exception as e:
                logger.error(f"❌ HermeneuticRouter: Konnte genai nicht konfigurieren: {e}")

        self.model = genai.GenerativeModel(
            model_name=MODEL_ROUTER,
            generation_config={"response_mime_type": "application/json"}
        )

    def route_query(self, query: str) -> Dict[str, Any]:
        """
        Analysiert die Query und gibt Retrieval-Parameter zurück.
        """
        prompt = f"""
        Du bist der Router für eine hermeneutische Suchmaschine.

        USER QUERY: "{query}"

        AUFGABE:
        Klassifiziere die Intention und bestimme die Such-Parameter.

        KATEGORIEN:
        - FACTUAL: Was ist X? Wann passierte Y? (Braucht Präzision)
        - LITERARY: Gedichte, Essays, Stil, Atmosphäre, "Ich"-Erzähler. (Braucht weiten Kontext)
        - ANALYTICAL: Vergleiche X mit Y. Entwicklung von A nach B. (Braucht viele Belege)

        OUTPUT (JSON):
        {{
            "intent": "FACTUAL" | "LITERARY" | "ANALYTICAL",
            "retrieval_limit": int,  // Wie viele Chunks sollen aus der DB geholt werden? (Factual: ~15, Literary: ~40, Analytical: ~30)
            "rerank_threshold": float, // Wie streng soll der Reranker sein? (0.0-1.0). (Factual: 0.75, Literary: 0.45, Analytical: 0.6)
            "reasoning": "Kurze Begründung"
        }}
        """

        try:
            response = self.model.generate_content(prompt)
            result = json.loads(response.text)

            # --- FIX v50.1: Handle Lists gracefully ---
            if isinstance(result, list):
                if len(result) > 0:
                    result = result[0]
                else:
                    raise ValueError("Empty JSON list returned")
            # ------------------------------------------

            # Fallback/Validierung
            intent_str = result.get("intent", "FACTUAL").upper()
            limit = result.get("retrieval_limit", 20)
            threshold = result.get("rerank_threshold", 0.6)

            logger.info(f"🧭 Router Decision: {intent_str} (k={limit}, thresh={threshold}) - {result.get('reasoning')}")

            return {
                "intent": intent_str,
                "limit": limit,
                "threshold": threshold
            }

        except Exception as e:
            logger.error(f"Router failed: {e}. Falling back to default.")
            return {
                "intent": "FACTUAL",
                "limit": 20,
                "threshold": 0.65
            }