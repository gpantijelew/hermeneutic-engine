# ui/emergency_sidebar.py — HRE v52.1
# Zuständig für: Notfall-Eingriff-Block in der Sidebar
#
# ARCHITEKTUR-REGEL:
# State-Schreibzugriffe ausschließlich via ui/state.py.
# Liest history read-only — schreibt nur via state.pop_last_message().

import streamlit as st
import ui.state as state
from modules.database import get_db_connection


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
    last_role = last_msg.get("role", "???")
    last_text = last_msg.get("parts", [{}])[0].get("text", "")
    last_msg_id = last_msg.get("id")  # Phase 6.5: ID der letzten Nachricht

    st.caption(f"Status: Letzte Nachricht von **{last_role.upper()}**")

    with st.expander("Inhalt prüfen"):
        st.text(f"Länge: {len(last_text)} Zeichen")
        st.code(last_text[:100])

    if st.button(
        "💀 Letztes Element löschen (Force)", key="sidebar_force_delete", type="primary"
    ):
        # 1. DB-Bereinigung — NUR noch über die exakte ID (Phase 6.5 Fix)
        if last_msg_id:
            try:
                from modules.database import delete_message_by_id
                delete_message_by_id(last_msg_id)
                logger.info(f"🗑️ Emergency Delete: Nachricht {last_msg_id} aus DB gelöscht.")
            except Exception as e:
                st.warning(f"DB-Löschung fehlgeschlagen: {e}")
        else:
            # Fallback für sehr alte Nachrichten ohne ID
            try:
                if st.session_state.chat_id:
                    db = get_db_connection()
                    db.execute(
                        """
                        DELETE FROM messages WHERE id IN (
                            SELECT id FROM messages WHERE chat_id = ?
                            ORDER BY timestamp DESC LIMIT 1
                        )
                    """,
                        (st.session_state.chat_id,),
                    )
                    db.commit()
            except Exception as e:
                st.warning(f"DB-Löschung (Fallback) fehlgeschlagen: {e}")

        # 2. State-Bereinigung via ui/state.py
        state.pop_last_message()
        st.session_state.last_error = None
        st.rerun()