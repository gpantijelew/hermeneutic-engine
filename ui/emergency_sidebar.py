# ui/emergency_sidebar.py — HRE v51
# Zuständig für: Notfall-Eingriff-Block in der Sidebar
#
# ARCHITEKTUR-REGEL:
# State-Schreibzugriffe ausschließlich via ui/state.py.
# Liest history read-only — schreibt nur via state.pop_last_message().

import streamlit as st
import ui.state as state
from modules.database import get_firestore_client


def render_emergency_sidebar() -> None:
    """
    Rendert den Notfall-Eingriff-Block in der Sidebar.
    Erlaubt das gezielte Löschen der letzten History-Nachricht
    bei hängenden oder fehlerhaften Modell-Antworten.
    """
    st.markdown("---")
    st.error("🚑 Notfall-Eingriff")

    if not st.session_state.get("history"):
        st.caption("History ist leer.")
        return

    last_msg = st.session_state.history[-1]
    last_role = last_msg.get('role', '???')
    last_text = last_msg.get('parts', [{}])[0].get('text', '')

    st.caption(f"Status: Letzte Nachricht von **{last_role.upper()}**")

    with st.expander("Inhalt prüfen"):
        st.text(f"Länge: {len(last_text)} Zeichen")
        st.code(last_text[:100])

    if st.button(
        "💀 Letztes Element löschen (Force)",
        key="sidebar_force_delete",
        type="primary"
    ):
        # 1. DB-Bereinigung (Versuch)
        try:
            if st.session_state.chat_id:
                db = get_firestore_client()
                db.execute("""
                    DELETE FROM messages WHERE id IN (
                        SELECT id FROM messages WHERE chat_id = ?
                        ORDER BY timestamp DESC LIMIT 1
                    )
                """, (st.session_state.chat_id,))
                db.commit()
        except Exception as e:
            print(f"DB Error: {e}")

        # 2. State-Bereinigung via ui/state.py
        state.pop_last_message()
        st.session_state.last_error = None
        st.rerun()