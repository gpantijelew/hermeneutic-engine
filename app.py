# app.py - v59: STILISTIC Mode + Stil-Distillation (Phase 0.5) + 6 Distillation-Kategorien
APP_VERSION = "[v59 (STILISTIC Mode + Stil-Distillation)]"

import os
from dotenv import load_dotenv
import hmac

# Lade Umgebungsvariablen aus der .env-Datei (nur für lokale Entwicklung)
load_dotenv(override=True)

import logging

# Logging GANZ FRÜH konfigurieren, damit logger.info funktioniert
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
# HTTP-Request-Spam unterdrücken
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("sentence_transformers").setLevel(logging.WARNING)

logger.info("=" * 80)
logger.info(f"🚀 STARTUP: app{APP_VERSION}.py lädt...")
logger.info("=" * 80)

# ==============================================================================
# STREAMLIT PAGE CONFIG (MUSS DIE ERSTE ST-ANWEISUNG SEIN!)
# ==============================================================================
import streamlit as st

st.set_page_config(
    page_title=f"Forschungs-Cockpit {APP_VERSION}",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- CUSTOM UI STYLING ---
st.markdown(
    """
    <style>
        /* Sidebar Standard-Breite massiv erhöht */
        [data-testid="stSidebar"] {
            min-width: 450px !important;
            max-width: 600px !important;
        }

        /* 1. Oberstes Padding der Sidebar radikal killen */
        [data-testid="stSidebarUserContent"] {
            padding-top: 0rem !important;
        }

        /* 2. Abstand zwischen den vertikalen Blöcken (Buttons/Texte) in der Sidebar minimieren */
        [data-testid="stSidebarUserContent"] div[data-testid="stVerticalBlock"] {
            gap: 0.2rem !important;
        }

        /* 3. Buttons flacher machen */
        [data-testid="stSidebarUserContent"] button {
            padding-top: 0.2rem !important;
            padding-bottom: 0.2rem !important;
            min-height: 2rem !important;
        }

        /* 4. Margins von Überschriften in der Sidebar entfernen */
        [data-testid="stSidebarUserContent"] h1, 
        [data-testid="stSidebarUserContent"] h2, 
        [data-testid="stSidebarUserContent"] h3 {
            margin-top: 0.2rem !important;
            margin-bottom: 0.2rem !important;
            padding-top: 0rem !important;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# ==============================================================================
# IMPORTS (Nach st.set_page_config!)
# ==============================================================================

# Neue Module-Importe
from modules.database import (
    get_chat_list,
    get_unreviewed_count,
)

from modules.importers.base import validate_parser_configs

try:
    validate_parser_configs()
except (ValueError, FileNotFoundError) as e:
    st.error(f"❌ CRITICAL: Parser-Config Fehler: {e}")
    st.stop()

# FIX v57: bulk_labeling und bulk_export waren nie separate Module.
# render_bulk_labeling() existiert in vector_admin.py.
# render_bulk_export_ui() wurde nie implementiert — Placeholder statt ImportError.
from modules.vector_admin import render_vector_admin_dashboard, render_bulk_labeling
import ui.state as state
from ui.import_tab import render_import_tab
from ui.analysis_tab import render_analysis_tab
from ui.session_stats import render_session_stats
from ui.settings_panel import render_settings_panel
from ui.chat_list import render_chat_list, clear_chat_cache
from ui.emergency_sidebar import render_emergency_sidebar
from ui.chat_tab import render_chat_tab
from ui.destillation_tab import render_destillation_tab
from ui.stilisierung_tab import render_stilisierung_tab
from ui.stilistic_lab_tab import render_stilistic_lab_tab    # v57.4: STILISTIC LAB
from ui.supervision_tab import render_supervision_tab
from ui.ifs_tab import render_ifs_tab
from ui.qa_review_tab import render_qa_review_tab
from ui.system_health_tab import render_system_health_tab  # (A.8: Confidence Calibration)

# ==============================================================================
# AUTHENTIFIZIERUNG (mit st.secrets) - NACH PAGE CONFIG!
# ==============================================================================

AUTH_ENABLED = True


def check_password():
    """Prüft das Passwort (Robust für Cloud & Lokal)."""
    if st.session_state.get("password_correct"):
        return True

    st.title(f"🚀 Forschungs-Cockpit {APP_VERSION} - SYSTEM ONLINE")
    password = st.text_input("Passwort eingeben:", type="password")

    if password:
        app_password = os.environ.get("APP_PASSWORD")
        if not app_password:
            try:
                app_password = st.secrets.get("APP_PASSWORD")
            except Exception:
                pass

        if not app_password:
            st.error(
                "⚠️ Kein Passwort konfiguriert. Setze APP_PASSWORD als Umgebungsvariable oder in st.secrets."
            )
            st.stop()

        if hmac.compare_digest(password, app_password):
            st.session_state.password_correct = True
            st.success("✅ Willkommen!")
            st.rerun()
        else:
            st.error("❌ Falsches Passwort")
    return False


# Authentifizierung durchführen
if AUTH_ENABLED:
    if not check_password():
        st.stop()

# ==============================================================================
# DEBUG MODE
# ==============================================================================
try:
    debug_env = os.environ.get("DEBUG_MODE", "False").lower() == "true"
    try:
        debug_local = st.secrets.get("DEBUG_MODE", False)
    except Exception:
        debug_local = False
    DEBUG_MODE = debug_env or debug_local
except Exception:
    DEBUG_MODE = False

if DEBUG_MODE:
    logger.setLevel(logging.DEBUG)
    st.sidebar.info("🐛 Debug-Mode AKTIV")

# ==============================================================================
# SESSION STATE & NAVIGATION (Restlicher Code bleibt exakt gleich)
# ==============================================================================
state.init_state()

# --- A.7: QA Reviews Badge ---
_unreviewed = get_unreviewed_count()
_badge = f" 🔴 {_unreviewed}" if _unreviewed > 0 else ""

st.sidebar.title("📡 Navigation")
_page_options = ["Chat", "Import", "Analyse", "Destillation", "Stilisierung", "Stilistic Lab", "Resonanzraum", "Supervision", "System Health", "Labeling", "DB-Export", f"QA Reviews{_badge}"]
page = st.sidebar.selectbox(
    "Seite wählen",
    _page_options,
    help="Wähle die gewünschte Funktion aus",
)
# Normalisiere Badge zurück für Vergleich
page = page.replace(_badge, "")

use_db = False
use_router = False
filter_mode = "Alles durchsuchen"
selected_rag_ids = None

if page == "Chat":
    with st.sidebar:
        render_session_stats()
        st.markdown("---")
        st.header("🎛️ Hybrid-Cockpit")

        use_db = st.toggle(
            "🔌 Datenbank-Wissen",
            value=False,
            key="toggle_use_db",
            help="AN: Zugriff auf deine Dokumente (RAG).\nAUS: Freier Chat mit lokalem LLM.",
        )

        if use_db:
            st.caption("🗃️ Datenbank-Steuerung")

            use_router = st.checkbox(
                "🧠 Auto-Router (v50)",
                value=True,
                key="check_use_router",
                help="AN: KI entscheidet Strategie (Fakt vs. Poesie).\nAUS: Standard-Suche.",
            )

            st.markdown("---")
            c1, c2 = st.columns([4, 1])
            c1.caption("🔍 Fokus (Scope)")

            if c2.button("🔄", help="Liste aktualisieren"):
                clear_chat_cache()
                st.rerun()

            from ui.chat_list import _get_cached_chat_list

            all_chats_list = _get_cached_chat_list()
            all_chats_list = sorted(all_chats_list, key=lambda x: x["title"].lower())
            chat_options = {c["title"]: c["id"] for c in all_chats_list}

            filter_mode = st.radio(
                "Quelle:",
                ["Alles durchsuchen", "Auswahl treffen"],
                label_visibility="collapsed",
                key="radio_filter_mode",
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
                    key="multi_select_docs",
                )
                if selected_titles:
                    selected_rag_ids = [chat_options[t] for t in selected_titles]
                else:
                    st.warning("⚠️ Keine Auswahl = Keine Suche!")
        st.markdown("---")
        render_settings_panel()
        render_chat_list()

if page == "Import":
    render_import_tab()
elif page == "System Health":
    render_system_health_tab()
elif page == "Labeling":
    render_bulk_labeling()
elif page == "DB-Export":
    st.header("📦 DB-Export")
    st.info("🚧 Bulk-Export ist noch nicht als separates Modul implementiert. "
            "Nutze den Export-Button in der Chat-Ansicht oder den Vector Admin "
            "in der Sidebar.")
elif page == "Analyse":
    all_chats = get_chat_list()
    render_analysis_tab(all_chats)
elif page == "Destillation":
    render_destillation_tab()
elif page == "Stilisierung":
    render_stilisierung_tab()
elif page == "Stilistic Lab":              # v57.4: STILISTIC LAB (Drei-Etappen)
    render_stilistic_lab_tab()
elif page == "Resonanzraum":
    render_ifs_tab()
elif page == "Supervision":              # <--- NEU
    render_supervision_tab()             # <--- NEU
elif page == "QA Reviews":
    render_qa_review_tab()
elif page == "Chat":
    render_chat_tab(
        use_db=use_db,
        use_router=use_router,
        filter_mode=filter_mode,
        selected_rag_ids=selected_rag_ids,
    )

    # FIX: Notfall-Sidebar erst rendern, NACHDEM der Chat die History aktualisiert hat
    with st.sidebar:
        render_emergency_sidebar()

render_vector_admin_dashboard()
