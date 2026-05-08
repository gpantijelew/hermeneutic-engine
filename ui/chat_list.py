# ui/chat_list.py — HRE v54
# Zuständig für: Chat-Liste + Neuer-Chat-Button + Suchleiste in der Sidebar
#
# ARCHITEKTUR-REGEL:
# State-Schreibzugriffe ausschließlich via ui/state.py.
# Kein direktes st.session_state-Schreiben außer für UI-interne
# Keys (rename_chat_id, delete_confirm_id) die keinen eigenen Setter haben.

import datetime

import streamlit as st

import ui.state as state
from modules.database import (
    get_chat_list,
    load_chat_history,
    rename_chat,
    delete_chat,
    search_chats_by_content,
    search_chats_by_title,
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


# --- Phase 4.3: Sidebar UX — Relative Zeit-Gruppierung ---

def _parse_chat_date(chat: dict) -> datetime.date:
    """Parst lastUpdated (ISO-String) zu date, robust bei Fehlern."""
    raw = chat.get("lastUpdated", "")
    try:
        # ISO-Format: 2026-05-04T09:11:00 → bis 'T' abschneiden
        date_part = raw.split("T")[0] if "T" in raw else raw[:10]
        return datetime.datetime.strptime(date_part, "%Y-%m-%d").date()
    except Exception:
        return datetime.date.min


def _group_chats_by_relative_time(chat_list: list) -> dict:
    """Gruppiert Chats nach relativer Zeit: Heute, Gestern, Letzte 7 Tage, Älter."""
    today = datetime.date.today()
    groups = {
        "Heute": [],
        "Gestern": [],
        "Letzte 7 Tage": [],
        "Älter": [],
    }
    for chat in chat_list:
        chat_date = _parse_chat_date(chat)
        delta = (today - chat_date).days
        if delta == 0:
            groups["Heute"].append(chat)
        elif delta == 1:
            groups["Gestern"].append(chat)
        elif 2 <= delta <= 7:
            groups["Letzte 7 Tage"].append(chat)
        else:
            groups["Älter"].append(chat)
    return {k: v for k, v in groups.items() if v}


def _format_chat_caption(chat: dict) -> str:
    """Baut die Caption-Zeile: Datum + Chunk-Count (auch 0 = noch nicht indexiert)."""
    raw = chat.get("lastUpdated", "")
    if raw:
        try:
            # ISO-Format parsen und als deutsches Format ausgeben
            date_part = raw.split("T")[0] if "T" in raw else raw[:10]
            parsed_date = datetime.datetime.strptime(date_part, "%Y-%m-%d")
            date_str = parsed_date.strftime("%d.%m.%Y")
        except Exception:
            date_str = raw[:10]  # Fallback auf Original
    else:
        date_str = "—"
    chunk_count = chat.get("chunk_count", 0)
    return f"📅 {date_str}  •  {chunk_count} Chunks"


def render_chat_list() -> None:
    """
    Rendert Neuer-Chat-Button, Suchleiste und Chat-Liste in der Sidebar.
    Phase 4.3: Relative Zeit-Gruppierung, Chunk-Count-Badge, Lazy-Load.
    """
    st.header("💬 Konversationen")

    # --- Neuer Chat ---
    if st.button("➕ Neuer Chat", width="stretch", type="primary"):
        state.reset_chat()
        state.reset_sidebar_offset()
        clear_chat_cache()
        st.rerun()

    # --- Suchleiste + Suchmodus ---
    search_term = st.text_input(
        "🔍 Chats durchsuchen",
        value="",
        placeholder="Titel oder Stichwort...",
        label_visibility="collapsed",
        key="chat_list_search",
    )

    search_mode = st.radio(
        "Suchmodus",
        ["Inhalt", "Titel", "Beides"],
        horizontal=True,
        label_visibility="collapsed",
        key="sidebar_search_mode",
    )

    # --- Liste laden + filtern ---
    chat_list = _get_cached_chat_list()

    # Aktualisieren-Button
    col_refresh, _ = st.columns([1, 4])
    if col_refresh.button("🔄", help="Liste aktualisieren", key="refresh_chat_list"):
        clear_chat_cache()
        state.reset_sidebar_offset()
        st.rerun()

    if search_term:
        if search_mode == "Inhalt":
            fts_results = search_chats_by_content(search_term)
            label = "Inhalt"
        elif search_mode == "Titel":
            fts_results = search_chats_by_title(search_term)
            label = "Titel"
        else:  # Beides
            content_results = search_chats_by_content(search_term)
            title_results = search_chats_by_title(search_term)
            seen = set()
            fts_results = []
            for r in title_results + content_results:
                if r["id"] not in seen:
                    seen.add(r["id"])
                    fts_results.append(r)
            label = "Beides"

        if fts_results:
            chat_list = fts_results
            st.caption(f"🔍 {label}: {len(fts_results)} Treffer für '{search_term}'")
        else:
            term_lower = search_term.lower()
            chat_list = [c for c in chat_list if term_lower in c["title"].lower()]
            if chat_list:
                st.caption(f"📋 Titel-Treffer: {len(chat_list)}")
        # Bei Suche: alle Treffer zeigen, Pagination zurücksetzen
        state.reset_sidebar_offset()

    if not chat_list:
        if search_term:
            st.caption("Keine Treffer. FTS-Index aktuell?")
            if st.button("🔧 FTS-Index neu aufbauen", key="rebuild_fts"):
                with st.spinner("Indiziere..."):
                    msg_n, chat_n = rebuild_fts_index()
                st.success(f"✅ {msg_n} Messages + {chat_n} Chats indiziert.")
                st.rerun()
        else:
            st.caption("Noch keine Chats.")
        return

    # --- Pagination (Lazy-Load) ---
    is_search = bool(search_term)
    offset = 0 if is_search else st.session_state.get("sidebar_offset", 0)
    page_size = st.session_state.get("sidebar_page_size", 50)

    if not is_search and len(chat_list) > page_size:
        visible_chats = chat_list[offset : offset + page_size]
    else:
        visible_chats = chat_list

    # --- Relative Zeit-Gruppierung ---
    groups = _group_chats_by_relative_time(visible_chats)

    for group_name, group_chats in groups.items():
        st.caption(f"— {group_name} —")
        for chat in group_chats:
            is_active = st.session_state.chat_id == chat["id"]
            _render_chat_entry(chat, is_active)

    # --- Lazy-Load: Ältere Chats ---
    if not is_search and len(chat_list) > offset + page_size:
        if st.button("📥 Ältere Chats laden...", key="load_more_chats"):
            state.increment_sidebar_offset()
            st.rerun()


def _render_chat_entry(chat: dict, is_active: bool) -> None:
    """Rendert einen einzelnen Chat-Eintrag (Normal / Umbenennen / Löschen)."""

    with st.container():
        # FALL A: UMBENENNEN
        if st.session_state.get("rename_chat_id") == chat["id"]:
            new_name = st.text_input(
                "Neuer Name:",
                value=chat["title"],
                key=f"rename_input_{chat['id']}",
                label_visibility="collapsed",
            )
            c1, c2 = st.columns(2)
            if c1.button("✓", key=f"save_{chat['id']}", width="stretch"):
                if rename_chat(chat["id"], new_name.strip()):
                    st.session_state.rename_chat_id = None
                    clear_chat_cache()
                    st.rerun()
            if c2.button("✗", key=f"cancel_{chat['id']}", width="stretch"):
                st.session_state.rename_chat_id = None
                st.rerun()

        # FALL B: LÖSCHEN BESTÄTIGEN
        elif st.session_state.get("delete_confirm_id") == chat["id"]:
            st.warning(f"**{chat['title']}** wirklich löschen?")
            c1, c2 = st.columns(2)
            if c1.button(
                "Ja, löschen",
                key=f"confirm_del_{chat['id']}",
                width="stretch",
                type="primary",
            ):
                if delete_chat(chat["id"]):
                    if st.session_state.chat_id == chat["id"]:
                        state.reset_chat()
                    st.session_state.delete_confirm_id = None
                    clear_chat_cache()
                    st.rerun()
            if c2.button(
                "Nein", key=f"cancel_del_{chat['id']}", width="stretch"
            ):
                st.session_state.delete_confirm_id = None
                st.rerun()

        # FALL C: NORMALE ANZEIGE
        else:
            cols = st.columns([6, 1, 1])

            if cols[0].button(
                chat["title"],
                key=f"load_{chat['id']}",
                width="stretch",
                type="primary" if is_active else "secondary",
            ):
                state.set_chat(chat["id"], load_chat_history(chat["id"]))
                st.rerun()

            if cols[1].button("✏️", key=f"edit_{chat['id']}", help="Umbenennen"):
                st.session_state.rename_chat_id = chat["id"]
                st.rerun()

            if cols[2].button("🗑️", key=f"delete_{chat['id']}", help="Löschen"):
                st.session_state.delete_confirm_id = chat["id"]
                st.rerun()

            # Phase 4.3: Datum + Chunk-Count Caption (flach, kein Expander)
            st.caption(_format_chat_caption(chat))
