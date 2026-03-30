# app.py - v50.9: Hybrid Cockpit Integration (Full Version)
APP_VERSION = "[v50.9 (Hybrid 2Gb lokal)]"
print("=" * 80)
print(f"🚀 STARTUP: app{APP_VERSION}.py lädt...")
print("=" * 80)

import os
from dotenv import load_dotenv
# Lade Umgebungsvariablen aus der .env-Datei (nur für lokale Entwicklung)
load_dotenv(override=True)
from modules.config import MODEL_CHAT_API, LM_STUDIO_MODEL, get_system_message
from modules.llm_wrapper import llm_call, llm_call_streaming
import hmac
from datetime import datetime
import streamlit as st
import json
import re
# v50.9-local: System Instruction aus config statt Gemini-spezifischem Modul
DEFAULT_SYSTEM_INSTRUCTION = get_system_message()
import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
import traceback
from typing import Optional, Dict, List, Tuple

# Neue Module-Importe
from modules.database import (
    get_firestore_client,
    create_chat_in_firestore,
    save_message,
    generate_and_update_title,
    delete_chat,
    get_chat_list,
    load_chat_history,
    rename_chat,
    load_global_settings,
    save_global_settings
)

# --- NEU: Importer Factory ---
from modules.importers import get_importer, detect_platform, IMPORTERS
# === NEU: Config-Validierung (v49.3) ===
from modules.importers.base import validate_parser_configs

try:
    validate_parser_configs()
except ValueError as e:
    st.error(f"❌ CRITICAL: Parser-Config Fehler: {e}")
    st.stop()# -----------------------------

from modules.bulk_labeling import render_bulk_labeling_ui  # v47 Feature
from modules.bulk_export import render_bulk_export_ui      # v47 Feature
from modules.vector_admin import render_vector_admin_dashboard
from modules.vector_store import FirestoreVectorStore
from modules.citation_rag import CitationRAG
from modules.synthesis_utils import post_process_synthesis
from modules.confidence_scoring import calculate_confidence_scores
from modules.export import generate_markdown, generate_json, generate_excel


# TESTZEILE
st.write(f"🚀 Die ({APP_VERSION}) wird ausgeführt!")

# ==============================================================================
# AUTHENTIFIZIERUNG (mit st.secrets) - WIEDERHERGESTELLT!
# ==============================================================================

AUTH_ENABLED = True  # Passwort-Schutz aktiviert

def check_password():
    """Prüft das Passwort (Robust für Cloud & Lokal)."""
    if st.session_state.get("password_correct"):
        return True

    # Zeige Passwort-Screen
    st.title(f"🚀 Forschungs-Cockpit {APP_VERSION} - SYSTEM ONLINE")
    password = st.text_input("Passwort eingeben:", type="password")

    if password:
        # 1. Versuch: Hole Passwort aus Umgebungsvariable (Cloud / Google Secrets)
        # Das ist der entscheidende Teil für Cloud Run!
        app_password = os.environ.get("APP_PASSWORD")

        # 2. Versuch: Hole Passwort aus st.secrets (Lokal)
        if not app_password:
            try:
                app_password = st.secrets.get("APP_PASSWORD")
            except:
                pass # Keine Secrets Datei gefunden (ist ok in der Cloud)

        # Fallback, falls gar nichts gesetzt ist
        if not app_password:
            app_password = "fallback_password_unsafe"

        if password == app_password:
            st.session_state.password_correct = True
            st.success("✅ Willkommen!")
            st.rerun()
        else:
            st.error("❌ Falsches Passwort")
    return False

# Authentifizierung durchführen (GANZ AM ANFANG!)
if AUTH_ENABLED:
    if not check_password():
        st.stop()

def format_timestamp(ts):
    if isinstance(ts, datetime):
        return ts.strftime("%d.%m.%Y, %H:%M:%S")
    return str(ts)

import logging

# Logging konfigurieren
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
# HTTP-Request-Spam unterdrücken (HuggingFace, httpx)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("sentence_transformers").setLevel(logging.WARNING)

# Debug-Mode aktivieren?
# Wir prüfen erst die Umgebungsvariable (Cloud), dann die Secrets (Lokal)
try:
    # Cloud-Weg (Environment Variable)
    debug_env = os.environ.get("DEBUG_MODE", "False").lower() == "true"

    # Lokaler Weg (Secrets Datei)
    try:
        debug_local = st.secrets.get("DEBUG_MODE", False)
    except:
        debug_local = False # Datei fehlt, ist ok

    DEBUG_MODE = debug_env or debug_local

except Exception:
    DEBUG_MODE = False

if DEBUG_MODE:
    logger.setLevel(logging.DEBUG)
    st.sidebar.info("🐛 Debug-Mode AKTIV")

# ==============================================================================
# 1. KONFIGURATION
# ==============================================================================

st.set_page_config(
    page_title=f"Forschungs-Cockpit {APP_VERSION}",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==============================================================================
# 2. KONSTANTEN
# ==============================================================================

# v50.9-local: PROJECT_ID und GEMINI_API_KEY entfernt (kein Cloud-Backend mehr)

# ==============================================================================
# 3. HELFERFUNKTIONEN
# ==============================================================================

@st.cache_resource
def configure_llm():
    """v50.9-local: LM Studio braucht kein globales Configure.
    llm_wrapper übernimmt die Verbindung transparent."""
    return True

# --- NEU: Caching für die Chat-Liste (Verhindert das Verschwinden der Auswahl!) ---
@st.cache_data(ttl=600) # 10 Minuten Cache
def get_cached_chat_list():
    """Lädt die Chat-Liste und cacht sie, damit die UI nicht flackert."""
    return get_chat_list()

def clear_chat_cache():
    """Muss aufgerufen werden, wenn ein neuer Chat entsteht, damit er in der Liste erscheint."""
    get_cached_chat_list.clear()

def get_default_settings():
    return {
        'temperature': 0.2, 
        'top_p': 0.95, 
        'system_instruction': DEFAULT_SYSTEM_INSTRUCTION, 
        'use_search': False,  # v50.9-local: kein Google Search in LM Studio
        'debug_mode': False,
        'model_name': LM_STUDIO_MODEL
    }

def send_message_local(prompt, history, system_instruction, temperature, **kwargs):
    """Sendet eine Nachricht an den lokalen LLM via llm_wrapper (v50.9-local).

    Ersetzt send_message_with_rest_api (Gemini REST).
    kwargs schluckt nicht mehr benötigte Parameter (top_p, use_search, debug_mode).

    Returns:
        Generator (für st.write_stream) — echtes Streaming-Output.
    """
    return llm_call_streaming(
        prompt,
        task="chat",
        system_instruction=system_instruction,
        temperature=temperature,
        history=history,
    )

# ==============================================================================
# IMPORT-SEITE (v47 Original - unverändert)
# ==============================================================================

def render_import_page():
    st.title("📥 Daten importieren")
    st.markdown("---")

    tab_paste, tab_upload, tab_json = st.tabs(["📋 Copy-Paste (Text)", "📄 Datei-Upload (HTML/PDF/ePub/MD)", "💾 JSON Backup"])

    # TAB 1: Copy-Paste
    with tab_paste:
        st.info("Anleitung: Chat-Text markieren (Strg+A), kopieren (Strg+C) und hier einfügen.")
        chat_text_input = st.text_area("Chat-Text hier einfügen:", height=300, key="gemini_paste_area")

        if st.button("🚀 Importieren (Paste)", use_container_width=True, type="primary"):
            if chat_text_input.strip():
                container = st.container()
                try:
                    importer = get_importer('text_fallback')
                    messages = importer.parse(chat_text_input, container=container)

                    if messages:
                         result = importer.import_to_firestore(messages, metadata={'source': 'paste'})
                         if result['chat_id']:
                                container.success(f"✅ Fertig! {result['message_count']} Nachrichten importiert.")
                                # NEU: Cache invalidieren und Chat öffnen
                                st.cache_data.clear()
                                st.session_state.chat_id = result['chat_id']
                                st.session_state.history = load_chat_history(result['chat_id'])
                                st.rerun()
                         else:
                                container.error("❌ Fehler beim Speichern in DB.")
                except Exception as e:
                    st.error(f"❌ Import-Fehler: {e}")
            else:
                st.error("❌ Bitte füge zuerst Text ein.")

    # TAB 2: Datei-Upload
    with tab_upload:
        # 1. Info aktualisiert (NEU: .md hinzugefügt)
        st.markdown("Unterstützte Formate: `.html`, `.txt`, `.pdf`, `.epub`, `.fb2`, `.md`")

        parser_mode = st.radio(
            "Modus:", 
            ["🤖 Auto-Detect (empfohlen)", "🎯 Manuell wählen", "🧠 Erzwinge KI-Parsing (Text)"],
            horizontal=True
        )

        manual_platform = None
        if parser_mode == "🎯 Manuell wählen":
            platform_options = {k: v().platform_name for k, v in IMPORTERS.items()}
            selected_name = st.selectbox("Plattform:", options=list(platform_options.values()))
            manual_platform = next((k for k, v in platform_options.items() if v == selected_name), None)

        # 2. Uploader aktualisiert (NEU: "md", "markdown" erlaubt)
        uploaded_files = st.file_uploader(
            "Dateien wählen:", 
            type=["html", "htm", "txt", "pdf", "epub", "fb2", "md", "markdown"], 
            accept_multiple_files=True
        )

        if uploaded_files and st.button("🚀 Start Upload", type="primary"):
            for uploaded_file in uploaded_files:
                file_container = st.container()
                file_container.markdown(f"**📄 {uploaded_file.name}**")
                try:
                    file_content = uploaded_file
                    # NEU: .md Dateien direkt in den Speicher lesen
                    if uploaded_file.name.lower().endswith(('.html', '.htm', '.txt', '.md', '.markdown')):
                        file_content = uploaded_file.read()

                    platform_key = 'text_fallback'
                    if parser_mode == "🧠 Erzwinge KI-Parsing (Text)":
                        platform_key = 'text_fallback'
                        if isinstance(file_content, bytes):
                            file_content = file_content.decode('utf-8', errors='ignore')
                    elif manual_platform:
                        platform_key = manual_platform
                    else:
                        filename = uploaded_file.name.lower()
                        if filename.endswith('.pdf'):
                            platform_key = 'pdf'
                        elif filename.endswith('.epub'):
                            platform_key = 'epub'
                        elif filename.endswith('.fb2'):
                            platform_key = 'fb2'
                        # 3. NEU: Markdown-Weiche hinzugefügt
                        elif filename.endswith(('.md', '.markdown')):
                            platform_key = 'markdown'
                        elif filename.endswith('.txt'):
                            platform_key = 'text_fallback'
                            if isinstance(file_content, bytes):
                                file_content = file_content.decode('utf-8', errors='ignore')
                        else:
                            detected, conf, _ = detect_platform(file_content)
                            if detected:
                                platform_key = detected
                                file_container.info(f"🔍 Erkannt: {IMPORTERS[platform_key]().platform_name} ({conf:.0%})")
                            else:
                                file_container.warning("⚠️ Keine Signatur erkannt. Nutze Text-Analyse...")
                                platform_key = 'text_fallback'
                                if isinstance(file_content, bytes):
                                    file_content = file_content.decode('utf-8', errors='ignore')

                    importer = get_importer(platform_key)
                    messages = importer.parse(file_content, container=file_container)
                    if messages:
                         if len(messages) == 1 and messages[0].get('content') == 'Diagnose Mode - Kein Import':
                            continue
                         res = importer.import_to_firestore(messages, metadata={'container': file_container})
                         if res['chat_id']:
                             file_container.success(f"✅ Importiert: {res['message_count']} Nachrichten.")
                             # Cache invalidieren und Chat öffnen
                             st.cache_data.clear()
                             st.session_state.chat_id = res['chat_id']
                             st.session_state.history = load_chat_history(res['chat_id'])
                             st.rerun()
                         else:
                             file_container.error("❌ Fehler beim Speichern.")
                    else:
                        file_container.error("❌ Keine Nachrichten gefunden.")
                except Exception as e:
                    file_container.error(f"❌ Kritischer Fehler bei {uploaded_file.name}: {e}")

    # TAB 3: JSON
    with tab_json:
        uploaded_json = st.file_uploader("JSON-Datei:", type=["json"], key="json_direct")
        if uploaded_json and st.button("💾 Wiederherstellen", type="primary"):
            try:
                json_data = json.load(uploaded_json)
                if isinstance(json_data, list):
                    chat_title = f"Restore: {uploaded_json.name}"
                    chat_id = create_chat_in_firestore(chat_title)
                    count = 0
                    for msg in json_data:
                        save_message(chat_id, msg.get('role','user'), msg.get('content',''))
                        count += 1
                    st.success(f"✅ {count} Nachrichten wiederhergestellt.")
            except Exception as e:
                st.error(f"❌ Fehler: {e}")

# ==============================================================================
# ANALYSE-SEITE (v47 + v48-Feature: Exegese/Diskurs-Modi)
# ==============================================================================

def render_analysis_page():
    st.title("🧠 Langzeitgedächtnis & Suche")
    st.markdown("---")

    db = get_firestore_client()
    if not db:
        st.error("Keine Datenbankverbindung.")
        return

    all_chats = get_chat_list()
    chat_map = {c['id']: c['title'] for c in all_chats}

    tab_search, tab_stats = st.tabs(["🔍 Semantische Suche", "📊 Statistik"])

    with tab_search:
        # ==============================================================================
        # 1. DISPLAY-BLOCK (Zuerst prüfen, ob Ergebnisse da sind!)
        # ==============================================================================
        if 'rag_results' in st.session_state and 'rag_answer' in st.session_state:

            # --- RESET BUTTON (Um zurück zur Eingabe zu kommen) ---
            if st.button("🔄 Neue Analyse starten", type="secondary", use_container_width=True):
                # State bereinigen
                keys_to_clear = ['rag_results', 'rag_answer', 'rag_query', 'rag_mode', 'verification_log']
                for k in keys_to_clear:
                    if k in st.session_state:
                        del st.session_state[k]
                st.rerun()

            # --- ERGEBNISSE ANZEIGEN (Original-Code) ---
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

            # Enforcer (v47 Original)
            rag_engine = CitationRAG()
            with st.expander("🛡️ Enforcer Protokoll (Validierung)", expanded=False):
                warnings = rag_engine.validate_citations(answer, len(results))

                if 'verification_log' not in st.session_state:
                    st.session_state.verification_log = {'structure_check': [], 'deep_check': []}
                st.session_state.verification_log['structure_check'] = warnings

                if warnings:
                    for w in warnings:
                        st.error(w)
                else:
                    st.success("✅ Struktur-Check bestanden: Alle Zitate sind gültig.")

                if st.button("🕵️‍♂️ Tiefenprüfung starten (Faktencheck)"):
                    import asyncio

                    # Container für Progress Bar
                    progress_bar = st.progress(0, text="Starte Enforcer Engine...")
                    status_text = st.empty()

                    # Callback für die Progress Bar
                    def update_progress(p):
                        progress_bar.progress(p, text=f"Prüfe Fakten... {int(p*100)}%")

                    # Async Runner
                    async def run_deep_check():
                        sentences = re.split(r'(?<=[.!?])\s+', answer)
                        # Filtere leere Sätze
                        sentences = [s for s in sentences if s.strip()]

                        if not sentences:
                            return []

                        return await rag_engine.verify_facts_parallel(
                            sentences, 
                            results, 
                            progress_callback=update_progress
                        )

                    with st.spinner("Der Enforcer prüft parallel (v49.1 Speedup)..."):
                        # Führe Async Code im Streamlit Sync Context aus
                        deep_check_log = asyncio.run(run_deep_check())

                        st.session_state.verification_log['deep_check'] = deep_check_log

                        # Auswertung anzeigen
                        issues_found = 0
                        checked_count = len(deep_check_log)

                        for entry in deep_check_log:
                            sent = entry['sentence']
                            m = entry['source_id']
                            is_valid = entry['valid']
                            reason = entry['reason']

                            if is_valid:
                                st.markdown(f"✅ **Verifiziert:** *\"{sent[:50]}...\"* -> Quelle [{m}]")
                            else:
                                st.error(f"❌ **Diskrepanz:** *\"{sent}\"*")
                                st.markdown(f"Grund: {reason}")
                                issues_found += 1

                        progress_bar.empty()
                        status_text.empty()

                        if checked_count == 0:
                            st.warning("Keine prüfbaren Zitate gefunden.")
                        elif issues_found == 0:
                            st.balloons()
                            st.success(f"🎉 Perfekt! {checked_count} Fakten erfolgreich verifiziert.")

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

                icon = "🤖"
                if platform == "Grok": icon = "🚀"
                elif platform == "Claude": icon = "🧠"
                elif platform == "Gemini": icon = "✨"
                elif platform == "DeepSeek": icon = "🐳"
                elif platform == "Kimi": icon = "🌙"
                elif platform == "GLM-4": icon = "💬"
                elif platform == "ChatGPT": icon = "🟢"
                elif platform == "LM Arena": icon = "⚔️"

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

                    st.caption(f"Original-ID: {res.get('message_id')} | Datum: {real_date}")

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

            safe_query = "".join([c for c in st.session_state.rag_query if c.isalnum() or c in (' ', '-', '_')]).strip()[:30]
            filename_base = f"Analyse_{safe_query}"

            col_exp1, col_exp2, col_exp3 = st.columns(3)
            with col_exp1:
                st.download_button("📄 Als Markdown", md_data, f"{filename_base}.md", "text/markdown", use_container_width=True)
            with col_exp2:
                st.download_button("📊 Als Excel", excel_data, f"{filename_base}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
            with col_exp3:
                st.download_button("🤖 Als JSON", json_data, f"{filename_base}.json", "application/json", use_container_width=True)

        # ==============================================================================
        # 2. INPUT-BLOCK (Nur anzeigen, wenn KEINE Ergebnisse da sind)
        # ==============================================================================
        else:
            st.subheader("Wissensbasis durchsuchen")

            with st.expander("🔍 Such-Fokus (Scope)", expanded=True):
                search_mode = st.radio(
                    "Modus:",
                    ["🎯 Investigativ (Nur ausgewählte Quellen)", "🧠 Gedächtnis (Alles durchsuchen)"],
                    index=0,
                    horizontal=True
                )

                selected_chat_ids = None
                if search_mode == "🎯 Investigativ (Nur ausgewählte Quellen)":
                    # v48-Feature: Alphabetisch sortieren!
                    sorted_chats = sorted(all_chats, key=lambda x: x['title'].lower())
                    chat_options = {c['title']: c['id'] for c in sorted_chats}
                    selected_titles = st.multiselect(
                        "Quellen auswählen:",
                        options=list(chat_options.keys()),
                        default=[]
                    )
                    if selected_titles:
                        selected_chat_ids = [chat_options[t] for t in selected_titles]
                    else:
                        st.warning("⚠️ Keine Quellen gewählt!")
                        selected_chat_ids = []

            col1, col2 = st.columns([3, 1])
            with col1:
                default_query = st.session_state.get('rag_query', "")
                search_query = st.text_input("Thema / Frage:", value=default_query, placeholder="z.B. Was sagt die KI über Zensur?")
            with col2:
                role_filter = st.radio("Suche in:", ["Alles", "Nur KI (Model)", "Nur Ich (User)"], index=1)

            search_btn = st.button("Analysieren & Antworten 🚀", type="primary", use_container_width=True)

            if search_btn and search_query:
                vector_store = FirestoreVectorStore(db)
                rag_engine = CitationRAG(vector_store=vector_store)

                with st.spinner(f"1. Suche relevante Fakten..."):
                    try:
                        keywords = rag_engine.extract_keywords(search_query)
                        dynamic_weight = 0.3
                        raw_results, query_vec = vector_store.hybrid_search(
                            search_query, 
                            keywords, 
                            limit=70, 
                            filter_role=None,
                            allowed_chat_ids=selected_chat_ids,
                            keyword_weight=dynamic_weight
                        )
                        results = calculate_confidence_scores(query_vec, raw_results)

                        if not results:
                            st.warning("Keine relevanten Quellen gefunden.")
                            if 'rag_results' in st.session_state:
                                del st.session_state.rag_results
                        else:
                            # ===================================================================
                            # NEU v50.3: IMBALANCE-CHECK VOR SYNTHESE!
                            # ===================================================================

                            # Temporäres Reranking für Imbalance-Analyse
                            with st.spinner("2. Analysiere Chunk-Verteilung..."):

                                # NEU – ein Aufruf, kein LLM-Call, kein weggeworfenes Ergebnis:
                                imbalance_info = rag_engine.check_imbalance_only(search_query, results, chat_id=selected_chat_ids)

                            # ===================================================================
                            # VARIANTE C: GESTUFTE INTERVENTION
                            # ===================================================================

                            strict_parity_choice = False  # Default
                            show_synthesis_button = True  # Normalerweise direkt weiter

                            if imbalance_info and imbalance_info.severity == "critical":
                                # CRITICAL (≥10:1) → USER MUSS ENTSCHEIDEN!

                                st.error("⚠️ **Kritische Unausgeglichenheit erkannt!**")

                                with st.expander("📊 Chunk-Verteilung (Details)", expanded=True):
                                    # Erstelle Tabelle
                                    import pandas as pd

                                    df_data = []
                                    total_chunks = sum(imbalance_info.doc_distribution.values())

                                    for doc_title, count in sorted(
                                        imbalance_info.doc_distribution.items(), 
                                        key=lambda x: x[1], 
                                        reverse=True
                                    ):
                                        percentage = (count / total_chunks) * 100
                                        df_data.append({
                                            'Dokument': doc_title,
                                            'Chunks': count,
                                            'Anteil': f"{percentage:.1f}%"
                                        })

                                    df = pd.DataFrame(df_data)
                                    st.dataframe(df, use_container_width=True)

                                    st.caption(f"⚠️ Verhältnis größtes:kleinstes = **{imbalance_info.ratio:.1f}:1** (KRITISCH!)")

                                st.markdown("""
**Das schwächste Dokument hat signifikant weniger Material als die anderen.**

Wie soll die Engine vorgehen?
""")

                                parity_mode = st.radio(
                                    "Parität-Modus:",
                                    [
                                        "🔧 Pragmatisch (Jedes Dokument nutzt verfügbares Material)",
                                        "⚖️ Strikt (Alle Dokumente auf kleinstes begrenzen)"
                                    ],
                                    key="parity_decision",
                                    help=f"""
**Pragmatisch:** Größtes Dokument nutzt bis zu {imbalance_info.max_chunks} Chunks, kleinstes {imbalance_info.min_chunks} Chunks.

**Strikt:** ALLE Dokumente werden auf {imbalance_info.min_chunks} Chunks begrenzt (perfekte Gleichheit).
"""
                                )

                                if parity_mode.startswith("⚖️"):
                                    st.info(f"✅ Alle Dokumente werden auf **{imbalance_info.min_chunks} Chunks** begrenzt (Strikte Parität).")
                                    strict_parity_choice = True
                                else:
                                    st.info("✅ Jedes Dokument nutzt sein verfügbares Material (Pragmatische Parität).")
                                    strict_parity_choice = False

                                # Bei critical: User muss Button klicken!
                                show_synthesis_button = True

                            elif imbalance_info and imbalance_info.severity == "info":
                                # INFO (5:1-10:1) → ZEIGE INFO-BOX, ABER BLOCKIERE NICHT

                                st.info(f"ℹ️ **Hinweis:** Chunk-Verteilung ist ungleich (Verhältnis: {imbalance_info.ratio:.1f}:1)")

                                with st.expander("📊 Details anzeigen"):
                                    import pandas as pd

                                    df_data = []
                                    total_chunks = sum(imbalance_info.doc_distribution.values())

                                    for doc_title, count in sorted(
                                        imbalance_info.doc_distribution.items(), 
                                        key=lambda x: x[1], 
                                        reverse=True
                                    ):
                                        percentage = (count / total_chunks) * 100
                                        df_data.append({
                                            'Dokument': doc_title,
                                            'Chunks': count,
                                            'Anteil': f"{percentage:.1f}%"
                                        })

                                    df = pd.DataFrame(df_data)
                                    st.dataframe(df, use_container_width=True)

                                st.caption("Die Engine verwendet pragmatische Parität (jedes Dokument nutzt verfügbares Material).")
                                strict_parity_choice = False
                                show_synthesis_button = False  # Kein extra Button nötig

                            else:
                                # NONE (< 5:1) → Keine Warnung, direkt weiter
                                show_synthesis_button = False

                            # ===================================================================
                            # SYNTHESE (mit oder ohne Button, je nach Severity)
                            # ===================================================================

                            run_synthesis = False

                            if show_synthesis_button:
                                # Bei critical/info: Zeige Button
                                if st.button("🚀 Synthese starten", type="primary", use_container_width=True):
                                    run_synthesis = True
                            else:
                                # Bei none: Direkt weiter
                                run_synthesis = True

                            if run_synthesis:
                                with st.spinner("3. Generiere Antwort mit Zitationen..."):
                                    raw_answer, used_sources, mode_name = rag_engine.generate_answer(
                                        search_query, 
                                        results,
                                        strict_parity=strict_parity_choice,  # v50.3: User-Choice!
                                        pre_reranked=imbalance_info
                                    )

                                    valid_indices = list(range(1, len(used_sources) + 1))

                                    with st.spinner("4. Veredle Synthese (Cleanup)..."):
                                        answer = post_process_synthesis(raw_answer, valid_indices)

                                st.session_state.rag_results = used_sources
                                st.session_state.rag_answer = answer
                                st.session_state.rag_query = search_query
                                st.session_state.rag_mode = mode_name

                                # RERUN UM ERGEBNISSE ANZUZEIGEN (Springt zu Block 1)
                                st.rerun()

                    except Exception as e:
                        st.error(f"Fehler: {e}")
                        import traceback
                        print(traceback.format_exc())

    with tab_stats:
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
# 4. SESSION STATE
# ==============================================================================

if 'chat_id' not in st.session_state: st.session_state.chat_id = None
if 'history' not in st.session_state: st.session_state.history = []
if 'password_correct' not in st.session_state: st.session_state.password_correct = False
if 'title_generated' not in st.session_state: st.session_state.title_generated = False
if 'rename_chat_id' not in st.session_state: st.session_state.rename_chat_id = None
if 'delete_confirm_id' not in st.session_state: st.session_state.delete_confirm_id = None
if 'global_settings' not in st.session_state: st.session_state.global_settings = load_global_settings(get_default_settings())
if 'last_error' not in st.session_state: st.session_state.last_error = None

# ==============================================================================
# 5. NAVIGATION (v47 ORIGINAL + v47 Admin-Features)
# ==============================================================================

st.sidebar.title("📡 Navigation")
page = st.sidebar.selectbox(
    "Seite wählen",
    ["💬 Chat", "📥 Import", "🧠 Analyse", "🏷️ Labeling", "💾 DB-Export"],  # v47 Features!
    help="Wähle die gewünschte Funktion aus"
)

# ==============================================================================
# 6. SEITEN-LOGIK
# ==============================================================================

if page == "📥 Import":
    render_import_page()
elif page == "🏷️ Labeling":
    render_bulk_labeling_ui()  # v47 Feature
elif page == "💾 DB-Export":
    render_bulk_export_ui()     # v47 Feature
elif page == "🧠 Analyse":
    render_analysis_page()
elif page == "💬 Chat":
    st.title("🧠 Dein persönliches Chat-Gedächtnis")


    # ==========================================================================
# v50 HYBRID COCKPIT (INTEGRATION) - FIXED (State Persistence)
    # ==========================================================================
    with st.sidebar:
        st.markdown("---")
        st.header("🎛️ Hybrid-Cockpit")
        
        # 1. HAUPTSCHALTER (Mit Key!)
        use_db = st.toggle(
            "🔌 Datenbank-Wissen", 
            value=False,
            key="toggle_use_db",
            help="AN: Zugriff auf deine Dokumente (RAG).\nAUS: Freier Chat mit lokalem LLM."
        )
        
        selected_rag_ids = None
        use_router = False
        
        if use_db:
            st.caption("🗃️ Datenbank-Steuerung")
            
            # 2. ROUTER (Mit Key!)
            use_router = st.checkbox(
                "🧠 Auto-Router (v50)", 
                value=True,
                key="check_use_router",
                help="AN: KI entscheidet Strategie (Fakt vs. Poesie).\nAUS: Standard-Suche."
            )
            
            # 3. DOKUMENTEN-FILTER (Mit Caching & Keys!)
            st.markdown("---")
            c1, c2 = st.columns([4, 1])
            c1.caption("🔍 Fokus (Scope)")
            
            if c2.button("🔄", help="Liste aktualisieren"):
                clear_chat_cache()
                st.rerun()
            
            # HIER IST DER FIX: Wir nutzen die gecachte Liste!
            all_chats_list = get_cached_chat_list()
            
            # Sortieren
            all_chats_list = sorted(all_chats_list, key=lambda x: x['title'].lower())
            chat_options = {c['title']: c['id'] for c in all_chats_list}
            
            # Radio Button mit Key (Wichtig für State)
            filter_mode = st.radio(
                "Quelle:", 
                ["Alles durchsuchen", "Auswahl treffen"], 
                label_visibility="collapsed",
                key="radio_filter_mode"
            )
            
            if filter_mode == "Auswahl treffen":
                # FIX: State-Persistenz erzwingen
                # Wir prüfen, ob im Session State schon eine Auswahl liegt
                current_selection = st.session_state.get("multi_select_docs", [])
                
                # Wir filtern die Auswahl, damit nur noch existierende Optionen drin sind
                # (Falls sich die Chat-Liste im Hintergrund geändert hat)
                valid_selection = [s for s in current_selection if s in chat_options.keys()]
                
                selected_titles = st.multiselect(
                    "Dokumente wählen:",
                    options=list(chat_options.keys()),
                    default=valid_selection, # <--- HIER IST DER FIX
                    placeholder="Wähle Chats/Texte...",
                    key="multi_select_docs"
                )
                
                if selected_titles:
                    selected_rag_ids = [chat_options[t] for t in selected_titles]
                else:
                    st.warning("⚠️ Keine Auswahl = Keine Suche!")
        
        st.markdown("---")
        st.sidebar.caption(f"📦 Forschungs-Cockpit {APP_VERSION}")
        
        # --- ADMIN BEREICH ---
        with st.expander("⚙️ Admin-Bereich", expanded=False):
            st.subheader("🔐 Passwort ändern")
            new_password = st.text_input("Neues Passwort:", type="password", key="new_pwd")
            
            if st.button("Passwort speichern", use_container_width=True):
                st.warning("⚠️ Online: Passwort muss in Google Secret Manager geändert werden.")
                st.info("Lokal: Ändere .streamlit/secrets.toml manuell")
        
        # --- KONVERSATIONEN (Mit Cache-Invalidierung!) ---
        st.header("💬 Konversationen")
        
        if st.button("➕ Neuer Chat", use_container_width=True, type="primary"):
            st.session_state.chat_id = None
            st.session_state.history = []
            st.session_state.title_generated = False
            st.session_state.rename_chat_id = None
            st.session_state.delete_confirm_id = None
            st.session_state.last_error = None
            clear_chat_cache() # Cache löschen, damit neuer Chat sichtbar wird
            st.rerun()
        
        # Liste laden (Gecacht!)
        chat_list = get_cached_chat_list()
        
        for chat in chat_list:
            is_active = (st.session_state.chat_id == chat['id'])
            
            with st.container():
                # FALL A: UMBENENNEN
                if st.session_state.rename_chat_id == chat['id']:
                    new_name = st.text_input(
                        "Neuer Name:", 
                        value=chat['title'], 
                        key=f"rename_input_{chat['id']}", 
                        label_visibility="collapsed"
                    )
                    
                    c1, c2 = st.columns(2)
                    
                    if c1.button("✓", key=f"save_{chat['id']}", use_container_width=True):
                        if rename_chat(chat['id'], new_name.strip()):
                            st.session_state.rename_chat_id = None
                            clear_chat_cache() # Cache aktualisieren
                            st.rerun()
                    
                    if c2.button("✗", key=f"cancel_{chat['id']}", use_container_width=True):
                        st.session_state.rename_chat_id = None
                        st.rerun()
                
                # FALL B: LÖSCHEN BESTÄTIGEN
                elif st.session_state.delete_confirm_id == chat['id']:
                    st.warning(f"**{chat['title']}** wirklich löschen?")
                    
                    c1, c2 = st.columns(2)
                    
                    if c1.button("Ja, löschen", key=f"confirm_del_{chat['id']}", use_container_width=True, type="primary"):
                        if delete_chat(chat['id']):
                            if st.session_state.chat_id == chat['id']:
                                st.session_state.chat_id = None
                                st.session_state.history = []
                            st.session_state.delete_confirm_id = None
                            clear_chat_cache() # Cache aktualisieren
                            st.rerun()
                    
                    if c2.button("Nein", key=f"cancel_del_{chat['id']}", use_container_width=True):
                        st.session_state.delete_confirm_id = None
                        st.rerun()
                
                # FALL C: NORMALE ANZEIGE
                else:
                    cols = st.columns([6, 1, 1])
                    
                    if cols[0].button(
                        chat['title'], 
                        key=f"load_{chat['id']}", 
                        use_container_width=True, 
                        type="primary" if is_active else "secondary"
                    ):
                        st.session_state.chat_id = chat['id']
                        st.session_state.history = load_chat_history(chat['id'])
                        st.session_state.title_generated = True
                        st.session_state.rename_chat_id = None
                        st.session_state.delete_confirm_id = None
                        st.session_state.last_error = None
                        st.rerun()
                    
                    if cols[1].button("✏️", key=f"edit_{chat['id']}", help="Umbenennen"):
                        st.session_state.rename_chat_id = chat['id']
                        st.rerun()
                    
                    if cols[2].button("🗑️", key=f"delete_{chat['id']}", help="Löschen"):
                        st.session_state.delete_confirm_id = chat['id']
                        st.rerun()
                    
                    if chat.get('lastUpdated'):
                        st.caption(f"🕒 {format_timestamp(chat['lastUpdated'])}")
        
        st.markdown("---") # Die Linie bleibt!
        
        # ==============================================================================
        # ERWEITERTE MODELLEINSTELLUNGEN (v47 ORIGINAL - WIEDERHERGESTELLT!)
        # ==============================================================================
        with st.expander("⚙️ Modelleinstellungen", expanded=False):
            st.caption("Globale Einstellungen für neue Chats")
            
            # v50.9-local: LM Studio — Modell wird in .env/LM_STUDIO_MODEL gesetzt,
            # nicht per UI-Dropdown. Wir zeigen es als Info an.
            current_model = LM_STUDIO_MODEL
            st.info(f"🤖 Aktives Modell: **{current_model}** (via LM Studio)\nModell wechseln: `LM_STUDIO_MODEL` in `.env` anpassen.")
            selected_model = current_model  # Wird unverändert gespeichert
            
            temp = st.slider(
                "Temperature", 
                0.0, 1.0, 
                st.session_state.global_settings.get('temperature', 0.2), 
                0.1
            )
            
            top_p = st.slider(
                "Top-P", 
                0.0, 1.0, 
                st.session_state.global_settings.get('top_p', 0.95), 
                0.05
            )
            
            # v50.9-local: Google Search nicht verfügbar in LM Studio
            use_search = False
            
            debug_mode = st.checkbox(
                "🐛 Debug-Modus", 
                value=st.session_state.global_settings.get('debug_mode', False)
            )
            
            sys_instr = st.text_area(
                "System Instruction", 
                st.session_state.global_settings.get('system_instruction', DEFAULT_SYSTEM_INSTRUCTION), 
                height=250
            )
            
            if st.button("💾 Einstellungen speichern", use_container_width=True):
                st.session_state.global_settings['model_name'] = selected_model
                st.session_state.global_settings['temperature'] = temp
                st.session_state.global_settings['top_p'] = top_p
                st.session_state.global_settings['system_instruction'] = sys_instr
                st.session_state.global_settings['use_search'] = use_search
                st.session_state.global_settings['debug_mode'] = debug_mode
                
                if save_global_settings(selected_model, temp, top_p, sys_instr, use_search, debug_mode):
                    st.success("✓ Gespeichert!")
                    time.sleep(1)
                    st.rerun()
    
        # ==============================================================================
        # 🚑 NOTFALL-SIDEBAR (Immer sichtbar)
        # ==============================================================================
        st.markdown("---")
        st.error("🚑 Notfall-Eingriff")

        if st.session_state.history:
            last_msg = st.session_state.history[-1]
            last_role = last_msg.get('role', '???')
            last_text = last_msg.get('parts', [{}])[0].get('text', '')

            st.caption(f"Status: Letzte Nachricht von **{last_role.upper()}**")
            with st.expander("Inhalt prüfen"):
                st.text(f"Länge: {len(last_text)} Zeichen")
                st.code(last_text[:100]) # Zeige die ersten 100 Zeichen

            if st.button("💀 Letztes Element löschen (Force)", key="sidebar_force_delete", type="primary"):
                # 1. DB Bereinigung (Versuch)
                try:
                    if st.session_state.chat_id:
                        from modules.database import get_firestore_client
                        db = get_firestore_client()
                        db.execute("""
                            DELETE FROM messages WHERE id IN (
                                SELECT id FROM messages WHERE chat_id = ?
                                ORDER BY timestamp DESC LIMIT 1
                            )
                        """, (st.session_state.chat_id,))
                        db.commit()
                except Exception as e:
                    print(f"DB Error: {e}")

                # 2. State Bereinigung
                st.session_state.history.pop()
                st.session_state.last_error = None
                st.rerun()
        else:
            st.caption("History ist leer.")

    # --- HAUPT-CHAT-INTERFACE (v50 HYBRID) ---
    if st.session_state.last_error:
        st.error(f"🚨 **Ein Fehler ist aufgetreten:**\n\n{st.session_state.last_error}")
        
        if st.button("❌ Fehlermeldung schließen"):
            st.session_state.last_error = None
            st.rerun()
    
    # Chat-Historie anzeigen
    for message in st.session_state.history:
        with st.chat_message(message["role"]):
            st.markdown(message["parts"][0]["text"])
    
    # ==============================================================================
    # EDIT/DELETE/EXPORT BUTTONS (v50.6 - EXPORT NEU HINZUGEFÜGT)
    # ==============================================================================
    if st.session_state.history and len(st.session_state.history) >= 2 and st.session_state.history[-1]['role'] == 'model':
        action_container = st.container()
        
        with action_container:
            col1, col2, col3, col4 = st.columns([.6, .1, .1, .2])
            
            # EDIT BUTTON
            with col2:
                if st.button("✏️", key="edit_last_turn", help="Letzte Frage bearbeiten"):
                    try:
                        db = get_firestore_client()
                        if db and st.session_state.chat_id:
                            db.execute("""
                                DELETE FROM messages WHERE id IN (
                                    SELECT id FROM messages WHERE chat_id = ?
                                    ORDER BY timestamp DESC LIMIT 2
                                )
                            """, (st.session_state.chat_id,))
                            db.commit()
                            
                            st.session_state.history = st.session_state.history[:-2]
                            st.success("Letzte Runde gelöscht.")
                            time.sleep(1)
                            st.rerun()
                    
                    except Exception as e: 
                        st.error(f"Fehler: {e}")
            
            # DELETE BUTTON
            with col3:
                if st.button("🗑️", key="delete_last_turn", help="Letzte Runde löschen"):
                    try:
                        db = get_firestore_client()
                        if db and st.session_state.chat_id:
                            db.execute("""
                                DELETE FROM messages WHERE id IN (
                                    SELECT id FROM messages WHERE chat_id = ?
                                    ORDER BY timestamp DESC LIMIT 2
                                )
                            """, (st.session_state.chat_id,))
                            db.commit()
                            
                            st.session_state.history = st.session_state.history[:-2]
                            st.success("Letzte Runde gelöscht.")
                            time.sleep(1)
                            st.rerun()
                    
                    except Exception as e: 
                        st.error(f"Fehler: {e}")
            
            # EXPORT BUTTON (FIXED v50.6)
            with col4:
                # 1. Der Trigger-Button
                if st.button("📄 Export", key="prep_export_btn", help="Markdown generieren", use_container_width=True):
                    with st.spinner("Generiere Dokument..."):
                        from modules.export import generate_markdown, generate_chat_markdown
                        from modules.database import get_chat_list # Korrekter Import!

                        # Chat-Titel holen
                        chat_title = "Chat-Protokoll"
                        if st.session_state.chat_id:
                            try:
                                db = get_firestore_client()
                                row = db.execute(
                                    "SELECT title FROM chats WHERE id = ?",
                                    (st.session_state.chat_id,)
                                ).fetchone()
                                if row:
                                    chat_title = row[0]                            
                            except Exception as e:
                                print(f"Export-Fehler (Titel): {e}")

                        # Prüfen: Haben wir RAG-Daten?
                        has_rag_sources = (
                            hasattr(st.session_state, 'last_rag_sources') 
                            and st.session_state.last_rag_sources
                            and len(st.session_state.last_rag_sources) > 0
                        )

                        markdown = None
                        filename = "export.md"

                        try:
                            if has_rag_sources:
                                # Voller Forschungs-Export
                                all_chats = get_chat_list()
                                chat_map = {c['id']: c['title'] for c in all_chats}

                                markdown = generate_markdown(
                                    query=st.session_state.last_rag_query,
                                    answer=st.session_state.history[-1]["parts"][0]["text"],
                                    results=st.session_state.last_rag_sources,
                                    chat_map=chat_map,
                                    verification_log=None
                                )
                                filename = f"Forschungsnotiz_{datetime.now().strftime('%H%M')}.md"
                            else:
                                # Einfacher Chat-Export
                                markdown = generate_chat_markdown(st.session_state.history, chat_title)
                                filename = f"Chat_{datetime.now().strftime('%H%M')}.md"

                            # WICHTIG: Im State speichern!
                            st.session_state.export_data = markdown
                            st.session_state.export_filename = filename
                            st.success("Fertig!")

                        except Exception as e:
                            st.error(f"Fehler: {e}")
                            print(f"Export-Crash: {e}")

                # 2. Der Download-Button (Erscheint dauerhaft, wenn Daten da sind)
                if "export_data" in st.session_state and st.session_state.export_data:
                    st.download_button(
                        label="💾 Download",
                        data=st.session_state.export_data,
                        file_name=st.session_state.export_filename,
                        mime="text/markdown",
                        key="dl_btn_persistent",
                        use_container_width=True
                    )

    # ==============================================================================
    # INPUT & LOGIK-WEICHE
    # ==============================================================================
    if prompt := st.chat_input("Stelle deine Frage..."):
        
        # Chat-ID erstellen, falls noch nicht vorhanden
        if st.session_state.chat_id is None:
            st.session_state.chat_id = create_chat_in_firestore("Neuer Chat")
            if st.session_state.chat_id is None:
                st.error("Konnte keinen neuen Chat erstellen.")
                st.stop()
        
        # User-Message speichern
        st.session_state.history.append({"role": "user", "parts": [{"text": prompt}]})
        save_message(st.session_state.chat_id, "user", prompt)
        
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # --- WEICHE: RAG vs. FREIER CHAT ---
        with st.chat_message("model"):
            
            # PFAD A: DATENBANK (RAG)
            if use_db:
                # Validierung der Auswahl
                if filter_mode == "Auswahl treffen" and not selected_rag_ids:
                    st.error("⚠️ Du hast 'Auswahl treffen' gewählt, aber keine Dokumente markiert.")
                    st.stop()
                
                status_container = st.empty()
                
                try:
                    with status_container.status("🔍 Konsultiere Datenbank...", expanded=True) as status:
                        db = get_firestore_client()
                        vs = FirestoreVectorStore(db)
                        rag = CitationRAG(vector_store=vs)
                        
                        status.write("📚 Suche relevante Stellen...")
                        
                        results = rag.retrieve_with_rrf(
                            prompt, 
                            chat_id=selected_rag_ids, 
                            use_router=use_router
                        )
                        
                        if not results:
                            status.update(label="❌ Nichts gefunden", state="error")
                            intent = "UNKNOWN"
                            final_text = "Ich habe in den ausgewählten Dokumenten keine Informationen dazu gefunden."
                            sources = []
                        
                        else:
                            status.write("📝 Synthetisiere Antwort...")
                            final_text, sources, intent = rag.generate_answer(prompt, results)
                            status.update(label=f"✅ Fertig ({intent})", state="complete", expanded=False)
                        
                        # NEU v50.6: Speichere RAG-Metadaten für Export (nur letzte Antwort)
                        st.session_state.last_rag_sources = sources
                        st.session_state.last_rag_query = prompt
                        st.session_state.last_rag_intent = intent
                        
                        # TODO v51: In History speichern für dauerhafte Persistenz:
                        # st.session_state.history.append({
                        #     "role": "model", 
                        #     "parts": [{"text": final_text}],
                        #     "rag_metadata": {"sources": sources, "intent": intent, "query": prompt}
                        # })
                    
                    st.markdown(final_text)
                    
                    if sources:
                        with st.expander(f"📚 Quellen ({len(sources)})"):
                            for s in sources:
                                st.markdown(f"**[{s.get('source_id')}] {s.get('metadata', {}).get('chat_title', 'Dokument')}**")
                                st.caption(s.get('content')[:200] + "...")
                    
                    st.session_state.history.append({"role": "model", "parts": [{"text": final_text}]})
                    save_message(st.session_state.chat_id, "model", final_text)
                    st.rerun()  # <--- NEU: Damit die Antwort sicher stehen bleibt!
                except Exception as e:
                    st.error(f"RAG Fehler: {e}")
            
            else:
                    # RAG-State löschen (da kein RAG gelaufen ist)
                    if hasattr(st.session_state, 'last_rag_sources'):
                        del st.session_state.last_rag_sources
                    if hasattr(st.session_state, 'last_rag_query'):
                        del st.session_state.last_rag_query
                    if hasattr(st.session_state, 'last_rag_intent'):
                        del st.session_state.last_rag_intent

                    try:
                        settings = st.session_state.global_settings

                        # v50.9-local: Streaming-Output via st.write_stream
                        stream = send_message_local(
                            prompt,
                            st.session_state.history[:-1],
                            settings['system_instruction'],
                            settings['temperature'],
                        )
                        response_text = st.write_stream(stream)

                        st.session_state.history.append({"role": "model", "parts": [{"text": response_text}]})
                        save_message(st.session_state.chat_id, "model", response_text)
                        st.session_state.last_error = None
                        st.rerun()
                    except Exception as e:
                        st.session_state.last_error = str(e)
                        st.rerun()
        
        # Titel generieren (falls noch nicht geschehen)
        if not st.session_state.title_generated and len(st.session_state.history) >= 2:
            generate_and_update_title(st.session_state.chat_id, st.session_state.history)
            st.rerun()

# ==========================================
# ADMIN-BEREICH (Ganz unten in app.py)
# ==========================================
render_vector_admin_dashboard()