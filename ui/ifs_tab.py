# ui/ifs_tab.py — HRE Mission D: Der Resonanzraum
#
# KONZEPT:
# Der User beschreibt eine reale Situation (3-5 Sätze).
# Er wählt eine innere Stimme (Part).
# Das Modell spielt diese Stimme in der Ersten Person.
# Der User ist das "Self" — der neugierige Beobachter.
#
# PÄDAGOGIK (Pedagogy by Design):
# Das Modell reagiert auf die QUALITÄT der Fragen:
# - Belehrung/Widerspruch → Stimme mauert, wird sturer
# - Offene, neugierige Fragen → Stimme öffnet sich
# Validiert durch: DeepSeek-Chat 30.04.2026 + Kimi-Szene 05.10.2025
#
# ARCHITEKTUR-REGEL:
# State-Schreibzugriffe ausschließlich via ui/state.py.
# Persönliche Inhalte werden NIE in die HRE-Datenbank gespeichert.
# Sys-Prompt wird bei JEDEM Turn neu gesetzt (Model-Drift-Schutz).

import logging
import uuid
from datetime import datetime

import streamlit as st

import ui.state as state

logger = logging.getLogger(__name__)

PARTS = {
    "ifs_control": {
        "label":       "🔵 Stimme der Kontrolle & Sicherheit",
        "short":       "Kontrolle",
        "color":       "#4A90D9",
        "description": (
            "Der Teil, der durch Kontrolle, Regeln und Rationalität schützt. "
            "Er fürchtet Fehler und Gesichtsverlust."
        ),
        "hint": (
            "Wenn diese Stimme mauert: Stelle keine Ratschläge. "
            "Frage stattdessen: 'Was befürchtest du, wenn du loslässt?'"
        ),
        "exile": False,
    },
    "ifs_fight": {
        "label":       "🔴 Stimme des Kampfes & der Abwehr",
        "short":       "Kampf",
        "color":       "#E8453C",
        "description": (
            "Der Teil, der sich angegriffen fühlt und zurückschlägt. "
            "Hinter seiner Wut steckt eine tiefere Verletzung."
        ),
        "hint": (
            "Wenn diese Stimme wütend wird: Nicht widersprechen. "
            "Frage: 'Was hat dich in dieser Situation am meisten getroffen?'"
        ),
        "exile": False,
    },
    "ifs_fear": {
        "label":       "🟣 Stimme der Überforderung & Angst",
        "short":       "Überforderung",
        "color":       "#9B59B6",
        "description": (
            "Der verletzliche Teil, der sich verstecken will. "
            "Er braucht Sicherheit, um Vertrauen zu fassen."
        ),
        "hint": (
            "Dieser Teil braucht Stille und Sicherheit. "
            "Frage: 'Was würdest du dir in diesem Moment wünschen?'"
        ),
        "exile": True,  # Stufe-2-Disclaimer
    },
}

MAX_TURNS = 12

_NOTFALL_TRIGGER = [
    "0800 111 0 111",
    "telefonseelsorge",
    "suizid",
    "selbstverletzung",
]


def render_ifs_tab() -> None:
    """Rendert den vollständigen IFS-Resonanzraum-Tab."""

    st.title("🟣 Resonanzraum")

    # Stufe-1-Disclaimer (immer sichtbar)
    st.caption(
        "Ein Reflexionswerkzeug — kein Ersatz für therapeutische Begleitung. "
        "Bei ernsthafter Belastung: Telefonseelsorge **0800 111 0 111** "
        "(kostenlos, 24h, anonym)."
    )

    st.markdown("---")

    # Notfall-Interceptor: Chat eingefroren
    if st.session_state.get("ifs_emergency", False):
        st.error(
            "🛑 **Pause.** Was du beschreibst, braucht echte menschliche Begleitung.\n\n"
            "**Telefonseelsorge: 0800 111 0 111** — kostenlos, rund um die Uhr, anonym.\n\n"
            "Das Gespräch hier ist jetzt beendet. Du kannst das Protokoll herunterladen "
            "und bei Bedarf eine neue Session beginnen."
        )
        histories = st.session_state.get("ifs_histories", {})
        situation = st.session_state.get("ifs_situation", "")
        if any(histories.get(pk, []) for pk in PARTS):
            _render_download_button(histories, situation)
        if st.button("🔄 Neue Session beginnen"):
            state.reset_ifs_session()
            st.rerun()
        return

    if not st.session_state.get("ifs_started", False):
        _render_setup_phase()
    else:
        _render_conversation_phase()


# ==============================================================================
# PHASE 1: SETUP
# ==============================================================================

def _render_setup_phase() -> None:
    """Phase 1: Situation beschreiben und Part wählen."""

    st.subheader("Schritt 1: Beschreibe deine Situation")
    st.caption(
        "Beschreibe in 3–5 Sätzen eine konkrete Situation, "
        "in der du innerlich unter Druck geraten bist. "
        "Je konkreter, desto echter wird das Gespräch."
    )

    situation = st.text_area(
        "Deine Situation:",
        value=st.session_state.get("ifs_situation", ""),
        height=150,
        placeholder=(
            "Beispiel: 'In der letzten Stunde hat ein Schüler mich vor der Klasse "
            "offen provoziert. Ich habe versucht, ruhig zu bleiben, aber innerlich "
            "war ich aufgewühlt. Später hatte ich das Gefühl, falsch reagiert zu haben.'"
        ),
        key="ifs_situation_input",
    )

    if not situation.strip():
        st.info("👆 Beschreibe zuerst deine Situation — dann öffne den Resonanzraum.")
        return

    st.markdown("---")
    st.subheader("Schritt 2: Modus wählen")

    mode_cols = st.columns(2)
    with mode_cols[0]:
        st.caption("**🟣 Triad-Modus**")
        st.markdown(
            "Alle drei Stimmen gleichzeitig sichtbar. "
            "Du sprichst in die Spalte, die du willst."
        )
        if st.button("Triad starten", type="primary"):
            state.start_ifs_session(situation=situation.strip(), mode="triad")
            st.rerun()

    with mode_cols[1]:
        st.caption("**🔵 Einzel-Modus**")
        st.markdown(
            "Eine Stimme nach der anderen. Mit Wechsel-Buttons. "
            "Fokussierter, weniger visueller Overhead."
        )
        if st.button("Einzel starten", type="secondary"):
            state.start_ifs_session(situation=situation.strip(), mode="single", part="ifs_control")
            st.rerun()


# ==============================================================================
# PHASE 2: GESPRÄCH
# ==============================================================================

def _render_conversation_phase() -> None:
    """Phase 2: Dispatch auf Single- oder Triad-Modus."""
    mode = st.session_state.get("ifs_mode", "triad")
    if mode == "single":
        _render_single_mode()
    else:
        _render_triad_mode()


def _render_single_mode() -> None:
    """Phase 2 (Single): Eine Spalte mit Part-Wechsel-Buttons."""

    current_part = st.session_state.get("ifs_current_part", "ifs_control")
    part_cfg = PARTS.get(current_part, PARTS["ifs_control"])
    histories = st.session_state.get("ifs_histories", {})
    history = histories.get(current_part, [])
    situation = st.session_state.get("ifs_situation", "")

    st.markdown(
        f"<div style='border-left: 4px solid {part_cfg['color']}; "
        f"padding-left: 12px; margin-bottom: 16px;'>"
        f"<strong>🔵 Du sprichst mit: {part_cfg['label']}</strong><br/>"
        f"<small style='color: #888;'>Situation: "
        f"{situation[:80]}{'...' if len(situation) > 80 else ''}</small>"
        f"</div>",
        unsafe_allow_html=True,
    )

    with st.expander("💡 Tipp für dieses Gespräch", expanded=False):
        st.caption(part_cfg["hint"])
        st.caption(
            "Deine Rolle als Self: Neugierig, ohne Wertung. "
            "Belehren schließt die Stimme. Echte Neugier öffnet sie."
        )

    # KI beginnt automatisch
    if not history:
        with st.spinner("Die Stimme meldet sich..."):
            _generate_opening(current_part, situation)
        st.rerun()

    # Chat-Verlauf
    for msg in history:
        role = msg.get("role", "user")
        text = msg.get("text", "")
        if role == "reflection":
            st.markdown(
                f"<div style='background:#1a1a2e; border-left: 3px solid #9B59B6; "
                f"padding: 10px; margin: 8px 0; border-radius: 4px;'>"
                f"<small style='color:#9B59B6'>🪞 Deine Reflexion:</small><br/>{text}"
                f"</div>",
                unsafe_allow_html=True,
                    )
        elif role == "user":
            with st.chat_message("user"):
                st.write(text)
        else:
            with st.chat_message("assistant"):
                st.write(text)

    turn_count = len([m for m in history if m.get("role") == "user"])

    if turn_count >= MAX_TURNS:
        st.info(
            f"Du hast {MAX_TURNS} Fragen gestellt — ein guter Moment für eine Pause."
        )
        if not any(m.get("role") == "reflection" for m in history):
            reflection = st.text_area(
                "Was hat dich überrascht? Was hat diese Stimme gebraucht, "
                "das sie dir heute zeigen durfte?",
                key="ifs_reflection",
                height=100,
            )
            if reflection and st.button("Reflexion speichern"):
                state.append_ifs_message(current_part, "reflection", reflection)
                st.rerun()
    else:
        remaining = MAX_TURNS - turn_count
        user_input = st.chat_input(
            f"Deine Frage an die {part_cfg['short']}-Stimme "
            f"({remaining} Fragen verbleiben)...",
            key="ifs_chat_input",
        )
        if user_input:
            state.append_ifs_message(current_part, "user", user_input)
            if current_part == "ifs_fear":
                _generate_response_streaming(current_part, situation, user_input)
            else:
                _generate_response(current_part, situation, user_input)
            st.rerun()

    # D.S3.2: Part-Wechsel mid-Session
    st.markdown("---")
    st.markdown(
        "<small style='color: #888;'>Andere innere Stimme wählen:</small>",
        unsafe_allow_html=True,
    )
    old_label = part_cfg["short"]
    switch_cols = st.columns(len(PARTS))
    for i, (part_key, cfg) in enumerate(PARTS.items()):
        if part_key == current_part:
            switch_cols[i].button(
                cfg["short"],
                disabled=True,
                        key=f"ifs_switch_{part_key}_{i}",
            )
        else:
            if switch_cols[i].button(
                cfg["short"],
                        key=f"ifs_switch_{part_key}_{i}",
            ):
                state.switch_ifs_part(
                    part_key,
                    old_label=old_label,
                    new_label=cfg["short"],
                )
                st.rerun()

    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Neue Session beginnen", ):
            state.reset_ifs_session()
            st.rerun()
    with col2:
        if history:
            _render_download_button_single(history, current_part, situation)


def _render_triad_mode() -> None:
    """Phase 2 (Triad): Drei Spalten — jede Part hat eigenen Chat."""

    situation = st.session_state.get("ifs_situation", "")
    histories = st.session_state.get("ifs_histories", {})

    st.markdown(
        f"<div style='border-left: 4px solid #9B59B6; padding-left: 12px; margin-bottom: 16px;'>"
        f"<strong>🟣 Resonanzraum</strong><br/>"
        f"<small style='color: #888;'>Situation: "
        f"{situation[:100]}{'...' if len(situation) > 100 else ''}</small>"
        f"</div>",
        unsafe_allow_html=True,
    )

    with st.expander("💡 Tipps für alle Gespräche", expanded=False):
        for pk, cfg in PARTS.items():
            st.caption(f"**{cfg['short']}:** {cfg['hint']}")
        st.caption(
            "Deine Rolle als Self: Neugierig, ohne Wertung. "
            "Belehren schließt die Stimme. Echte Neugier öffnet sie."
        )

    # Drei Spalten nebeneinander
    cols = st.columns(3)
    for i, (part_key, part_cfg) in enumerate(PARTS.items()):
        with cols[i]:
            _render_part_column(part_key, part_cfg, situation, histories.get(part_key, []))

    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Neue Session beginnen", ):
            state.reset_ifs_session()
            st.rerun()
    with col2:
        if any(histories.get(pk, []) for pk in PARTS):
            _render_download_button(histories, situation)


def _render_part_column(part_key: str, part_cfg: dict, situation: str, history: list) -> None:
    """Rendert eine einzelne Part-Spalte im Triad-Layout."""

    st.markdown(
        f"<div style='border-left: 4px solid {part_cfg['color']}; "
        f"padding: 8px; border-radius: 4px; margin-bottom: 8px; background: rgba(74,144,217,0.05);'>"
        f"<strong>{part_cfg['label']}</strong>"
        f"</div>",
        unsafe_allow_html=True,
    )

    turn_count = len([m for m in history if m.get("role") == "user"])

    # Stufe-2-Disclaimer für Exile (einmalig pro Session)
    if part_cfg["exile"] and not st.session_state.get("ifs_exile_warned", False):
        st.info(
            "Diese Stimme kann tief gehen. Nimm dir Zeit. "
            "Telefonseelsorge: **0800 111 0 111**",
            icon="🟣",
        )
        st.session_state.ifs_exile_warned = True

    # Chat-Verlauf
    for msg in history:
        role = msg.get("role", "user")
        text = msg.get("text", "")
        if role == "reflection":
            st.markdown(
                f"<div style='background:#1a1a2e; border-left: 3px solid {part_cfg['color']}; "
                f"padding: 6px; margin: 4px 0; border-radius: 4px; font-size: 0.85em;'>"
                f"<small>🪞 {text}</small>"
                f"</div>",
                unsafe_allow_html=True,
                    )
        elif role == "user":
            with st.chat_message("user"):
                st.write(text)
        else:
            with st.chat_message("assistant"):
                st.write(text)

    # Start-Button wenn leer
    if not history:
        if st.button(
            "Mit dieser Stimme sprechen",
            key=f"start_{part_key}",
                type="primary",
        ):
            with st.spinner("Die Stimme meldet sich..."):
                _generate_opening(part_key, situation)
            st.rerun()
        return

    # Turn-Limit erreicht
    if turn_count >= MAX_TURNS:
        st.info(
            f"{MAX_TURNS} Fragen gestellt — Pause.",
            icon="⏸️",
        )
        if not any(m.get("role") == "reflection" for m in history):
            reflection = st.text_area(
                "Was hat dich überrascht? Was hat diese Stimme gebraucht, "
                "das sie dir heute zeigen durfte?",
                key=f"ifs_reflection_{part_key}",
                height=80,
            )
            if reflection and st.button(
                "Reflexion speichern",
                key=f"save_refl_{part_key}",
            ):
                state.append_ifs_message(part_key, "reflection", reflection)
                st.rerun()
        return

    # Chat-Input pro Spalte
    remaining = MAX_TURNS - turn_count
    user_input = st.chat_input(
        f"Frage ({remaining} verbleiben)...",
        key=f"ifs_chat_input_{part_key}",
    )
    if user_input:
        state.append_ifs_message(part_key, "user", user_input)
        if part_key == "ifs_fear":
            _generate_response_streaming(part_key, situation, user_input)
        else:
            _generate_response(part_key, situation, user_input)
        st.rerun()


# ==============================================================================
# LLM-INTEGRATION
# ==============================================================================

def _generate_opening(part: str, situation: str) -> None:
    """Generiert den Eröffnungssatz der inneren Stimme."""
    try:
        from modules.ifs_engine import IFSEngine
        engine = IFSEngine()
        response = engine.generate_opening(
            part_intent=part,
            situation=situation,
        )
        if response:
            state.append_ifs_message(part, "assistant", response)
    except Exception as e:
        logger.error(f"IFS Opening Error: {e}")
        state.append_ifs_message(
            part, "assistant",
            "*(Verbindungsfehler — bitte Seite neu laden)*"
        )


def _generate_response(part: str, situation: str, user_message: str) -> None:
    """Generiert die Antwort der inneren Stimme auf eine User-Frage."""
    try:
        from modules.ifs_engine import IFSEngine
        engine = IFSEngine()

        histories = st.session_state.get("ifs_histories", {})
        history = histories.get(part, [])
        history_for_llm = [
            {"role": msg["role"], "content": msg["text"]}
            for msg in history[:-1]
            if msg.get("text") and msg.get("role") in ("user", "assistant")
        ]

        with st.spinner(""):
            response = engine.generate_response(
                user_message=user_message,
                part_intent=part,
                situation=situation,
                conversation_history=history_for_llm,
            )

        if response:
            # Notfall-Interceptor (Stufe 3)
            if any(t in response.lower() for t in _NOTFALL_TRIGGER):
                st.session_state["ifs_emergency"] = True

            state.append_ifs_message(part, "assistant", response)
        else:
            state.append_ifs_message(
                part, "assistant",
                "*(Keine Antwort — bitte erneut versuchen)*"
            )
    except Exception as e:
        logger.error(f"IFS Response Error: {e}")
        state.append_ifs_message(
            part, "assistant",
            "*(Verbindungsfehler — bitte erneut versuchen)*"
        )


def _generate_response_streaming(part: str, situation: str, user_message: str) -> None:
    """Streaming-Variante fuer Fear-Part (laengerer Text, subjektiv schneller)."""
    try:
        from modules.ifs_engine import IFSEngine
        engine = IFSEngine()

        histories = st.session_state.get("ifs_histories", {})
        history = histories.get(part, [])
        history_for_llm = [
            {"role": msg["role"], "content": msg["text"]}
            for msg in history[:-1]
            if msg.get("text") and msg.get("role") in ("user", "assistant")
        ]

        with st.chat_message("assistant"):
            placeholder = st.empty()
            full_response = ""
            for chunk in engine.generate_response_streaming(
                user_message=user_message,
                part_intent=part,
                situation=situation,
                conversation_history=history_for_llm,
            ):
                if chunk:
                    full_response += chunk
                    placeholder.markdown(full_response)

        if full_response:
            # Notfall-Interceptor (Stufe 3)
            if any(t in full_response.lower() for t in _NOTFALL_TRIGGER):
                st.session_state["ifs_emergency"] = True
            state.append_ifs_message(part, "assistant", full_response)
        else:
            state.append_ifs_message(
                part, "assistant",
                "*(Keine Antwort — bitte erneut versuchen)*"
            )
    except Exception as e:
        logger.error(f"IFS Streaming Error: {e}")
        state.append_ifs_message(
            part, "assistant",
            "*(Verbindungsfehler — bitte erneut versuchen)*"
        )


# ==============================================================================
# DOWNLOAD
# ==============================================================================

def _render_download_button_single(
    history: list, current_part: str, situation: str
) -> None:
    """Bietet Download des Protokolls als Markdown an — Single-Modus."""

    part_cfg = PARTS.get(current_part, {})
    part_label = part_cfg.get("label", "Unbekannt")
    ts = datetime.now().strftime("%Y-%m-%d_%H%M")
    session_id = str(uuid.uuid4())[:8]

    md = "# Resonanzraum-Protokoll\n\n"
    md += f"**Stimme:** {part_label}\n"
    md += f"**Datum:** {ts}\n"
    md += f"**Session-ID:** {session_id}\n\n"
    md += f"**Situation:**\n> {situation}\n\n"
    md += "---\n\n"

    for msg in history:
        role = msg.get("role", "user")
        text = msg.get("text", "")
        if role == "reflection":
            md += f"**🪞 Reflexion:**\n{text}\n\n"
        elif role == "user":
            md += f"**Ich (Self):**\n{text}\n\n"
        else:
            md += f"**{part_cfg.get('short', 'Stimme')}:**\n{text}\n\n"

    st.download_button(
        label="📥 Protokoll herunterladen",
        data=md,
        file_name=f"resonanzraum_{ts}.md",
        mime="text/markdown",
        help="Wird nur lokal gespeichert — nie in der HRE-Datenbank.",
    )


def _render_download_button(
    histories: dict, situation: str
) -> None:
    """Bietet Download des Protokolls als Markdown an — alle drei Spalten."""

    ts = datetime.now().strftime("%Y-%m-%d_%H%M")
    session_id = str(uuid.uuid4())[:8]

    md = "# Resonanzraum-Protokoll (Triad)\n\n"
    md += f"**Datum:** {ts}\n"
    md += f"**Session-ID:** {session_id}\n\n"
    md += f"**Situation:**\n> {situation}\n\n"
    md += "---\n\n"

    for part_key, part_cfg in PARTS.items():
        history = histories.get(part_key, [])
        if not history:
            continue
        md += f"## {part_cfg['label']}\n\n"
        for msg in history:
            role = msg.get("role", "user")
            text = msg.get("text", "")
            if role == "reflection":
                md += f"**🪞 Reflexion:**\n{text}\n\n"
            elif role == "user":
                md += f"**Ich (Self):**\n{text}\n\n"
            else:
                md += f"**{part_cfg['short']}:**\n{text}\n\n"
        md += "\n---\n\n"

    st.download_button(
        label="📥 Protokoll herunterladen",
        data=md,
        file_name=f"resonanzraum_triad_{ts}.md",
        mime="text/markdown",
        help="Wird nur lokal gespeichert — nie in der HRE-Datenbank.",
    )
