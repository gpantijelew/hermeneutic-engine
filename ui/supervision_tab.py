import streamlit as st
import ui.state as state
from modules.database import get_chat_list, load_chat_history
from modules.citation_rag import CitationRAG
from modules.ifs_engine import IFS_PART_MAP  # v59.1 Fix 6 — IFS-Kontext importieren

# v59.1 Fix 1 — IFS-Rollen-Karte für descriptive Labels
# Statt abstrakter [USER]/[MODEL] Labels, die kleinere Modelle verwirren,
# verwenden wir IFS-spezifische Rollenbeschreibungen wenn der Chat aus
# dem Resonanzraum stammt.
IFS_ROLE_LABELS = {
    "user": "PERSON (Ich/Self)",
    "model": "INNERE STIMME",
    "assistant": "INNERE STIMME",
}


def _detect_ifs_context(history: list) -> dict:
    """
    v59.1 Fix 6 — Erkennt ob ein Chat aus dem IFS Resonanzraum stammt
    und welche innere Stimme aktiv war.

    Returns:
        dict mit 'is_ifs', 'part_type', 'part_label' Keys
    """
    # Heuristik: Prüfe ob Chat-Metadaten einen IFS-Intent tragen
    # oder ob die Nachrichten IFS-typische Muster enthalten
    result = {"is_ifs": False, "part_type": None, "part_label": None}

    if not history:
        return result

    # Strategie 1: Prüfe auf IFS-Metadaten im Chat (falls vorhanden)
    for msg in history[:3]:
        metadata = msg.get("metadata", {})
        if isinstance(metadata, dict):
            part_intent = metadata.get("part_intent", "")
            if part_intent in IFS_PART_MAP:
                result["is_ifs"] = True
                result["part_type"] = part_intent
                result["part_label"] = IFS_PART_MAP[part_intent]
                return result

    # Strategie 2: Heuristik — prüfe auf IFS-typische Sprachmuster
    # in den Modell-Antworten (ich-Perspektive als innerer Anteil)
    model_texts = []
    for msg in history:
        role = msg.get("role", "")
        if role in ("model", "assistant"):
            text = msg.get("parts", [{}])[0].get("text", "") if msg.get("parts") else msg.get("content", "")
            if text:
                model_texts.append(text.lower())

    if model_texts:
        ifs_keywords = ["innerer anteil", "ich als", "mein anteil", "ich bin der teil",
                        "ich bin die stimme", "kontrollzwang", "mauern", "verletzlichkeit"]
        keyword_hits = sum(1 for t in model_texts for kw in ifs_keywords if kw in t)
        if keyword_hits >= 2:
            result["is_ifs"] = True
            # Versuche den Part-Typ zu erraten
            all_text = " ".join(model_texts)
            if any(kw in all_text for kw in ["kontrolle", "regeln", "risiko", "professionell"]):
                result["part_type"] = "IFS_CONTROL"
                result["part_label"] = IFS_PART_MAP["IFS_CONTROL"]
            elif any(kw in all_text for kw in ["wut", "wütend", "angriff", "verteidigung", "stolz"]):
                result["part_type"] = "IFS_FIGHT"
                result["part_label"] = IFS_PART_MAP["IFS_FIGHT"]
            elif any(kw in all_text for kw in ["angst", "überfordert", "hilflos", "verstecken"]):
                result["part_type"] = "IFS_FEAR"
                result["part_label"] = IFS_PART_MAP["IFS_FEAR"]
            else:
                result["part_label"] = "innerer Anteil (unbekannt)"

    return result


def _format_role_label(role: str, ifs_context: dict) -> str:
    """
    v59.1 Fix 1 — Gibt ein deskriptives Rollen-Label zurück.

    Für IFS-Chats: [PERSON (Ich/Self)] statt [USER],
                    [INNERE STIMME: Kampf/Abwehr] statt [MODEL]
    Für Nicht-IFS-Chats: [USER] / [MODEL] wie bisher
    """
    if ifs_context["is_ifs"]:
        if role in ("model", "assistant"):
            part_label = ifs_context.get("part_label", "innerer Anteil")
            return f"INNERE STIMME ({part_label})"
        elif role == "user":
            return "PERSON (Ich/Self)"
    # Fallback: klassische Labels
    return role.upper()


def render_supervision_tab():
    st.header("🧑‍⚖️ IFS Supervisions-Panel")
    st.markdown("""
    Dieser Modus analysiert einen kompletten Chat als psychologisches System.
    Zwei Agenten (Manager-Fokus & Exile-Fokus) untersuchen den Text parallel.
    Ein Tribunal-Agent bewertet anschließend die Meta-Dynamik.
    """)

    # Chats laden (KORRIGIERT)
    all_chats = get_chat_list()

    if not all_chats:
        st.info("Keine Chats in der Datenbank gefunden.")
        return

    # Chat Auswahl
    chat_options = {chat['id']: chat['title'] for chat in all_chats}
    selected_chat_id = st.selectbox(
        "Wähle einen Chat für die Supervision:",
        options=list(chat_options.keys()),
        format_func=lambda x: chat_options[x]
    )

    if st.button("🚀 Supervision starten", type="primary"):
        # Lade Chat-Historie (KORRIGIERT)
        history = load_chat_history(selected_chat_id)
        if not history:
            st.warning("Dieser Chat ist leer.")
            return

        # v59.1 Fix 6 — IFS-Kontext erkennen
        ifs_context = _detect_ifs_context(history)

        # v59.1 Fix 1 — IFS-context-aware Rollen-Labels
        # Formatiere Chat als Text mit deskriptiven Rollen-Labels
        parts = []
        for msg in history:
            role = msg.get("role", "unknown")
            text = msg.get("parts", [{}])[0].get("text", "") if msg.get("parts") else msg.get("content", "")
            if text.strip():
                role_label = _format_role_label(role, ifs_context)
                parts.append(f"[{role_label}]\n{text.strip()}")
        chat_text = "\n\n".join(parts)

        # v59.1 Fix 6 — IFS-Kontext-Präfix für Supervisions-Pipeline
        # Wenn IFS erkannt wurde, wird ein Kontext-Header vorangestellt,
        # damit die Supervisions-Agenten die Rollenstruktur verstehen.
        if ifs_context["is_ifs"]:
            ifs_header = (
                f"=== IFS-RESONANZRAUM KONTEXT ===\n"
                f"Dieser Dialog stammt aus dem IFS Resonanzraum.\n"
                f"Aktive innere Stimme: {ifs_context['part_label']}\n"
                f"Rollenstruktur:\n"
                f"  - [PERSON (Ich/Self)] = Der User, der mit seiner inneren Stimme spricht\n"
                f"  - [INNERE STIMME ({ifs_context['part_label']})] = Der innere Anteil, gespielt vom KI-Modell\n"
                f"Die Analyse MUSS diese IFS-Rollenstruktur berücksichtigen.\n"
                f"=== ENDE IFS-KONTEXT ===\n\n"
            )
            chat_text = ifs_header + chat_text

        with st.status("Führe psychosystemische Analyse durch...", expanded=True) as status:
            st.write("Starte Map-Reduce Pipeline (Manager & Exile parallel)...")
            if ifs_context["is_ifs"]:
                st.write(f"IFS-Modus erkannt: {ifs_context['part_label']}")
            try:
                # Aufruf der neuen Pipeline
                rag = CitationRAG()
                results = rag.generate_ifs_supervision(chat_text)
                status.update(label="Supervision erfolgreich abgeschlossen!", state="complete", expanded=False)

                # Ergebnisse im State speichern, damit sie beim Tab-Wechsel bleiben
                state.set_supervision_result(results, chat_options[selected_chat_id])
            except Exception as e:
                status.update(label="Fehler bei der Supervision", state="error")
                st.error(f"Pipeline-Fehler: {e}")
                import traceback
                st.code(traceback.format_exc())
                return

    # Ergebnisse anzeigen
    res, chat_title = state.get_supervision_result()
    if res:
        st.subheader("📋 Meta-Gutachten (System-Dynamik)")
        st.info(res["meta"])

        st.markdown("---")
        st.subheader("🔍 Fachgutachten")

        col1, col2 = st.columns(2)
        with col1:
            with st.expander("🛡️ Struktur-Analyse (Manager)", expanded=True):
                st.write(res["manager"])
        with col2:
            with st.expander("🌋 Tiefen-Analyse (Exile)", expanded=True):
                st.write(res["exile"])

        # Export
        st.markdown("---")
        export_text = f"# IFS Supervision: {st.session_state.last_supervision_chat}\n\n"
        export_text += f"## Meta-Gutachten\n{res['meta']}\n\n"
        export_text += f"## Struktur-Analyse (Manager)\n{res['manager']}\n\n"
        export_text += f"## Tiefen-Analyse (Exile)\n{res['exile']}\n"

        st.download_button(
            label="📥 Gutachten als Markdown exportieren",
            data=export_text,
            file_name="ifs_supervision_gutachten.md",
            mime="text/markdown"
        )
