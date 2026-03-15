# modules/hermeneutic_router.py
"""
Hermeneutic Router - Adaptive RAG-Strategie-Entscheidung.

PHILOSOPHIE:
Entscheidet VOR dem Retrieval über die Such-Parameter basierend auf Query-Intent.

TAXONOMIE (orthogonal zu QueryType aus query_classifier.py):
- FACTUAL: Präzise Fakten, Definitionen → Enge Suche, hohe Präzision
- LITERARY: Gedichte, Essays, Metaphern → Weite Suche, niedrige Schwelle
- ANALYTICAL: Vergleiche, Entwicklungen → Mittlere Suche, Balance

WICHTIG: Router-Intent und QueryType sind KOMPLEMENTÄR:
┌──────────────┬──────────┬───────────┬────────────┐
│              │ FACTUAL  │ LITERARY  │ ANALYTICAL │
├──────────────┼──────────┼───────────┼────────────┤
│ DISCOURSE    │    ✓     │     ✓     │     ✓      │
│ EXEGESIS     │    ✓     │     ✓     │     ✓      │
└──────────────┴──────────┴───────────┴────────────┘

Beispiel:
- "Vergleiche Heideggers frühe vs. späte Werke"
  → Router: ANALYTICAL (Vergleich braucht viele Belege)
  → Classifier: DISCOURSE (zwei "Sprecher": früh/spät)

- "Was ist Dasein?"
  → Router: FACTUAL (Definition braucht Präzision)
  → Classifier: EXEGESIS (Konzept-Erklärung, keine Diskursivität)

ÄNDERUNGSHISTORIE:
- v50.7: Migration auf neues google.genai SDK
- v50.6: Klarere Taxonomie-Dokumentation, orthogonale Beziehung zu QueryType
- v50: Initiale Version (Adaptive RAG)
"""

import logging
import json
import os
from google import genai
from enum import Enum
from typing import Dict, Any

from modules.config import MODEL_ROUTER

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
    """
    FACTUAL = "factual"
    LITERARY = "literary"
    ANALYTICAL = "analytical"
    ANALYTICAL_FORENSIC = "analytical_forensic"


class HermeneuticRouter:
    """
    Entscheidet VOR dem Retrieval über die Strategie.
    
    ROLLE IN DER PIPELINE:
    1. Router analysiert Query → FACTUAL/LITERARY/ANALYTICAL/ANALYTICAL_FORENSIC
    2. Retrieval mit adaptiven Parametern (limit, threshold)
    3. Query-Classifier analysiert Results → DISCOURSE/EXEGESIS
    4. Synthesis mit passendem Prompt (beide Infos kombiniert)
    """
    
    def __init__(self):
        """
        Initialisiert den Router mit neuem google.genai SDK.
        
        Raises:
            Loggt Fehler bei fehlender API-Key (aber wirft keine Exception,
            da Router-Failure nicht fatal sein soll → Fallback auf Defaults)
        """
        # Selbstständige Authentifizierung mit neuem SDK
        api_key = os.environ.get("GEMINI_API_KEY")
        
        if not api_key:
            logger.error(
                "❌ HermeneuticRouter: Kein GEMINI_API_KEY in Environment! "
                "Router wird auf Default-Parameter zurückfallen."
            )
            self.client = None
        else:
            try:
                self.client = genai.Client(api_key=api_key)
                logger.info("✅ HermeneuticRouter initialized successfully.")
            except Exception as e:
                logger.error(f"❌ HermeneuticRouter: Konnte Client nicht erstellen: {e}")
                self.client = None
    
    def route_query(self, query: str) -> Dict[str, Any]:
        """
        Analysiert die Query und gibt Retrieval-Parameter zurück.
        
        Args:
            query: User-Frage (natürlichsprachig)
        
        Returns:
            Dict mit:
            - intent (str): FACTUAL, LITERARY, ANALYTICAL, ANALYTICAL_FORENSIC
            - limit (int): Anzahl Chunks aus DB (15-40)
            - threshold (float): Reranker-Schwelle (0.45-0.75)
            - reasoning (str): Begründung der Entscheidung
        
        Bei Fehler: Fallback auf sichere Defaults
        
        Beispiel:
            >>> router = HermeneuticRouter()
            >>> result = router.route_query("Was ist Heideggers Dasein-Begriff?")
            >>> result
            {
                'intent': 'FACTUAL',
                'limit': 15,
                'threshold': 0.75,
                'reasoning': 'Definition gesucht, braucht Präzision'
            }
        """
        prompt = f"""
Du bist der Router für eine hermeneutische Suchmaschine.

USER QUERY: "{query}"

AUFGABE:
Klassifiziere die Intention und bestimme die Such-Parameter.

KATEGORIEN:

**FACTUAL**: Definitionen, Fakten, "Was ist X?", "Wann passierte Y?"
→ Braucht: Präzision, wenige hochrelevante Treffer
→ Parameter: retrieval_limit=15, rerank_threshold=0.75

**LITERARY**: Gedichte, Essays, Stil, Atmosphäre, "Ich"-Erzähler, Metaphorik
→ Braucht: Weiten Kontext, viele Nuancen
→ Parameter: retrieval_limit=40, rerank_threshold=0.45

**ANALYTICAL**: Vergleiche ("X vs. Y"), Entwicklungen ("von A nach B"), Diskurse
→ Braucht: Viele Belege für beide Seiten, Balance
→ Parameter: retrieval_limit=30, rerank_threshold=0.6

**ANALYTICAL_FORENSIC**: Dekonstruktion, Motivanalyse, Widersprüche aufdecken,
"Warum hat X seine Meinung geändert?", "Welche Interessen stecken hinter?",
"Was verschweigt der Text?", Selbstzeugnisse kritisch hinterfragen
→ Braucht: Viele Belege, breite Abdeckung für kritische Analyse
→ Parameter: retrieval_limit=35, rerank_threshold=0.45

OUTPUT (JSON):
{{
    "intent": "FACTUAL" | "LITERARY" | "ANALYTICAL" | "ANALYTICAL_FORENSIC",
    "retrieval_limit": int,
    "rerank_threshold": float,
    "reasoning": "Kurze Begründung (1 Satz)"
}}

WICHTIG:
- Antworte NUR mit dem JSON-Objekt, ohne Markdown-Backticks oder Präambel!
- Wähle EINE Kategorie (die dominante)
"""
        
        try:
            # Prüfe ob Client verfügbar
            if not self.client:
                raise Exception("Client nicht initialisiert")
            
            # Neues SDK: generate_content
            response = self.client.models.generate_content(
                model=MODEL_ROUTER,
                contents=prompt
            )
            
            # Extrahiere Text und bereinige
            result_text = response.text.strip()
            
            # Entferne mögliche Markdown-Backticks
            if result_text.startswith("```json"):
                result_text = result_text[7:]
            if result_text.startswith("```"):
                result_text = result_text[3:]
            if result_text.endswith("```"):
                result_text = result_text[:-3]
            
            result_text = result_text.strip()
            result = json.loads(result_text)
            
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
                logger.warning(f"⚠️ Router gab unplausibles Limit: {limit}. Normalisiere auf 20.")
                limit = 20
            
            if threshold < 0.0 or threshold > 1.0:
                logger.warning(f"⚠️ Router gab unplausible Threshold: {threshold}. Normalisiere auf 0.65.")
                threshold = 0.65
            
            logger.info(
                f"🧭 Router Decision: {intent_str} "
                f"(k={limit}, thresh={threshold:.2f}) - {reasoning}"
            )
            
            return {
                "intent": intent_str,
                "limit": limit,
                "threshold": threshold,
                "reasoning": reasoning
            }
        
        except Exception as e:
            logger.error(f"❌ Router failed: {e}. Falling back to FACTUAL defaults.")
            
            # Fallback: Konservative, sichere Parameter
            return {
                "intent": "FACTUAL",
                "limit": 20,
                "threshold": 0.65,
                "reasoning": "Router Error - Fallback zu sicheren Defaults"
            }