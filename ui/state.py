# ui/state.py — HRE v51
# Zentrales Session State Management.
#
# ARCHITEKTUR-REGEL:
# Nur diese Datei schreibt in st.session_state.
# Alle anderen Module lesen — schreiben nicht direkt.
#
# LEBENSZYKLEN (strikt getrennt):
# - Chat-State:    reset_chat()
# - Analyse-State: reset_analysis_search()
# - RAG-State:     clear_rag_state()

import streamlit as st
from modules.config import get_system_message, LM_STUDIO_MODEL
from modules.database import load_global_settings


# ==============================================================================
# DEFAULT SETTINGS
# ==============================================================================


def get_default_settings() -> dict:
    """
    Kapselt die Default-Einstellungen.
    DEFAULT_SYSTEM_INSTRUCTION kommt aus modules/config.get_system_message()
    — kein Import aus app.py, kein Circular Import.
    """
    return {
        "temperature": 0.2,
        "top_p": 0.95,
        "system_instruction": get_system_message(),
        "use_search": False,
        "debug_mode": False,
        "model_name": LM_STUDIO_MODEL,
    }


# ==============================================================================
# INIT (Einstiegspunkt, einmal pro Session)
# ==============================================================================


def init_state() -> None:
    """
    Initialisiert alle session_state-Keys mit ihren Default-Werten.
    Idempotent: Bereits gesetzte Keys werden nicht überschrieben.
    Einziger erlaubter Aufruf-Ort: app.py, nach Auth-Check.
    """
    # Auth
    _set_default("password_correct", False)

    # Chat Core
    _set_default("chat_id", None)
    _set_default("history", [])
    _set_default("title_generated", False)
    _set_default("last_error", None)

    # Chat List UI
    _set_default("rename_chat_id", None)
    _set_default("delete_confirm_id", None)
    _set_default("sidebar_offset", 0)
    _set_default("sidebar_page_size", 50)

    # Settings
    if "global_settings" not in st.session_state:
        st.session_state["global_settings"] = load_global_settings(
            get_default_settings()
        )

    # Monitoring
    _set_default("call_stats", [])

    # Analyse-Tab: UI-Persistenz-Keys
    # Lebenszyklus: überleben Chat-Wechsel bewusst!
    _set_default("rag_saved_titles", [])
    _set_default("rag_saved_query", "")
    _set_default("verification_log", {"structure_check": [], "deep_check": []})

    # Chat-RAG-State, Analyse-Ergebnisse, Export:
    # Bewusst KEIN Default — Abwesenheit ist Signal.
    # Sie entstehen on-demand und werden explizit gelöscht.

    # Analyse-Modus-Kontext
    _set_default("selected_chat_for_analysis", None)

    # IFS Resonanzraum (Mission D) — Dual-Modus: Triad + Single (D.S3.3)
    _set_default("ifs_mode", "triad")        # "triad" | "single"
    _set_default("ifs_situation", "")
    _set_default("ifs_current_part", None)   # Nur im Single-Modus aktiv
    _set_default("ifs_histories", {
        "ifs_control": [],
        "ifs_fight": [],
        "ifs_fear": [],
    })
    _set_default("ifs_started", False)
    _set_default("ifs_emergency", False)
    _set_default("ifs_exile_warned", False)


# ==============================================================================
# LIFECYCLE-SETTER (autorisierte Schreibpfade)
# ==============================================================================


def reset_chat() -> None:
    """
    Setzt Chat-spezifische Keys zurück.
    NICHT für Analyse-Keys — deren Lebenszyklus ist unabhängig.
    Einzige autorisierte Methode für den 'Neuer Chat'-Button.
    """
    st.session_state.chat_id = None
    st.session_state.history = []
    st.session_state.title_generated = False
    st.session_state.rename_chat_id = None
    st.session_state.delete_confirm_id = None
    st.session_state.last_error = None
    clear_rag_state()


def reset_analysis_search() -> None:
    """
    Löscht UI-Persistenz-Keys des Analyse-Tabs.
    Eigener Lebenszyklus: wird nur explizit durch
    den User (Reset-Button) ausgelöst — nie durch Chat-Wechsel.
    """
    for key in (
        "rag_saved_titles",
        "rag_saved_query",
        "rag_results",
        "rag_answer",
        "rag_mode",
        "rag_query",
        "verification_log",
        "rag_pipeline_trace",
    ):
        if key in st.session_state:
            del st.session_state[key]


def set_chat(chat_id: str, history: list) -> None:
    """Autorisierter Schreibpfad für Chat-Load-Events."""
    st.session_state.chat_id = chat_id
    st.session_state.history = history
    st.session_state.title_generated = True
    st.session_state.rename_chat_id = None
    st.session_state.delete_confirm_id = None
    st.session_state.last_error = None


def set_rag_result(sources: list, query: str, intent: str) -> None:
    """Autorisierter Schreibpfad für Chat-RAG-Ergebnisse."""
    st.session_state.last_rag_sources = sources
    st.session_state.last_rag_query = query
    st.session_state.last_rag_intent = intent


def set_analysis_result(
    results: list, answer: str, query: str, mode: str, pipeline_trace: dict = None
) -> None:
    """Autorisierter Schreibpfad für Analyse-Tab-Ergebnisse."""
    st.session_state.rag_results = results
    st.session_state.rag_answer = answer
    st.session_state.rag_query = query
    st.session_state.rag_mode = mode
    if pipeline_trace is not None:
        st.session_state.rag_pipeline_trace = pipeline_trace


def clear_rag_state() -> None:
    """Löscht transiente RAG-Keys (Chat-Pfad)."""
    for key in ("last_rag_sources", "last_rag_query", "last_rag_intent"):
        if key in st.session_state:
            del st.session_state[key]


def reset_sidebar_offset() -> None:
    """Setzt Sidebar-Pagination auf Seite 1 zurück."""
    st.session_state.sidebar_offset = 0


def increment_sidebar_offset() -> None:
    """Lädt die nächste Seite Chats in der Sidebar."""
    st.session_state.sidebar_offset += st.session_state.sidebar_page_size


def remove_last_turn() -> None:
    """
    Entfernt die letzte User+Model-Runde (2 Einträge) aus der History.
    Autorisierter Schreibpfad für Edit- und Delete-Buttons.
    Idempotent: Tut nichts wenn History leer oder zu kurz.
    """
    if len(st.session_state.history) >= 2:
        st.session_state.history = st.session_state.history[:-2]


def pop_last_message() -> None:
    """
    Entfernt nur den letzten einzelnen Eintrag aus der History.
    Autorisierter Schreibpfad für den Notfall-Sidebar-Button.
    Idempotent: Tut nichts wenn History leer.
    """
    if st.session_state.history:
        st.session_state.history.pop()


def append_to_history(role: str, text: str) -> None:
    """
    Autorisierter Schreibpfad für history.
    Kapselt das Format — kein UI-Modul kennt die interne Struktur.
    """
    st.session_state.history.append({"role": role, "parts": [{"text": text}]})

def set_last_error(message: str | None = None) -> None:
    """Autorisierter Schreibpfad für Fehlermeldungen. None löscht den Fehler."""
    st.session_state.last_error = message


def reset_ifs_session() -> None:
    """
    Setzt den IFS-Resonanzraum vollständig zurück.
    Eigener Lebenszyklus — nie durch Chat-Wechsel ausgelöst.
    Nur durch expliziten User-Klick.
    """
    st.session_state.ifs_mode = "triad"
    st.session_state.ifs_situation = ""
    st.session_state.ifs_current_part = None
    st.session_state.ifs_histories = {
        "ifs_control": [],
        "ifs_fight": [],
        "ifs_fear": [],
    }
    st.session_state.ifs_started = False
    st.session_state.ifs_emergency = False
    st.session_state.ifs_exile_warned = False


def start_ifs_session(situation: str, mode: str = "triad", part: str = "ifs_control") -> None:
    """Startet eine neue IFS-Session im gewählten Modus."""
    st.session_state.ifs_mode = mode
    st.session_state.ifs_situation = situation
    st.session_state.ifs_current_part = part if mode == "single" else None
    st.session_state.ifs_histories = {
        "ifs_control": [],
        "ifs_fight": [],
        "ifs_fear": [],
    }
    st.session_state.ifs_started = True
    st.session_state.ifs_emergency = False


def switch_ifs_part(new_part: str, old_label: str = "", new_label: str = "") -> None:
    """Wechselt im Single-Modus zu einer anderen inneren Stimme.
    Fügt eine Reflection-Nachricht im alten Part ein."""
    current = st.session_state.get("ifs_current_part")
    if current and current != new_part:
        st.session_state.ifs_histories[current].append({
            "role": "reflection",
            "text": f"Wechsel zur {new_label}-Stimme.",
        })
    st.session_state.ifs_current_part = new_part


def append_ifs_message(part: str, role: str, text: str) -> None:
    """
    Autorisierter Schreibpfad für IFS-Gesprächsverlauf.
    part: 'ifs_control', 'ifs_fight', oder 'ifs_fear'
    role: 'user', 'assistant', oder 'reflection'
    """
    st.session_state.ifs_histories[part].append({
        "role": role,
        "text": text,
    })

# ==============================================================================
# PRIVATE HELPERS
# ==============================================================================


def _set_default(key: str, value) -> None:
    """Setzt einen Key nur, wenn er noch nicht existiert."""
    if key not in st.session_state:
        st.session_state[key] = value
