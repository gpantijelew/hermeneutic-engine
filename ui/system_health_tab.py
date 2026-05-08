"""
A.8 + A.16: System Health Dashboard.

Enthält zwei Unter-Tabs:
- 🎯 Confidence Calibration: Reliability Diagram, ECE
- 📊 Corpus Statistics: Chats, Nachrichten, Chunks, Dedup-Status, Timeline
"""

import streamlit as st
import pandas as pd
import altair as alt
from typing import List, Dict, Tuple

from modules.database import (
    get_calibration_data,
    calculate_ece,
    get_human_review_count,
    get_chat_count,
    get_message_count,
    get_chunk_registry_count,
    get_orphan_chat_count,
    get_hashed_chunk_count,
    get_unique_hash_count,
    get_chunk_timeline,
)
from modules.config import ENFORCER_CALIBRATION_TARGET


def render_system_health_tab():
    """Rendert den System Health Tab mit zwei Unter-Tabs."""
    st.header("System Health")

    tab_calibration, tab_corpus = st.tabs(["🎯 Confidence Calibration", "📊 Corpus Statistics"])

    with tab_calibration:
        _render_calibration_section()

    with tab_corpus:
        _render_corpus_section()


def _render_calibration_section():
    """A.8: Confidence Calibration — bestehende Logik."""
    st.markdown(
        "Kalibrierung des Enforcers: Wie gut decken sich vorhergesagte Confidence "
        "mit der tatsächlichen Accuracy? Ein gut kalibrierter Enforcer folgt der diagonalen Linie."
    )

    # Daten laden
    cal_data = get_calibration_data()
    n_reviews = len(cal_data)
    n_human = get_human_review_count()

    # Minimum-Sample-Gate (N < 20)
    if n_reviews < 20:
        st.warning(
            f"⚠️ **Zu wenige Reviews für verlässliche Kalibrierung**\n\n"
            f"Aktuell: **{n_reviews}/{n_human}** human-reviewed Claims mit Confidence-Scores\n"
            f"Ziel: **{ENFORCER_CALIBRATION_TARGET}** Reviews\n\n"
            f"Das Diagramm wird angezeigt, aber die Aussagekraft ist begrenzt."
        )

    # ECE berechnen
    ece, bins_info = calculate_ece(cal_data, n_bins=5)

    # Leere Bins zählen
    filled_bins = sum(1 for b in bins_info if b["count"] > 0)
    empty_bins = len(bins_info) - filled_bins

    # Metriken anzeigen
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Human Reviews", n_human)
    with col2:
        st.metric("Mit Confidence", n_reviews)
    with col3:
        st.metric("Gefüllte Bins", f"{filled_bins}/5")
    with col4:
        st.metric("ECE", f"{ece:.3f}" if n_reviews > 0 else "—")

    # Warnung bei >2 leeren Bins
    if empty_bins >= 3 and n_reviews >= 20:
        st.warning(
            f"⚠️ **Nur {filled_bins} von 5 Confidence-Bins werden genutzt**\n\n"
            f"Die Verteilung ist extrem konzentriert. "
            f"Der Enforcer sollte mit der Confidence-Skala differenzieren."
        )

    # Diagramme nur anzeigen wenn Daten vorhanden
    if n_reviews == 0:
        st.info("Noch keine Kalibrierungsdaten verfügbar. Reviews werden gesammelt...")
        return

    # DataFrames für Altair
    df_bins = pd.DataFrame([
        {
            "bin_center": b["bin_center"],
            "accuracy": b["accuracy"] if b["accuracy"] is not None else 0,
            "count": b["count"],
            "avg_confidence": b["avg_confidence"] if b["avg_confidence"] is not None else b["bin_center"],
        }
        for b in bins_info
    ])

    # Confidence-Distribution: Rohdaten in Bins einteilen
    conf_values = [item["enforcer_confidence"] for item in cal_data]
    df_dist = pd.DataFrame({"confidence": conf_values})

    # Chart 1: Reliability Diagram
    st.subheader("Reliability Diagram")
    st.markdown("*Perfekt kalibriert: Punkte liegen auf der diagonalen Linie*")

    base = alt.Chart(df_bins[df_bins["count"] > 0]).encode(
        x=alt.X(
            "avg_confidence:Q",
            title="Enforcer Confidence",
            scale=alt.Scale(domain=[0, 1]),
            axis=alt.Axis(format=".1f"),
        ),
        y=alt.Y(
            "accuracy:Q",
            title="Empirical Accuracy",
            scale=alt.Scale(domain=[0, 1]),
            axis=alt.Axis(format=".1f"),
        ),
        tooltip=[
            alt.Tooltip("avg_confidence:Q", title="Confidence", format=".2f"),
            alt.Tooltip("accuracy:Q", title="Accuracy", format=".2f"),
            alt.Tooltip("count:Q", title="Samples"),
        ],
    )

    bars = base.mark_bar(
        color="#4A90D9",
        width=80,
        opacity=0.8,
    )

    diagonal = alt.Chart(
        pd.DataFrame({"x": [0, 1], "y": [0, 1]})
    ).mark_line(
        color="red",
        strokeDash=[5, 5],
        strokeWidth=2,
    ).encode(x="x:Q", y="y:Q")

    chart1 = (diagonal + bars).properties(
        width=400,
        height=300,
    )

    # Chart 2: Confidence Distribution
    st.subheader("Confidence Distribution")
    st.markdown("*Verteilung der Confidence-Scores über alle Reviews*")

    chart2 = alt.Chart(df_dist).mark_bar(
        color="#9B59B6",
        opacity=0.7,
    ).encode(
        x=alt.X(
            "confidence:Q",
            title="Enforcer Confidence",
            bin=alt.Bin(step=0.2, extent=[0, 1]),
            scale=alt.Scale(domain=[0, 1]),
        ),
        y=alt.Y(
            "count()",
            title="Number of Reviews",
        ),
        tooltip=[
            alt.Tooltip("confidence:Q", bin=True, title="Confidence Range"),
            alt.Tooltip("count()", title="Count"),
        ],
    ).properties(
        width=400,
        height=300,
    )

    st.altair_chart(chart1 | chart2, use_container_width=True)

    # Bin-Details als Tabelle
    with st.expander("Bin-Details"):
        st.dataframe(
            df_bins[["bin_center", "count", "accuracy", "avg_confidence"]].rename(
                columns={
                    "bin_center": "Bin Center",
                    "count": "Samples",
                    "accuracy": "Accuracy",
                    "avg_confidence": "Avg Confidence",
                }
            ),
            width='stretch',
        )

    st.info(
        "**Interpretation:**\n\n"
        "- **ECE (Expected Calibration Error):** Durchschnittliche Abweichung zwischen "
        "Confidence und Accuracy, gewichtet nach Sample-Anzahl. Niedriger = besser.\n"
        "- **Diagonal:** Perfekte Kalibrierung (Confidence = Accuracy).\n"
        "- **Über der Diagonalen:** Enforcer ist unterconfident (zu pessimistisch).\n"
        "- **Unter der Diagonalen:** Enforcer ist overconfident (zu optimistisch)."
    )


def _render_corpus_section():
    """A.16: Corpus Statistics — KPI-Cards, Warnungen, Timeline."""
    # --- KPI-Cards ---
    chat_count = get_chat_count()
    msg_count = get_message_count()
    chunk_count = get_chunk_registry_count()
    orphan_count = get_orphan_chat_count()
    hashed_count = get_hashed_chunk_count()
    unique_count = get_unique_hash_count()

    avg_chunks = chunk_count / chat_count if chat_count > 0 else 0

    st.subheader("Korpus-Übersicht")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Chats", f"{chat_count:,}")
    with col2:
        st.metric("Nachrichten", f"{msg_count:,}")
    with col3:
        st.metric("Chunks", f"{chunk_count:,}")
    with col4:
        st.metric("Ø Chunks/Chat", f"{avg_chunks:.1f}")

    # --- Warnung: Chats ohne Chunks ---
    if orphan_count > 0:
        st.warning(
            f"⚠️ **{orphan_count} Chat(s) ohne Vektordaten** — "
            f"diese sind in Analysen und RAG-Suchen nicht auffindbar."
        )

    # --- Deduplizierung (A.13) ---
    if chunk_count > 0 and hashed_count > 0:
        st.subheader("Deduplizierung (A.13)")

        col_d1, col_d2, col_d3 = st.columns(3)
        with col_d1:
            st.metric("Gesamt-Chunks", f"{chunk_count:,}")
        with col_d2:
            st.metric("Eindeutige Inhalte", f"{unique_count:,}")
        with col_d3:
            coverage = (hashed_count / chunk_count) * 100 if chunk_count else 0
            st.metric("Hash-Abdeckung", f"{coverage:.1f}%")

        if unique_count < chunk_count:
            duplicate_chunks = chunk_count - unique_count
            st.info(
                f"🔄 {duplicate_chunks:,} Chunk(s) sind Duplikate von bereits existierenden Inhalten."
            )

    # --- Timeline: Chunks über Zeit ---
    timeline = get_chunk_timeline()
    if timeline:
        st.subheader("Chunks über Zeit")
        st.markdown("*Wöchentliche Chunk-Erstellung*")

        df_timeline = pd.DataFrame(timeline)
        chart = alt.Chart(df_timeline).mark_bar(
            color="#2ECC71",
            opacity=0.8,
        ).encode(
            x=alt.X("week:N", title="Woche", sort=None),
            y=alt.Y("count:Q", title="Chunks"),
            tooltip=[
                alt.Tooltip("week:N", title="Woche"),
                alt.Tooltip("count:Q", title="Chunks", format=","),
            ],
        ).properties(
            height=300,
        )

        st.altair_chart(chart, use_container_width=True)
    else:
        st.info("Noch keine Timeline-Daten verfügbar.")


def render_calibration_summary():
    """Kompakte Zusammenfassung für die Sidebar oder Overview."""
    cal_data = get_calibration_data()
    if not cal_data:
        return

    ece, _ = calculate_ece(cal_data, n_bins=5)
    st.metric("ECE", f"{ece:.3f}", help="Expected Calibration Error (niedriger = besser)")
