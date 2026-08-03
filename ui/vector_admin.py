# modules/vector_admin.py - v50.7: Cache-Invalidierung harmonisiert
"""
Vector Admin Dashboard - UI für Sprecher-Labeling und Reindizierung.

PHILOSOPHIE:
Ermöglicht manuelle Korrektur von Sprecher-Labels (model_name) in der Datenbank
und Reindizierung der zugehörigen Embeddings.

NEU v50.7 (AUDIT-FIX):
- Cache-Invalidierung nach Bulk-Labeling
- Klarere Warnungen über Notwendigkeit der Reindizierung
- Harmonisierung mit vector_store.py v50.7.1

ÄNDERUNGSHISTORIE:
- v50.7: Cache-Invalidierung + Warnungen
- v47: Initiale Version (Bulk-Labeling)
"""

import streamlit as st
import time
from modules.database import (
    get_all_chats_metadata,
    update_chat_metadata,
    get_raw_chat_messages,
    get_db_connection,
)
from modules.vector_store import LocalVectorStore


def render_vector_admin_dashboard():
    """
    Rendert das Admin-Dashboard in der Sidebar.

    FEATURES:
    1. Label-Übersicht (Statistik)
    2. Chat-Label-Editor (Einzeln)
    3. Bulk-Labeling (Automatisch)
    """
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🔧 Vector Admin v2")
    st.sidebar.info("Setze Sprecher-Labels für präzises RAG")
    # Feature 1: Label-Übersicht
    render_label_overview()
    # Feature 2: Chat-Label-Editor
    render_chat_label_editor()
    # Feature 3: Bulk-Labeling
    render_bulk_labeling()
    # Feature 4: Re-Index fehlgeschlagener Chunks
    render_reindex_skipped()


def render_chat_label_editor():
    """
    Einzelner Chat-Editor mit zwei Modi:
    - "Speichern": Nur Metadata ändern (schnell)
    - "Indexieren": Metadata + Embeddings neu erstellen (langsam)
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
        "Chat auswählen:", options=list(chat_options.keys()), key="vec_admin_select"
    )

    selected_chat = chat_options[selected_label]
    chat_id = selected_chat["id"]
    current_label = selected_chat["model_name"]

    # Label Wahl
    available_labels = [
        "Kimi",
        "DeepSeek",
        "ChatGPT",
        "Claude",
        "Gemini",
        "Grok",
        "Perplexity",
        "GLM-4.6",
        "Unbekannt",
    ]

    try:
        idx = available_labels.index(current_label)
    except ValueError:
        idx = available_labels.index("Unbekannt")

    new_label = st.sidebar.selectbox(
        "Sprecher setzen:", available_labels, index=idx, key="vec_admin_label"
    )

    col1, col2 = st.sidebar.columns(2)

    # =========================================================================
    # Button 1: Nur Metadata Speichern (Schnell, aber unvollständig)
    # =========================================================================
    if col1.button("💾 Speichern", key="btn_save_meta"):
        try:
            update_chat_metadata(chat_id, model_name=new_label)
            st.sidebar.success(f"Label '{new_label}' gespeichert!")
            st.sidebar.warning(
                "⚠️ WICHTIG: Du musst den Chat neu indizieren (🔄), "
                "damit das neue Label auch in den Embeddings erscheint!"
            )
            time.sleep(2)
            st.rerun()
        except Exception as e:
            st.sidebar.error(f"Fehler: {e}")

    # =========================================================================
    # Button 2: Metadata Speichern + Embeddings Neu-Indizieren (Langsam, vollständig)
    # =========================================================================
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
                db = get_db_connection()
                vector_store = LocalVectorStore(db)

                # 4. Alte Vektoren löschen (Hard Delete via Firestore Query)
                status.write("Lösche alte Vektoren...")
                vector_store.delete_chat_embeddings(chat_id)

                # 5. Neu Indizieren
                status.write("Erstelle neue Vektoren...")

                # Metadaten für den Chunk
                meta = {
                    "title": selected_chat["title"],
                    "model_name": new_label,  # <--- DAS WICHTIGE FELD
                    "platform": new_label,
                    "source": "admin_dashboard",
                }

                count, skipped = vector_store.process_and_store_chat(
                    chat_id, messages, meta
                )

                status.update(label="Fertig!", state="complete", expanded=False)
                st.sidebar.success(f"✅ {count} Chunks als '{new_label}' indiziert.")
                time.sleep(2)
                st.rerun()

            except Exception as e:
                st.sidebar.error(f"Fehler: {e}")


def render_label_overview():
    """
    Zeigt eine Übersicht aller Chats mit/ohne Label.

    STATISTIK:
    - Anzahl gelabelter Chats
    - Anzahl ungelabelter Chats
    - Liste der ersten 10 Chats ohne Label
    """
    with st.sidebar.expander("📊 Label-Übersicht", expanded=False):
        chats = get_all_chats_metadata()

        # Gruppiere nach Label-Status
        labeled = [c for c in chats if c["model_name"] not in ["Unbekannt", None, ""]]
        unlabeled = [c for c in chats if c["model_name"] in ["Unbekannt", None, ""]]

        # Statistik
        st.metric("Gelabelt", len(labeled))
        st.metric("Ohne Label", len(unlabeled))

        # Details
        if unlabeled:
            st.markdown("**🔍 Chats ohne Label:**")
            for chat in unlabeled[:10]:  # Zeige erste 10
                st.caption(f"- {chat['title'][:50]}...")
            if len(unlabeled) > 10:
                st.caption(f"...und {len(unlabeled) - 10} weitere.")
        else:
            st.success("✅ Alle Chats haben ein Label!")


def render_bulk_labeling():
    """
    Automatische Label-Vorschläge basierend auf Titel-Heuristik.

    STRATEGIE:
    1. Finde Chats ohne Label
    2. Analysiere Titel (Keyword-Matching)
    3. Generiere Vorschläge
    4. User klickt Button → Metadata wird geändert
    5. NEU v50.7: BM25-Cache wird invalidiert (wichtig!)

    WICHTIG:
    Nach Bulk-Labeling MÜSSEN die Chats einzeln neu indiziert werden,
    damit die neuen Labels auch in den Embeddings erscheinen!
    """
    with st.sidebar.expander("📦 Bulk-Labeling (Auto)"):
        chats = get_all_chats_metadata()

        # Finde Chats, die noch "Unbekannt" oder leer sind
        unlabeled = [c for c in chats if c["model_name"] in ["Unbekannt", None, ""]]

        if not unlabeled:
            st.info("Alles sauber! Keine ungelabelten Chats.")
            return

        st.write(f"{len(unlabeled)} Chats ohne Label.")

        # Heuristische Label-Vorschläge
        suggestions = []
        for chat in unlabeled:
            title = chat["title"].lower()
            sugg = "Unbekannt"

            # Keyword-Matching (Simple Heuristik)
            if "kimi" in title:
                sugg = "Kimi"
            elif "deepseek" in title:
                sugg = "DeepSeek"
            elif "chatgpt" in title:
                sugg = "ChatGPT"
            elif "claude" in title:
                sugg = "Claude"
            elif "gemini" in title:
                sugg = "Gemini"
            elif "grok" in title:
                sugg = "Grok"
            elif "perplexity" in title:
                sugg = "Perplexity"

            if sugg != "Unbekannt":
                suggestions.append((chat, sugg))

        if not suggestions:
            st.warning("Keine offensichtlichen Labels im Titel gefunden.")
            return

        st.markdown("---")
        st.markdown("**Vorschläge:**")

        # Preview (erste 5)
        for chat, sugg in suggestions[:5]:
            st.caption(f"'{chat['title']}' → **{sugg}**")

        if len(suggestions) > 5:
            st.caption(f"...und {len(suggestions) - 5} weitere.")

        # =====================================================================
        # Bulk-Apply Button
        # =====================================================================
        if st.button(f"✅ {len(suggestions)} Labels anwenden"):
            count = 0
            progress = st.progress(0)

            # 1. Metadata ändern
            for i, (chat, sugg) in enumerate(suggestions):
                update_chat_metadata(chat["id"], model_name=sugg)
                count += 1
                progress.progress((i + 1) / len(suggestions))

            # 2. NEU v50.7: BM25-Cache invalidieren (KRITISCH!)
            # Rationale: Ohne Cache-Invalidierung würde BM25-Suche
            # noch die alten Labels zurückgeben, was zu Inkonsistenzen führt.
            try:
                db = get_db_connection()
                vector_store = LocalVectorStore(db)
                vector_store.invalidate_bm25_cache()
                st.info("🗑️ BM25-Cache invalidiert (alte Labels entfernt).")
            except Exception as e:
                st.warning(f"⚠️ Cache-Invalidierung fehlgeschlagen: {e}")

            # 3. User-Warnung
            st.success(f"✅ {count} Labels aktualisiert! ")
            st.warning(
                "⚠️ WICHTIG: Die neuen Labels sind NUR in den Metadata! "
                "Bitte indiziere die Chats einzeln neu (🔄 Indexieren), "
                "damit die Labels auch in den Embeddings erscheinen."
            )

            time.sleep(3)
            st.rerun()


def render_reindex_skipped():
    """
    Zeigt Chats mit fehlgeschlagenen Chunks und ermöglicht gezieltes Re-Indizieren.
    """
    with st.sidebar.expander("🔁 Re-Index fehlgeschlagener Chunks", expanded=False):
        from modules.database import get_db_connection

        db = get_db_connection()
        if db is None:
            st.error("Keine DB-Verbindung.")
            return

        rows = db.execute(
            """SELECT id, title, skipped_chunks
               FROM chats
               WHERE skipped_chunks > 0
               ORDER BY skipped_chunks DESC"""
        ).fetchall()

        if not rows:
            st.success("✅ Keine fehlgeschlagenen Chunks.")
            return

        st.warning(f"⚠️ {len(rows)} Chat(s) mit fehlgeschlagenen Chunks:")

        for row in rows:
            chat_id = row["id"]
            title = row["title"] or f"Chat {chat_id[-8:]}"
            skipped = row["skipped_chunks"]

            col1, col2 = st.columns([3, 1])
            col1.caption(f"**{title}** ({skipped} übersprungen)")

            if col2.button("🔄", key=f"reindex_{chat_id}", help="Re-indizieren"):
                with st.spinner(f"Re-indiziere {title}..."):
                    try:
                        from modules.database import get_raw_chat_messages
                        from modules.vector_store import LocalVectorStore

                        messages = get_raw_chat_messages(chat_id)
                        if not messages:
                            st.error("Keine Nachrichten gefunden.")
                            continue

                        vs = LocalVectorStore()
                        meta = {"chat_title": title}
                        total, skipped_new = vs.process_and_store_chat(
                            chat_id, messages, meta
                        )
                        st.success(
                            f"✅ {total} Chunks indiziert, {skipped_new} übersprungen."
                        )
                        st.rerun()
                    except Exception as e:
                        st.error(f"Fehler: {e}")
