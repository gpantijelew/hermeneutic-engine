# ui/analysis_tab.py — HRE v51
# Zuständig für: Analyse-Tab (Semantische Suche + Statistik)
#
# ARCHITEKTUR-REGEL:
# State-Schreibzugriffe ausschließlich via ui/state.py.
# render_pipeline_trace() ist bereits in ui/pipeline_trace.py gekapselt.

import streamlit as st
import re
import asyncio
import pandas as pd

import ui.state as state
from ui.pipeline_trace import render_pipeline_trace

from modules.database import get_firestore_client
from modules.vector_store import FirestoreVectorStore
from modules.citation_rag import CitationRAG
from modules.synthesis_utils import post_process_synthesis
from modules.confidence_scoring import calculate_confidence_scores
from modules.export import generate_markdown, generate_json, generate_excel

def render_analysis_tab(all_chats: list) -> None:
    """
    Rendert den vollständigen Analyse-Tab.

    Args:
        all_chats: Liste aller Chats aus get_chat_list().
                   Wird von app.py übergeben — kein DB-Aufruf hier.
    """
    st.title("🧠 Langzeitgedächtnis & Suche")
    st.markdown("---")

    db = get_firestore_client()
    if not db:
        st.error("Keine Datenbankverbindung.")
        return

    chat_map = {c['id']: c['title'] for c in all_chats}

    tab_search, tab_stats = st.tabs(["🔍 Semantische Suche", "📊 Statistik"])

    with tab_search:
        _render_search_tab(chat_map, all_chats)

    with tab_stats:
        _render_stats_tab()


# ==============================================================================
# PRIVATE: DISPLAY-BLOCK (Ergebnisse vorhanden)
# ==============================================================================

def _render_search_tab(chat_map: dict, all_chats: list) -> None:
    """Verzweigt zwischen Display- und Input-Block."""

    if 'rag_results' in st.session_state and 'rag_answer' in st.session_state:
        _render_results_block(chat_map)
    else:
        _render_input_block(chat_map, all_chats)


def _render_results_block(chat_map: dict) -> None:
    """Zeigt die Analyse-Ergebnisse an."""

    if st.button("🔄 Neue Analyse starten", type="secondary", use_container_width=True):
        state.reset_analysis_search()  # v51: via ui/state.py
        st.rerun()

    results = st.session_state.rag_results
    answer = st.session_state.rag_answer
    mode = st.session_state.get('rag_mode', 'discourse')

    st.markdown("### 💡 Synthese")

    if mode == "exegesis":
        st.caption("📖 **Modus: EXEGESE** (Fokus auf Erklärung & Definition)")
    elif mode == "discourse":
        st.caption("🗣️ **Modus: DISKURS** (Fokus auf Vergleich & Debatte)")
    else:
        st.caption(f"⚙️ Modus: {mode}")

    st.info(answer)

    # Enforcer Protokoll
    rag_engine = CitationRAG()
    with st.expander("🛡️ Enforcer Protokoll (Validierung)", expanded=False):
        warnings = rag_engine.validate_citations(answer, len(results))

        st.session_state.verification_log['structure_check'] = warnings

        if warnings:
            for w in warnings:
                st.error(w)
        else:
            st.success("✅ Struktur-Check bestanden: Alle Zitate sind gültig.")

        if st.button("🕵️‍♂️ Tiefenprüfung starten (Faktencheck)"):
            progress_bar = st.progress(0, text="Starte Enforcer Engine...")

            def update_progress(p):
                progress_bar.progress(p, text=f"Prüfe Fakten... {int(p*100)}%")

            async def run_deep_check():
                sentences = re.split(r'(?<=[.!?])\s+', answer)
                sentences = [s for s in sentences if s.strip()]
                if not sentences:
                    return []
                return await rag_engine.verify_facts_parallel(
                    sentences, results, progress_callback=update_progress
                )

            with st.spinner("Der Enforcer prüft parallel (v49.1 Speedup)..."):
                deep_check_log = asyncio.run(run_deep_check())
                st.session_state.verification_log['deep_check'] = deep_check_log

                issues_found = 0
                checked_count = len(deep_check_log)

                for entry in deep_check_log:
                    sent = entry['sentence']
                    m = entry['source_id']
                    is_valid = entry['valid']
                    reason = entry['reason']

                    if is_valid:
                        st.markdown(
                            f"✅ **Verifiziert:** *\"{sent[:50]}...\"* -> Quelle [{m}]"
                        )
                    else:
                        st.error(f"❌ **Diskrepanz:** *\"{sent}\"*")
                        st.markdown(f"Grund: {reason}")
                        issues_found += 1

                progress_bar.empty()

                if checked_count == 0:
                    st.warning("Keine prüfbaren Zitate gefunden.")
                elif issues_found == 0:
                    st.balloons()
                    st.success(f"🎉 Perfekt! {checked_count} Fakten erfolgreich verifiziert.")

    # Pipeline-Trace (v51: bereits extrahiert)
    render_pipeline_trace()

    # Quellen
    st.markdown("---")
    st.markdown("### 📚 Verwendete Quellen (Beweise)")

    for i, res in enumerate(results):
        meta = res.get('metadata', {})
        role = meta.get('role', 'unknown')
        chat_id = res.get('chat_id', 'unknown')
        platform = meta.get('platform', 'Unbekannt')
        real_date = meta.get('real_date_str', 'Datum unbekannt')
        chat_title = chat_map.get(chat_id, f"Chat ...{chat_id[-4:]}")
        score = res.get('confidence_score', 0)

        icon = _platform_icon(platform)
        header_text = f"[{i+1}] {icon} {platform} | {score:.1f}% Relevanz | {chat_title}"

        with st.expander(header_text):
            st.progress(int(score) / 100, text=f"Konfidenz: {score:.1f}%")
            st.markdown(f"**{role.upper()}:**")

            raw_content = res.get('content', '')
            thought, speech = rag_engine.split_thought_and_speech(raw_content)

            if thought:
                st.info(f"🧠 **Interner Gedanke:**\n\n{thought}")
            if speech:
                st.write(f"💬 **Aussage:**\n\n{speech}")
            elif not thought:
                st.write(raw_content)

            st.caption(
                f"Original-ID: {res.get('message_id')} | Datum: {real_date}"
            )

    # Export
    st.markdown("---")
    st.subheader("💾 Export & Sicherung")

    md_data = generate_markdown(
        st.session_state.rag_query,
        answer,
        results,
        chat_map,
        st.session_state.get('verification_log')
    )
    json_data = generate_json(st.session_state.rag_query, answer, results)
    excel_data = generate_excel(results, chat_map)

    safe_query = "".join([
        c for c in st.session_state.rag_query
        if c.isalnum() or c in (' ', '-', '_')
    ]).strip()[:30]
    filename_base = f"Analyse_{safe_query}"

    col_exp1, col_exp2, col_exp3 = st.columns(3)
    with col_exp1:
        st.download_button(
            "📄 Als Markdown", md_data,
            f"{filename_base}.md", "text/markdown",
            use_container_width=True
        )
    with col_exp2:
        st.download_button(
            "📊 Als Excel", excel_data,
            f"{filename_base}.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
    with col_exp3:
        st.download_button(
            "🤖 Als JSON", json_data,
            f"{filename_base}.json", "application/json",
            use_container_width=True
        )


# ==============================================================================
# PRIVATE: INPUT-BLOCK (Keine Ergebnisse)
# ==============================================================================

def _render_input_block(chat_map: dict, all_chats: list) -> None:
    """Zeigt die Such-Eingabe an."""

    st.subheader("Wissensbasis durchsuchen")
    with st.expander("🔍 Such-Fokus (Scope)", expanded=True):
        search_mode = st.radio(
            "Modus:",
            ["🎯 Investigativ (Nur ausgewählte Quellen)",
             "🧠 Gedächtnis (Alles durchsuchen)"],
            index=0,
            horizontal=True
        )

        selected_chat_ids = None
        if search_mode == "🎯 Investigativ (Nur ausgewählte Quellen)":
            sorted_chats = sorted(all_chats, key=lambda x: x['title'].lower())
            chat_options = {c['title']: c['id'] for c in sorted_chats}

            if "analyse_source_select" not in st.session_state:
                saved_titles = st.session_state.get("rag_saved_titles", [])
                st.session_state["analyse_source_select"] = [
                    t for t in saved_titles if t in chat_options.keys()
                ]

            selected_titles = st.multiselect(
                "Quellen auswählen:",
                options=list(chat_options.keys()),
                key="analyse_source_select"
            )

            if selected_titles:
                selected_chat_ids = [chat_options[t] for t in selected_titles]
            else:
                st.warning("⚠️ Keine Quellen gewählt!")
                selected_chat_ids = []

    col1, col2 = st.columns([3, 1])
    with col1:
        saved_query = st.session_state.get("rag_saved_query", "")
        search_query = st.text_input(
            "Thema / Frage:", value=saved_query,
            placeholder="z.B. Was sagt die KI über Zensur?"
        )
        if st.session_state.get("rag_saved_query") !=search_query:
            st.session_state["rag_saved_query"] = search_query
    with col2:
        role_filter = st.radio(
            "Suche in:", ["Alles", "Nur KI (Model)", "Nur Ich (User)"], index=1
        )

    search_btn = st.button(
        "Analysieren & Antworten 🚀", type="primary", use_container_width=True
    )

    if search_btn and search_query:
        _run_analysis_pipeline(search_query, selected_chat_ids, chat_map)


def _run_analysis_pipeline(
    search_query: str,
    selected_chat_ids,
    chat_map: dict
) -> None:
    """Führt die vollständige RAG-Pipeline aus."""

    db = get_firestore_client()
    vector_store = FirestoreVectorStore(db)
    rag_engine = CitationRAG(vector_store=vector_store)

    with st.spinner("1. Suche relevante Fakten..."):
        try:
            keywords = rag_engine.extract_keywords(search_query)
            raw_results, query_vec = vector_store.hybrid_search(
                search_query,
                keywords,
                limit=70,
                filter_role=None,
                allowed_chat_ids=selected_chat_ids,
                keyword_weight=0.3
            )
            results = calculate_confidence_scores(query_vec, raw_results)

            if not results:
                st.warning("Keine relevanten Quellen gefunden.")
                return

            with st.spinner("2. Analysiere Chunk-Verteilung..."):
                imbalance_info = rag_engine.check_imbalance_only(
                    search_query, results, chat_id=selected_chat_ids
                )

            if imbalance_info and imbalance_info.severity == "critical":
                _render_imbalance_warning(imbalance_info)
            elif imbalance_info and imbalance_info.severity == "info":
                _render_imbalance_info(imbalance_info)
                with st.spinner("3. Generiere Antwort mit Zitationen..."):
                    raw_answer, used_sources, mode_name = rag_engine.generate_answer(
                        search_query,
                        results,
                        pre_reranked=imbalance_info
                    )
                    valid_indices = list(range(1, len(used_sources) + 1))

                    with st.spinner("4. Veredle Synthese (Cleanup)..."):
                        answer = post_process_synthesis(raw_answer, valid_indices)

                trace = getattr(rag_engine, 'last_pipeline_trace', None)
                state.set_analysis_result(  # v51: via ui/state.py
                    results=used_sources,
                    answer=answer,
                    query=search_query,
                    mode=mode_name,
                    pipeline_trace=trace
                )
                st.rerun()

        except Exception as e:
            st.error(f"Fehler: {e}")
            import traceback
            print(traceback.format_exc())

def _render_imbalance_warning(imbalance_info) -> None:
    """Zeigt Imbalance-Warnung — blockiert den Flow NICHT."""
    with st.expander(
        f"⚠️ Chunk-Verteilung ungleich (Ratio {imbalance_info.ratio:.1f}:1) — Details",
        expanded=False
    ):
        total_chunks = sum(imbalance_info.doc_distribution.values())
        df_data = [
            {
                'Dokument': title,
                'Chunks':   count,
                'Anteil':   f"{(count / total_chunks) * 100:.1f}%"
            }
            for title, count in sorted(
                imbalance_info.doc_distribution.items(),
                key=lambda x: x[1], reverse=True
            )
        ]
        st.dataframe(pd.DataFrame(df_data), use_container_width=True)
        st.caption(
            "Die Engine gleicht die Verteilung via Essence Parity aus. "
            "Synthese läuft trotzdem vollständig durch."
        )

def _render_imbalance_info(imbalance_info) -> None:
    """Zeigt Info-Imbalance-Hinweis."""
    st.info(
        f"ℹ️ **Hinweis:** Chunk-Verteilung ist ungleich "
        f"(Verhältnis: {imbalance_info.ratio:.1f}:1)"
    )
    with st.expander("📊 Details anzeigen"):
        total_chunks = sum(imbalance_info.doc_distribution.values())
        df_data = [
            {
                'Dokument': title,
                'Chunks': count,
                'Anteil': f"{(count / total_chunks) * 100:.1f}%"
            }
            for title, count in sorted(
                imbalance_info.doc_distribution.items(),
                key=lambda x: x[1], reverse=True
            )
        ]
        st.dataframe(pd.DataFrame(df_data), use_container_width=True)
    st.caption("Die Engine verwendet pragmatische Parität.")


def _render_stats_tab() -> None:
    """Zeigt Speicher-Statistik."""
    st.info("Speicher-Status")
    if st.button("Zählen"):
        try:
            from modules.vector_store import _get_chroma_collection
            col = _get_chroma_collection()
            count = col.count()
            st.metric("Gespeicherte Wissens-Chunks", count)
        except Exception as e:
            st.error(f"Fehler: {e}")


# ==============================================================================
# PRIVATE: HELPERS
# ==============================================================================

def _platform_icon(platform: str) -> str:
    icons = {
        "Grok": "🚀", "Claude": "🧠", "Gemini": "✨",
        "DeepSeek": "🐳", "Kimi": "🌙", "GLM-4": "💬",
        "ChatGPT": "🟢", "LM Arena": "⚔️"
    }
    return icons.get(platform, "🤖")