import streamlit as st
import time
from modules.database import (
    get_all_chats_metadata, 
    update_chat_metadata, 
    get_raw_chat_messages,
    get_firestore_client
)
from modules.vector_store import FirestoreVectorStore

def render_vector_admin_dashboard():
    """
    Rendert das Admin-Dashboard in der Sidebar.
    """
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🔧 Vector Admin v2")
    st.sidebar.info("Setze Sprecher-Labels für präzises RAG")

    # Feature 1: Label-Übersicht (NEU!)
    render_label_overview()
    
    # Feature 2: Chat-Label-Editor
    render_chat_label_editor()
    
    # Feature 3: Bulk-Labeling
    render_bulk_labeling()

def render_chat_label_editor():
    """
    Einzelner Chat-Editor.
    """
    chats = get_all_chats_metadata()

    if not chats:
        st.sidebar.warning("Keine Chats gefunden")
        return

    # Dropdown Optionen bauen
    chat_options = {}
    for chat in chats:
        label = f"{chat['title']} (Label: {chat['model_name']})"
        chat_options[label] = chat

    selected_label = st.sidebar.selectbox(
        "Chat auswählen:",
        options=list(chat_options.keys()),
        key="vec_admin_select"
    )

    selected_chat = chat_options[selected_label]
    chat_id = selected_chat['id']
    current_label = selected_chat['model_name']

    # Label Wahl
    available_labels = ["Kimi", "DeepSeek", "ChatGPT", "Claude", "Gemini", "Grok", "Perplexity", "GLM-4.6", "Unbekannt"]
    try:
        idx = available_labels.index(current_label)
    except ValueError:
        idx = available_labels.index("Unbekannt")

    new_label = st.sidebar.selectbox(
        "Sprecher setzen:",
        available_labels,
        index=idx,
        key="vec_admin_label"
    )

    col1, col2 = st.sidebar.columns(2)

    # Button 1: Nur Speichern
    if col1.button("💾 Speichern", key="btn_save_meta"):
        try:
            update_chat_metadata(chat_id, model_name=new_label)
            st.sidebar.success(f"Label '{new_label}' gespeichert!")
            time.sleep(1)
            st.rerun()
        except Exception as e:
            st.sidebar.error(f"Fehler: {e}")

    # Button 2: Speichern & Indizieren
    if col2.button("🔄 Indexieren", key="btn_reindex"):
        with st.sidebar.status("Arbeite...") as status:
            try:
                # 1. Metadaten speichern
                status.write("Speichere Label...")
                update_chat_metadata(chat_id, model_name=new_label)

                # 2. Nachrichten holen
                status.write("Lade Nachrichten...")
                messages = get_raw_chat_messages(chat_id)

                if not messages:
                    st.sidebar.error("Chat ist leer!")
                    return

                # 3. Vector Store Init
                db = get_firestore_client()
                vector_store = FirestoreVectorStore(db)

                # 4. Alte Vektoren löschen (Hard Delete via Firestore Query)
                status.write("Lösche alte Vektoren...")
                vector_store.delete_chat_embeddings(chat_id)

                # 5. Neu Indizieren
                status.write("Erstelle neue Vektoren...")

                # Metadaten für den Chunk
                meta = {
                    'title': selected_chat['title'],
                    'model_name': new_label, # <--- DAS WICHTIGE FELD
                    'platform': new_label,
                    'source': 'admin_dashboard'
                }

                count, skipped = vector_store.process_and_store_chat(chat_id, messages, meta)

                status.update(label="Fertig!", state="complete", expanded=False)
                st.sidebar.success(f"✅ {count} Chunks als '{new_label}' indiziert.")
                time.sleep(2)
                st.rerun()

            except Exception as e:
                st.sidebar.error(f"Fehler: {e}")

def render_label_overview():
    """
    Zeigt eine Übersicht aller Chats mit/ohne Label.
    """
    with st.sidebar.expander("📊 Label-Übersicht", expanded=False):
        chats = get_all_chats_metadata()
        
        # Gruppiere nach Label-Status
        labeled = [c for c in chats if c['model_name'] not in ['Unbekannt', None, '']]
        unlabeled = [c for c in chats if c['model_name'] in ['Unbekannt', None, '']]
        
        # Statistik
        st.metric("Gelabelt", len(labeled))
        st.metric("Ohne Label", len(unlabeled))
        
        # Details
        if unlabeled:
            st.markdown("**🔍 Chats ohne Label:**")
            for chat in unlabeled[:10]:  # Zeige erste 10
                st.caption(f"- {chat['title'][:50]}...")
            if len(unlabeled) > 10:
                st.caption(f"...und {len(unlabeled)-10} weitere.")
        else:
            st.success("✅ Alle Chats haben ein Label!")

def render_bulk_labeling():
    """
    Automatische Vorschläge basierend auf Titel.
    """
    with st.sidebar.expander("📦 Bulk-Labeling (Auto)"):
        chats = get_all_chats_metadata()
        # Finde Chats, die noch "Unbekannt" oder leer sind
        unlabeled = [c for c in chats if c['model_name'] in ['Unbekannt', None, '']]

        if not unlabeled:
            st.info("Alles sauber! Keine ungelabelten Chats.")
            return

        st.write(f"{len(unlabeled)} Chats ohne Label.")

        suggestions = []
        for chat in unlabeled:
            title = chat['title'].lower()
            sugg = "Unbekannt"
            if 'kimi' in title: sugg = 'Kimi'
            elif 'deepseek' in title: sugg = 'DeepSeek'
            elif 'chatgpt' in title: sugg = 'ChatGPT'
            elif 'claude' in title: sugg = 'Claude'
            elif 'gemini' in title: sugg = 'Gemini'

            if sugg != "Unbekannt":
                suggestions.append((chat, sugg))

        if not suggestions:
            st.warning("Keine offensichtlichen Labels im Titel gefunden.")
            return

        st.markdown("---")
        st.markdown("**Vorschläge:**")
        for chat, sugg in suggestions[:5]: # Preview
            st.caption(f"'{chat['title']}' -> **{sugg}**")

        if len(suggestions) > 5:
            st.caption(f"...und {len(suggestions)-5} weitere.")

        if st.button(f"✅ {len(suggestions)} Labels anwenden"):
            count = 0
            progress = st.progress(0)
            for i, (chat, sugg) in enumerate(suggestions):
                update_chat_metadata(chat['id'], model_name=sugg)
                count += 1
                progress.progress((i + 1) / len(suggestions))

            st.success(f"{count} Labels aktualisiert! Bitte indiziere die Chats nun einzeln neu.")
            time.sleep(2)
            st.rerun()