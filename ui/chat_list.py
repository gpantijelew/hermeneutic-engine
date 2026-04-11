# ui/chat_list.py — HRE v51
# Zuständig für: Chat-Liste + Neuer-Chat-Button + Suchleiste in der Sidebar
#
# ARCHITEKTUR-REGEL:
# State-Schreibzugriffe ausschließlich via ui/state.py.
# Kein direktes st.session_state-Schreiben außer für UI-interne
# Keys (rename_chat_id, delete_confirm_id) die keinen eigenen Setter haben.

import streamlit as st

import ui.state as state
from modules.database import (
    get_chat_list,
    load_chat_history,
    rename_chat,
    delete_chat,
    search_chats_by_content,
    rebuild_fts_index,
)


# --- Cache-Hygiene (lokaler Wrapper) ---
@st.cache_data(ttl=600)
def _get_cached_chat_list():
    """Gecachte Chat-Liste. Nur über clear_chat_cache() invalidieren."""
    return get_chat_list()


def clear_chat_cache() -> None:
    """Öffentliche Schnittstelle für app.py und andere Module."""
    _get_cached_chat_list.clear()


def render_chat_list() -> None:
    """
    Rendert Neuer-Chat-Button, Suchleiste und Chat-Liste in der Sidebar.

    Grigoris Anforderungen:
    - Suchleiste: filtert Chat-Titel in Python (kein DB-Query nötig bei
      typischer Korpusgröße; bei >10.000 Chats auf DB-Query umstellen).
    - Atomare Klicks: State-Update ausschließlich via state.set_chat(),
      kein zweistufiges Rerun-Muster mehr.
    """
    st.header("💬 Konversationen")

    # --- Neuer Chat ---
    if st.button("➕ Neuer Chat", use_container_width=True, type="primary"):
        state.reset_chat()
        clear_chat_cache()
        st.rerun()

    # --- Suchleiste (Grigoris Feature-Request) ---
    search_term = st.text_input(
        "🔍 Chats durchsuchen",
        value="",
        placeholder="Titel oder Stichwort...",
        label_visibility="collapsed",
        key="chat_list_search"
    )

    # --- Liste laden + filtern ---
    chat_list = _get_cached_chat_list()

    # Aktualisieren-Button
    col_refresh, _ = st.columns([1, 4])
    if col_refresh.button("🔄", help="Liste aktualisieren", key="refresh_chat_list"):
        clear_chat_cache()
        st.rerun()

    if search_term:
        fts_results = search_chats_by_content(search_term)
        if fts_results:
            chat_list = fts_results
            st.caption(f"🔍 Volltext: {len(fts_results)} Treffer für '{search_term}'")
        else:
            # Fallback: Titel-Filter
            term_lower = search_term.lower()
            chat_list = [c for c in chat_list if term_lower in c['title'].lower()]
            if chat_list:
                st.caption(f"📋 Titel-Treffer: {len(chat_list)}")

    if not chat_list:
        if search_term:
            st.caption("Keine Treffer. FTS-Index aktuell?")
            if st.button("🔧 FTS-Index neu aufbauen", key="rebuild_fts"):
                with st.spinner("Indiziere..."):
                    n = rebuild_fts_index()
                st.success(f"✅ {n} Einträge indiziert.")
                st.rerun()
        else:
            st.caption("Noch keine Chats.")
        return

    # --- Chat-Einträge rendern ---
    for chat in chat_list:
        is_active = (st.session_state.chat_id == chat['id'])
        _render_chat_entry(chat, is_active)


def _render_chat_entry(chat: dict, is_active: bool) -> None:
    """Rendert einen einzelnen Chat-Eintrag (Normal / Umbenennen / Löschen)."""

    with st.container():

        # FALL A: UMBENENNEN
        if st.session_state.get("rename_chat_id") == chat['id']:
            new_name = st.text_input(
                "Neuer Name:",
                value=chat['title'],
                key=f"rename_input_{chat['id']}",
                label_visibility="collapsed"
            )
            c1, c2 = st.columns(2)
            if c1.button("✓", key=f"save_{chat['id']}", use_container_width=True):
                if rename_chat(chat['id'], new_name.strip()):
                    st.session_state.rename_chat_id = None
                    clear_chat_cache()
                    st.rerun()
            if c2.button("✗", key=f"cancel_{chat['id']}", use_container_width=True):
                st.session_state.rename_chat_id = None
                st.rerun()

        # FALL B: LÖSCHEN BESTÄTIGEN
        elif st.session_state.get("delete_confirm_id") == chat['id']:
            st.warning(f"**{chat['title']}** wirklich löschen?")
            c1, c2 = st.columns(2)
            if c1.button(
                "Ja, löschen", key=f"confirm_del_{chat['id']}",
                use_container_width=True, type="primary"
            ):
                if delete_chat(chat['id']):
                    if st.session_state.chat_id == chat['id']:
                        state.reset_chat()
                    st.session_state.delete_confirm_id = None
                    clear_chat_cache()
                    st.rerun()
            if c2.button("Nein", key=f"cancel_del_{chat['id']}", use_container_width=True):
                st.session_state.delete_confirm_id = None
                st.rerun()

        # FALL C: NORMALE ANZEIGE
        else:
            cols = st.columns([6, 1, 1])

            # Atomarer Klick-Handler (Grigoris Bug-Fix):
            # state.set_chat() schreibt alle Keys in einem Zug —
            # kein zweistufiges Update, keine Race Condition.
            if cols[0].button(
                chat['title'],
                key=f"load_{chat['id']}",
                use_container_width=True,
                type="primary" if is_active else "secondary"
            ):
                state.set_chat(
                    chat['id'],
                    load_chat_history(chat['id'])
                )
                st.rerun()

            if cols[1].button("✏️", key=f"edit_{chat['id']}", help="Umbenennen"):
                st.session_state.rename_chat_id = chat['id']
                st.rerun()

            if cols[2].button("🗑️", key=f"delete_{chat['id']}", help="Löschen"):
                st.session_state.delete_confirm_id = chat['id']
                st.rerun()