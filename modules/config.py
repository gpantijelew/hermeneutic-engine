# modules/config.py
"""
Zentrale Konfiguration für die Hermeneutic Reconstruction Engine v50.9+.

PHILOSOPHIE:
- Vollständig lokal: LM Studio (LLM) + sentence-transformers (Embeddings)
- Keine Cloud-Abhängigkeit, kein API-Key erforderlich
- LLM_BACKEND-Schalter ermöglicht späteren Drop-in zu Claude API

ÄNDERUNGSHISTORIE:
- v50.9: Migration von Gemini/Firestore → LM Studio/ChromaDB/SQLite
- v49:   Erstellt als zentrale Model-Registry
"""

import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Dict

# Lade .env für lokale Entwicklung (optional)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ==============================================================================
# PROJEKT-ROOT BESTIMMUNG
# ==============================================================================
if hasattr(sys, '_MEIPASS'):
    PROJECT_ROOT = Path(sys._MEIPASS)
else:
    PROJECT_ROOT = Path(__file__).parent.parent

# ==============================================================================
# LOKALE INFRASTRUKTUR-PFADE
# ==============================================================================
DATA_DIR = PROJECT_ROOT / "hre_data"
DATA_DIR.mkdir(exist_ok=True)

SQLITE_PATH = DATA_DIR / "hre.db"
CHROMA_PATH = DATA_DIR / "chroma"

# ==============================================================================
# LLM BACKEND KONFIGURATION
# ==============================================================================
# Schalter für späteren Claude-API-Drop-in:
# LLM_BACKEND=lmstudio  → LM Studio lokal (Standard)
# LLM_BACKEND=anthropic → Claude API (sobald verfügbar)
# LLM_BACKEND=openai    → OpenAI API
LLM_BACKEND = os.getenv("LLM_BACKEND", "lmstudio")

# LM Studio Konfiguration
LM_STUDIO_BASE_URL = os.getenv("LM_STUDIO_BASE_URL", "http://127.0.0.1:8888/v1")
print(f"DEBUG LM_STUDIO_BASE_URL = {LM_STUDIO_BASE_URL}")  # ← temporär
LM_STUDIO_API_KEY  = "lm-studio"  # Dummy — LM Studio prüft das nicht

# Modell-Identifier (exakt wie LM Studio ihn meldet)
# Nach Download von Gemma 3 27B Q3_K_M hier anpassen:
LM_STUDIO_MODEL = os.getenv("LM_STUDIO_MODEL", "qwen3.5-27b-instruct")

# ==============================================================================
# SYSTEM-HYGIENE & LOGGING
# ==============================================================================
def setup_logging():
    """Konfiguriert das Logging zentral."""
    log_dir = PROJECT_ROOT / "logs"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "engine.log"

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    if logger.hasHandlers():
        logger.handlers.clear()

    file_handler = RotatingFileHandler(
        log_file, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8'
    )
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_formatter = logging.Formatter('%(levelname)s: %(message)s')
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # Geschwätzige Bibliotheken stummschalten
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("chromadb").setLevel(logging.WARNING)
    logging.getLogger("sentence_transformers").setLevel(logging.WARNING)

setup_logging()

# ==============================================================================
# MODEL-REGISTRY
# Task-Architektur vollständig erhalten — alle Tasks zeigen vorerst
# auf dasselbe lokale Modell. Differenzierung möglich sobald
# mehrere LM Studio Backends oder Claude API verfügbar.
# ==============================================================================
MODEL_CHAT_API       = LM_STUDIO_MODEL
MODEL_SYNTHESIS      = LM_STUDIO_MODEL
MODEL_ENFORCER       = LM_STUDIO_MODEL
MODEL_FACT_EXTRACTION= LM_STUDIO_MODEL
MODEL_QUERY_EXPANSION= LM_STUDIO_MODEL
MODEL_ROUTER         = LM_STUDIO_MODEL
MODEL_RERANKER       = LM_STUDIO_MODEL
MODEL_BULK_LABELING  = LM_STUDIO_MODEL
MODEL_TITLE_GEN      = LM_STUDIO_MODEL
MODEL_QUESTION_CONV  = LM_STUDIO_MODEL

# ==============================================================================
# EMBEDDING KONFIGURATION
# ==============================================================================
EMBEDDING_MODEL      = "intfloat/multilingual-e5-large"
EMBEDDING_DIMENSIONS = 1024  # XLM-RoBERTa-Large Architektur

# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================
def get_model_for_task(task: str) -> str:
    """Gibt das konfigurierte Modell für eine spezifische Aufgabe zurück."""
    MODEL_REGISTRY: Dict[str, str] = {
        'chat':           MODEL_CHAT_API,
        'synthesis':      MODEL_SYNTHESIS,
        'enforcer':       MODEL_ENFORCER,
        'fact_extraction':MODEL_FACT_EXTRACTION,
        'query_expansion':MODEL_QUERY_EXPANSION,
        'router':         MODEL_ROUTER,
        'reranker':       MODEL_RERANKER,
        'bulk_labeling':  MODEL_BULK_LABELING,
        'title_gen':      MODEL_TITLE_GEN,
        'question_conv':  MODEL_QUESTION_CONV,
    }
    if task not in MODEL_REGISTRY:
        raise ValueError(
            f"Unbekannter Task: '{task}'. "
            f"Erlaubte Tasks: {list(MODEL_REGISTRY.keys())}"
        )
    return MODEL_REGISTRY[task]

def get_llm_client():
    """
    Gibt einen konfigurierten LLM-Client zurück.
    Zentraler Einstiegspunkt für den LLM_BACKEND-Schalter.

    Returns:
        Tuple: (client, model_name)
    """
    from openai import OpenAI

    if LLM_BACKEND == "lmstudio":
        client = OpenAI(
            base_url=LM_STUDIO_BASE_URL,
            api_key=LM_STUDIO_API_KEY
        )
        return client, LM_STUDIO_MODEL

    elif LLM_BACKEND == "anthropic":
        # TODO: Claude API Drop-in sobald verfügbar
        # import anthropic
        # return anthropic.Anthropic(), "claude-sonnet-4-20250514"
        raise NotImplementedError(
            "Claude API noch nicht konfiguriert. "
            "LLM_BACKEND=lmstudio in .env setzen."
        )

    elif LLM_BACKEND == "openai":
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        return client, os.getenv("LLM_MODEL", "gpt-4o-mini")

    else:
        raise ValueError(f"Unbekanntes LLM_BACKEND: {LLM_BACKEND}")

def get_system_message() -> str:
    """
    Gibt die Standard-Systeminstruction zurück.
    /no_think deaktiviert Qwen3-Reasoning-Modus (Token-Effizienz).
    Bei anderen Modellen harmlos ignoriert.
    """
    return os.getenv(
        "LLM_SYSTEM_PREFIX",
        "/no_think\nDu bist ein präziser Forschungsassistent der "
        "Hermeneutic Reconstruction Engine."
    )

def validate_config() -> bool:
    """Prüft ob LM Studio erreichbar ist."""
    import urllib.request
    all_valid = True

    try:
        urllib.request.urlopen(
            LM_STUDIO_BASE_URL.replace("/v1", ""), timeout=2
        )
        print(f"✅ LM Studio erreichbar: {LM_STUDIO_BASE_URL}")
    except Exception:
        print(f"⚠️  LM Studio nicht erreichbar: {LM_STUDIO_BASE_URL}")
        print(f"    Starte LM Studio und aktiviere den Developer-Server.")
        all_valid = False

    print(f"✅ Embedding-Modell: {EMBEDDING_MODEL} ({EMBEDDING_DIMENSIONS} Dim.)")
    print(f"✅ SQLite: {SQLITE_PATH}")
    print(f"✅ ChromaDB: {CHROMA_PATH}")

    return all_valid

if __name__ == "__main__":
    print("=== HERMENEUTIC ENGINE CONFIG v50.9 ===")
    print(f"Projekt-Root:  {PROJECT_ROOT}")
    print(f"LLM Backend:   {LLM_BACKEND}")
    print(f"LLM Modell:    {LM_STUDIO_MODEL}")
    print(f"Embedding:     {EMBEDDING_MODEL}")
    print("\nValidierung...")
    validate_config()