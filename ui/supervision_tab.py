import streamlit as st
import ui.state as state
from modules.database import get_chat_list, load_chat_history
from modules.citation_rag import CitationRAG

def render_supervision_tab():
    st.header("🧑‍⚖️ IFS Supervisions-Panel")
    st.markdown("""
    Dieser Modus analysiert einen kompletten Chat als psychologisches System. 
    Zwei Agenten (Manager-Fokus & Exile-Fokus) untersuchen den Text parallel. 
    Ein Tribunal-Agent bewertet anschließend die Meta-Dynamik.
    """)

    # Chats laden (KORRIGIERT)
    all_chats = get_chat_list()

    if not all_chats:
        st.info("Keine Chats in der Datenbank gefunden.")
        return

    # Chat Auswahl
    chat_options = {chat['id']: chat['title'] for chat in all_chats}
    selected_chat_id = st.selectbox(
        "Wähle einen Chat für die Supervision:",
        options=list(chat_options.keys()),
        format_func=lambda x: chat_options[x]
    )

    if st.button("🚀 Supervision starten", type="primary"):
        # Lade Chat-Historie (KORRIGIERT)
        history = load_chat_history(selected_chat_id)
        if not history:
            st.warning("Dieser Chat ist leer.")
            return

        # Formatiere Chat als Text
        parts = []
        for msg in history:
            role = msg.get("role", "unknown")
            text = msg.get("parts", [{}])[0].get("text", "")
            if text.strip():
                parts.append(f"[{role.upper()}]\n{text.strip()}")
        chat_text = "\n\n".join(parts)

        with st.status("Führe psychosystemische Analyse durch...", expanded=True) as status:
            st.write("Starte Map-Reduce Pipeline (Manager & Exile parallel)...")
            try:
                # Aufruf der neuen Pipeline
                rag = CitationRAG()
                results = rag.generate_ifs_supervision(chat_text)
                status.update(label="Supervision erfolgreich abgeschlossen!", state="complete", expanded=False)

                # Ergebnisse im State speichern, damit sie beim Tab-Wechsel bleiben
                state.set_supervision_result(results, chat_options[selected_chat_id])
            except Exception as e:
                status.update(label="Fehler bei der Supervision", state="error")
                st.error(f"Pipeline-Fehler: {e}")
                import traceback
                st.code(traceback.format_exc())
                return

    # Ergebnisse anzeigen
    res, chat_title = state.get_supervision_result()
    if res:
        st.subheader("📋 Meta-Gutachten (System-Dynamik)")
        st.info(res["meta"])

        st.markdown("---")
        st.subheader("🔍 Fachgutachten")

        col1, col2 = st.columns(2)
        with col1:
            with st.expander("🛡️ Struktur-Analyse (Manager)", expanded=True):
                st.write(res["manager"])
        with col2:
            with st.expander("🌋 Tiefen-Analyse (Exile)", expanded=True):
                st.write(res["exile"])

        # Export
        st.markdown("---")
        export_text = f"# IFS Supervision: {st.session_state.last_supervision_chat}\n\n"
        export_text += f"## Meta-Gutachten\n{res['meta']}\n\n"
        export_text += f"## Struktur-Analyse (Manager)\n{res['manager']}\n\n"
        export_text += f"## Tiefen-Analyse (Exile)\n{res['exile']}\n"

        st.download_button(
            label="📥 Gutachten als Markdown exportieren",
            data=export_text,
            file_name="ifs_supervision_gutachten.md",
            mime="text/markdown"
        )