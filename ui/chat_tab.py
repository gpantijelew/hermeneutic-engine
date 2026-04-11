# ui/chat_tab.py — HRE v51
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
    get_firestore_client,
    create_chat_in_firestore,
    save_message,
    generate_and_update_title,
    get_chat_list,
)
from modules.vector_store import FirestoreVectorStore
from modules.citation_rag import CitationRAG


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
        use_search=use_search
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
        st.error(
            f"🚨 **Ein Fehler ist aufgetreten:**\n\n"
            f"{st.session_state.last_error}"
        )
        if st.button("❌ Fehlermeldung schließen"):
            st.session_state.last_error = None
            st.rerun()

    # --- Chat-Historie anzeigen ---
    for message in st.session_state.history:
        with st.chat_message(message["role"]):
            st.markdown(message["parts"][0]["text"])

    # --- Edit / Delete / Export ---
    _render_action_buttons()

    # --- Chat-Modus (Online vs. Labor) ---
    use_search = _render_mode_selector()

    # --- Input & Logik-Weiche ---
    if prompt := st.chat_input("Stelle deine Frage..."):
        _handle_input(
            prompt, use_db, use_router,
            filter_mode, selected_rag_ids, use_search
        )


# ==============================================================================
# PRIVATE: Action-Buttons (Edit / Delete / Export)
# ==============================================================================

def _render_action_buttons() -> None:
    """Edit-, Delete- und Export-Buttons unter der letzten Modell-Antwort."""
    history = st.session_state.history
    if not (history and len(history) >= 2 and history[-1]['role'] == 'model'):
        return

    with st.container():
        col1, col2, col3, col4 = st.columns([.6, .1, .1, .2])

        with col2:
            if st.button("✏️", key="edit_last_turn", help="Letzte Frage bearbeiten"):
                _delete_last_db_turn()
                state.remove_last_turn()
                st.success("Letzte Runde gelöscht.")
                time.sleep(1)
                st.rerun()

        with col3:
            if st.button("🗑️", key="delete_last_turn", help="Letzte Runde löschen"):
                _delete_last_db_turn()
                state.remove_last_turn()
                st.success("Letzte Runde gelöscht.")
                time.sleep(1)
                st.rerun()

        with col4:
            if st.button(
                "📄 Export", key="prep_export_btn",
                help="Markdown generieren", use_container_width=True
            ):
                _prepare_export()

            if st.session_state.get("export_data"):
                st.download_button(
                    label="💾 Download",
                    data=st.session_state.export_data,
                    file_name=st.session_state.get("export_filename", "export.md"),
                    mime="text/markdown",
                    key="dl_btn_persistent",
                    use_container_width=True
                )


def _delete_last_db_turn() -> None:
    """Löscht die letzten 2 DB-Einträge (User + Model)."""
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
    except Exception as e:
        st.error(f"Fehler: {e}")


def _prepare_export() -> None:
    """Generiert Export-Daten und speichert sie im Session State."""
    with st.spinner("Generiere Dokument..."):
        from modules.export import generate_markdown, generate_chat_markdown

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

        has_rag = bool(st.session_state.get("last_rag_sources"))

        try:
            if has_rag:
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
                markdown = generate_chat_markdown(
                    st.session_state.history, chat_title
                )
                filename = f"Chat_{datetime.now().strftime('%H%M')}.md"

            st.session_state.export_data = markdown
            st.session_state.export_filename = filename
            st.success("Fertig!")
        except Exception as e:
            st.error(f"Fehler: {e}")
            print(f"Export-Crash: {e}")


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
        ["🌐 Online (Google Search aktiv)", "🔬 Labor (nur Modell-Wissen)"],
        index=0,
        horizontal=True,
        key="chat_search_mode"
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
) -> None:
    """Verarbeitet User-Input: Chat-ID anlegen, History schreiben, Weiche."""

    # Chat-ID anlegen falls nötig
    if st.session_state.chat_id is None:
        st.session_state.chat_id = create_chat_in_firestore("Neuer Chat")
        if st.session_state.chat_id is None:
            st.error("Konnte keinen neuen Chat erstellen.")
            st.stop()

    state.append_to_history("user", prompt)
    save_message(st.session_state.chat_id, "user", prompt)

    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("model"):
        if use_db:
            _handle_rag(prompt, filter_mode, selected_rag_ids, use_router)
        else:
            _handle_free_chat(prompt, use_search)

    # Titel generieren
    if (not st.session_state.get("title_generated")
            and len(st.session_state.history) >= 2):
        generate_and_update_title(
            st.session_state.chat_id, st.session_state.history
        )
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
                    st.caption(s.get('content')[:200] + "...")

        state.append_to_history("model", final_text)
        save_message(st.session_state.chat_id, "model", final_text)
        st.rerun()

    except Exception as e:
        st.error(f"RAG Fehler: {e}")


def _handle_free_chat(prompt: str, use_search: bool) -> None:
    """PFAD B: Freier Chat via LLM."""
    state.clear_rag_state()

    try:
        settings = st.session_state.global_settings
        stream = _send_message(
            prompt,
            st.session_state.history[:-1],
            settings['system_instruction'],
            settings['temperature'],
            use_search=use_search,
        )
        response_text = st.write_stream(stream)

        state.append_to_history("model", response_text)
        save_message(st.session_state.chat_id, "model", response_text)
        st.session_state.last_error = None
        st.rerun()

    except Exception as e:
        st.session_state.last_error = str(e)
        st.rerun()