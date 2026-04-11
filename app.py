# app.py - v51: Hybrid Cockpit Integration (Full Version)
APP_VERSION = "[v51 (Hybrid 2Gb lokal)]"
print("=" * 80)
print(f"🚀 STARTUP: app{APP_VERSION}.py lädt...")
print("=" * 80)

import os
from dotenv import load_dotenv
# Lade Umgebungsvariablen aus der .env-Datei (nur für lokale Entwicklung)
load_dotenv(override=True)
from modules.config import LM_STUDIO_MODEL, get_system_message, LLM_BACKEND, VERTEX_MODEL
import hmac
from datetime import datetime
import streamlit as st
import json
import re
# v51-local: System Instruction aus config statt Gemini-spezifischem Modul
import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
import traceback
from typing import Optional, Dict, List, Tuple

# Neue Module-Importe
from modules.database import (
    get_firestore_client,
    create_chat_in_firestore,
    save_message,
    generate_and_update_title,
    delete_chat,
    get_chat_list,
    load_chat_history,
    rename_chat,
    load_global_settings,
)

# --- NEU: Importer Factory ---
from modules.importers import get_importer, detect_platform, IMPORTERS
# === NEU: Config-Validierung (v49.3) ===
from modules.importers.base import validate_parser_configs

try:
    validate_parser_configs()
except ValueError as e:
    st.error(f"❌ CRITICAL: Parser-Config Fehler: {e}")
    st.stop()# -----------------------------

from modules.bulk_labeling import render_bulk_labeling_ui  # v47 Feature
from modules.bulk_export import render_bulk_export_ui      # v47 Feature
from modules.vector_admin import render_vector_admin_dashboard
from modules.vector_store import FirestoreVectorStore
from modules.citation_rag import CitationRAG
from modules.synthesis_utils import post_process_synthesis
from modules.confidence_scoring import calculate_confidence_scores
from modules.export import generate_markdown, generate_json, generate_excel
import ui.state as state
from ui.pipeline_trace import render_pipeline_trace
from ui.import_tab import render_import_tab
from ui.analysis_tab import render_analysis_tab
from ui.session_stats import render_session_stats
from ui.settings_panel import render_settings_panel
from ui.chat_list import render_chat_list, clear_chat_cache
from ui.emergency_sidebar import render_emergency_sidebar
from ui.chat_tab import render_chat_tab

# TESTZEILE
st.write(f"🚀 Die ({APP_VERSION}) wird ausgeführt!")

# ==============================================================================
# AUTHENTIFIZIERUNG (mit st.secrets) - WIEDERHERGESTELLT!
# ==============================================================================

AUTH_ENABLED = True  # Passwort-Schutz aktiviert

def check_password():
    """Prüft das Passwort (Robust für Cloud & Lokal)."""
    if st.session_state.get("password_correct"):
        return True

    # Zeige Passwort-Screen
    st.title(f"🚀 Forschungs-Cockpit {APP_VERSION} - SYSTEM ONLINE")
    password = st.text_input("Passwort eingeben:", type="password")

    if password:
        # 1. Versuch: Hole Passwort aus Umgebungsvariable (Cloud / Google Secrets)
        # Das ist der entscheidende Teil für Cloud Run!
        app_password = os.environ.get("APP_PASSWORD")

        # 2. Versuch: Hole Passwort aus st.secrets (Lokal)
        if not app_password:
            try:
                app_password = st.secrets.get("APP_PASSWORD")
            except:
                pass # Keine Secrets Datei gefunden (ist ok in der Cloud)

        # Fallback, falls gar nichts gesetzt ist
        if not app_password:
            app_password = "fallback_password_unsafe"

        if password == app_password:
            st.session_state.password_correct = True
            st.success("✅ Willkommen!")
            st.rerun()
        else:
            st.error("❌ Falsches Passwort")
    return False

# Authentifizierung durchführen (GANZ AM ANFANG!)
if AUTH_ENABLED:
    if not check_password():
        st.stop()

import logging

# Logging konfigurieren
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
# HTTP-Request-Spam unterdrücken (HuggingFace, httpx)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("sentence_transformers").setLevel(logging.WARNING)

# Debug-Mode aktivieren?
# Wir prüfen erst die Umgebungsvariable (Cloud), dann die Secrets (Lokal)
try:
    # Cloud-Weg (Environment Variable)
    debug_env = os.environ.get("DEBUG_MODE", "False").lower() == "true"

    # Lokaler Weg (Secrets Datei)
    try:
        debug_local = st.secrets.get("DEBUG_MODE", False)
    except:
        debug_local = False # Datei fehlt, ist ok

    DEBUG_MODE = debug_env or debug_local

except Exception:
    DEBUG_MODE = False

if DEBUG_MODE:
    logger.setLevel(logging.DEBUG)
    st.sidebar.info("🐛 Debug-Mode AKTIV")

# ==============================================================================
# 1. KONFIGURATION
# ==============================================================================

st.set_page_config(
    page_title=f"Forschungs-Cockpit {APP_VERSION}",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)
# --- CUSTOM UI STYLING ---
st.markdown(
    """
    <style>
        /* Sidebar Standard-Breite massiv erhöhen (z.B. auf 450 Pixel) */
        [data-testid="stSidebar"] {
            min-width: 450px !important;
            max-width: 600px !important;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# ==============================================================================
# 2. KONSTANTEN
# ==============================================================================

# v50.9-local: PROJECT_ID und GEMINI_API_KEY entfernt (kein Cloud-Backend mehr)

# ==============================================================================
# 4. SESSION STATE
# ==============================================================================
state.init_state()

# ==============================================================================
# 5. NAVIGATION (v47 ORIGINAL + v47 Admin-Features)
# ==============================================================================

st.sidebar.title("📡 Navigation")
page = st.sidebar.selectbox(
    "Seite wählen",
    ["Chat", "Import", "Analyse", "Labeling", "DB-Export"],  # v47 Features!
    help="Wähle die gewünschte Funktion aus"
)

# ==============================================================================
# 6. SEITEN-LOGIK
# ==============================================================================

# Defaults für Chat-Parameter
use_db           = False
use_router       = False
filter_mode      = "Alles durchsuchen"
selected_rag_ids = None
# ==============================================================================
# HYBRID-COCKPIT SIDEBAR (nur im Chat-Modus)
# ==============================================================================
if page == "Chat":
    with st.sidebar:
        render_session_stats()
        st.markdown("---")
        st.header("🎛️ Hybrid-Cockpit")

        use_db = st.toggle(
            "🔌 Datenbank-Wissen",
            value=False,
            key="toggle_use_db",
            help="AN: Zugriff auf deine Dokumente (RAG).\nAUS: Freier Chat mit lokalem LLM."
        )

        if use_db:
            st.caption("🗃️ Datenbank-Steuerung")

            use_router = st.checkbox(
                "🧠 Auto-Router (v50)",
                value=True,
                key="check_use_router",
                help="AN: KI entscheidet Strategie (Fakt vs. Poesie).\nAUS: Standard-Suche."
            )

            st.markdown("---")
            c1, c2 = st.columns([4, 1])
            c1.caption("🔍 Fokus (Scope)")

            if c2.button("🔄", help="Liste aktualisieren"):
                clear_chat_cache()
                st.rerun()

            from ui.chat_list import _get_cached_chat_list
            all_chats_list = _get_cached_chat_list()
            all_chats_list = sorted(all_chats_list, key=lambda x: x['title'].lower())
            chat_options = {c['title']: c['id'] for c in all_chats_list}

            filter_mode = st.radio(
                "Quelle:",
                ["Alles durchsuchen", "Auswahl treffen"],
                label_visibility="collapsed",
                key="radio_filter_mode"
            )

            if filter_mode == "Auswahl treffen":
                current_selection = st.session_state.get("multi_select_docs", [])
                valid_selection = [
                    s for s in current_selection if s in chat_options.keys()
                ]
                selected_titles = st.multiselect(
                    "Dokumente wählen:",
                    options=list(chat_options.keys()),
                    default=valid_selection,
                    placeholder="Wähle Chats/Texte...",
                    key="multi_select_docs"
                )
                if selected_titles:
                    selected_rag_ids = [chat_options[t] for t in selected_titles]
                else:
                    st.warning("⚠️ Keine Auswahl = Keine Suche!")
        st.markdown("---")
        render_settings_panel()
        render_chat_list()
        render_emergency_sidebar()
if page == "Import":
    render_import_tab()
elif page == "Labeling":
    render_bulk_labeling_ui()
elif page == "DB-Export":
    render_bulk_export_ui()
elif page == "Analyse":
    all_chats = get_chat_list()
    render_analysis_tab(all_chats)
elif page == "Chat":
    render_chat_tab(
        use_db=use_db,
        use_router=use_router,
        filter_mode=filter_mode,
        selected_rag_ids=selected_rag_ids,
    )

# ==========================================
# ADMIN-BEREICH (Ganz unten in app.py)
# ==========================================
render_vector_admin_dashboard()