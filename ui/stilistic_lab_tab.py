"""ui/stilistic_lab_tab.py — STILISTIC LAB Tab (v57.5.1)

Drei-Etappen-Architektur:
  Etappe 1: SEZIEREN (Python) — deterministische Textstatistiken
  Etappe 2+3: BEOBACHTEN + FREIER RAUM (LLM, pro Quelle)
  Globale Synthese: Vergleichende Stilbeobachtung (LLM)

v57.5.1: Fix A (Individual-Stats im Export) + Fix C (Frage nur in Synthese).
v57.5.1: user_question-Feld, use_container_width→width='stretch', NS-Fix.
v57.4.5: use_container_width→width='stretch', NS-Fix text_analyzer.
"""

import logging
from datetime import datetime

import streamlit as st

from modules.database import get_chat_list, get_raw_chat_messages
from modules.stilistic_lab_pipeline import run_stilistic_lab, format_result_as_markdown

logger = logging.getLogger(__name__)


def _load_chat_text(chat_id: str) -> str:
    """Laedt den Text eines Chats aus der DB.

    Strategie: user-Nachrichten zuerst (enthaelt meist den Quelltext),
    Fallback auf alle Nachrichten.
    """
    messages = get_raw_chat_messages(chat_id)
    if not messages:
        return ""

    # Nur user-Nachrichten (Quelltext)
    user_parts = []
    for msg in messages:
        content = msg.get("content")
        role = msg.get("role", "")
        if content and role == "user":
            user_parts.append(str(content).strip())

    if user_parts:
        return "\n\n".join(user_parts)

    # Fallback: alle mit Inhalt
    all_parts = []
    for msg in messages:
        content = msg.get("content")
        if content:
            all_parts.append(str(content).strip())

    return "\n\n".join(all_parts) if all_parts else ""


def render_stilistic_lab_tab():
    """Render den STILISTIC LAB Tab."""

    st.header("Stilistic Lab")
    st.caption(
        "Drei-Etappen-Architektur: Sezieren -> Einordnen -> Freier Raum. "
        "Python zaehlt, LLM charakterisiert auf Faktenbasis. "
        "Keine Annahmen ohne Code-Beweis."
    )

    # --- DB-Optionen (einmalig laden) ---
    all_chats = get_chat_list()
    chat_options = {}
    if all_chats:
        all_chats_sorted = sorted(all_chats, key=lambda x: x["title"].lower())
        chat_options = {c["title"]: c["id"] for c in all_chats_sorted}

    # --- Quellen-Eingabe ---
    st.subheader("Quellen")

    num_sources = st.number_input(
        "Anzahl Quellen",
        min_value=2,
        max_value=8,
        value=2,
        step=1,
    )

    source_texts = {}

    for i in range(num_sources):
        # Zeile 1: Label + DB-Auswahl
        col_label, col_db = st.columns([1, 2])

        with col_label:
            label = st.text_input(
                "Label",
                value=f"QUELLE {i + 1}",
                key=f"sl_label_{i}",
                label_visibility="collapsed",
            )

        with col_db:
            if chat_options:
                db_options = ["--- aus DB laden ---"] + list(chat_options.keys())
                db_choice = st.selectbox(
                    "Aus DB",
                    options=db_options,
                    index=0,
                    key=f"sl_db_{i}",
                    label_visibility="collapsed",
                )

                # Wenn Auswahl geaendert -> Text in Session State laden
                last_loaded_key = f"sl_db_last_{i}"
                last_loaded = st.session_state.get(last_loaded_key, "")

                if db_choice != last_loaded and db_choice != db_options[0]:
                    chat_id = chat_options.get(db_choice)
                    if chat_id:
                        loaded = _load_chat_text(chat_id)
                        if loaded:
                            st.session_state[f"sl_text_{i}"] = loaded
                        else:
                            st.session_state[f"sl_text_{i}"] = ""
                    st.session_state[last_loaded_key] = db_choice

                # Wenn zurueck auf "---" -> Text loeschen
                if db_choice == db_options[0] and last_loaded != db_options[0]:
                    st.session_state[f"sl_text_{i}"] = ""
                    st.session_state[last_loaded_key] = db_choice
            else:
                st.caption("Keine DB-Dokumente")

        # Zeile 2: Text-Area
        text = st.text_area(
            label,
            height=250,
            key=f"sl_text_{i}",
            placeholder="Quelltext hier einfuegen (Copy & Paste) oder aus DB laden...",
        )

        if text and text.strip():
            source_texts[label] = text.strip()

        st.divider()

    # --- Frage / Ergaenzung (v57.5.1) ---
    st.subheader("Frage / Ergaenzung")
    st.caption("Wird nur in der Globalen Synthese beruecksichtigt, nicht in der Einzelanalyse.")
    user_question = st.text_area(
        "Optionale Frage, die in die Synthese injiziert wird",
        key="sl_user_question",
        placeholder=(
            "z.B. Identifiziere die stilistischen Affinitaeten zwischen "
            "Herzen und Lenin — jenseits der inhaltlichen Ebene. "
            "Was verbindet diese Autoren sprachlich?"
        ),
        height=80,
        label_visibility="collapsed",
    )
    if user_question and user_question.strip():
        st.caption(f"Frage aktiv: \"{user_question.strip()[:80]}...\"" if len(user_question.strip()) > 80 else f"Frage aktiv: \"{user_question.strip()}\"")
    else:
        st.caption("Optional — leer lassen fuer Standard-Analyse")

    # --- Start-Button (IMMER sichtbar) ---
    if st.button("Stilistic Lab starten", type="primary"):
        if len(source_texts) < 2:
            st.warning(
                f"{len(source_texts)}/2 Quellen mit Text. "
                f"Mindestens 2 Quelltexte noetig."
            )
        else:
            with st.spinner("STILISTIC LAB laeuft..."):
                progress_placeholder = st.empty()

                def update_progress(msg):
                    progress_placeholder.info(f"... {msg}")

                try:
                    result = run_stilistic_lab(
                        source_texts=source_texts,
                        progress_callback=update_progress,
                        user_question=user_question if user_question else "",
                    )

                    st.session_state["sl_result"] = result
                    st.session_state["sl_timestamp"] = datetime.now().isoformat()

                    progress_placeholder.empty()
                    st.success("STILISTIC LAB abgeschlossen!")

                except Exception as e:
                    logger.error(f"STILISTIC LAB Fehler: {e}")
                    st.error(f"Fehler im STILISTIC LAB: {e}")

    # --- Ergebnis-Anzeige ---
    result = st.session_state.get("sl_result")
    if not result:
        return

    st.markdown("---")

    # Etappe 1
    with st.expander("Etappe 1: SEZIEREN (Vergleichstabelle)", expanded=True):
        comparison = result.get("etappe1", {}).get("comparison_table", [])
        if comparison:
            import pandas as pd
            df = pd.DataFrame(comparison)
            st.dataframe(df, width="stretch", hide_index=True)
        else:
            st.info("Keine Vergleichsdaten verfuegbar.")

        individual = result.get("etappe1", {}).get("individual", {})
        for lbl, stats in individual.items():
            if "error" in stats:
                continue
            with st.expander(f"Detail: {lbl}", expanded=False):
                ss = stats.get("sentence_stats", {})
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Satzlaenge", f"{ss.get('avg_length', '?')} Woerter")
                col2.metric("Median", f"{ss.get('median_length', '?')} Woerter")
                col3.metric("Max", f"{ss.get('max_length', '?')} Woerter")
                col4.metric("Saetze", stats.get("sentence_count", "?"))

                st_obj = stats.get("sentence_types", {})
                col1, col2, col3 = st.columns(3)
                col1.metric("HS", st_obj.get("HS", 0))
                col2.metric("NS", st_obj.get("NS", 0))
                col3.metric("Gemischt", st_obj.get("gemischt", 0))

                col1, col2 = st.columns(2)
                col1.metric("TTR", f"{stats.get('type_token_ratio', 0):.3f}")
                col2.metric("Morph.Kompl.", f"{stats.get('morphological_complexity', 0):.1f}")

                top_content = stats.get("top_content_words", [])
                if top_content:
                    st.markdown("**Haeufigste Inhaltstwoerter:**")
                    st.markdown(" | ".join(f"{w} ({c}x)" for w, c in top_content[:8]))

                bigrams = stats.get("bigrams", [])
                if bigrams:
                    st.markdown("**Bigramme:**")
                    st.markdown(" | ".join(f"{g} ({c}x)" for g, c in bigrams[:5]))

    # Etappe 2+3
    st.subheader("Etappe 2+3: Beobachtungen pro Quelle")
    etappen_results = result.get("etappen_2_3", {})
    for lbl, text in etappen_results.items():
        with st.expander(lbl, expanded=True):
            if text.startswith("FEHLER"):
                st.error(text)
            else:
                st.markdown(text)

    # Globale Synthese
    st.markdown("---")
    st.subheader("Globale Synthese")
    synthese = result.get("globale_synthese", "(Keine Synthese verfuegbar)")
    if synthese.startswith("FEHLER"):
        st.error(synthese)
    else:
        st.markdown(synthese)

    # Metadaten
    meta = result.get("metadata", {})
    with st.expander("Metadaten", expanded=False):
        st.markdown(f"- **Quellen:** {meta.get('source_count', '?')}")
        st.markdown(f"- **Erfolgreich:** {meta.get('valid_sources', '?')}")
        st.markdown(f"- **Modell Etappe 2+3:** {meta.get('model_etappe_2_3', '?')}")
        st.markdown(f"- **Modell Synthese:** {meta.get('model_synthese', '?')}")
        st.markdown(f"- **Dauer:** {meta.get('elapsed_seconds', '?')}s")
        uq = meta.get('user_question', '')
        if uq:
            st.markdown(f"- **Frage:** {uq}")

    # Download
    ts = st.session_state.get("sl_timestamp", "")
    md_content = format_result_as_markdown(result)
    st.download_button(
        label="Als Markdown herunterladen",
        data=md_content,
        file_name=f"stilistic_lab_{ts[:10] if ts else 'unknown'}.md",
        mime="text/markdown",
    )
