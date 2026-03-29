# modules/bulk_labeling.py
import streamlit as st
from modules.llm_wrapper import llm_call_json
from modules.config import MODEL_BULK_LABELING
import json
import re
from modules.database import get_firestore_client
from modules.vector_store import FirestoreVectorStore

def render_bulk_labeling_ui():
    st.title("🏷️ Enhanced Bulk Labeling (Full Control)")

    db = get_firestore_client()
    if not db:
        st.error("Keine Datenbankverbindung.")
        return

    vs = FirestoreVectorStore(db)

    # --- 1. SETTINGS & FILTER ---
    with st.expander("⚙️ Einstellungen & Filter", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            preview_length = st.slider("Vorschau-Länge:", 100, 1000, 300, 50)
        with c2:
            pass 

        f1, f2, f3 = st.columns(3)
        filter_speaker = f1.selectbox("Speaker:", ["Alle", "Unknown", "Unbekannt", "User", "Kimi", "DeepSeek", "ChatGPT", "Claude", "Gemini"])
        filter_type = f2.selectbox("Typ:", ["Alle", "None", "Analyse", "Selbstreflexion", "Vergleich", "Frage", "Dialog"])
        filter_text = f3.text_input("Text enthält:")

        if st.button("🔎 Chunks laden"):
            st.session_state.bulk_chunks = load_chunks_deep(vs, filter_speaker, filter_type, filter_text)
            # Reset KI-Vorschläge bei neuem Laden
            if 'ai_suggestions' in st.session_state: del st.session_state.ai_suggestions

    # --- 2. LISTE ---
    if 'bulk_chunks' in st.session_state and st.session_state.bulk_chunks:
        chunks = st.session_state.bulk_chunks
        st.success(f"✅ {len(chunks)} Chunks geladen")

        # --- DER ZAUBERSTAB ---
        if st.button("✨ KI-Vorschläge generieren (Flash Lite)", type="secondary"):
            with st.spinner("Die KI analysiert deine Chunks..."):
                suggestions = generate_ai_suggestions(chunks)
                if suggestions:
                    st.session_state.ai_suggestions = suggestions
                    st.success(f"{len(suggestions)} Vorschläge generiert! Die Dropdowns wurden aktualisiert.")
                else:
                    st.warning("KI konnte keine Vorschläge generieren.")

        st.divider()

        # --- TABELLE MIT INDIVIDUELLEN DROPDOWNS ---

        # Header
        c1, c2, c3, c4 = st.columns([0.5, 2, 2, 4])
        c1.markdown("**Fix?**")
        c2.markdown("**Sprecher (Neu)**")
        c3.markdown("**Typ (Neu)**")
        c4.markdown("**Inhalt (Aktuell: Grau)**")

        # Listen für Dropdowns
        SPEAKER_OPTIONS = ["Unknown", "User", "Kimi", "DeepSeek", "ChatGPT", "Claude", "Gemini", "Dialog"]
        TYPE_OPTIONS = ["None", "Analyse", "Selbstreflexion", "Vergleich", "Frage", "Dialog"]

        updates_to_apply = {} # ID -> {field: value}

        # Sicherstellen, dass ai_suggestions ein Dict ist
        ai_suggestions = st.session_state.get('ai_suggestions', {})
        if not isinstance(ai_suggestions, dict): ai_suggestions = {}

        for chunk in chunks:
            chunk_id = chunk['id']
            meta = chunk.get('metadata', {})
            text = chunk.get('content', '')

            curr_speaker = meta.get('model_name', 'Unknown')
            curr_type = meta.get('content_type', 'None')

            # KI Vorschlag holen
            ai_sugg = ai_suggestions.get(chunk_id, {})
            sugg_speaker = ai_sugg.get('speaker')
            sugg_type = ai_sugg.get('type')

            # Bestimme den Startwert für das Dropdown
            # Priorität: 1. KI-Vorschlag, 2. Aktueller Wert, 3. "Unknown"

            # Speaker Index finden
            default_speaker_val = sugg_speaker if sugg_speaker in SPEAKER_OPTIONS else (curr_speaker if curr_speaker in SPEAKER_OPTIONS else "Unknown")
            try:
                sp_idx = SPEAKER_OPTIONS.index(default_speaker_val)
            except:
                sp_idx = 0

            # Type Index finden
            default_type_val = sugg_type if sugg_type in TYPE_OPTIONS else (curr_type if curr_type in TYPE_OPTIONS else "None")
            try:
                tp_idx = TYPE_OPTIONS.index(default_type_val)
            except:
                tp_idx = 0

            with st.container():
                cc1, cc2, cc3, cc4 = st.columns([0.5, 2, 2, 4])

                # 1. Checkbox (Wird automatisch aktiviert, wenn KI was vorschlägt, kann aber abgewählt werden)
                has_suggestion = (sugg_speaker is not None)
                apply_this = cc1.checkbox("Go", key=f"chk_{chunk_id}", value=False)

                # 2. Speaker Dropdown (Editierbar!)
                new_speaker = cc2.selectbox(
                    "Sprecher", 
                    SPEAKER_OPTIONS, 
                    index=sp_idx, 
                    key=f"sp_{chunk_id}", 
                    label_visibility="collapsed"
                )

                # 3. Type Dropdown (Editierbar!)
                new_type = cc3.selectbox(
                    "Typ", 
                    TYPE_OPTIONS, 
                    index=tp_idx, 
                    key=f"tp_{chunk_id}", 
                    label_visibility="collapsed"
                )

                # 4. Text & Info
                # Zeige an, was aktuell in der DB steht, damit man vergleichen kann
                info_text = f":grey[{curr_speaker} | {curr_type}]"
                if has_suggestion:
                    info_text += " | :green[✨ KI]"

                cc4.caption(info_text)
                cc4.markdown(f"`{text[:preview_length]}...`")

                # Logik: Wenn Checkbox an, dann nimm die Werte aus den Dropdowns
                if apply_this:
                    updates_to_apply[chunk_id] = {
                        'metadata.model_name': new_speaker,
                        'metadata.content_type': new_type
                    }

                st.divider()

        # GLOBALER SPEICHER BUTTON
        if updates_to_apply:
            st.markdown("### 💾 Speichern")
            st.info(f"{len(updates_to_apply)} Änderungen bereit.")
            if st.button("Änderungen jetzt in Datenbank schreiben", type="primary"):
                apply_batch_updates(vs, updates_to_apply)
                st.success("Gespeichert! Liste wird neu geladen...")
                # Cleanup
                if 'ai_suggestions' in st.session_state: del st.session_state.ai_suggestions
                st.session_state.bulk_chunks = load_chunks_deep(vs, filter_speaker, filter_type, filter_text)
                st.rerun()

    elif 'bulk_chunks' in st.session_state:
        st.warning("Keine Chunks gefunden.")

# --- LOGIK ---

def generate_ai_suggestions(chunks):
    """Nutzt lokalen LLM via llm_wrapper, um Metadaten zu raten.
    v50.9-local: genai.Client ersetzt durch llm_call_json.
    """
    # Batching (max 20 für Demo/Speed)
    batch_chunks = chunks[:20]

    prompt = """Analysiere diese Text-Fragmente aus einem Chat-Verlauf.

AUFGABE:
Bestimme für jedes Fragment:
1. SPEAKER: Wer spricht? (Kimi, DeepSeek, User, ChatGPT). Wenn unklar -> 'Dialog'.
2. TYPE: Was ist das? (Analyse, Selbstreflexion, Frage, Dialog).

FORMAT:
Antworte als JSON-LISTE von Objekten:
[
    {"id": "ID_DES_CHUNKS", "speaker": "...", "type": "..."},
    ...
]

Fragmente:
"""
    for c in batch_chunks:
        prompt += f"ID: {c['id']}\nTEXT: {c.get('content', '')[:300]}\n---\n"

    try:
        parsed_data = llm_call_json(prompt, task="bulk_labeling", fallback=[])

        suggestions = {}
        if isinstance(parsed_data, list):
            for item in parsed_data:
                cid = item.get('id')
                if cid:
                    suggestions[cid] = item
        elif isinstance(parsed_data, dict):
            if 'results' in parsed_data and isinstance(parsed_data['results'], list):
                for item in parsed_data['results']:
                    cid = item.get('id')
                    if cid:
                        suggestions[cid] = item
            else:
                suggestions = parsed_data

        return suggestions

    except Exception as e:
        st.error(f"KI-Fehler: {e}")
        return {}

def load_chunks_deep(vs, speaker, ctype, text_filter):
    """
    Lädt Chunks aus ChromaDB mit client-seitiger Filterung.
    v50.9-local: col_ref.stream() ersetzt durch vs.get_all_chunks().
    """
    all_chunks = vs.get_all_chunks(limit=500)  # Sicherheitslimit für UI
    results = []

    for d in all_chunks:
        meta = d.get('metadata', {})

        if speaker != "Alle":
            curr = meta.get('model_name', 'Unknown')
            if speaker in ["Unknown", "Unbekannt"] and curr not in ["Unknown", "Unbekannt", None]:
                continue
            if speaker not in ["Unknown", "Unbekannt"] and curr != speaker:
                continue

        if ctype != "Alle" and meta.get('content_type') != ctype:
            continue

        if text_filter and text_filter.lower() not in d.get('content', '').lower():
            continue

        # Für UI-Kompatibilität: 'id' aus 'vector_doc_id' ableiten
        d['id'] = d.get('vector_doc_id', '')
        results.append(d)

        if len(results) >= 50:
            break

    return results

def apply_batch_updates(vs, updates_dict):
    """
    Schreibt Metadaten-Updates in ChromaDB.
    v50.9-local: Firestore batch ersetzt durch vs.update_chunk_metadata().
    """
    success_count = 0
    fail_count = 0

    for chunk_id, fields in updates_dict.items():
        if vs.update_chunk_metadata(chunk_id, fields):
            success_count += 1
        else:
            fail_count += 1

    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"✅ Batch-Update: {success_count} erfolgreich, {fail_count} fehlgeschlagen.")

    if fail_count > 0:
        st.warning(f"⚠️ {fail_count} Chunks konnten nicht aktualisiert werden.")