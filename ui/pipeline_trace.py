# ui/pipeline_trace.py — HRE v51 (Ticket 10: Pipeline-Transparenz)
# Drei Ebenen: Router → Reranker → Chunks (behalten + verworfen)
#
# ARCHITEKTUR-REGEL:
# Liest session_state — schreibt nie.

import streamlit as st
import pandas as pd
from typing import Optional, Dict, Any


def render_pipeline_trace(trace: Optional[Dict[str, Any]] = None) -> None:
    """
    Drei-Ebenen-Transparenz der hermeneutischen Pipeline.

    Ebene 1: Router-Entscheidung (immer sichtbar)
    Ebene 2: Reranker-Statistik + Helikopter-Blick (Tabelle)
    Ebene 3: Deep-Dive verworfene Chunks (opt-in Expander)
    """
    if trace is None:
        if 'rag_pipeline_trace' not in st.session_state:
            return
        trace = st.session_state.rag_pipeline_trace

    if not trace:
        return

    with st.expander("🔍 Pipeline-Transparenz", expanded=False):

        # ══════════════════════════════════════════════════════
        # EBENE 1: ROUTER
        # ══════════════════════════════════════════════════════
        st.markdown("#### 🧭 Router-Entscheidung")

        col1, col2, col3 = st.columns(3)
        col1.metric("Intent", trace.get("intent", "—"))
        col2.metric("Sem. Intent", trace.get("semantic_intent", "—"))
        col3.metric("Threshold", f"{trace.get('threshold', 0):.2f}")

        reasoning = trace.get("router_reasoning", "")
        if reasoning:
            st.caption(f"💬 *{reasoning}*")

        parity = trace.get("essence_parity", False)
        st.caption(
            f"⚖️ Essence Parity: {'✅ Aktiv' if parity else '❌ Inaktiv'}"
        )

        st.markdown("---")

        # ══════════════════════════════════════════════════════
        # EBENE 2: RERANKER + HELIKOPTER-BLICK
        # ══════════════════════════════════════════════════════
        st.markdown("#### ⚖️ Reranker-Statistik")

        total    = trace.get("reranker_total", 0)
        passed   = trace.get("reranker_passed", 0)
        rejected = trace.get("reranker_rejected", 0)
        avg      = trace.get("reranker_avg", 0.0)
        chunks   = trace.get("chunks_retrieved", 0)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Kandidaten", total)
        col2.metric("Bestanden ✅", passed)
        col3.metric("Verworfen ❌", rejected)
        col4.metric("Im Kontext", chunks)

        if total > 0:
            pass_rate = (passed / total) * 100
            st.progress(
                min(int(pass_rate), 100),
                text=f"Pass-Rate: {pass_rate:.1f}% | Ø Score: {avg:.3f}"
            )

        # Helikopter-Blick: behaltene Chunks
        chunk_table = trace.get("chunk_table", [])
        if chunk_table:
            st.markdown("**📋 Behaltene Chunks**")
            df_kept = pd.DataFrame(chunk_table).rename(columns={
                "title":   "Dokument",
                "score":   "Score",
                "rescued": "Gerettet",
                "date":    "Datum",
                "preview": "Vorschau",
            })
            df_kept["Gerettet"] = df_kept["Gerettet"].apply(
                lambda x: "🚑" if x else ""
            )
            st.dataframe(
                df_kept,
                use_container_width=True,
                column_config={
                    "Score": st.column_config.ProgressColumn(
                        "Score", min_value=0.0, max_value=1.0, format="%.3f"
                    ),
                    "Vorschau": st.column_config.TextColumn(
                        "Vorschau", width="large"
                    ),
                },
                hide_index=True,
            )
            rescued_count = sum(1 for c in chunk_table if c.get("rescued"))
            if rescued_count:
                st.caption(
                    f"🚑 {rescued_count} Chunk(s) via Rescue Mission gerettet."
                )

        st.markdown("---")

        # ══════════════════════════════════════════════════════
        # EBENE 3: DEEP-DIVE VERWORFENE CHUNKS
        # ══════════════════════════════════════════════════════
        rejected_chunks = trace.get("rejected_chunks", [])
        if not rejected_chunks:
            return

        with st.expander(
            f"🔬 Deep-Dive: Verworfene Chunks ({len(rejected_chunks)}) — "
            f"False-Positive-Analyse",
            expanded=False
        ):
            st.caption(
                "Diese Chunks haben den Reranker-Threshold nicht erreicht. "
                "Hohe Scores hier deuten auf einen zu strengen Threshold hin."
            )

            df_rejected = pd.DataFrame(rejected_chunks).rename(columns={
                "title":   "Dokument",
                "score":   "Score",
                "date":    "Datum",
                "preview": "Vorschau",
            })

            # Absteigend nach Score — die knapp gescheiterten zuerst
            df_rejected = df_rejected.sort_values("Score", ascending=False)

            st.dataframe(
                df_rejected,
                use_container_width=True,
                column_config={
                    "Score": st.column_config.ProgressColumn(
                        "Score", min_value=0.0, max_value=1.0, format="%.3f"
                    ),
                    "Vorschau": st.column_config.TextColumn(
                        "Vorschau", width="large"
                    ),
                },
                hide_index=True,
            )

            # Grenzwert-Hinweis: Chunks knapp unter Threshold
            threshold = trace.get("threshold", 0.65)
            borderline = [
                c for c in rejected_chunks
                if c["score"] >= threshold * 0.85
            ]
            if borderline:
                st.warning(
                    f"⚠️ {len(borderline)} Chunk(s) lagen knapp unter dem "
                    f"Threshold ({threshold:.2f}). "
                    f"Bei LITERARY/ANALYTICAL: Router-Threshold prüfen."
                )