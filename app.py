# app_forschung_v46.py - Vollständige Version mit LM-Arena-Support
APP_VERSION = "v46"  # ← Ändere das bei jedem Update
print("=" * 80)
print("🚀 STARTUP: app_forschung_v46.py lädt...")
print("=" * 80)

import os
import hmac
from datetime import datetime
import streamlit as st
from google.cloud import firestore
import json
import re
from system_prompts import GEMINI_3_SYSTEM_INSTRUCTION
DEFAULT_SYSTEM_INSTRUCTION = GEMINI_3_SYSTEM_INSTRUCTION
import google.generativeai as genai
import requests
from bs4 import BeautifulSoup
import time
import traceback
from typing import Optional, Dict, List, Tuple
from dotenv import load_dotenv

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
# -----------------------------

from modules.bulk_labeling import render_bulk_labeling_ui
from modules.vector_admin import render_vector_admin_dashboard
from modules.vector_store import FirestoreVectorStore
from modules.citation_rag import CitationRAG
from modules.synthesis_utils import post_process_synthesis
from modules.confidence_scoring import calculate_confidence_scores, get_color_for_score
from modules.export import generate_markdown, generate_json, generate_excel
from modules.bulk_export import render_bulk_export_ui

# CACHE-BUSTER: 2025-12-05 19:00 - Gemini Collector Fix

# Lade Umgebungsvariablen aus der .env-Datei (nur für lokale Entwicklung)
load_dotenv(override=False)
# HIER DIE TESTZEILE EINFÜGEN:
st.write("🚀 KANARIENVOGEL-TEST: Diese Datei (v46) wird ausgeführt!")

# ==============================================================================
# AUTHENTIFIZIERUNG (mit st.secrets)
# ==============================================================================
AUTH_ENABLED = True  # Passwort-Schutz aktiviert

def check_password():
    """Prüft das Passwort via st.session_state."""
    if st.session_state.get("password_correct"):
        return True
    
    # Zeige Passwort-Screen
    st.title("🚀 Forschungs-Cockpit v45 - SYSTEM ONLINE")
    password = st.text_input("Passwort eingeben:", type="password")
    
    if password:
        app_password = st.secrets.get("APP_PASSWORD", "fallback_password_unsafe")
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

# Debug-Mode aktivieren?
DEBUG_MODE = st.secrets.get("DEBUG_MODE", False)
if DEBUG_MODE:
    logger.setLevel(logging.DEBUG)
    st.sidebar.info("🐛 Debug-Mode AKTIV")

# ==============================================================================
# 1. KONFIGURATION
# ==============================================================================
st.set_page_config(
    page_title="Forschungs-Cockpit v46",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==============================================================================
# 2. KONSTANTEN
# ==============================================================================
model = genai.GenerativeModel(
    model_name="gemini-3-pro-preview",
    system_instruction=GEMINI_3_SYSTEM_INSTRUCTION
)
PROJECT_ID = "comparative-studies-ai-models"
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
MAX_HTML_LENGTH_FOR_AI = 50000
HARD_LIMIT_WARNING = 200000

# ==========================================
# KONSTANTEN & MARKER FÜR IMPORT-ERKENNUNG
# ==========================================

# 1. Marker zur automatischen Erkennung der Plattform im HTML
# Wird von der Funktion 'detect_platform' genutzt.

# ==============================================================================
# 3. HELFERFUNKTIONEN
# ==============================================================================
@st.cache_resource
def configure_genai():
    if GEMINI_API_KEY:
        try:
            genai.configure(api_key=GEMINI_API_KEY)
            return True
        except Exception as e:
            st.error(f" Gemini API Konfiguration fehlgeschlagen: {e}")
            return False
    return False

def get_default_settings():
    return {
        'temperature': 0.2, 
        'top_p': 0.95, 
        'system_instruction': DEFAULT_SYSTEM_INSTRUCTION, 
        'use_search': True, 
        'debug_mode': False,
        'model_name': "gemini-2.0-flash-lite-001" # Sicherstellen, dass das dabei ist
    }

def send_message_with_rest_api(prompt, history, system_instruction, temperature, top_p, use_search, debug_mode=False):
    """Sendet eine Nachricht an die Gemini API über die REST-Schnittstelle."""
    if not configure_genai():
        logger.error("Gemini API konnte nicht konfiguriert werden")
        raise Exception("❌ Gemini API nicht konfiguriert.")
    
    try:  # ← TRY STARTET HIER
        if not GEMINI_API_KEY:
            logger.error("GEMINI_API_KEY fehlt!")
            raise Exception("❌ GEMINI_API_KEY nicht gefunden!")
        
        # Konvertiere History für REST API
        rest_history = []
        for msg in history:
             rest_history.append({
                "role": "user" if msg["role"] == "user" else "model",
                "parts": [{"text": msg["parts"][0]["text"]}]
            })
        contents = rest_history + [{"role": "user", "parts": [{"text": prompt}]}]
        
        payload = {
            "contents": contents,
            "systemInstruction": {"parts": [{"text": system_instruction}]},
            "generationConfig": {"temperature": temperature, "topP": top_p}
        }
        if use_search:
            payload["tools"] = [{"googleSearch": {}}]
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={GEMINI_API_KEY}"
        headers = {"Content-Type": "application/json"}
        
        if debug_mode:
            st.info("🔍 DEBUG: Sende Anfrage an REST API...")
        
        logger.info(f"📤 Sende Gemini-Anfrage: prompt_length={len(prompt)}, history={len(history)}, use_search={use_search}")
        response = requests.post(url, headers=headers, json=payload, timeout=120)
        response.raise_for_status()
        result = response.json()
        
        if debug_mode:
            with st.expander("Response-Details (von Google empfangen)"):
                st.json(result)
        
        # Fall 1: Normale Textantwort
        if 'candidates' in result and len(result['candidates']) > 0:
            candidate = result['candidates'][0]
            if 'content' in candidate and 'parts' in candidate['content'] and candidate['content']['parts'][0].get('text'):
                text = candidate['content']['parts'][0]['text']
                logger.info(f"📥 Antwort erhalten: length={len(text)}")
                return text
            
            # Fall 2: Grounding Metadata (Google Search genutzt)
            elif 'groundingMetadata' in candidate or (result.get('usageMetadata', {}).get('toolUsePromptTokenCount', 0) > 0):
                logger.info("🔍 Google Search verwendet, aber keine direkte Textantwort")
                return "*(Das Modell hat die Google-Suche verwendet, um den Link zu analysieren, aber keine direkte Textantwort generiert. Bitte stelle eine spezifischere Frage zum Inhalt des Links.)*"
        
        # Fall 3: Keine Antwort
        logger.error(f"Keine Candidates in API-Response: {result}")
        raise Exception(f"Keine gültige Antwort von der API.")
    
    # ← EXCEPTION-HANDLING STARTET HIER
    except requests.Timeout:
        logger.error("API-Timeout nach 120 Sekunden")
        raise Exception("⏱️ Timeout: Die API-Anfrage hat zu lange gedauert.")
    
    except requests.RequestException as e:
        logger.error(f"Netzwerkfehler: {e.response.status_code if e.response else 'unknown'}")
        raise Exception(f"🌐 Netzwerkfehler: {str(e)}")
    
    except Exception as e:
        logger.error(f"❌ API-Fehler: {str(e)}")
        raise Exception(f"❌ Ein unerwarteter Fehler: {str(e)}")

# ==========================================
# LOKALE IMPORT-FUNKTION (Umgeht Import-Fehler)
# ==========================================
# ==============================================================================
# ==============================================================================
# IMPORT-SEITE (Refactored v47)
# ==============================================================================
def render_import_page():
    st.title("📥 Daten importieren")
    st.markdown("---")

    tab_paste, tab_upload, tab_json = st.tabs(["📋 Copy-Paste (Text)", "📄 Datei-Upload (HTML/PDF/ePub)", "💾 JSON Backup"])

    # TAB 1: Copy-Paste
    with tab_paste:
        st.info("Anleitung: Chat-Text markieren (Strg+A), kopieren (Strg+C) und hier einfügen.")
        chat_text_input = st.text_area("Chat-Text hier einfügen:", height=300, key="gemini_paste_area")

        if st.button("🚀 Importieren (Paste)", use_container_width=True, type="primary"):
            if chat_text_input.strip():
                container = st.container()
                try:
                    # Factory Aufruf: Text Fallback
                    importer = get_importer('text_fallback')

                    # 1. Parse
                    messages = importer.parse(chat_text_input, container=container)

                    # 2. Import
                    if messages:
                        result = importer.import_to_firestore(messages, metadata={'source': 'paste'})
                        if result['chat_id']:
                            container.success(f"✅ Fertig! {result['message_count']} Nachrichten importiert.")
                        else:
                            container.error("❌ Fehler beim Speichern in DB.")
                except Exception as e:
                    st.error(f"❌ Import-Fehler: {e}")
            else:
                st.error("❌ Bitte füge zuerst Text ein.")

    # TAB 2: Datei-Upload
    with tab_upload:
        st.markdown("Unterstützte Formate: `.html`, `.txt`, `.pdf`, `.epub`")

        # Modus-Auswahl
        parser_mode = st.radio(
            "Modus:", 
            ["🤖 Auto-Detect (empfohlen)", "🎯 Manuell wählen", "🧠 Erzwinge KI-Parsing (Text)"],
            horizontal=True
        )

        manual_platform = None
        if parser_mode == "🎯 Manuell wählen":
            # Dynamische Liste aus den registrierten Importern generieren
            # Wir instanziieren kurz, um den Namen zu holen (leichtgewichtig)
            platform_options = {k: v().platform_name for k, v in IMPORTERS.items()}
            selected_name = st.selectbox("Plattform:", options=list(platform_options.values()))
            manual_platform = next((k for k, v in platform_options.items() if v == selected_name), None)

        # File Uploader mit neuen Typen
        uploaded_files = st.file_uploader(
            "Dateien wählen:", 
            type=["html", "htm", "txt", "pdf", "epub"], 
            accept_multiple_files=True
        )

        if uploaded_files and st.button("🚀 Start Upload", type="primary"):
            for uploaded_file in uploaded_files:
                file_container = st.container()
                file_container.markdown(f"**📄 {uploaded_file.name}**")

                try:
                    # Datei-Inhalt lesen
                    # Für PDF/ePub übergeben wir das File-Objekt direkt (wegen Binary/Stream)
                    # Für Text/HTML lesen wir Bytes
                    file_content = uploaded_file
                    if uploaded_file.name.lower().endswith(('.html', '.htm', '.txt')):
                        file_content = uploaded_file.read()

                    # 1. Plattform bestimmen
                    platform_key = 'text_fallback' # Default

                    if parser_mode == "🧠 Erzwinge KI-Parsing (Text)":
                        platform_key = 'text_fallback'
                        # Bei Text-Erzwingung müssen wir Bytes decoden, falls es HTML war
                        if isinstance(file_content, bytes):
                            file_content = file_content.decode('utf-8', errors='ignore')

                    elif manual_platform:
                        platform_key = manual_platform

                    else:
                        # Auto-Detect
                        filename = uploaded_file.name.lower()
                        if filename.endswith('.pdf'):
                            platform_key = 'pdf'
                        elif filename.endswith('.epub'):
                            platform_key = 'epub'
                        elif filename.endswith('.txt'):
                            platform_key = 'text_fallback'
                            if isinstance(file_content, bytes):
                                file_content = file_content.decode('utf-8', errors='ignore')
                        else:
                            # HTML Detection
                            detected, conf, _ = detect_platform(file_content)
                            if detected:
                                platform_key = detected
                                file_container.info(f"🔍 Erkannt: {IMPORTERS[platform_key]().platform_name} ({conf:.0%})")
                            else:
                                file_container.warning("⚠️ Keine Signatur erkannt. Nutze Text-Analyse...")
                                platform_key = 'text_fallback'
                                if isinstance(file_content, bytes):
                                    file_content = file_content.decode('utf-8', errors='ignore')

                    # 2. Importer holen & Parsen
                    importer = get_importer(platform_key)

                    # Spezialfall Gemini Diagnose (Target Word)
                    target_word = ""
                    if platform_key == 'gemini':
                        # Das Input-Feld müsste eigentlich vorher gerendert werden. 
                        # Für jetzt lassen wir es leer oder nutzen einen festen Wert, 
                        # da wir im Loop sind. (UI-Limitierung)
                        pass

                    messages = importer.parse(file_content, container=file_container, target_word=target_word)

                    # 3. Importieren
                    if messages:
                        # Check auf Diagnose-Modus (Gemini)
                        if len(messages) == 1 and messages[0].get('content') == 'Diagnose Mode - Kein Import':
                            continue # Nichts speichern

                        res = importer.import_to_firestore(messages, metadata={'container': file_container})

                        if res['chat_id']:
                            file_container.success(f"✅ Importiert: {res['message_count']} Nachrichten.")
                        else:
                            file_container.error("❌ Fehler beim Speichern.")
                    else:
                        file_container.error("❌ Keine Nachrichten gefunden.")

                except Exception as e:
                    file_container.error(f"❌ Kritischer Fehler bei {uploaded_file.name}: {e}")
                    # traceback.print_exc() # Optional für Logs

    # TAB 3: JSON (Bleibt unverändert, da einfache Logik)
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

def render_analysis_page():
    st.title("🧠 Langzeitgedächtnis & Suche")
    st.markdown("---")

    db = get_firestore_client()
    if not db:
        st.error("Keine Datenbankverbindung.")
        return

    # Chat-Titel laden für die Anzeige
    all_chats = get_chat_list()
    chat_map = {c['id']: c['title'] for c in all_chats}

    # HIER WERDEN DIE TABS DEFINIERT (Das fehlte vorher!)
    tab_search, tab_stats = st.tabs(["🔍 Semantische Suche", "📊 Statistik"])

       # --- TAB 1: SUCHE ---
    with tab_search:
        st.subheader("Wissensbasis durchsuchen")

        # --- NEU: SCOPE FILTER (Investigativ vs. Gedächtnis) ---
        with st.expander("🔍 Such-Fokus (Scope)", expanded=True):
            search_mode = st.radio(
                "Modus:",
                ["🎯 Investigativ (Nur ausgewählte Quellen)", "🧠 Gedächtnis (Alles durchsuchen)"],
                index=0,
                horizontal=True,
                help="Investigativ: Wähle spezifische Chats aus, um 'Lärm' zu vermeiden.\nGedächtnis: Durchsucht das gesamte Projekt."
            )

            selected_chat_ids = None
            if search_mode == "🎯 Investigativ (Nur ausgewählte Quellen)":
                # Wir laden die Chat-Liste für das Dropdown
                # all_chats wurde oben schon geladen (Zeile 429)
                chat_options = {c['title']: c['id'] for c in all_chats}

                selected_titles = st.multiselect(
                    "Quellen auswählen:",
                    options=list(chat_options.keys()),
                    default=[] # Standardmäßig leer, damit man bewusst wählt
                )

                if selected_titles:
                    selected_chat_ids = [chat_options[t] for t in selected_titles]
                else:
                    st.warning("⚠️ Keine Quellen gewählt! Die Suche wird leer sein.")
                    selected_chat_ids = [] # Leere Liste = Nichts finden
        # -------------------------------------------------------

        col1, col2 = st.columns([3, 1])
        with col1:
            # Suchfeld mit Memory-Funktion
            default_query = st.session_state.get('rag_query', "")
            search_query = st.text_input("Thema / Frage:", value=default_query, placeholder="z.B. Was sagt die KI über Zensur?")

        with col2:
            role_filter = st.radio("Suche in:", ["Alles", "Nur KI (Model)", "Nur Ich (User)"], index=1)

        search_btn = st.button("Analysieren & Antworten 🚀", type="primary", use_container_width=True)

        # --- LOGIK: SUCHE AUSFÜHREN ---
        if search_btn and search_query:
            vector_store = FirestoreVectorStore(db)
            rag_engine = CitationRAG() # Init ohne Vector Store, da wir Ergebnisse übergeben

            with st.spinner(f"1. Suche relevante Fakten..."):
                try:
                    raw_results = []
                    query_vec = None

                    # --- ADAPTIVE SUCHE (NEU) ---
                    # 1. Keywords holen
                    keywords = rag_engine.extract_keywords(search_query)

                    # 2. Modus bestimmen (Präzision vs. Konzept)
                    words = search_query.split()
                    has_proper_nouns = any(word[0].isupper() for word in words if len(word) > 1 and word.lower() not in ["wie", "was", "wo", "wer"])

                    if has_proper_nouns:
                        dynamic_weight = 0.60
                        st.toast(f"⚖️ Modus: PRÄZISION (Gewicht: {dynamic_weight})")
                    else:
                        dynamic_weight = 0.20
                        st.toast(f"⚖️ Modus: KONZEPT (Gewicht: {dynamic_weight})")

                    # 3. Suche ausführen (mit Filter & Gewicht)
                    # Wir nutzen IMMER hybrid_search, da es robuster ist
                    raw_results, query_vec = vector_store.hybrid_search(
                        search_query, 
                        keywords, 
                        limit=70, 
                        filter_role=None, # Wir filtern nicht hart nach Rolle, um Kontext zu behalten
                        allowed_chat_ids=selected_chat_ids, # Der Scope-Filter aus der Sidebar
                        keyword_weight=dynamic_weight # Die adaptive Intelligenz
                    )
                    # -----------------------------

                    # Scores berechnen (für UI)
                    results = calculate_confidence_scores(query_vec, raw_results)

                    if not results:
                        st.warning("Keine relevanten Quellen gefunden.")
                        if 'rag_results' in st.session_state: del st.session_state.rag_results
                    else:
                        # Antwort generieren
                        with st.spinner("2. Generiere Antwort mit Zitationen..."):
                            # Wir übergeben die GEFUNDENEN Ergebnisse an die Engine
                            raw_answer, used_sources = rag_engine.generate_answer(search_query, results)

                            # Post-Processing
                            valid_indices = list(range(1, len(used_sources) + 1))
                            with st.spinner("3. Veredle Synthese (Cleanup)..."):
                                answer = post_process_synthesis(raw_answer, valid_indices)

                        # Speichern
                        st.session_state.rag_results = used_sources
                        st.session_state.rag_answer = answer
                        st.session_state.rag_query = search_query

                except Exception as e:
                    st.error(f"Fehler: {e}")
                    print(traceback.format_exc())

        # --- ANZEIGE: ERGEBNISSE ---
        if 'rag_results' in st.session_state and 'rag_answer' in st.session_state:

            results = st.session_state.rag_results
            answer = st.session_state.rag_answer

            # 1. Synthese
            st.markdown("### 💡 Synthese")
            st.info(answer)

            # 2. Enforcer
            rag_engine = CitationRAG()

            with st.expander("🛡️ Enforcer Protokoll (Validierung)", expanded=False):
                warnings = rag_engine.validate_citations(answer, len(results))

                # Log initialisieren
                if 'verification_log' not in st.session_state:
                    st.session_state.verification_log = {'structure_check': [], 'deep_check': []}
                st.session_state.verification_log['structure_check'] = warnings

                if warnings:
                    for w in warnings: st.error(w)
                else:
                    st.success("✅ Struktur-Check bestanden: Alle Zitate sind gültig.")

                st.caption("Der Inhalts-Check prüft stichprobenartig, ob die Zitate wirklich das aussagen, was behauptet wird.")

                if st.button("🕵️‍♂️ Tiefenprüfung starten (Faktencheck)"):
                    with st.spinner("Der Enforcer prüft die Fakten..."):
                        import re
                        sentences = re.split(r'(?<=[.!?])\s+', answer)
                        issues_found = 0
                        checked_count = 0
                        deep_check_log = []

                        for sent in sentences:
                            matches = re.findall(r'\[(\d+)\]', sent)
                            if matches:
                                for m in matches:
                                    idx = int(m) - 1
                                    if 0 <= idx < len(results):
                                        checked_count += 1
                                        source_content = results[idx].get('content', '')
                                        source_meta = results[idx].get('metadata', {})

                                        is_valid, reason = rag_engine.verify_fact_match(sent, source_content, source_meta)

                                        log_entry = {'sentence': sent[:60], 'source_id': m, 'valid': is_valid, 'reason': reason}
                                        deep_check_log.append(log_entry)

                                        if is_valid:
                                            st.markdown(f"✅ **Verifiziert:** *\"{sent[:50]}...\"* -> Quelle [{m}]")
                                        else:
                                            st.error(f"❌ **Diskrepanz:** *\"{sent}\"*")
                                            st.markdown(f"Grund: {reason}")
                                            st.markdown(f"Quelle [{m}]: _{source_content[:100]}..._")
                                            issues_found += 1

                        st.session_state.verification_log['deep_check'] = deep_check_log

                        if checked_count == 0:
                            st.warning("Keine Sätze mit Zitationen gefunden.")
                        elif issues_found == 0:
                            st.balloons()
                            st.success(f"🎉 Perfekt! {checked_count} Zitate geprüft.")

            st.markdown("---")
            st.markdown("### 📚 Verwendete Quellen (Beweise)")

            # 3. Quellen-Liste
            for i, res in enumerate(results):
                meta = res.get('metadata', {})
                role = meta.get('role', 'unknown')
                chat_id = res.get('chat_id', 'unknown')
                platform = meta.get('platform', 'Unbekannt')
                real_date = meta.get('real_date_str', 'Datum unbekannt')
                chat_title = chat_map.get(chat_id, f"Chat ...{chat_id[-4:]}")

                score = res.get('confidence_score', 0)
                color = get_color_for_score(score)

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

                    # Split Thinking/Speech
                    raw_content = res.get('content', '')
                    thought, speech = rag_engine.split_thought_and_speech(raw_content)

                    if thought:
                        st.info(f"🧠 **Interner Gedanke:**\n\n{thought}")

                    if speech:
                        st.write(f"💬 **Aussage:**\n\n{speech}")
                    elif not thought:
                        st.write(raw_content)

                    st.caption(f"Original-ID: {res.get('message_id')} | Datum: {real_date}")

            # 4. Export
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

    # --- TAB 2: STATISTIK ---
    with tab_stats:
        st.info("Speicher-Status")
        if st.button("Zählen"):
            try:
                coll = db.collection('embeddings')
                snapshot = coll.count().get()
                count = snapshot[0][0].value
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
# 5. NAVIGATION
# ==============================================================================
st.sidebar.title(" Navigation")
page = st.sidebar.selectbox(
    "Seite wählen",
    [" Chat", " Import", " Analyse", "🏷️ Labeling", "💾 DB-Export"],
    help="Wähle die gewünschte Funktion aus"
)

# ==============================================================================
# 6. SEITEN-LOGIK
# ==============================================================================
if page == " Import":
    render_import_page()
elif page == "🏷️ Labeling":  # <--- NEU
    render_bulk_labeling_ui()
elif page == "💾 DB-Export": # <--- NEU
    render_bulk_export_ui()
elif page == " Analyse":
    render_analysis_page()
elif page == " Chat":  # Korrigiert von "💬 Chat" zu " Chat" um mit selectbox übereinzustimmen
    st.title("🧠 Dein persönliches Chat-Gedächtnis")

    # --- SIDEBAR-LOGIK ---
    with st.sidebar:
        st.markdown("---")
        st.sidebar.caption(f"📦 Forschungs-Cockpit {APP_VERSION}")
        with st.expander("⚙️ Admin-Bereich", expanded=False):
             st.subheader("🔐 Passwort ändern")
             new_password = st.text_input("Neues Passwort:", type="password", key="new_pwd")
             if st.button("Passwort speichern", use_container_width=True):
                 # Warnung: Das geht nur lokal in secrets.toml
                 st.warning("⚠️ Online: Passwort muss in Google Secret Manager geändert werden.")
                 st.info("Lokal: Ändere .streamlit/secrets.toml manuell")
        st.header("💬 Konversationen")
        if st.button("➕ Neuer Chat", use_container_width=True, type="primary"):
            st.session_state.chat_id = None
            st.session_state.history = []
            st.session_state.title_generated = False
            st.session_state.rename_chat_id = None
            st.session_state.delete_confirm_id = None
            st.session_state.last_error = None
            st.rerun()

        # HINWEIS: Diese Funktion wird jetzt korrekt aus dem oberen Teil der Datei aufgerufen
        chat_list = get_chat_list()
        for chat in chat_list:
            is_active = (st.session_state.chat_id == chat['id'])
            with st.container():
                if st.session_state.rename_chat_id == chat['id']:
                    new_name = st.text_input("Neuer Name:", value=chat['title'], key=f"rename_input_{chat['id']}", label_visibility="collapsed")
                    c1, c2 = st.columns(2)
                    if c1.button("✓", key=f"save_{chat['id']}", use_container_width=True):
                        if rename_chat(chat['id'], new_name.strip()):
                            st.session_state.rename_chat_id = None
                            st.rerun()
                    if c2.button("✗", key=f"cancel_{chat['id']}", use_container_width=True):
                        st.session_state.rename_chat_id = None
                        st.rerun()
                elif st.session_state.delete_confirm_id == chat['id']:
                    st.warning(f"**{chat['title']}** wirklich löschen?")
                    c1, c2 = st.columns(2)
                    if c1.button("Ja, löschen", key=f"confirm_del_{chat['id']}", use_container_width=True, type="primary"):
                        if delete_chat(chat['id']):
                            if st.session_state.chat_id == chat['id']:
                                st.session_state.chat_id = None
                                st.session_state.history = []
                            st.session_state.delete_confirm_id = None
                            st.rerun()
                    if c2.button("Nein", key=f"cancel_del_{chat['id']}", use_container_width=True):
                        st.session_state.delete_confirm_id = None
                        st.rerun()
                else:
                    cols = st.columns([6, 1, 1])
                    if cols[0].button(chat['title'], key=f"load_{chat['id']}", use_container_width=True, type="primary" if is_active else "secondary"):
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
        st.markdown("---")
        
        # ==============================================================================
        # ERWEITERTE MODELLEINSTELLUNGEN (mit Modell-Auswahl)
        # ==============================================================================
        with st.expander("⚙️ Modelleinstellungen", expanded=False):
            st.caption("Globale Einstellungen für neue Chats")

            # Modellauswahl
            available_models = [
                "gemini-2.5-flash-lite-preview-09-2025", 
                "gemini-2.5-flash-preview-09-2025",
                "gemini-3-pro-image-preview",
                "gemini-2.5-pro",
                "gemini-3-pro-preview" # Platzhalter für das neue Modell
            ]
            
            current_model = st.session_state.global_settings.get('model_name', "gemini-2.5-pro")
            
            try:
                current_model_index = available_models.index(current_model)
            except ValueError:
                current_model_index = 0

            selected_model = st.selectbox(
                "Wähle ein Gemini-Modell:",
                options=available_models,
                index=current_model_index,
                help="Das ausgewählte Modell wird für alle neuen Chats verwendet."
            )
            
            # Globale MODEL_NAME Konstante für die aktuelle Sitzung aktualisieren
            MODEL_NAME = selected_model

            temp = st.slider("Temperature", 0.0, 1.0, st.session_state.global_settings.get('temperature', 0.2), 0.1)
            top_p = st.slider("Top-P", 0.0, 1.0, st.session_state.global_settings.get('top_p', 0.95), 0.05)
            use_search = st.checkbox("🔍 Google Search aktivieren", value=st.session_state.global_settings.get('use_search', True))
            debug_mode = st.checkbox("🐛 Debug-Modus", value=st.session_state.global_settings.get('debug_mode', False))
            sys_instr = st.text_area("System Instruction", st.session_state.global_settings.get('system_instruction', DEFAULT_SYSTEM_INSTRUCTION), height=250)
            
            if st.button("💾 Einstellungen speichern", use_container_width=True):
                # Speichere auch das neue Modell in den Settings
                st.session_state.global_settings['model_name'] = selected_model
                st.session_state.global_settings['temperature'] = temp
                st.session_state.global_settings['top_p'] = top_p
                st.session_state.global_settings['system_instruction'] = sys_instr
                st.session_state.global_settings['use_search'] = use_search
                st.session_state.global_settings['debug_mode'] = debug_mode

                # Rufe die angepasste save_global_settings Funktion auf
                if save_global_settings(
                    selected_model, temp, top_p, sys_instr, use_search, debug_mode
                ):
                    st.success("✓ Gespeichert!")
                    time.sleep(1)
                    st.rerun()

    # --- HAUPT-CHAT-INTERFACE ---
    if st.session_state.last_error:
        st.error(f"🚨 **Ein Fehler ist aufgetreten:**\n\n{st.session_state.last_error}")
        if st.button("❌ Fehlermeldung schließen"):
            st.session_state.last_error = None
            st.rerun()

    for message in st.session_state.history:
        with st.chat_message(message["role"]):
            st.markdown(message["parts"][0]["text"])

    # Logik zum Bearbeiten/Löschen der letzten Nachricht
    if st.session_state.history and len(st.session_state.history) >= 2 and st.session_state.history[-1]['role'] == 'model':
        action_container = st.container()
        with action_container:
            col1, col2, col3, col4 = st.columns([.7, .1, .1, .1])
            with col2:
                if st.button("✏️", key="edit_last_turn", help="Letzte Frage bearbeiten (löscht die letzte Runde)"):
                    try:
                        db = get_firestore_client()
                        if db and st.session_state.chat_id:
                            messages_ref = db.collection('chats').document(st.session_state.chat_id).collection('messages')
                            query = messages_ref.order_by('timestamp', direction=firestore.Query.DESCENDING).limit(2)
                            for doc in query.stream():
                                doc.reference.delete()
                            st.session_state.history = st.session_state.history[:-2]
                            st.success("Letzte Runde gelöscht. Du kannst deine Frage jetzt neu formulieren.")
                            time.sleep(1)
                            st.rerun()
                    except Exception as e:
                        st.error(f"Fehler beim Bearbeiten: {e}")
            with col3:
                if st.button("🗑️", key="delete_last_turn", help="Letzte Runde löschen"):
                    try:
                        db = get_firestore_client()
                        if db and st.session_state.chat_id:
                            messages_ref = db.collection('chats').document(st.session_state.chat_id).collection('messages')
                            query = messages_ref.order_by('timestamp', direction=firestore.Query.DESCENDING).limit(2)
                            for doc in query.stream():
                                doc.reference.delete()
                            st.session_state.history = st.session_state.history[:-2]
                            st.success("Letzte Runde gelöscht.")
                            time.sleep(1)
                            st.rerun()
                    except Exception as e:
                        st.error(f"Fehler beim Löschen: {e}")

    # Das Chat-Input-Feld
    if prompt := st.chat_input("Stelle deine Frage..."):
        if st.session_state.chat_id is None:
            st.session_state.chat_id = create_chat_in_firestore("Neuer Chat")
            if st.session_state.chat_id is None:
                st.error("Konnte keinen neuen Chat erstellen. Bitte prüfe die Datenbankverbindung.")
                st.stop()
        
        st.session_state.history.append({"role": "user", "parts": [{"text": prompt}]})
        save_message(st.session_state.chat_id, "user", prompt)
        
        with st.chat_message("user"):
            st.markdown(prompt)
        
        with st.spinner("Gemini denkt nach..."):
            try:
                settings = st.session_state.global_settings
                response_text = send_message_with_rest_api(
                    prompt, 
                    st.session_state.history[:-1], 
                    settings['system_instruction'], 
                    settings['temperature'], 
                    settings['top_p'], 
                    settings['use_search'], 
                    settings.get('debug_mode', False)
                )
                st.session_state.history.append({"role": "model", "parts": [{"text": response_text}]})
                save_message(st.session_state.chat_id, "model", response_text)
                st.session_state.last_error = None
                
                if not st.session_state.title_generated and len(st.session_state.history) >= 2:
                    generate_and_update_title(st.session_state.chat_id, st.session_state.history)
                
                st.rerun()
            
            except Exception as e:
                st.session_state.last_error = str(e)
                st.rerun()

# ==========================================
# ADMIN-BEREICH (Ganz unten in app.py)
# ==========================================
render_vector_admin_dashboard()