# modules/bulk_export.py
import streamlit as st
import pandas as pd
import json
from io import BytesIO
from modules.database import get_firestore_client

def render_bulk_export_ui():
    """
    UI für den Massen-Export von Vektor-Chunks (Datenbank-Dump).
    """
    st.title("💾 Datenbank-Export")
    st.markdown("Hier kannst du deine gesamte Wissensbasis (oder Teile davon) für Backups oder externe Analysen exportieren.")

    db = get_firestore_client()
    if not db:
        st.error("Keine Datenbankverbindung.")
        return

    col_ref = db.collection('embeddings')

    # --- 1. FILTER ---
    with st.expander("🔍 Export-Filter konfigurieren", expanded=True):
        c1, c2 = st.columns(2)

        # Wir holen die Filter-Werte hardcoded, um DB-Calls zu sparen. 
        # (Alternativ könnte man sie dynamisch laden, aber das kostet Zeit)
        filter_speaker = c1.multiselect(
            "Sprecher filtern:", 
            ["Kimi", "DeepSeek", "ChatGPT", "Claude", "Gemini", "User", "Unknown"]
        )

        filter_type = c2.multiselect(
            "Typ filtern:", 
            ["Analyse", "Selbstreflexion", "Vergleich", "Frage"]
        )

        # Limit 0 bedeutet "Alles", aber wir setzen ein Sicherheitslimit für die UI
        limit = st.number_input("Maximale Anzahl (0 = Alle, Vorsicht bei großen DBs):", min_value=0, value=1000, step=500)

    # --- 2. FORMAT ---
    export_format = st.radio("Format:", ["Excel (.xlsx)", "JSON (.json)", "CSV (.csv)"], horizontal=True)

    st.markdown("---")

    # --- 3. ACTION ---
    if st.button("🚀 Daten exportieren"):
        with st.spinner("Lade Daten aus Firestore... (Das kann kurz dauern)"):
            data = fetch_data(col_ref, filter_speaker, filter_type, limit)

            if not data:
                st.warning("Keine Daten mit diesen Filtern gefunden.")
                return

            df = pd.DataFrame(data)
            st.success(f"✅ {len(df)} Datensätze geladen.")

            # Dateiname generieren
            filename_base = "wissensbasis_export"

            # Download Buttons rendern
            if "Excel" in export_format:
                buffer = BytesIO()
                with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False, sheet_name='Chunks')

                st.download_button(
                    label="📥 Download Excel starten",
                    data=buffer.getvalue(),
                    file_name=f"{filename_base}.xlsx",
                    mime="application/vnd.ms-excel"
                )

            elif "JSON" in export_format:
                json_str = df.to_json(orient='records', indent=2, force_ascii=False)
                st.download_button(
                    label="📥 Download JSON starten",
                    data=json_str,
                    file_name=f"{filename_base}.json",
                    mime="application/json"
                )

            elif "CSV" in export_format:
                csv_str = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Download CSV starten",
                    data=csv_str,
                    file_name=f"{filename_base}.csv",
                    mime="text/csv"
                )

def fetch_data(col_ref, speakers, types, limit):
    """
    Lädt Daten für den Export (Deep Scan).
    """
    # Auch hier: Kein Limit an der Quelle, wir filtern selbst
    docs = col_ref.stream()

    results = []
    count = 0

    for doc in docs:
        d = doc.to_dict()
        meta = d.get('metadata', {})

        # Filterlogik (Listen-basiert für Multiselect)
        if speakers and meta.get('model_name') not in speakers:
            continue
        if types and meta.get('content_type') not in types:
            continue

        # Daten flachklopfen
        row = {
            'ID': doc.id,
            'Chat ID': d.get('chat_id'),
            'Sprecher': meta.get('model_name', 'Unknown'),
            'Typ': meta.get('content_type', 'Analyse'),
            'Themen': meta.get('subjects', ''),
            'Inhalt': d.get('content', ''),
            'Erstellt am': d.get('created_at')
        }
        results.append(row)
        count += 1

        # Limit prüfen (0 = Alle)
        if limit > 0 and count >= limit:
            break

    return results