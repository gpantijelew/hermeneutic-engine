# modules/config.py
"""
Zentrale Konfiguration für die Hermeneutic Reconstruction Engine v52.

PHILOSOPHIE:
- Local-First: LM Studio (LLM) + sentence-transformers (Embeddings)
- Kein API-Key erforderlich für den Standard-Betrieb
- LLM_BACKEND-Schalter ermöglicht optionalen Wechsel zu OpenAI-kompatiblen
  Cloud-APIs oder Vertex AI

ÄNDERUNGSHISTORIE:
- v52:   Public Release — Local-First, Cloud optional
- v51:   4-Tier Model-Registry
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
LM_STUDIO_BASE_URL = os.getenv("LM_STUDIO_BASE_URL", "http://localhost:1234/v1")
LM_STUDIO_API_KEY  = "lm-studio"  # Dummy — LM Studio prüft das nicht

# Modell-Identifier (exakt wie LM Studio ihn meldet)
# Nach Download von Gemma 3 27B Q3_K_M hier anpassen:
LM_STUDIO_MODEL = os.getenv("LM_STUDIO_MODEL", "qwen3.5-9b-highiq-instruct")
# Vertex AI Konfiguration
VERTEX_MODEL   = os.getenv("VERTEX_MODEL", "gemini-3.1-pro-preview")
VERTEX_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "hre-research-2026")

# ==============================================================================
# BACKEND-SPEZIFISCHE PIPELINE-LIMITS (NEU)
# ==============================================================================
if LLM_BACKEND == "vertex":
    # Vertex AI Pipeline-Konfigurationen
    RERANKER_CANDIDATES = 70
    MAX_CHUNKS_FINAL = 8
    MAX_TOKENS_PER_CALL = 32768 # v51: 8192 war zu knapp bei langen Synthesen
else:
    # Lokale LM Studio / Standard-Pipeline Konfigurationen
    RERANKER_CANDIDATES = int(os.getenv("LOCAL_RERANKER_CANDIDATES", "20"))
    MAX_CHUNKS_FINAL = int(os.getenv("LOCAL_MAX_CHUNKS", "4"))
    MAX_TOKENS_PER_CALL = 2048

# ==============================================================================
# MODEL-REGISTRY FÜR VERTEX AI (NEU - 3-TIER ARCHITEKTUR)
# ==============================================================================
if LLM_BACKEND == "vertex":
# --- TIER 1: The Mastermind (Deepest Reasoning, User-Facing) ---
    # Nutzt VERTEX_MODEL (Standard: gemini-3.1-pro-preview)
    # --- TIER 2: The Senior Analyst (High Logic, Background Tasks) ---
    # Nutzt gemini-2.5-pro (Starkes Reasoning, günstiger als 3.1)
    # --- TIER 3: The Fast Worker (Massive Context, Extraction) ---
    # Nutzt gemini-2.5-flash (Extrem günstig für große Chunks)
    # --- TIER 4: The Micro-Tasker (Ultra-Fast, Economy) ---
    # Nutzt gemini-2.5-flash-lite-preview (Minimale Latenz & Kosten)
    MODEL_REGISTRY = {
        "chat":            VERTEX_MODEL,
        "synthesis":       VERTEX_MODEL,
        "enforcer":        "gemini-2.5-pro",         # Tier 2 (Regeln strikt durchsetzen)
        "query_expansion": "gemini-2.5-pro",         # Tier 2 (Semantische Tiefe für die Suche)
        "fact_extraction": "gemini-2.5-flash",       # Tier 3 (Der große Geldsparer!)
        "reranker":        "gemini-2.5-flash",       # Tier 3
        "bulk_labeling":   "gemini-2.5-flash",       # Tier 3
        "router":          "gemini-2.5-flash-lite-preview-09-2025", # Tier 4
        "title_gen":       "gemini-2.5-flash-lite-preview-09-2025", # Tier 4
        "question_conv":   "gemini-2.5-flash-lite-preview-09-2025", # Tier 4
    }
else:
    MODEL_REGISTRY = {k: LM_STUDIO_MODEL for k in [
        "chat", "synthesis", "enforcer", "fact_extraction",
        "query_expansion", "router", "reranker",
        "bulk_labeling", "title_gen", "question_conv"
    ]}
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
# MODEL-REGISTRY (LEGACY — BEHALTEN FÜR COMPATIBILITÄT)
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
    # Wir nutzen das neue, dynamische MODEL_REGISTRY (das Vertex/LM Studio respektiert)
    if task not in MODEL_REGISTRY:
        logger.warning(f"Task '{task}' nicht in MODEL_REGISTRY. Fallback auf Chat-Modell.")
        return MODEL_REGISTRY.get("chat", VERTEX_MODEL)

    return MODEL_REGISTRY[task]

def get_llm_client(task: str = "synthesis"):
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
        # TODO: Claude API integration
        # import anthropic
        # return anthropic.Anthropic(), "claude-sonnet-4-20250514"
        raise NotImplementedError(
            "Anthropic API not yet configured. "
            "Set LLM_BACKEND=lmstudio in .env."
        )

    elif LLM_BACKEND == "openai":
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        return client, os.getenv("LLM_MODEL", "gpt-4o-mini")

    elif LLM_BACKEND == "vertex":
        from google import genai
        from google.genai.types import HttpOptions
        client = genai.Client(
            vertexai=True,
            project=VERTEX_PROJECT,
            location="global",
            http_options=HttpOptions(api_version="v1")
        )
        return client, MODEL_REGISTRY.get(task, VERTEX_MODEL)

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
    if LLM_BACKEND != "vertex":
        try:
            urllib.request.urlopen(
                LM_STUDIO_BASE_URL.replace("/v1", ""), timeout=2
            )
            print(f"✅ LM Studio erreichbar: {LM_STUDIO_BASE_URL}")
        except Exception:
            print(f"⚠️  LM Studio nicht erreichbar: {LM_STUDIO_BASE_URL}")
            print(f"    Starte LM Studio und aktiviere den Developer-Server.")
            all_valid = False
    else:
        print(f"✅ Vertex AI Backend: {VERTEX_PROJECT} / {VERTEX_MODEL}")

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
