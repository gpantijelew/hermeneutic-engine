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
import json
from io import BytesIO
from modules.database import get_firestore_client


@st.cache_data(ttl=3600)  # Cache für 1 Stunde
def get_unique_speakers():
    """
    Lädt alle eindeutigen Sprecher aus der Datenbank.
    
    WICHTIG: Gecacht, um nicht bei jedem UI-Reload zu scannen.
    Cache läuft nach 1h ab oder wird manuell invalidiert (🔄 Button).
    
    Returns:
        Sortierte Liste von Speaker-Namen
    """
    db = get_firestore_client()
    if not db:
        return []
    
    col_ref = db.collection('embeddings')
    speakers = set()
    
    # Scan durch alle Dokumente (bei 8k Chunks: ~5 Sekunden)
    for doc in col_ref.stream():
        meta = doc.to_dict().get('metadata', {})
        speaker = meta.get('model_name', 'Unknown')
        speakers.add(speaker)
    
    return sorted(speakers)


@st.cache_data(ttl=3600)  # Cache für 1 Stunde
def get_unique_content_types():
    """
    Lädt alle eindeutigen Content-Types aus der Datenbank.
    
    Returns:
        Sortierte Liste von Content-Types
    """
    db = get_firestore_client()
    if not db:
        return []
    
    col_ref = db.collection('embeddings')
    types = set()
    
    for doc in col_ref.stream():
        meta = doc.to_dict().get('metadata', {})
        content_type = meta.get('content_type', 'Analyse')
        types.add(content_type)
    
    return sorted(types)


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
        c1, c2, c3 = st.columns([2, 2, 1])
        
        # NEU v50.6: Dynamische Listen laden
        available_speakers = get_unique_speakers()
        available_types = get_unique_content_types()
        
        filter_speaker = c1.multiselect(
            "Sprecher filtern:", 
            available_speakers,
            help="Leer = Alle Sprecher"
        )
        
        filter_type = c2.multiselect(
            "Typ filtern:", 
            available_types,
            help="Leer = Alle Typen"
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
            help="Bei großen DBs kann 'Alle' lange dauern. Starte mit 1000 zum Testen."
        )
    
    # --- 2. FORMAT ---
    export_format = st.radio(
        "Format:", 
        ["Excel (.xlsx)", "JSON (.json)", "CSV (.csv)"], 
        horizontal=True
    )
    
    st.markdown("---")
    
    # --- 3. ACTION ---
    if st.button("🚀 Daten exportieren", type="primary"):
        with st.spinner("Lade Daten aus Firestore... (Das kann kurz dauern)"):
            data = fetch_data(col_ref, filter_speaker, filter_type, limit)
            
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
                with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False, sheet_name='Chunks')
                    
                    # TODO v51: Zusätzliches "Metadata"-Sheet mit Export-Info
                
                st.download_button(
                    label="📥 Download Excel starten",
                    data=buffer.getvalue(),
                    file_name=f"{filename_base}.xlsx",
                    mime="application/vnd.ms-excel"
                )
            
            elif "JSON" in export_format:
                # TODO v51: Wrap in Metadata-Objekt
                # export_data = {
                #     "metadata": {"export_date": ..., "filters": ...},
                #     "data": df.to_dict(orient='records')
                # }
                
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
    Lädt Daten für den Export (Deep Scan mit Filterung).
    
    PERFORMANCE:
    - Bei 8k Chunks: ~5-10 Sekunden
    - Bei 50k Chunks: ~30-60 Sekunden
    - TODO v51: Progress-Bar für bessere UX
    
    Args:
        col_ref: Firestore Collection Reference
        speakers: Liste von Speaker-Namen (leer = alle)
        types: Liste von Content-Types (leer = alle)
        limit: Max. Anzahl (0 = alle)
    
    Returns:
        Liste von Dicts (flach, für DataFrame-Konversion)
    """
    # TODO v51: Wenn keine Filter und limit > 0, nutze Firestore .limit()
    # if not speakers and not types and limit > 0:
    #     docs = col_ref.limit(limit).stream()
    # else:
    #     docs = col_ref.stream()
    
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
        
        # Daten flachklopfen für DataFrame
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