# ui/session_stats.py — HRE v51
# Zuständig für: Token-Statistik-Anzeige in der Sidebar
#
# ARCHITEKTUR-REGEL:
# Liest session_state — schreibt nie.
# Einzige erlaubte Schreibinstanz: ui/state.py

import streamlit as st


def render_session_stats() -> None:
    """
    Zeigt Token-Statistik der aktuellen Session in der Sidebar.
    Liest ausschließlich aus st.session_state.call_stats (read-only).
    Zeigt Fallback-Caption wenn noch keine Calls stattfanden.
    """
    st.header("📊 Session Stats")

    call_stats = st.session_state.get("call_stats", [])

    if call_stats:
        total_calls = len(call_stats)
        total_prompt = sum(s.get("prompt_tokens") or 0 for s in call_stats)
        total_comp = sum(s.get("completion_tokens") or 0 for s in call_stats)

        col1, col2 = st.columns([1, 2.5])
        col1.metric("Calls", total_calls)
        col2.metric("Tokens (In/Out)", f"{total_prompt} / {total_comp}")
    else:
        st.caption("Noch keine API-Calls in dieser Session.")
