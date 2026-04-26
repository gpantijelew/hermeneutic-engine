# ui/chat_tab.py — HRE v52
# Zuständig für: Haupt-Chat-Interface (History, Input, RAG-Weiche, Export)
#
# ARCHITEKTUR-REGEL:
# State-Schreibzugriffe ausschließlich via ui/state.py.
# Empfängt RAG-Kontext als Parameter von app.py (kein direkter Sidebar-Zugriff).

import time
from datetime import datetime
import streamlit as st

import ui.state as state
from ui.chat_list import clear_chat_cache

from modules.config import LLM_BACKEND
from modules.llm_wrapper import llm_call_streaming
from modules.database import (
    get_db_connection,
    create_chat,
    save_message,
    generate_and_update_title,
    get_chat_list,
)
from modules.vector_store import LocalVectorStore
from modules.citation_rag import CitationRAG
from modules.hermeneutic_router import HermeneuticRouter

# ==============================================================================
# PRIVATE: LLM-Streaming-Wrapper
# ==============================================================================


def _send_message(prompt, history, system_instruction, temperature, **kwargs):
    """Sendet Nachricht via llm_wrapper. Gibt Generator zurück."""
    use_search = kwargs.get("use_search", False)
    return llm_call_streaming(
        prompt,
        task="chat",
        system_instruction=system_instruction,
        temperature=temperature,
        history=history,
        use_search=use_search,
    )


# ==============================================================================
# PUBLIC: Haupt-Einstiegspunkt
# ==============================================================================


def render_chat_tab(
    use_db: bool = False,
    use_router: bool = False,
    filter_mode: str = "Alles durchsuchen",
    selected_rag_ids=None,
) -> None:
    """
    Rendert das vollständige Chat-Interface.

    Args:
        use_db:           Datenbank-Wissen aktiv (RAG-Modus)
        use_router:       Auto-Router aktiv
        filter_mode:      "Alles durchsuchen" | "Auswahl treffen"
        selected_rag_ids: Liste der ausgewählten Chat-IDs (oder None)
    """
    st.title("🧠 Dein persönliches Chat-Gedächtnis")

    # --- Fehlermeldung ---
    if st.session_state.get("last_error"):
        st.error(f"🚨 **Ein Fehler ist aufgetreten:**\n\n{st.session_state.last_error}")
        if st.button("❌ Fehlermeldung schließen"):
            state.set_last_error(None)
            st.rerun()

    # --- Chat-Historie anzeigen (Phase 6.5: Editor-Modus) ---
    history = st.session_state.history
    for i, message in enumerate(history):
        msg_id = message.get("id")
        role = message["role"]
        text = message["parts"][0]["text"]
        is_editing = st.session_state.get("editing_msg_id") == msg_id

        with st.chat_message(role):
            if is_editing:
                new_text = st.text_area("Edit:", value=text, key=f"edit_area_{msg_id}", height=150)
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("📝 Nur Text korrigieren", key=f"fix_{msg_id}"):
                        _action_fix_text(msg_id, new_text, i)
                with col2:
                    if st.button("⏳ Speichern & Zeitreise", key=f"time_{msg_id}"):
                        _action_time_travel(msg_id, new_text, i)
            else:
                st.markdown(text)

            # --- Action-Buttons ---
            if not is_editing and msg_id:
                btn_col1, btn_col2, btn_col3 = st.columns([0.15, 0.15, 0.7])
                
                if role == "user":
                    with btn_col1:
                        if st.button("✏️ Edit", key=f"edit_btn_{msg_id}"):
                            st.session_state.editing_msg_id = msg_id
                            st.rerun()
                    with btn_col2:
                        # Schere: Nur anzeigen, wenn eine Model-Antwort folgt
                        if i + 1 < len(history) and history[i+1]["role"] == "model":
                            if st.button("✂️ Turn", key=f"del_turn_{msg_id}"):
                                _action_delete_turn(msg_id, history[i+1].get("id"), i)

                elif role == "model" and i == len(history) - 1:
                    # Neu würfeln: Nur an der allerletzten KI-Antwort
                    with btn_col1:
                        if st.button("🔄 Neu würfeln", key=f"regen_{msg_id}"):
                            _action_regenerate(msg_id, i)

    # --- Edit / Delete / Export ---
    _render_action_buttons()

    # --- Chat-Modus (Online vs. Labor) ---
    use_search = _render_mode_selector()

    # --- ORCHESTRATOR (Phase 6.5: Regenerate Flags abarbeiten) ---
    if st.session_state.get("trigger_regenerate"):
        prompt = st.session_state.trigger_regenerate
        st.session_state.trigger_regenerate = None
        _handle_input(
            prompt, use_db, use_router, filter_mode, selected_rag_ids, use_search
        )

    # --- Vision: Optionaler Bild-Upload ---
    uploader_key = f"chat_vision_upload_{st.session_state.get('vision_upload_counter', 0)}"
    
    if LLM_BACKEND == "vertex":
        st.file_uploader(
            "📷 Bis zu 2 Bilder für (Vergleichs-)Analyse (optional):",
            type=["png", "jpg", "jpeg", "webp"],
            key=uploader_key,
            accept_multiple_files=True,
            help="1 Bild = Einzelanalyse, 2 Bilder = Vergleichsanalyse. Max 2 Bilder! Werden NICHT gespeichert."
        )
        image_origin = st.selectbox(
            "Bildtyp:",
            ["ai_generated", "photograph", "screenshot", "scan"],
            format_func=lambda x: {
                "ai_generated": "🤖 KI-generiert",
                "photograph": "📷 Fotografie",
                "screenshot": "🖥️ Screenshot",
                "scan": "📄 Scan/Dokument"
            }[x],
            key="chat_vision_origin",
            help="Bestimmt die Analyse-Strategie der HRE"
        )

    # --- Input & Logik-Weiche ---
    if prompt := st.chat_input("Stelle deine Frage..."):
        uploaded_files = st.session_state.get(uploader_key, [])
        image_origin = st.session_state.get("chat_vision_origin", "photograph")
        
        # Validierung: Maximal 2 Bilder erlauben
        if uploaded_files and len(uploaded_files) > 2:
            st.warning("⚠️ Maximal 2 Bilder erlaubt. Nur die ersten beiden werden analysiert.")
            uploaded_files = uploaded_files[:2]
            
        _handle_input(
            prompt, use_db, use_router, filter_mode, selected_rag_ids, use_search, uploaded_files, image_origin
        )
def _render_action_buttons() -> None:
    """Export-Buttons unter der letzten Modell-Antwort (Phase 6.5: Edit/Delete sind jetzt inline)."""
    history = st.session_state.history
    if not (history and len(history) >= 2 and history[-1]["role"] == "model"):
        return

    with st.container():
        col1, col2 = st.columns([0.3, 0.7])

        with col1:
            st.selectbox(
                "Export Scope:", ["Alles", "Letzter Turn"], 
                key="export_scope_select", label_visibility="collapsed"
            )

        with col2:
            if st.button(
                "📄 Export",
                key="prep_export_btn",
                help="Markdown generieren",
            ):
                _prepare_export()

            if st.session_state.get("export_data"):
                st.download_button(
                    label="💾 Download",
                    data=st.session_state.export_data,
                    file_name=st.session_state.get("export_filename", "export.md"),
                    mime="text/markdown",
                    key="dl_btn_persistent",
                )


def _prepare_export() -> None:
    """Generiert Export-Daten mit Provenance-Header."""
    with st.spinner("Generiere Dokument..."):
        from modules.export import generate_markdown, generate_chat_markdown

        chat_title = "Chat-Protokoll"
        if st.session_state.chat_id:
            try:
                db = get_db_connection()
                row = db.execute(
                    "SELECT title FROM chats WHERE id = ?", (st.session_state.chat_id,)
                ).fetchone()
                if row:
                    chat_title = row[0]
            except Exception as e:
                print(f"Export-Fehler (Titel): {e}")

        # Provenance Header zusammenbauen
        settings = st.session_state.get("global_settings", {})
        rag_intent = st.session_state.get("last_rag_intent", "N/A")
        rag_docs = []
        if st.session_state.get("last_rag_sources"):
            seen = set()
            for s in st.session_state.last_rag_sources:
                t = s.get('metadata', {}).get('chat_title', 'Unknown')
                if t not in seen:
                    rag_docs.append(t)
                    seen.add(t)
        
        header = f"""---
Datum: {datetime.now().strftime('%d.%m.%Y %H:%M')}
LLM-Modell: {settings.get('model_name', 'Unbekannt')}
RAG-Modus: {rag_intent}
Dokumente: [{', '.join(rag_docs) if rag_docs else 'Keine'}]
Engine-Version: v52.1
---

"""

        # Letzter Turn oder ganzer Chat?
        export_scope = st.session_state.get("export_scope_select", "Alles")
        has_rag = bool(st.session_state.get("last_rag_sources"))

        try:
            if export_scope == "Letzter Turn" and len(st.session_state.history) >= 2:
                last_turn = st.session_state.history[-2:]
                markdown_body = generate_chat_markdown(last_turn, chat_title)
            elif has_rag:
                all_chats = get_chat_list()
                chat_map = {c["id"]: c["title"] for c in all_chats}
                markdown_body = generate_markdown(
                    query=st.session_state.last_rag_query,
                    answer=st.session_state.history[-1]["parts"][0]["text"],
                    results=st.session_state.last_rag_sources,
                    chat_map=chat_map,
                    verification_log=None,
                )
            else:
                markdown_body = generate_chat_markdown(st.session_state.history, chat_title)

            st.session_state.export_data = header + markdown_body
            st.session_state.export_filename = f"Forschungsnotiz_{datetime.now().strftime('%H%M')}.md"
            st.success("Fertig!")
        except Exception as e:
            st.error(f"Fehler: {e}")

# ==============================================================================
# PRIVATE: Modus-Selektor (Online / Labor)
# ==============================================================================


def _render_mode_selector() -> bool:
    """
    Rendert Online/Labor-Umschalter.
    Gibt use_search zurück.
    Im Analyse-Modus (selected_chat_for_analysis) wird Search erzwungen aus.
    """
    if st.session_state.get("selected_chat_for_analysis"):
        st.caption(
            "🔬 **Labor-Modus** — Search Grounding deaktiviert (Chat-Analyse aktiv)"
        )
        return False

    if LLM_BACKEND != "vertex":
        return False

    search_mode = st.radio(
        "Modus:",
        ["🌐 Online (Web-Suche aktiv)", "🔬 Labor (nur Modell-Wissen)"],
        index=0,
        horizontal=True,
        key="chat_search_mode",
    )
    return search_mode.startswith("🌐")


# ==============================================================================
# PRIVATE: Input-Handler & RAG-Weiche
# ==============================================================================


def _handle_input(
    prompt: str,
    use_db: bool,
    use_router: bool,
    filter_mode: str,
    selected_rag_ids,
    use_search: bool,
    uploaded_files=None,
    image_origin="photograph",
) -> None:
    """Verarbeitet User-Input: Chat-ID anlegen, History schreiben, Weiche."""

    # Chat-ID anlegen falls nötig
    if st.session_state.chat_id is None:
        st.session_state.chat_id = create_chat("Neuer Chat")
        if st.session_state.chat_id is None:
            st.error("Konnte keinen neuen Chat erstellen.")
            st.stop()

    # Phase 6.5: Verhindere doppeltes Speichern bei Zeitreise/Neu würfeln
    is_regenerating = st.session_state.get("is_regenerating", False)
    st.session_state.is_regenerating = False # Flag zurücksetzen

    if not is_regenerating:
        msg_id = save_message(st.session_state.chat_id, "user", prompt)
        state.append_to_history("user", prompt)
        if msg_id:
            from datetime import datetime
            st.session_state.history[-1]["id"] = msg_id
            st.session_state.history[-1]["timestamp"] = datetime.utcnow().isoformat()

    with st.chat_message("user"):
        if not is_regenerating:
            st.markdown(prompt)
    with st.chat_message("model"):
        if use_db:
            _handle_rag(prompt, filter_mode, selected_rag_ids, use_router)
        else:
            _handle_free_chat(prompt, use_search, uploaded_files, image_origin)

    # Titel generieren
    if (
        not st.session_state.get("title_generated")
        and len(st.session_state.history) >= 2
    ):
        generate_and_update_title(st.session_state.chat_id, st.session_state.history)
        clear_chat_cache()
        st.rerun()

def _handle_rag(
    prompt: str,
    filter_mode: str,
    selected_rag_ids,
    use_router: bool,
) -> None:
    """PFAD A: Datenbank-RAG."""
    if filter_mode == "Auswahl treffen" and not selected_rag_ids:
        st.error("⚠️ Du hast 'Auswahl treffen' gewählt, aber keine Dokumente markiert.")
        st.stop()

    status_container = st.empty()

    try:
        with status_container.status(
            "🔍 Konsultiere Datenbank...", expanded=True
        ) as status:
            db = get_db_connection()
            vs = LocalVectorStore(db)
            rag = CitationRAG(vector_store=vs)

            status.write("📚 Suche relevante Stellen...")
            results, query_vector = rag.retrieve_with_rrf(
                prompt, chat_id=selected_rag_ids, use_router=use_router
            )

            if not results:
                status.update(label="❌ Nichts gefunden", state="error")
                final_text = (
                    "Ich habe in den ausgewählten Dokumenten "
                    "keine Informationen dazu gefunden."
                )
                sources = []
                intent = "UNKNOWN"
            else:
                status.write("📝 Synthetisiere Antwort...")
                final_text, sources, intent = rag.generate_answer(prompt, results)
                status.update(
                    label=f"✅ Fertig ({intent})", state="complete", expanded=False
                )

            state.set_rag_result(sources, prompt, intent)

        st.markdown(final_text)

        if sources:
            with st.expander(f"📚 Quellen ({len(sources)})"):
                for s in sources:
                    st.markdown(
                        f"**[{s.get('source_id')}] "
                        f"{s.get('metadata', {}).get('chat_title', 'Dokument')}**"
                    )
                    st.caption(s.get("content")[:200] + "...")

        msg_id = save_message(st.session_state.chat_id, "model", final_text)
        # State-Sync: ID und Timestamp hinzufügen
        if msg_id:
            from datetime import datetime
            state.append_to_history("model", final_text)
            st.session_state.history[-1]["id"] = msg_id
            st.session_state.history[-1]["timestamp"] = datetime.utcnow().isoformat()
        st.rerun()

    except Exception as e:
        st.error(f"RAG Fehler: {e}")


def _handle_free_chat(prompt: str, use_search: bool, uploaded_files=None, image_origin="photograph") -> None:
    """PFAD B: Freier Chat via LLM — mit optionalem Vision-Support (Vergleiche möglich)."""
    state.clear_rag_state()

    try:
        # Vision-Pfad: Bilder vorhanden
        if uploaded_files:
            from modules.llm_wrapper import llm_call_vision
            from modules.prompt_manager import PromptManager

            # Intent-Awareness: Router analysiert die User-Frage
            semantic_intent = "FACTUAL"
            try:
                router = HermeneuticRouter()
                route = router.route_query(prompt if prompt else "Analysiere Bild")
                semantic_intent = route.get("intent", "FACTUAL")
            except Exception:
                semantic_intent = "FACTUAL"

            pm = PromptManager()
            vision_sys = pm.get_vision_instruction(semantic_intent=semantic_intent)

            # Bilddaten für API aufbereiten
            images_payload = []
            filenames = []
            for f in uploaded_files:
                images_payload.append({"bytes": f.read(), "mime": f.type})
                filenames.append(f.name)

            # Dynamischer Default-Prompt, falls User leer gelassen
            final_prompt = prompt
            if not final_prompt:
                if len(images_payload) >= 2:
                    final_prompt = "Analysiere und vergleiche diese beiden Bilder präzise nach dem Protokoll."
                else:
                    final_prompt = "Analysiere dieses Bild präzise nach dem Protokoll."

            spinner_text = f"🔍 Analysiere {len(images_payload)} Bild(er) semiotisch..."
            with st.spinner(spinner_text):
                protocol = llm_call_vision(
                    images=images_payload,
                    user_question=final_prompt,
                    image_origin=image_origin,
                    system_instruction=vision_sys,
                )

            if not protocol:
                st.error("❌ Vision-Analyse fehlgeschlagen. Gesamtgröße < 20MB? Vision-fähiges Modell geladen?")
                return

            # UX-Marker für den Chat-Verlauf
            file_str = ", ".join(filenames)
            response_text = f"📷 **[Bildanalyse zu: {file_str}]**\n\n{protocol}"
            
            st.markdown(response_text)
            msg_id = save_message(st.session_state.chat_id, "model", response_text)
            if msg_id:
                from datetime import datetime
                state.append_to_history("model", response_text)
                st.session_state.history[-1]["id"] = msg_id
                st.session_state.history[-1]["timestamp"] = datetime.utcnow().isoformat()
            
            # Uploader leeren: Key-Counter hochzählen und Rerun auslösen
            st.session_state.vision_upload_counter = st.session_state.get('vision_upload_counter', 0) + 1
            st.rerun()
            return

        # Standard-Pfad: kein Bild (Normaler Streaming-Chat)
        settings = st.session_state.global_settings
        response_text_placeholder = st.empty()
        full_response = ""

        # Historie für den LLM-Call (ohne den aktuellen Prompt, der kommt separat)
        history = st.session_state.history[:-1]

        for chunk in _send_message(
            prompt, 
            history, 
            settings.get("system_instruction", ""), 
            settings.get("temperature", 0.7),
            use_search=use_search
        ):
            full_response += chunk
            response_text_placeholder.markdown(full_response)

        msg_id = save_message(st.session_state.chat_id, "model", full_response)
        if msg_id:
            from datetime import datetime
            state.append_to_history("model", full_response)
            st.session_state.history[-1]["id"] = msg_id
            st.session_state.history[-1]["timestamp"] = datetime.utcnow().isoformat()

    except Exception as e:
        state.set_last_error(str(e))
        st.rerun()

# ==============================================================================
# PRIVATE: EDITOR ACTION HANDLERS (Phase 6.5)
# ==============================================================================

def _action_fix_text(msg_id: str, new_text: str, index: int) -> None:
    """Button A: Nur Text korrigieren (Silent Update)."""
    from modules.database import update_message_content
    update_message_content(msg_id, new_text)
    st.session_state.history[index]["parts"][0]["text"] = new_text
    st.session_state.editing_msg_id = None
    st.rerun()

def _action_time_travel(msg_id: str, new_text: str, index: int) -> None:
    """Button B: Speichern & Zeitreise (Zukunft löschen, neu generieren)."""
    from modules.database import update_message_content, delete_messages_after
    chat_id = st.session_state.chat_id
    timestamp = st.session_state.history[index].get("timestamp")
    
    update_message_content(msg_id, new_text)
    delete_messages_after(chat_id, timestamp)
    
    # In-Memory History abschneiden und editierten Text einfügen
    st.session_state.history = st.session_state.history[:index]
    st.session_state.history.append({
        "role": "user", "parts": [{"text": new_text}], 
        "id": msg_id, "timestamp": timestamp
    })
    
    st.session_state.editing_msg_id = None
    st.session_state.is_regenerating = True  # Verhindere Doppel-Insert
    st.session_state.trigger_regenerate = new_text
    st.rerun()

def _action_delete_turn(user_msg_id: str, model_msg_id: str, index: int) -> None:
    """Schere: User+Model Turn löschen."""
    from modules.database import delete_messages_by_ids
    ids = [user_msg_id]
    if model_msg_id: ids.append(model_msg_id)
    
    delete_messages_by_ids(ids)
    st.session_state.history = st.session_state.history[:index] + st.session_state.history[index+2:]
    st.rerun()

def _action_regenerate(model_msg_id: str, index: int) -> None:
    """Neu würfeln: KI-Antwort löschen und Pipeline neu triggern."""
    from modules.database import delete_message_by_id
    delete_message_by_id(model_msg_id)
    st.session_state.history.pop(index)
    
    if index > 0 and st.session_state.history[index-1]["role"] == "user":
        user_prompt = st.session_state.history[index-1]["parts"][0]["text"]
        st.session_state.is_regenerating = True  # Verhindere Doppel-Insert
        st.session_state.trigger_regenerate = user_prompt
    st.rerun()