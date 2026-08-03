"""
ui/supervision_tab.py — IFS Supervisions-Panel
v60.2 — v59.1 Fixes integriert:

Fix 1 (Rollen-Disambiguierung Layer 1):
  Abstrakte [USER]/[MODEL]-Labels werden durch deskriptive Labels ersetzt.
  Default: [MENSCH] / [KI-MODELL] — selbsterklärend für kleinere Modelle,
  die bei der Zuordnung User/Assistant die Orientierung verlieren.
  Betrifft: gemma-4-26b-a4b-it und ähnliche Open-Source-Modelle.

Fix 6 (IFS-Kontext-Erkennung):
  Wenn der zu analysierende Chat IFS-spezifische Marker enthält
  (Stimme der Kontrolle/Kampf/Furcht, IFS-Resonanzraum, Manager/Exile/
  Firefighter), werden IFS-spezifische Rollen-Labels verwendet:
    - User-Nachrichten → [MENSCH]
    - Modell-Nachrichten → [STIMME DER KONTROLLE] etc. (wenn zuordenbar)
      oder [KI-MODELL] (fallback)
  Dies signalisiert dem LLM, dass es sich um ein IFS-Gespräch handelt.

Workaround-Hinweis:
  Aktuell wird IFS-Kontext via Text-Heuristik erkannt (Regex). Langfristig
  soll part_intent als Metadatum in Chat-Nachrichten gespeichert werden
  (siehe Backlog AGENTS.md → IFS-Metadaten-Injektion). Bis dahin liefert
  die Heuristik zuverlässige Ergebnisse für explizit IFS-benannte Chats.

Siehe auch: AGENTS.md → v59.1 Rollen-Disambiguierung.
"""

import streamlit as st
import re

import ui.state as state
from modules.database import get_chat_list, load_chat_history
from modules.citation_rag import CitationRAG

# v59.1 Fix 6 — IFS-Kontext-Erkennung importieren
from modules.ifs_engine import (
    IFS_PART_MAP,
    DEFAULT_HUMAN_LABEL,
    DEFAULT_MODEL_LABEL,
    is_ifs_context,
)


# =============================================================================
# v59.1 Fix 1 + Fix 6 — ROLLEN-LABELLING
# =============================================================================
# _resolve_role_label() liefert für eine Chat-Nachricht das passende Label.
#   1. Default: [MENSCH] für user, [KI-MODELL] für model/assistant
#   2. Bei IFS-Kontext im Gesamt-Chat: versucht, IFS-Part zuzuordnen
#      (über Message-Präfix wie "Stimme der Kontrolle:" im Text)
# =============================================================================

# Regex: Erkennt IFS-Part-Zuordnung im Nachrichtentext.
# IFS-Resonanzraum-Chats haben oft Präfixe wie:
#   "Stimme der Kontrolle: ..." oder "Kampf-Stimme: ..."
_IFS_PART_PREFIX_PATTERNS = {
    "ifs_control": re.compile(
        r"^\s*(Stimme der Kontrolle|Kontroll-Stimme|IFS_CONTROL)\s*:",
        re.IGNORECASE,
    ),
    "ifs_fight": re.compile(
        r"^\s*(Stimme des Kampfes|Kampf-Stimme|IFS_FIGHT)\s*:",
        re.IGNORECASE,
    ),
    "ifs_fear": re.compile(
        r"^\s*(Stimme der Furcht|Furcht-Stimme|IFS_FEAR)\s*:",
        re.IGNORECASE,
    ),
}


def _detect_ifs_part_from_text(text: str) -> str | None:
    """
    Versucht, den IFS-Part aus dem Präfix des Modell-Textes zu erkennen.

    Args:
        text: Nachrichtentext (typischerweise Modell-Antwort im IFS-Chat).

    Returns:
        IFS-Part-Key ("ifs_control" / "ifs_fight" / "ifs_fear") oder None,
        wenn kein IFS-Präfix gefunden wurde.
    """
    if not text:
        return None
    for part_key, pattern in _IFS_PART_PREFIX_PATTERNS.items():
        if pattern.search(text):
            return part_key
    return None


def _resolve_role_label(
    role: str,
    text: str,
    ifs_mode: bool,
) -> str:
    """
    Liefert das deskriptive Rollen-Label für eine Chat-Nachricht.

    Args:
        role: Rolle aus der DB ("user" / "model" / "assistant" / etc.)
        text: Nachrichtentext (für IFS-Part-Erkennung im Präfix).
        ifs_mode: True, wenn Gesamt-Chat als IFS-Kontext erkannt wurde.

    Returns:
        Label-String OHNE Klammern (z.B. "MENSCH", "KI-MODELL",
        "STIMME DER KONTROLLE"). Aufrufer fügt [ ] hinzu.
    """
    role_lower = (role or "").lower()

    # User-Seite → immer [MENSCH] (egal ob IFS oder nicht)
    if role_lower in ("user", "human"):
        return DEFAULT_HUMAN_LABEL

    # Modell-Seite
    if role_lower in ("model", "assistant", "ai"):
        if ifs_mode:
            # Versuche, IFS-Part aus Präfix zu erkennen
            part_key = _detect_ifs_part_from_text(text)
            if part_key and part_key in IFS_PART_MAP:
                return IFS_PART_MAP[part_key]
        return DEFAULT_MODEL_LABEL

    # Unbekannte Rolle → generisches Label (nicht [USER]/[MODEL]!)
    return f"ROLLE-{role.upper()}" if role else DEFAULT_MODEL_LABEL


def _format_chat_for_supervision(history: list) -> tuple[str, bool]:
    """
    Formatiert Chat-Historie als Text für die Supervisions-Pipeline.

    v59.1 Fix 1 + Fix 6:
      - Verwendet deskriptive Labels statt [USER]/[MODEL]
      - Erkennt IFS-Kontext und verwendet IFS-spezifische Labels

    Args:
        history: Liste von Message-Dicts mit role und parts.

    Returns:
        Tuple (formatted_text, is_ifs).
        - formatted_text: Formatierter Chat für LLM-Input.
        - is_ifs: True, wenn IFS-Kontext erkannt wurde (für Logging/Debug).
    """
    parts = []
    raw_concat = []  # Für IFS-Kontext-Heuristik

    for msg in history:
        role = msg.get("role", "unknown")
        text = msg.get("parts", [{}])[0].get("text", "") if msg.get("parts") else ""
        if text and text.strip():
            raw_concat.append(text.strip())

    # IFS-Kontext-Heuristik auf den Gesamt-Text anwenden
    full_text = "\n".join(raw_concat)
    ifs_detected = is_ifs_context(full_text)

    # Jetzt mit passenden Labels formatieren
    for msg in history:
        role = msg.get("role", "unknown")
        text = msg.get("parts", [{}])[0].get("text", "") if msg.get("parts") else ""
        if text and text.strip():
            label = _resolve_role_label(role, text.strip(), ifs_detected)
            parts.append(f"[{label}]\n{text.strip()}")

    return "\n\n".join(parts), ifs_detected


# =============================================================================
# TAB-RENDERING
# =============================================================================

def render_supervision_tab():
    """
    Rendert das IFS Supervisions-Panel.

    Analysiert einen kompletten Chat als psychologisches System:
    Zwei Agenten (Manager-Fokus & Exile-Fokus) untersuchen den Text parallel.
    Ein META-Agent bewertet anschließend die Meta-Dynamik.

    v60.2: Chat-Formatierung mit deskriptiven Rollen-Labels (Fix 1) und
    IFS-Kontext-Erkennung (Fix 6).
    """
    st.header("🧑‍⚖️ IFS Supervisions-Panel")
    st.markdown("""
    Dieser Modus analysiert einen kompletten Chat als psychologisches System.
    Zwei Agenten (Manager-Fokus & Exile-Fokus) untersuchen den Text parallel.
    Ein Tribunal-Agent bewertet anschließend die Meta-Dynamik.

    **v59.1+:** Rollen-Labels wurden für kleinere Modelle optimiert
    (deskriptiv statt abstrakt). IFS-Chats werden automatisch erkannt.
    """)

    # Chats laden
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
        # Lade Chat-Historie
        history = load_chat_history(selected_chat_id)
        if not history:
            st.warning("Dieser Chat ist leer.")
            return

        # v59.1 Fix 1 + Fix 6 — Chat mit deskriptiven Labels formatieren
        chat_text, ifs_detected = _format_chat_for_supervision(history)

        # Debug-Info (nur bei aktivem Debug-Mode)
        if st.session_state.get("global_settings", {}).get("debug_mode", False):
            st.caption(f"IFS-Kontext erkannt: {'Ja' if ifs_detected else 'Nein'}")
            with st.expander("Formatierter Chat-Text (Debug)", expanded=False):
                st.code(chat_text, language="markdown")

        with st.status("Führe psychosystemische Analyse durch...", expanded=True) as status:
            st.write("Starte Map-Reduce Pipeline (Manager & Exile parallel)...")
            if ifs_detected:
                st.write("🔍 IFS-Kontext erkannt — verwende IFS-spezifische Rollen-Labels.")
            try:
                # Aufruf der Supervisions-Pipeline
                rag = CitationRAG()
                results = rag.generate_ifs_supervision(chat_text)
                status.update(
                    label="Supervision erfolgreich abgeschlossen!",
                    state="complete",
                    expanded=False,
                )

                # Ergebnisse im State speichern
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


# =============================================================================
# SELF-TEST (wird nur bei direktem Aufruf ausgeführt)
# =============================================================================
if __name__ == "__main__":
    print("=== Self-Test: supervision_tab.py v60.2 ===\n")

    # Test 1: _resolve_role_label — Default-Labels
    print("--- Test 1: Default-Labels (kein IFS-Modus) ---")
    assert _resolve_role_label("user", "Hallo", False) == "MENSCH"
    assert _resolve_role_label("model", "Antwort", False) == "KI-MODELL"
    assert _resolve_role_label("assistant", "Antwort", False) == "KI-MODELL"
    print("  ✅ Default-Labels korrekt")

    # Test 2: _resolve_role_label — IFS-Modus ohne erkennbaren Part
    print("--- Test 2: IFS-Modus ohne erkennbaren Part ---")
    assert _resolve_role_label("user", "Hallo", True) == "MENSCH"
    assert _resolve_role_label("model", "Einfache Antwort ohne Präfix", True) == "KI-MODELL"
    print("  ✅ IFS-Modus ohne Präfix → KI-MODELL (Fallback)")

    # Test 3: _resolve_role_label — IFS-Modus mit erkennbarem Part
    print("--- Test 3: IFS-Modus mit Präfix ---")
    assert _resolve_role_label(
        "model", "Stimme der Kontrolle: Ich halte Struktur.", True
    ) == "STIMME DER KONTROLLE"
    assert _resolve_role_label(
        "model", "Stimme des Kampfes: Ich wehre mich.", True
    ) == "STIMME DES KAMPFES"
    assert _resolve_role_label(
        "model", "Stimme der Furcht: Ich habe Angst.", True
    ) == "STIMME DER FURCHT"
    print("  ✅ IFS-Part-Erkennung korrekt")

    # Test 4: is_ifs_context — Heuristik
    print("--- Test 4: IFS-Kontext-Heuristik ---")
    assert is_ifs_context("Wir sind im IFS-Resonanzraum.") == True
    assert is_ifs_context("Stimme der Kontrolle sagt Hallo.") == True
    assert is_ifs_context("Ein ganz normaler Chat ohne IFS-Bezug.") == False
    assert is_ifs_context("") == False
    print("  ✅ Heuristik korrekt")

    # Test 5: _format_chat_for_supervision — End-to-End
    print("--- Test 5: _format_chat_for_supervision (End-to-End) ---")
    test_history = [
        {"role": "user", "parts": [{"text": "Hallo, ich möchte über meinen Kampf reden."}]},
        {"role": "model", "parts": [{"text": "Stimme des Kampfes: Ich bin hier. Was sagt du?"}]},
    ]
    formatted, ifs_flag = _format_chat_for_supervision(test_history)
    assert ifs_flag == True, f"IFS sollte erkannt werden, got: {ifs_flag}"
    assert "[MENSCH]" in formatted
    assert "[STIMME DES KAMPFES]" in formatted
    assert "[USER]" not in formatted
    assert "[MODEL]" not in formatted
    print("  ✅ End-to-End-Formatierung korrekt")
    print(f"  Formatted preview:\n{formatted[:200]}...")

    print("\n=== Alle Tests bestanden ===")
