# ui/settings_panel.py — HRE v51
# Zuständig für: Modelleinstellungen-Expander in der Sidebar
#
# ARCHITEKTUR-REGEL:
# Liest und schreibt session_state NUR via ui/state.py-kompatible
# Wege — direktes Schreiben auf global_settings hier erlaubt,
# da settings_panel der einzige autorisierte Schreiber für diesen Key ist.

import time
import streamlit as st

from modules.config import LLM_BACKEND, LM_STUDIO_MODEL, VERTEX_MODEL
from modules.database import save_global_settings


def render_settings_panel() -> None:
    """
    Rendert den Modelleinstellungen-Expander in der Sidebar.
    Liest aus st.session_state.global_settings.
    Schreibt zurück via save_global_settings() + session_state update.
    """
    with st.expander("⚙️ Modelleinstellungen", expanded=False):
        st.caption("Globale Einstellungen für neue Chats")

        # --- Backend-spezifische Modell-Anzeige ---
        if LLM_BACKEND == "vertex":
            current_model = VERTEX_MODEL
            available_models = [
                "gemini-3.1-pro-preview",
                "gemini-2.5-pro",
                "gemini-2.5-flash-preview-09-2025"
            ]
            selected_model = st.selectbox(
                "Gemini-Modell wählen:",
                options=available_models,
                index=available_models.index(current_model)
                      if current_model in available_models else 0
            )
        else:
            current_model = LM_STUDIO_MODEL
            st.info(
                f"🤖 Aktives Modell: **{current_model}** (via LM Studio)\n"
                f"Modell wechseln: `LM_STUDIO_MODEL` in `.env` anpassen."
            )
            selected_model = current_model

        # --- Slider ---
        temp = st.slider(
            "Temperature", 0.0, 1.0,
            st.session_state.global_settings.get('temperature', 0.2), 0.1
        )
        top_p = st.slider(
            "Top-P", 0.0, 1.0,
            st.session_state.global_settings.get('top_p', 0.95), 0.05
        )

        # --- Google Search (nur Vertex) ---
        if LLM_BACKEND == "vertex":
            use_search = st.checkbox(
                "🔍 Google Search aktivieren",
                value=st.session_state.global_settings.get('use_search', True)
            )
        else:
            use_search = False

        # --- Debug ---
        debug_mode = st.checkbox(
            "🐛 Debug-Modus",
            value=st.session_state.global_settings.get('debug_mode', False)
        )

        # --- System Instruction ---
        sys_instr = st.text_area(
            "System Instruction",
            st.session_state.global_settings.get('system_instruction', ''),
            height=250
        )

        # --- Speichern ---
        if st.button("💾 Einstellungen speichern", use_container_width=True):
            st.session_state.global_settings['model_name']         = selected_model
            st.session_state.global_settings['temperature']        = temp
            st.session_state.global_settings['top_p']              = top_p
            st.session_state.global_settings['system_instruction'] = sys_instr
            st.session_state.global_settings['use_search']         = use_search
            st.session_state.global_settings['debug_mode']         = debug_mode

            if save_global_settings(
                selected_model, temp, top_p, sys_instr, use_search, debug_mode
            ):
                st.success("✓ Gespeichert!")
                time.sleep(1)
                st.rerun()