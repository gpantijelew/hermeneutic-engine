# modules/bulk_export.py
"""
Massen-Export für die Vektor-Wissensbasis.

USE-CASE:
- Backup der gesamten Wissensbasis
- Externe Datenanalyse (Python, R, Excel)
- Migration zu anderen Systemen

ÄNDERUNGSHISTORIE:
- v50.6: Dynamische Speaker-Liste (statt hardcoded)
- v49: Initiale Version mit Excel/JSON/CSV-Export
"""

import streamlit as st
import pandas as pd
from io import BytesIO
from modules.database import get_db_connection
from modules.vector_store import LocalVectorStore


@st.cache_data(ttl=3600)
def get_unique_speakers():
    """
    Lädt alle eindeutigen Sprecher aus ChromaDB.
    v50.9-local: col_ref.stream() ersetzt durch vs.get_all_chunks().
    """
    db = get_db_connection()
    if not db:
        return []
    vs = LocalVectorStore(db)
    chunks = vs.get_all_chunks()
    speakers = {c.get("metadata", {}).get("model_name", "Unknown") for c in chunks}
    return sorted(speakers)


@st.cache_data(ttl=3600)
def get_unique_content_types():
    """
    Lädt alle eindeutigen Content-Types aus ChromaDB.
    v50.9-local: col_ref.stream() ersetzt durch vs.get_all_chunks().
    """
    db = get_db_connection()
    if not db:
        return []
    vs = LocalVectorStore(db)
    chunks = vs.get_all_chunks()
    types = {c.get("metadata", {}).get("content_type", "Analyse") for c in chunks}
    return sorted(types)


def render_bulk_export_ui():
    """
    UI für den Massen-Export von Vektor-Chunks (Datenbank-Dump).
    v50.9-local: ChromaDB via LocalVectorStore.
    """
    st.title("💾 Datenbank-Export")
    st.markdown(
        "Hier kannst du deine gesamte Wissensbasis (oder Teile davon) für Backups oder externe Analysen exportieren."
    )

    db = get_db_connection()
    if not db:
        st.error("Keine Datenbankverbindung.")
        return

    vs = LocalVectorStore(db)

    # --- 1. FILTER ---
    with st.expander("🔍 Export-Filter konfigurieren", expanded=True):
        c1, c2, c3 = st.columns([2, 2, 1])

        # NEU v50.6: Dynamische Listen laden
        available_speakers = get_unique_speakers()
        available_types = get_unique_content_types()

        filter_speaker = c1.multiselect(
            "Sprecher filtern:", available_speakers, help="Leer = Alle Sprecher"
        )

        filter_type = c2.multiselect(
            "Typ filtern:", available_types, help="Leer = Alle Typen"
        )

        # Cache-Refresh-Button
        if c3.button("🔄", help="Filter-Listen aktualisieren"):
            st.cache_data.clear()
            st.rerun()

        # Limit 0 bedeutet "Alles", aber wir setzen ein Sicherheitslimit für die UI
        limit = st.number_input(
            "Maximale Anzahl (0 = Alle):",
            min_value=0,
            value=1000,
            step=500,
            help="Bei großen DBs kann 'Alle' lange dauern. Starte mit 1000 zum Testen.",
        )

    # --- 2. FORMAT ---
    export_format = st.radio(
        "Format:", ["Excel (.xlsx)", "JSON (.json)", "CSV (.csv)"], horizontal=True
    )

    st.markdown("---")

    # --- 3. ACTION ---
    if st.button("🚀 Daten exportieren", type="primary"):
        with st.spinner("Lade Daten aus ChromaDB..."):
            data = fetch_data(vs, filter_speaker, filter_type, limit)

            if not data:
                st.warning("Keine Daten mit diesen Filtern gefunden.")
                return

            df = pd.DataFrame(data)
            st.success(f"✅ {len(df)} Datensätze geladen.")

            # TODO v51: Zeige Statistik-Preview (Top 5 Sprecher, Zeitraum, etc.)

            # Dateiname generieren
            filename_base = "wissensbasis_export"

            # Download Buttons rendern
            if "Excel" in export_format:
                buffer = BytesIO()
                with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
                    df.to_excel(writer, index=False, sheet_name="Chunks")

                    # TODO v51: Zusätzliches "Metadata"-Sheet mit Export-Info

                st.download_button(
                    label="📥 Download Excel starten",
                    data=buffer.getvalue(),
                    file_name=f"{filename_base}.xlsx",
                    mime="application/vnd.ms-excel",
                )

            elif "JSON" in export_format:
                # TODO v51: Wrap in Metadata-Objekt
                # export_data = {
                #     "metadata": {"export_date": ..., "filters": ...},
                #     "data": df.to_dict(orient='records')
                # }

                json_str = df.to_json(orient="records", indent=2, force_ascii=False)

                st.download_button(
                    label="📥 Download JSON starten",
                    data=json_str,
                    file_name=f"{filename_base}.json",
                    mime="application/json",
                )

            elif "CSV" in export_format:
                csv_str = df.to_csv(index=False).encode("utf-8")

                st.download_button(
                    label="📥 Download CSV starten",
                    data=csv_str,
                    file_name=f"{filename_base}.csv",
                    mime="text/csv",
                )


def fetch_data(vs, speakers, types, limit):
    """
    Lädt Chunks für den Export aus ChromaDB.
    v50.9-local: col_ref.stream() ersetzt durch vs.get_all_chunks().

    Args:
        vs:       LocalVectorStore-Instanz
        speakers: Liste von Speaker-Namen (leer = alle)
        types:    Liste von Content-Types (leer = alle)
        limit:    Max. Anzahl (0 = alle)

    Returns:
        Liste von Dicts (flach, für DataFrame-Konversion)
    """
    all_chunks = vs.get_all_chunks(limit=limit)
    results = []

    for d in all_chunks:
        meta = d.get("metadata", {})

        if speakers and meta.get("model_name") not in speakers:
            continue
        if types and meta.get("content_type") not in types:
            continue

        results.append(
            {
                "ID": d.get("vector_doc_id", ""),
                "Chat ID": d.get("chat_id", ""),
                "Sprecher": meta.get("model_name", "Unknown"),
                "Typ": meta.get("content_type", "Analyse"),
                "Themen": meta.get("subjects", ""),
                "Inhalt": d.get("content", ""),
                "Erstellt am": meta.get("date", ""),
            }
        )

    return results
