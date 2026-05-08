# ui/destillation_tab.py — Mission E v1: Best-of Synthese
import logging
from datetime import datetime

import streamlit as st

from modules.database import get_chat_list, load_chat_history
from modules.vector_store import LocalVectorStore
from modules.citation_rag import CitationRAG

logger = logging.getLogger(__name__)


def _extract_full_text(chat_id: str) -> str:
    """Holt alle User+Model Nachrichten eines Chats als zusammenhängenden Text."""
    history = load_chat_history(chat_id)
    parts = []
    for msg in history:
        role = msg.get("role", "unknown")
        text = msg.get("parts", [{}])[0].get("text", "")
        if text.strip():
            parts.append(f"[{role.upper()}]\n{text.strip()}")
    return "\n\n".join(parts)


def render_destillation_tab() -> None:
    """Rendert den Destillation-Tab für Best-of-Synthese."""
    st.title("🔥 Destillation")

    intent = "SYNTHESIS_BEST_OF"
    st.caption(
        "Wähle mehrere Chat-Iterationen aus. Die KI destilliert daraus einen fließenden Meistertext."
    )

    all_chats = get_chat_list()
    chat_options = {c["title"]: c["id"] for c in all_chats}

    if not chat_options:
        st.warning("Keine Chats verfügbar. Bitte zuerst Chats importieren oder erstellen.")
        return

    selected_titles = st.multiselect(
        "Iterationen (Chats) auswählen:",
        options=list(chat_options.keys()),
        help="Wähle 2–5 Chats, deren Inhalte zu einem Meistertext verschmolzen werden.",
    )

    if not selected_titles:
        st.info("⬆️ Wähle mindestens einen Chat aus, um zu beginnen.")
        return

    if len(selected_titles) > 5:
        st.warning("⚠️ Empfohlen: maximal 5 Chats für beste Qualität.")

    with st.expander("📄 Vorschau der ausgewählten Iterationen"):
        for title in selected_titles:
            chat_id = chat_options[title]
            text = _extract_full_text(chat_id)
            st.markdown(f"**{title}** ({len(text)} Zeichen)")
            st.text(text[:500] + ("..." if len(text) > 500 else ""))

    source_label = selected_titles
    button_label = "🔥 Destillieren"
    spinner_text = "Destillation läuft..."
    result_header = "Destillation: Best-of Synthese"

    def _get_texts():
        texts = [_extract_full_text(chat_options[t]) for t in selected_titles]
        texts = [t for t in texts if t.strip()]
        if not texts:
            st.error("❌ Alle ausgewählten Chats sind leer.")
            return None
        return texts

    # --- Ausführungs-Button ---
    if st.button(button_label, type="primary"):
        iteration_texts = _get_texts()
        if iteration_texts is None:
            return

        with st.spinner(spinner_text):
            try:
                rag = CitationRAG()
                result = rag.generate_synthesis_best_of(
                    iteration_texts,
                    intent=intent,
                )

                st.session_state["destillation_result"] = result
                st.session_state["destillation_timestamp"] = datetime.now().isoformat()
                st.session_state["destillation_sources"] = source_label

                st.success("✅ Destillation abgeschlossen!")

            except Exception as e:
                logger.error(f"Destillation Fehler: {e}")
                st.error(f"❌ Fehler bei der Destillation: {e}")

    # --- Ergebnis-Anzeige ---
    if st.session_state.get("destillation_result"):
        st.markdown("---")
        st.subheader("📝 Ergebnis — Destillation")
        st.markdown(st.session_state["destillation_result"])

        # --- In Stilisierung übernehmen ---
        if st.button("🎭 In Stilisierung übernehmen", width="stretch"):
            st.session_state["stilisierung_input"] = st.session_state["destillation_result"]
            st.info("📋 Ergebnis wurde in die Stilisierungs-Eingabe kopiert. Wechsel zum 🎭 Stilisierung-Tab.")

        # --- Markdown-Download ---
        sources = st.session_state.get("destillation_sources", [])
        ts = st.session_state.get("destillation_timestamp", "")
        header = f"""---
{result_header}
Quellen: {', '.join(sources)}
Erstellt: {ts}
Engine: HRE v52
---

"""
        markdown = header + st.session_state["destillation_result"]
        file_name = f"Destillation_{datetime.now().strftime('%H%M')}.md"

        st.download_button(
            label="💾 Download als Markdown",
            data=markdown,
            file_name=file_name,
            mime="text/markdown",
            key="destillation_download",
        )
