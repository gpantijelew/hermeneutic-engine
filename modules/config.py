# modules/config.py
"""
Zentrale Konfiguration für die Hermeneutic Reconstruction Engine v49+.

PHILOSOPHIE:
- **Pro (2.5/3.0):** Für kritische hermeneutische Aufgaben (Synthesis, Validation)
- **Flash (2.0):** Für schnelle, weniger kritische Aufgaben (Labeling, Cleanup)
- **Flash-Lite:** Für Batch-Prozesse mit vielen Items (Bulk Operations)

ÄNDERUNGSHISTORIE:
- v49: Erstellt als zentrale Model-Registry
- v50: (Zukünftig) Könnte dynamische Model-Auswahl via UI enthalten
"""

import os
import sys
from pathlib import Path
from typing import Dict

# Lade .env für lokale Entwicklung (optional, in Production nicht nötig)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv ist optional

# ==============================================================================
# PROJEKT-ROOT BESTIMMUNG (Für absolute Pfade)
# ==============================================================================

if hasattr(sys, '_MEIPASS'):  # Falls als exe kompiliert (PyInstaller)
    PROJECT_ROOT = Path(sys._MEIPASS)
else:
    # modules/config.py → zwei Ebenen hoch = Projekt-Root
    PROJECT_ROOT = Path(__file__).parent.parent

# ==============================================================================
# PRIMARY MODELS (Kritische hermeneutische Aufgaben)
# ==============================================================================

# Chat-Interface (Gemini 3 für neueste Features)
MODEL_CHAT_API = os.getenv("CHAT_MODEL", "gemini-3-pro-preview")

# RAG Answer Generation (Hermeneutische Synthese)
MODEL_SYNTHESIS = "gemini-2.5-pro"

# Fact Validation (Enforcer - muss präzise sein!)
# Empirische Begründung: Flash war "zu dumm" für Hermeneutik (Grigori, Dez 2025)
MODEL_ENFORCER = "gemini-2.5-pro"

# Atomic Fact Extraction (Qualitätssicherung am Pipeline-Anfang)
# Rationale: Hochwertige Fakten → weniger False Positives im Enforcer
MODEL_FACT_EXTRACTION = "gemini-2.5-pro"

# ==============================================================================
# SECONDARY MODELS (Speed-optimiert für weniger kritische Aufgaben)
# ==============================================================================

# Query Expansion (Multilingual Keyword Generation für BM25)
# Rationale: Kritisch für RRF-Erfolg, aber Flash reicht für Keyword-Gen
MODEL_QUERY_EXPANSION = "gemini-2.0-flash-001"

# NEU v50: Hermeneutic Router (Adaptive RAG)
# Muss extrem schnell sein, entscheidet über Retrieval-Strategie
MODEL_ROUTER = "gemini-2.0-flash-lite-001"

# Relevance Scoring (Reranker - viele Chunks, Speed wichtig)
MODEL_RERANKER = "gemini-2.0-flash-lite-001"

# ==============================================================================
# TERTIARY MODELS (Batch & Cleanup-Tasks)
# ==============================================================================

# Bulk Metadata Labeling (KI-Vorschläge für Admin-UI)
MODEL_BULK_LABELING = "gemini-2.0-flash-lite-001"

# Chat Title Generation (Kosmetisch, nicht kritisch)
MODEL_TITLE_GEN = "gemini-2.0-flash-lite-001"

# Question → Statement Conversion (Synthesis Post-Processing)
MODEL_QUESTION_CONV = "gemini-2.0-flash-lite-001"

# ==============================================================================
# SERVICE ACCOUNT & CREDENTIALS
# ==============================================================================

# Service Account Key Path (Absoluter Pfad!)
SERVICE_ACCOUNT_KEY_PATH = os.getenv(
    "GOOGLE_APPLICATION_CREDENTIALS",
    str(PROJECT_ROOT / ".secrets" / "comparative-studies-ai-models-1bf59eb77077.json")
)

# ==============================================================================
# EMBEDDING MODEL (Konstant für v49)
# ==============================================================================

EMBEDDING_MODEL = "models/text-embedding-004"
EMBEDDING_DIMENSIONS = 768

# ==============================================================================
# HELPER FUNCTION (Optional - für dynamische Model-Auswahl in v50+)
# ==============================================================================

def get_model_for_task(task: str) -> str:
    """
    Gibt das konfigurierte Model für eine spezifische Aufgabe zurück.
    
    Args:
        task: Eine der definierten Task-Keys (z.B. 'synthesis', 'enforcer')
    
    Returns:
        Model-Name als String
    
    Raises:
        ValueError: Wenn task unbekannt ist
    """
    MODEL_REGISTRY: Dict[str, str] = {
        'chat': MODEL_CHAT_API,
        'synthesis': MODEL_SYNTHESIS,
        'enforcer': MODEL_ENFORCER,
        'fact_extraction': MODEL_FACT_EXTRACTION,
        'query_expansion': MODEL_QUERY_EXPANSION,
        'router': MODEL_ROUTER, # <--- NEU
        'reranker': MODEL_RERANKER,
        'bulk_labeling': MODEL_BULK_LABELING,
        'title_gen': MODEL_TITLE_GEN,
        'question_conv': MODEL_QUESTION_CONV,
    }
    
    if task not in MODEL_REGISTRY:
        raise ValueError(f"Unbekannter Task: '{task}'. Erlaubte Tasks: {list(MODEL_REGISTRY.keys())}")
    
    return MODEL_REGISTRY[task]

# ==============================================================================
# CONFIGURATION VALIDATION (Für Tests)
# ==============================================================================

def validate_config() -> bool:
    """
    Prüft, ob alle Models valide sind und API-Key verfügbar ist.
    Nützlich für Startup-Tests.
    """
    import google.generativeai as genai
    
    all_valid = True
    
    # API Key Check
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        print("⚠️ WARNUNG: GEMINI_API_KEY nicht gesetzt!")
        print("   Lösung: Erstelle .env mit: GEMINI_API_KEY=dein-key")
        all_valid = False
    else:
        print(f"✅ GEMINI_API_KEY gefunden (Länge: {len(api_key)} Zeichen)")
    
    # Service Account Check
    if not os.path.exists(SERVICE_ACCOUNT_KEY_PATH):
        print(f"❌ FEHLER: Service Account Key nicht gefunden!")
        print(f"   Gesucht: {SERVICE_ACCOUNT_KEY_PATH}")
        print(f"   Lösung: Verschiebe die Key-Datei nach .secrets/")
        all_valid = False
    else:
        print(f"✅ Service Account Key gefunden: {SERVICE_ACCOUNT_KEY_PATH}")
    
    if all_valid:
        print("\n✅ Konfiguration vollständig valide!")
    else:
        print("\n⚠️ Konfiguration hat Probleme (siehe oben).")
    
    return all_valid

# ==============================================================================
# USAGE EXAMPLE (Für Entwickler)
# ==============================================================================

if __name__ == "__main__":
    # Test der Config
    print("=== HERMENEUTIC ENGINE CONFIG v49 ===")
    print(f"Projekt-Root: {PROJECT_ROOT}")
    print(f"Chat Model: {MODEL_CHAT_API}")
    print(f"Synthesis Model: {MODEL_SYNTHESIS}")
    print(f"Enforcer Model: {MODEL_ENFORCER}")
    print(f"Service Account: {SERVICE_ACCOUNT_KEY_PATH}")
    print("\nValidierung...")
    validate_config()