# ui/import_tab.py — HRE v51
# Zuständig für: Import-Seite (Copy-Paste, Datei-Upload, JSON-Backup)
#
# ARCHITEKTUR-REGEL:
# State-Schreibzugriffe ausschließlich via ui/state.py.
# Dieses Modul kennt kein st.session_state direkt.

import streamlit as st
import json
import ui.state as state

from modules.database import load_chat_history, create_chat_in_firestore, save_message
from modules.importers import get_importer, detect_platform, IMPORTERS


def render_import_tab() -> None:
    """Rendert die vollständige Import-Seite mit allen drei Tabs."""
    st.title("📥 Daten importieren")
    st.markdown("---")

    tab_paste, tab_upload, tab_json = st.tabs([
        "📋 Copy-Paste (Text)",
        "📄 Datei-Upload (HTML/PDF/ePub/MD/json)",
        "💾 JSON Backup"
    ])

    # ------------------------------------------------------------------
    with tab_paste:
        st.info("Anleitung: Chat-Text markieren (Strg+A), kopieren (Strg+C) und hier einfügen.")
        chat_text_input = st.text_area(
            "Chat-Text hier einfügen:", height=300, key="gemini_paste_area"
        )

        if st.button("🚀 Importieren (Paste)", use_container_width=True, type="primary"):
            if chat_text_input.strip():
                container = st.container()
                try:
                    importer = get_importer('text_fallback')
                    messages = importer.parse(chat_text_input, container=container)

                    if messages:
                        result = importer.import_to_firestore(
                            messages, metadata={'source': 'paste'}
                        )
                        if result['chat_id']:
                            container.success(
                                f"✅ Fertig! {result['message_count']} Nachrichten importiert."
                            )
                            st.cache_data.clear()
                            state.set_chat(  # v51: via ui/state.py
                                result['chat_id'],
                                load_chat_history(result['chat_id'])
                            )
                            st.rerun()
                        else:
                            container.error("❌ Fehler beim Speichern in DB.")
                except Exception as e:
                    st.error(f"❌ Import-Fehler: {e}")
            else:
                st.error("❌ Bitte füge zuerst Text ein.")

    # ------------------------------------------------------------------
    with tab_upload:
        st.markdown(
            "Unterstützte Formate: `.html`, `.txt`, `.pdf`, `.epub`, `.fb2`, `.md`, `.json`"
        )

        parser_mode = st.radio(
            "Modus:",
            ["🤖 Auto-Detect (empfohlen)", "🎯 Manuell wählen", "🧠 Erzwinge KI-Parsing (Text)"],
            horizontal=True
        )

        manual_platform = None
        if parser_mode == "🎯 Manuell wählen":
            platform_options = {k: v().platform_name for k, v in IMPORTERS.items()}
            selected_name = st.selectbox(
                "Plattform:", options=list(platform_options.values())
            )
            manual_platform = next(
                (k for k, v in platform_options.items() if v == selected_name), None
            )

        uploaded_files = st.file_uploader(
            "Dateien wählen:",
            type=["html", "htm", "txt", "pdf", "epub", "fb2", "md", "markdown", "json"],
            accept_multiple_files=True
        )

        if uploaded_files and st.button("🚀 Start Upload", type="primary"):
            for uploaded_file in uploaded_files:
                file_container = st.container()
                file_container.markdown(f"**📄 {uploaded_file.name}**")
                try:
                    file_content = uploaded_file
                    if uploaded_file.name.lower().endswith(
                        ('.html', '.htm', '.txt', '.md', '.markdown', '.json')
                    ):
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
                                file_container.info(
                                    f"🔍 Erkannt: "
                                    f"{IMPORTERS[platform_key]().platform_name} ({conf:.0%})"
                                )
                            else:
                                file_container.warning(
                                    "⚠️ Keine Signatur erkannt. Nutze Text-Analyse..."
                                )
                                platform_key = 'text_fallback'
                                if isinstance(file_content, bytes):
                                    file_content = file_content.decode('utf-8', errors='ignore')

                    importer = get_importer(platform_key)
                    messages = importer.parse(file_content, container=file_container)

                    if messages:
                        if len(messages) == 1 and \
                                messages[0].get('content') == 'Diagnose Mode - Kein Import':
                            continue
                        res = importer.import_to_firestore(
                            messages, metadata={'container': file_container}
                        )
                        if res['chat_id']:
                            file_container.success(
                                f"✅ Importiert: {res['message_count']} Nachrichten."
                            )
                            st.cache_data.clear()
                            state.set_chat(  # v51: via ui/state.py
                                res['chat_id'],
                                load_chat_history(res['chat_id'])
                            )
                            st.rerun()
                        else:
                            file_container.error("❌ Fehler beim Speichern.")
                    else:
                        file_container.error("❌ Keine Nachrichten gefunden.")

                except Exception as e:
                    file_container.error(
                        f"❌ Kritischer Fehler bei {uploaded_file.name}: {e}"
                    )

    # ------------------------------------------------------------------
    with tab_json:
        uploaded_json = st.file_uploader(
            "JSON-Datei:", type=["json"], key="json_direct"
        )
        if uploaded_json and st.button("💾 Wiederherstellen", type="primary"):
            try:
                json_data = json.load(uploaded_json)
                if isinstance(json_data, list):
                    chat_title = f"Restore: {uploaded_json.name}"
                    chat_id = create_chat_in_firestore(chat_title)
                    count = 0
                    for msg in json_data:
                        save_message(
                            chat_id,
                            msg.get('role', 'user'),
                            msg.get('content', '')
                        )
                        count += 1
                    st.success(f"✅ {count} Nachrichten wiederhergestellt.")
            except Exception as e:
                st.error(f"❌ Fehler: {e}")