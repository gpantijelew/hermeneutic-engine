# modules/config.py
"""
Zentrale Konfiguration für die Hermeneutic Reconstruction Engine seit v50.9+.

PHILOSOPHIE:
- Vollständig lokal: LM Studio (LLM) + sentence-transformers (Embeddings)
- Keine Cloud-Abhängigkeit, kein API-Key erforderlich
- LLM_BACKEND-Schalter ermöglicht späteren Drop-in zu Claude API

ÄNDERUNGSHISTORIE:
- v55: IFS-Supervisions-Panel, Map-Reduce Pipeline, supervision_tab.py, wissenschaftliche Methodik in hermeneutic_protocol.yaml
- v51: 4 Tiers
- v50.9: Migration von Gemini/Firestore → LM Studio/ChromaDB/SQLite
- v49:   Erstellt als zentrale Model-Registry
"""

import os
import sys
import time
import urllib.request
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Lade .env für lokale Entwicklung (optional)
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

# ==============================================================================
# PROJEKT-ROOT BESTIMMUNG
# ==============================================================================
if hasattr(sys, "_MEIPASS"):
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
LM_STUDIO_API_KEY = "lm-studio"  # Dummy — LM Studio prüft das nicht

# Modell-Identifier (exakt wie LM Studio ihn meldet)
# Nach Download von Gemma 3 27B Q3_K_M hier anpassen:
LM_STUDIO_MODEL = os.getenv("LM_STUDIO_MODEL", "qwen3.5-27b-instruct")
# NEU: Konfigurierbare Timeouts für große Modelle (Gemma 3 27B etc.)
LM_STUDIO_VALIDATE_TIMEOUT = int(os.getenv("LM_STUDIO_VALIDATE_TIMEOUT", "10"))
LM_STUDIO_VALIDATE_RETRIES = int(os.getenv("LM_STUDIO_VALIDATE_RETRIES", "3"))
# Vertex AI Konfiguration
VERTEX_MODEL = os.getenv("VERTEX_MODEL", "gemini-3.1-pro-preview")
VERTEX_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "hre-research-2026")

# ==============================================================================
# BACKEND-SPEZIFISCHE PIPELINE-LIMITS (NEU)
# ==============================================================================
if LLM_BACKEND == "vertex":
    # Vertex AI Pipeline-Konfigurationen
    RERANKER_CANDIDATES = 70  # Unverändert — wir opfern keinen Recall
    RERANKER_BATCH_SIZE = 6   # NEU: 6 Chunks × 800 Zeichen = 4800 Zeichen
                           # + ~2000 Zeichen Prompt-Overhead = 6800 Zeichen
                           # Sicher unter dem Fehler-Schwellwert (~10.000)
    MAX_CHUNKS_FINAL = 30  # <--- NEU: Erhöht von 8 auf 30 für Meta-Analysen!
    MAX_TOKENS_PER_CALL = 8192  # Verringert von 32768! Verhindert Timeouts bei langen Thinking-Prozessen. Reicht für ausführliche Analysen.
    MAX_TOKENS_STILISIERUNG = 8192 # <--- NEU: Fehlte im Vertex-Zweig, verursachte ImportError
    MAX_IFS_TOKENS = 2048  # FIX: 3.1-pro-preview braucht mehr Puffer (war 768, MAX_TOKENS-Abbruch)
else:
    MAX_IFS_TOKENS = 2048  # FIX: 3.1-pro-preview braucht mehr Puffer (war 768, MAX_TOKENS-Abbruch)
    # Lokale LM Studio / Standard-Pipeline Konfigurationen
    RERANKER_CANDIDATES = int(os.getenv("LOCAL_RERANKER_CANDIDATES", "20"))
    MAX_CHUNKS_FINAL = int(os.getenv("LOCAL_MAX_CHUNKS", "4"))
    MAX_TOKENS_PER_CALL = 4096  # <--- ERHÖHT: 2048 ist zu wenig, wenn der Prompt schon 2000 hat!
    MAX_TOKENS_STILISIERUNG = 8192 # <--- NEU: LM Studio kann das auch!

# Essence Parity & Rescue Mission
ESSENCE_TOTAL_BUDGET = 60
RESCUE_THRESHOLD = 4
MINIMUM_RESCUE_SCORE = 0.5

# Rate Limiting für Importer-Loops (Schutz vor 429 Quota Errors)
IMPORT_RATE_LIMIT_DELAY = 0.5 if LLM_BACKEND == "vertex" else 0.0

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
        "chat": VERTEX_MODEL,
        "synthesis": VERTEX_MODEL,
        "ifs": "gemini-3.1-pro-preview",  # Tier 1 — max_output_tokens respektiert (2.5-pro hat technical limitation)
        "enforcer": "gemini-2.5-pro",  # Tier 2 (Regeln strikt durchsetzen)
        "query_expansion": "gemini-2.5-pro",  # Tier 2 (Semantische Tiefe für die Suche)
        "fact_extraction": "gemini-2.5-flash",  # Tier 3 (Der große Geldsparer!)
        "reranker": "gemini-3-flash-preview", # Tier 3 (Gen 3 Upgrade: Perfektes Batch-JSON & Speed!)
        "bulk_labeling": "gemini-2.5-flash",  # Tier 3
        "router": "gemini-2.5-flash-lite-preview-09-2025",  # Tier 4
        "title_gen": "gemini-2.5-flash-lite-preview-09-2025",  # Tier 4
        "question_conv": "gemini-2.5-flash-lite-preview-09-2025",  # Tier 4
    }
else:
    MODEL_REGISTRY = {
        k: LM_STUDIO_MODEL
        for k in [
            "chat",
            "synthesis",
            "ifs",
            "enforcer",
            "fact_extraction",
            "query_expansion",
            "router",
            "reranker",
            "bulk_labeling",
            "title_gen",
            "question_conv",
        ]
    }


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
        log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_formatter = logging.Formatter("%(levelname)s: %(message)s")
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
MODEL_CHAT_API = LM_STUDIO_MODEL
MODEL_SYNTHESIS = LM_STUDIO_MODEL
MODEL_ENFORCER = LM_STUDIO_MODEL
MODEL_FACT_EXTRACTION = LM_STUDIO_MODEL
MODEL_QUERY_EXPANSION = LM_STUDIO_MODEL
MODEL_ROUTER = LM_STUDIO_MODEL
MODEL_RERANKER = LM_STUDIO_MODEL
MODEL_BULK_LABELING = LM_STUDIO_MODEL
MODEL_TITLE_GEN = LM_STUDIO_MODEL
MODEL_QUESTION_CONV = LM_STUDIO_MODEL

# ==============================================================================
# EMBEDDING KONFIGURATION
# ==============================================================================
EMBEDDING_MODEL = "intfloat/multilingual-e5-large"
EMBEDDING_DIMENSIONS = 1024  # XLM-RoBERTa-Large Architektur

# ==============================================================================
# CITATION RAG PIPELINE CONSTANTS (Phase 2.6)
# ==============================================================================
RESCUE_FETCH_LIMIT = (
    3  # Wie viele Chunks bei der Rettungsmission pro Dokument geholt werden
)
# NEU: Dynamisches Token-Budget (Vertex verträgt massiv mehr als LM Studio)
TRIM_TOKEN_BUDGET = 60000 if LLM_BACKEND == "vertex" else 4000

# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================
def get_model_for_task(task: str) -> str:
    """Gibt das konfigurierte Modell für eine spezifische Aufgabe zurück."""
    # Wir nutzen das neue, dynamische MODEL_REGISTRY (das Vertex/LM Studio respektiert)
    if task not in MODEL_REGISTRY:
        logger.warning(
            f"Task '{task}' nicht in MODEL_REGISTRY. Fallback auf Chat-Modell."
        )
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
        client = OpenAI(base_url=LM_STUDIO_BASE_URL, api_key=LM_STUDIO_API_KEY)
        return client, LM_STUDIO_MODEL

    elif LLM_BACKEND == "anthropic":
        # TODO: Claude API Drop-in sobald verfügbar
        # import anthropic
        # return anthropic.Anthropic(), "claude-sonnet-4-20250514"
        raise NotImplementedError(
            "Claude API noch nicht konfiguriert. LLM_BACKEND=lmstudio in .env setzen."
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
            http_options=HttpOptions(api_version="v1"),
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
        "Hermeneutic Reconstruction Engine.",
    )


def validate_config() -> bool:
    """
    Prüft ob LM Studio erreichbar ist.

    Mit Retry-Logik und exponentiellem Backoff für große Modelle
    (Gemma 3 27B kann 5-10s zum Starten brauchen).
    """
    all_valid = True

    if LLM_BACKEND != "vertex":
        url = LM_STUDIO_BASE_URL.replace("/v1", "")

        # Retry-Logik mit exponentiellem Backoff
        for attempt in range(1, LM_STUDIO_VALIDATE_RETRIES + 1):
            try:
                urllib.request.urlopen(url, timeout=LM_STUDIO_VALIDATE_TIMEOUT)
                print(f"✅ LM Studio erreichbar: {LM_STUDIO_BASE_URL} "
                      f"(Versuch {attempt}/{LM_STUDIO_VALIDATE_RETRIES})")
                break  # Erfolg — keine weiteren Retries

            except Exception as e:
                wait_time = 2 ** (attempt - 1)  # 1s, 2s, 4s

                if attempt < LM_STUDIO_VALIDATE_RETRIES:
                    print(f"⏳  LM Studio nicht erreichbar (Versuch {attempt}): {e}")
                    print(f"     Warte {wait_time}s vor Retry...")
                    time.sleep(wait_time)
                else:
                    # Letzter Versuch fehlgeschlagen
                    print(f"⚠️  LM Studio nach {LM_STUDIO_VALIDATE_RETRIES} Versuchen "
                          f"nicht erreichbar: {LM_STUDIO_BASE_URL}")
                    print(f"     Letzter Fehler: {e}")
                    print("     Tipps:")
                    print("       1. LM Studio gestartet?")
                    print("       2. Developer-Server aktiv (Port 8888)?")
                    print("       3. Firewall blockiert?")
                    print("       4. Großes Modell lädt noch? (Gemma 3 27B: bis zu 30s)")
                    print(f"     Konfigurierbar via Umgebungsvariable: "
                          f"LM_STUDIO_VALIDATE_TIMEOUT (aktuell: {LM_STUDIO_VALIDATE_TIMEOUT}s)")
                    all_valid = False

    else:
        print(f"✅ Vertex AI Backend: {VERTEX_PROJECT} / {VERTEX_MODEL}")

    print(f"✅ Embedding-Modell: {EMBEDDING_MODEL} ({EMBEDDING_DIMENSIONS} Dim.)")
    print(f"✅ SQLite: {SQLITE_PATH}")
    print(f"✅ ChromaDB: {CHROMA_PATH}")

    return all_valid

# --- A.2 DETERMINISTIC PIPELINE MODE ---

DOMAIN_ANALYSIS = "analysis_pipeline"
DOMAIN_IFS = "ifs_resonanzraum"
DOMAIN_STILISIERUNG = "stilisierung"

# Backend-Fähigkeiten (Schutz für lokale Server)
BACKEND_CAPABILITIES = {
    "vertex": {"seed": True},
    "openai": {"seed": True},
    "lm_studio": {"seed": False},
}

# Parameter-Profile pro Domain
DOMAIN_PROFILES = {
    DOMAIN_ANALYSIS: {
        "temperature": 0.3,
        "top_p": 0.85,
        "seed": 42,
    },
    DOMAIN_IFS: None,          # Nutzt YAML-Defaults
    DOMAIN_STILISIERUNG: None, # Nutzt YAML-Defaults
}

# --- A.7 ENFORCER SAMPLING ---
ENFORCER_SAMPLING_RATE_HIGH = 5     # 20% Sampling-Rate am Anfang
ENFORCER_SAMPLING_RATE_LOW = 20     # 5% Sampling-Rate für Dauerbetrieb
ENFORCER_CALIBRATION_TARGET = 100   # Ab 100 manuellen Reviews greift die LOW-Rate
ENFORCER_VERSION = "v1.0"           # Aktuelle Version der Enforcer-Logik/Prompts

if __name__ == "__main__":
    print("=== HERMENEUTIC ENGINE CONFIG v53 ===")
    print(f"Projekt-Root:  {PROJECT_ROOT}")
    print(f"LLM Backend:   {LLM_BACKEND}")
    print(f"LLM Modell:    {LM_STUDIO_MODEL}")
    print(f"Embedding:     {EMBEDDING_MODEL}")
    print("\nValidierung...")
    validate_config()
