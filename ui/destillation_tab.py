# ui/destillation_tab.py — Mission E v2: Mode-Aware Best-of Synthese
import logging
from datetime import datetime

import streamlit as st

from modules.database import get_chat_list, load_chat_history
from modules.vector_store import LocalVectorStore
from modules.citation_rag import CitationRAG
from modules.config import MAX_TOKENS_STILISIERUNG, ENGINE_VERSION
from modules.stilistic_lab_pipeline import run_meta_vergleich, format_meta_vergleich_as_markdown

logger = logging.getLogger(__name__)

# ── Verfügbare Analyse-Modi ──
MODE_OPTIONS = {
    "STILISTIC": "Vergleichende Stil-Synthese (5-Kategorien-Befund)",
    "STILISTIC_DEEPENING": "Funktionale Interpretation der Befunde",
    "META_ANALYTICAL": "Methodologische Analyse der Analyse",
    "LITERARY": "Literarische Nuancen und Metaphorik",
    "STILISTIC_LAB": "Drei-Etappen-Pipeline (Python+LLM+Synthese)",
}


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
    """Rendert den Destillation-Tab für mode-aware Best-of-Synthese."""
    st.title("🔥 Destillation")

    # ── Modus-Wahl ──
    st.subheader("Destillations-Modus")
    destillation_mode = st.radio(
        "Wie sollen die Iterationen verarbeitet werden?",
        options=["best_of_stilistic", "generic", "meta_vergleich"],
        format_func=lambda x: {
            "best_of_stilistic": "🎭 Mode-Aware Best-of (Stil-Synthese aus Perspektiven)",
            "generic": "📝 Generisch (Meistertext aus Iterationen)",
            "meta_vergleich": "🔬 Meta-Vergleich (Methode & Leistung zweier Verfahren)",
        }[x],
        horizontal=True,
    )

    if destillation_mode == "best_of_stilistic":
        intent = "SYNTHESIS_BEST_OF_STILISTIC"
        st.caption(
            "Wähle mehrere Chat-Iterationen aus und weise ihnen Analyse-Modi zu. "
            "Die KI destilliert daraus den schärfsten Meistertext."
        )
    elif destillation_mode == "meta_vergleich":
        intent = "META_VERGLEICH"
        st.caption(
            "Vergleiche Methode und Leistung zweier analytischer Verfahren. "
            "Zwei Seiten mit editierbaren Labels — je aus DB oder Freitext."
        )
    else:
        intent = "SYNTHESIS_BEST_OF"
        st.caption(
            "Wähle mehrere Chat-Iterationen aus. Die KI destilliert daraus einen fließenden Meistertext."
        )

    # ── Meta-Vergleich: Eigene UI ──
    if destillation_mode == "meta_vergleich":
        _render_meta_vergleich_ui()
        return

    # ── Best-of / Generic: Chat-Auswahl-UI ──
    all_chats = get_chat_list()
    chat_options = {c["title"]: c["id"] for c in all_chats}

    if not chat_options:
        st.warning("Keine Chats verfügbar. Bitte zuerst Chats importieren oder erstellen.")
        return

    # ── Chat-Auswahl ──
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

    # ── Modus-Zuweisung (nur bei best_of_stilistic) ──
    mode_labels = {}
    if destillation_mode == "best_of_stilistic":
        st.markdown("---")
        st.subheader("🏷️ Modus-Zuweisung")
        st.caption("Weise jedem Chat seinen Analyse-Modus zu.")

        mode_keys = list(MODE_OPTIONS.keys())
        for i, title in enumerate(selected_titles):
            default_mode = mode_keys[min(i, len(mode_keys) - 1)]
            selected_mode = st.selectbox(
                f"**{title}**",
                options=mode_keys,
                index=mode_keys.index(default_mode),
                format_func=lambda x: f"{x} — {MODE_OPTIONS[x]}",
                key=f"mode_{i}_{title[:20]}",
            )
            mode_labels[title] = selected_mode

    # ── Vorschau ──
    with st.expander("📄 Vorschau der ausgewählten Iterationen"):
        for title in selected_titles:
            chat_id = chat_options[title]
            text = _extract_full_text(chat_id)
            mode_tag = f" [{mode_labels[title]}]" if title in mode_labels else ""
            st.markdown(f"**{title}**{mode_tag} ({len(text)} Zeichen)")
            st.text(text[:500] + ("..." if len(text) > 500 else ""))

    source_label = selected_titles
    button_label = "🔥 Destillieren"
    spinner_text = "Destillation läuft..."
    result_header = "Destillation: Best-of Stil-Synthese" if destillation_mode == "best_of_stilistic" else "Destillation: Best-of Synthese"

    def _get_texts():
        texts = [_extract_full_text(chat_options[t]) for t in selected_titles]
        texts = [t for t in texts if t.strip()]
        if not texts:
            st.error("❌ Alle ausgewählten Chats sind leer.")
            return None
        return texts

    # ── Ausführungs-Button ──
    if st.button(button_label, type="primary"):
        iteration_texts = _get_texts()
        if iteration_texts is None:
            return

        with st.spinner(spinner_text):
            try:
                rag = CitationRAG()

                # Mode-Labels als geordnetes Dict (nur bei best_of_stilistic)
                labels = None
                if destillation_mode == "best_of_stilistic" and mode_labels:
                    labels = {i + 1: mode_labels[t] for i, t in enumerate(selected_titles) if t in mode_labels}

                result = rag.generate_synthesis_best_of(
                    iteration_texts,
                    intent=intent,
                    mode_labels=labels,
                )

                st.session_state["destillation_result"] = result
                st.session_state["destillation_timestamp"] = datetime.now().isoformat()
                st.session_state["destillation_sources"] = source_label
                st.session_state["destillation_mode"] = destillation_mode

                st.success("✅ Destillation abgeschlossen!")

            except Exception as e:
                logger.error(f"Destillation Fehler: {e}")
                st.error(f"❌ Fehler bei der Destillation: {e}")

    # ── Ergebnis-Anzeige ──
    if st.session_state.get("destillation_result"):
        st.markdown("---")
        st.subheader("📝 Ergebnis — Destillation")
        st.markdown(st.session_state["destillation_result"])

        # ── In Stilisierung übernehmen ──
        if st.button("🎭 In Stilisierung übernehmen", key="to_stilisierung"):
            st.session_state["stilisierung_input"] = st.session_state["destillation_result"]
            st.info("📋 Ergebnis wurde in die Stilisierungs-Eingabe kopiert. Wechsel zum 🎭 Stilisierung-Tab.")

        # ── Markdown-Download ──
        sources = st.session_state.get("destillation_sources", [])
        ts = st.session_state.get("destillation_timestamp", "")
        dmode = st.session_state.get("destillation_mode", "generic")
        mode_tag = " Mode-Aware" if dmode == "best_of_stilistic" else ""
        header = f"""---
{result_header}
Quellen: {', '.join(sources)}
Modus: {dmode}{mode_tag}
Erstellt: {ts}
Engine: HRE {ENGINE_VERSION}
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


def _render_meta_vergleich_ui() -> None:
    """Rendert die UI für den Meta-Vergleich-Modus."""
    st.markdown("---")
    st.subheader("🔬 Zwei-Seiten-Vergleich")

    # ── Labels ──
    col_l1, col_l2 = st.columns(2)
    with col_l1:
        label_a = st.text_input("Label Seite A", value="Tynjanow", key="mv_label_a")
    with col_l2:
        label_b = st.text_input("Label Seite B", value="HRE", key="mv_label_b")

    # ── Quellen für jede Seite ──
    all_chats = get_chat_list()
    chat_options = {c["title"]: c["id"] for c in all_chats}

    text_a = ""
    text_b = ""

    # ── Seite A ──
    st.markdown(f"**Seite A: {label_a}**")
    source_a = st.radio(
        f"Quelle für {label_a}:",
        options=["Freitext", "Aus Datenbank"],
        key="mv_source_a",
        horizontal=True,
    )
    if source_a == "Aus Datenbank" and chat_options:
        selected_a = st.selectbox(
            f"Chat für {label_a}:",
            options=list(chat_options.keys()),
            key="mv_chat_a",
        )
        text_a = _extract_full_text(chat_options[selected_a])
        with st.expander(f"📄 Vorschau {label_a}"):
            st.text(text_a[:500] + ("..." if len(text_a) > 500 else ""))
    else:
        text_a = st.text_area(
            f"Text für {label_a}:",
            height=200,
            key="mv_text_a",
            help="Füge den analytischen Text hier ein.",
        )

    # ── Seite B ──
    st.markdown(f"**Seite B: {label_b}**")
    source_b = st.radio(
        f"Quelle für {label_b}:",
        options=["Freitext", "Aus Datenbank"],
        key="mv_source_b",
        horizontal=True,
    )
    if source_b == "Aus Datenbank" and chat_options:
        selected_b = st.selectbox(
            f"Chat für {label_b}:",
            options=list(chat_options.keys()),
            key="mv_chat_b",
        )
        text_b = _extract_full_text(chat_options[selected_b])
        with st.expander(f"📄 Vorschau {label_b}"):
            st.text(text_b[:500] + ("..." if len(text_b) > 500 else ""))
    else:
        text_b = st.text_area(
            f"Text für {label_b}:",
            height=200,
            key="mv_text_b",
            help="Füge den analytischen Text hier ein.",
        )

    # ── Optionale Frage ──
    user_question = st.text_input(
        "Optionale Frage (als Zusatz zur Vergleichs-Aufgabe):",
        key="mv_question",
        help="Leer lassen für Standard-5-Achsen-Vergleich.",
    )

    # ── Ausführungs-Button ──
    if st.button("🔬 Meta-Vergleich starten", type="primary"):
        if not text_a.strip() or not text_b.strip():
            st.error("❌ Beide Seiten müssen Text enthalten.")
            return

        with st.spinner("Meta-Vergleich läuft..."):
            try:
                result = run_meta_vergleich(
                    text_a=text_a,
                    label_a=label_a,
                    text_b=text_b,
                    label_b=label_b,
                    user_question=user_question,
                )

                st.session_state["destillation_result"] = result.get("vergleich", "")
                st.session_state["destillation_timestamp"] = datetime.now().isoformat()
                st.session_state["destillation_sources"] = [label_a, label_b]
                st.session_state["destillation_mode"] = "meta_vergleich"
                st.session_state["meta_vergleich_result"] = result

                st.success("✅ Meta-Vergleich abgeschlossen!")

            except Exception as e:
                logger.error(f"Meta-Vergleich Fehler: {e}")
                st.error(f"❌ Fehler beim Meta-Vergleich: {e}")

    # ── Ergebnis-Anzeige ──
    if st.session_state.get("destillation_result") and st.session_state.get("destillation_mode") == "meta_vergleich":
        st.markdown("---")
        st.subheader("📝 Ergebnis — Meta-Vergleich")
        st.markdown(st.session_state["destillation_result"])

        # ── Markdown-Download ──
        mv_result = st.session_state.get("meta_vergleich_result", {})
        md_content = format_meta_vergleich_as_markdown(mv_result)
        ts = st.session_state.get("destillation_timestamp", "")
        file_name = f"MetaVergleich_{datetime.now().strftime('%H%M')}.md"

        st.download_button(
            label="💾 Download als Markdown",
            data=md_content,
            file_name=file_name,
            mime="text/markdown",
            key="meta_vergleich_download",
        )
