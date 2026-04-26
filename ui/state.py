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

# ==============================================================================
# PRIVATE HELPERS
# ==============================================================================


def _set_default(key: str, value) -> None:
    """Setzt einen Key nur, wenn er noch nicht existiert."""
    if key not in st.session_state:
        st.session_state[key] = value
