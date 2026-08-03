# ui/ifs_tab.py — HRE Mission D: Der Resonanzraum + Anker-Modus (v60.3.1)
#
# v60.3.1 — BUGFIX: Anker-Intro-Phase als eigenständige Seite vor dem
# Modus-Start. Verhindert, dass die methodische Einordnung während des
# parallelen LLM-Calls + st.rerun() verschwindet (Bug aus v60.3).
# v60.3.1 — ERWEITERUNG: Begrenzte Konkretisierungsfreiheit im ANKER-Prompt
# (siehe hermeneutic_protocol_v603.yaml).
#
# KONZEPT (IFS Resonanzraum — bestehend):
# Der User beschreibt eine reale Situation (3-5 Sätze).
# Er wählt eine innere Stimme (Part).
# Das Modell spielt diese Stimme in der Ersten Person.
# Der User ist das "Self" — der neugierige Beobachter.
#
# KONZEPT (Anker-Modus — v60.3, ersetzt Trost-Modus v60.2):
# KEIN IFS-Part. KEINE simulierte Co-Regulation. KEINE Validierungsmaschine.
# Ein Werkzeug, das dem User seine selbst formulierten Ressourcen
# (anker_liste.md) zurückspiegelt. Das LLM produziert nichts Eigenes —
# es wählt aus der Liste aus und gibt es in kürzester Form zurück.
# Methodische Neuausrichtung nach Claude-Consult (10.07.2026):
# Trost ist keine Beschwichtigung. Ein LLM kann kein echtes Polyvagal-
# Attunement leisten. Eine simulierte Wärme wäre therapeutisch
# kontraindiziert. ANKER ist bewusst kühl — die Kühle ist die Form des
# Respekts.
#
# ARCHITEKTUR-REGEL:
# State-Schreibzugriffe für IFS via ui/state.py.
# State-Schreibzugriffe für Anker direkt via st.session_state (separater
# State-Namespace: anker_*, isoliert von ifs_*, abwärtskompatibel mit
# trost_*).
# Persönliche Inhalte werden NIE in die HRE-Datenbank gespeichert.
# Sys-Prompt wird bei JEDEM Turn neu gesetzt (Model-Drift-Schutz).
#
# v60.3 Änderungen gegenüber v60.2:
#   - Umbenennung: Trost-Modus → Anker-Modus (UI-Labels, State-Keys)
#   - TrostEngine → AnkerEngine (modules/ifs_engine.py)
#   - Intent CO_REGULATION → ANKER
#   - Anker-Liste (resonanzraum/anker_liste.md) wird als Kontext injiziert
#   - Visuelle Trennung: Orange/Warm → Grau/Kühl (bewusster Bruch)
#   - Setup-Phase-Beschreibung umgeschrieben: "keine simulierte Begegnung"
#   - Backward-Kompatibilität: trost_*-State-Keys werden als Alias behandelt
#
# v60.2 Änderungen gegenüber v59 (historisch):
#   - Setup-Phase: 3. Button "Trost-Modus" hinzugefügt (jetzt Anker-Modus)
#   - Emergency-Interceptor auf User-Input VOR LLM-Call
#   - Question-Stripper-Integration
#   - Separater Download-Button

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
MAX_ANKER_TURNS = 20  # Anker-Modus erlaubt mehr Turns (niedrigere kognitive Last)

_NOTFALL_TRIGGER = [
    "0800 111 0 111",
    "telefonseelsorge",
    "suizid",
    "selbstverletzung",
]


# =============================================================================
# ANKER-MODUS STATE-KEYS (v60.3 — ersetzt TROST-MODUS STATE-KEYS)
# =============================================================================
# Separater State-Namespace für Anker-Modus. Getrennt von ifs_* um
# Modus-Verwirrung zu vermeiden. Direkter session_state-Zugriff,
# weil Anker-Modus eigene Logik hat (keine Part-Wechsel, keine Triade).
#
# Backward-Kompatibilität: Alte trost_*-Keys werden als Alias behandelt,
# damit laufende Sessions nach dem Update nicht abstürzen. Neue Sessions
# verwenden ausschließlich anker_*-Keys.


def _is_anker_active() -> bool:
    """Prüft, ob Anker-Modus (oder historischer Trost-Modus) aktiv ist."""
    return (
        st.session_state.get("anker_started", False)
        or st.session_state.get("trost_started", False)  # BC
    )


def _reset_anker_session() -> None:
    """Setzt den Anker-State (und historischen Trost-State) zurück."""
    for key in [
        "anker_started", "anker_history", "anker_emergency", "anker_info_shown",
        "anker_info_pending",  # v60.3.1 — Intro-Phase State
        "trost_started", "trost_history", "trost_emergency", "trost_info_shown",  # BC
    ]:
        if key in st.session_state:
            del st.session_state[key]


def _append_anker_message(role: str, text: str) -> None:
    """Fügt eine Nachricht zur Anker-Historie hinzu.

    Schreibt sowohl in anker_history als auch (für BC) in trost_history,
    falls dieser Key existiert.
    """
    if "anker_history" not in st.session_state:
        st.session_state["anker_history"] = []
    st.session_state["anker_history"].append({"role": role, "text": text})
    # BC: Falls alte UI trost_history liest, parallel schreiben
    if "trost_history" in st.session_state:
        st.session_state["trost_history"].append({"role": role, "text": text})


def _get_anker_history() -> list:
    """Liefert die Anker-Historie (mit BC-Fallback auf trost_history)."""
    if "anker_history" in st.session_state:
        return st.session_state["anker_history"]
    return st.session_state.get("trost_history", [])


def _set_anker_emergency(value: bool) -> None:
    """Setzt den Emergency-Flag (mit BC-Fallback)."""
    st.session_state["anker_emergency"] = value
    st.session_state["trost_emergency"] = value  # BC


# =============================================================================
# HAUPT-EINTRITTSPUNKT
# =============================================================================

def render_ifs_tab() -> None:
    """Rendert den vollständigen IFS-Resonanzraum-Tab inkl. Anker-Modus."""

    st.title("🟣 Resonanzraum")

    # Stufe-1-Disclaimer (immer sichtbar)
    st.caption(
        "Ein Reflexionswerkzeug — kein Ersatz für therapeutische Begleitung. "
        "Bei ernsthafter Belastung: Telefonseelsorge **0800 111 0 111** "
        "(kostenlos, 24h, anonym)."
    )

    st.markdown("---")

    # Notfall-Interceptor: Chat eingefroren (IFS oder Anker)
    if st.session_state.get("ifs_emergency", False) or \
       st.session_state.get("anker_emergency", False) or \
       st.session_state.get("trost_emergency", False):  # BC
        _render_emergency_frozen()
        return

    # v60.3.1 — Anker-Intro-Phase (vor Modus-Start)
    # Zeigt die methodische Einordnung als eigene Seite. Erst wenn der
    # User "Los" klickt, wird `anker_started = True` gesetzt und der
    # eigentliche Modus (inkl. LLM-Call) startet. So bleibt die Info
    # stabil sichtbar — kein Rauschen durch parallelen LLM-Call.
    if st.session_state.get("anker_info_pending", False):
        _render_anker_intro()
        return

    # Anker-Modus aktiv?
    if _is_anker_active():
        _render_anker_mode()
        return

    # IFS-Modus aktiv?
    if st.session_state.get("ifs_started", False):
        _render_conversation_phase()
        return

    # Setup-Phase: Modus wählen
    _render_setup_phase()


def _render_emergency_frozen() -> None:
    """Rendert den eingefrorenen Zustand nach Krisen-Erkennung."""

    which = "IFS" if st.session_state.get("ifs_emergency") else "Anker"

    st.error(
        "🛑 **Pause.** Was du beschreibst, braucht echte menschliche Begleitung.\n\n"
        "**Telefonseelsorge: 0800 111 0 111** — kostenlos, rund um die Uhr, anonym.\n\n"
        "Das Gespräch hier ist jetzt beendet. Du kannst das Protokoll herunterladen "
        "und bei Bedarf eine neue Session beginnen."
    )

    # Protokoll-Download anbieten (je nach Modus)
    if which == "IFS":
        histories = st.session_state.get("ifs_histories", {})
        situation = st.session_state.get("ifs_situation", "")
        if any(histories.get(pk, []) for pk in PARTS):
            _render_download_button(histories, situation)
    else:
        anker_history = _get_anker_history()
        if anker_history:
            _render_anker_download_button(anker_history)

    if st.button("🔄 Neue Session beginnen"):
        state.reset_ifs_session()
        _reset_anker_session()
        st.rerun()


# ==============================================================================
# PHASE 1: SETUP
# ==============================================================================

def _render_setup_phase() -> None:
    """Phase 1: Situation beschreiben und Modus wählen."""

    st.subheader("Schritt 1: Was brauchst du heute?")

    # v60.3 — Erklärung der beiden Modi (Anker statt Trost)
    with st.expander("💡 Welchen Modus soll ich wählen?", expanded=True):
        st.markdown(
            "**🟣 IFS Resonanzraum** — Wenn du Energie hast, mit einer inneren "
            "Stimme zu sprechen. Du beschreibst eine Situation, wählst eine "
            "Stimme (Kontrolle, Kampf, Überforderung) und führst einen Dialog. "
            "Voraussetzung: Neugier, Reflexionsfähigkeit, Mentale Energie."
        )
        st.markdown(
            "**⚫ Anker-Modus** — Wenn du erschöpft, überfordert oder im "
            "Hamsterrad bist und nicht mehr reflektieren kannst. Du bekommst "
            "keine simulierte Wärme, kein Gespräch. Du bekommst einen Anker "
            "— etwas, das du selbst in deine Anker-Liste geschrieben hast "
            "und das dich in diesem Moment trägt.\n\n"
            "*Anker ist KEINE IFS-Arbeit und KEINE Co-Regulation. Ein LLM "
            "kann kein echtes Nervensystem-Attunement leisten — eine simulierte "
            "Wärme wäre Beschwichtigung als Trost verkauft. Anker ist bewusst "
            "kühl: ein Spiegel, kein Therapeut.*"
        )
        st.markdown(
            "**Pflege deine Anker-Liste:** `resonanzraum/anker_liste.md` — "
            "zwei Abschnitte: Ablenkung/Aktivierung (was tun verlangt) und "
            "Downregulation (was auch im Bett, nachts, geht)."
        )

    # v60.3 — Anker-Modus ist situationsunabhängig. IFS braucht Situation.
    # Daher: Modus-Wahl zuerst, dann ggf. Situation-Abfrage.

    mode_cols = st.columns(3)

    # === IFS Triad ===
    with mode_cols[0]:
        st.caption("**🟣 IFS Triad-Modus**")
        st.markdown(
            "Alle drei Stimmen gleichzeitig. "
            "Voraussetzung: Situation + Energie."
        )
        if st.button("Triad starten", type="primary", key="btn_triad"):
            # Für IFS brauchen wir eine Situation — also zur Situation-Abfrage
            st.session_state["_pending_ifs_mode"] = "triad"
            st.rerun()

    # === IFS Single ===
    with mode_cols[1]:
        st.caption("**🔵 IFS Einzel-Modus**")
        st.markdown(
            "Eine Stimme nach der anderen. "
            "Voraussetzung: Situation + Energie."
        )
        if st.button("Einzel starten", type="secondary", key="btn_single"):
            st.session_state["_pending_ifs_mode"] = "single"
            st.rerun()

    # === Anker-Modus (v60.3 — ersetzt Trost-Modus) ===
    with mode_cols[2]:
        st.caption("**⚫ Anker-Modus**")
        st.markdown(
            "Ressourcen-Spiegel. "
            "Braucht keine Situation, keine Energie."
        )
        if st.button("Anker-Modus öffnen", type="secondary", key="btn_anker"):
            # v60.3.1 — ZWEISTUFIGER START: Erst Intro-Phase (Info lesen),
            # dann Modus-Start (LLM-Call). Verhindert, dass die Info während
            # des LLM-Calls + Rerun verschwindet.
            st.session_state["anker_info_pending"] = True
            st.session_state["anker_started"] = False
            st.session_state["anker_history"] = []
            st.session_state["anker_emergency"] = False
            st.session_state["anker_info_shown"] = False
            # IFS-State zurücksetzen (falls vorhanden)
            if st.session_state.get("ifs_started"):
                state.reset_ifs_session()
            st.rerun()

    # === Situation-Abfrage (nur bei IFS) ===
    if st.session_state.get("_pending_ifs_mode"):
        st.markdown("---")
        st.subheader("Schritt 2: Beschreibe deine Situation")
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
            st.info("👆 Beschreibe zuerst deine Situation — dann startet das Gespräch.")
            return

        mode = st.session_state["_pending_ifs_mode"]
        if mode == "triad":
            if st.button("Triad jetzt starten", type="primary", key="confirm_triad"):
                state.start_ifs_session(situation=situation.strip(), mode="triad")
                if "_pending_ifs_mode" in st.session_state:
                    del st.session_state["_pending_ifs_mode"]
                st.rerun()
        elif mode == "single":
            if st.button("Einzel jetzt starten", type="primary", key="confirm_single"):
                state.start_ifs_session(
                    situation=situation.strip(), mode="single", part="ifs_control"
                )
                if "_pending_ifs_mode" in st.session_state:
                    del st.session_state["_pending_ifs_mode"]
                st.rerun()


# ==============================================================================
# PHASE 2: IFS GESPRÄCH (bestehend, unverändert)
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
    # UNVERÄNDERT GEGENÜBER v59 — siehe bestehende ifs_tab.py
    # ... (Volle Implementation aus v59 ifs_tab.py übernehmen)

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

    if not history:
        with st.spinner("Die Stimme meldet sich..."):
            _generate_opening(current_part, situation)
        st.rerun()

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
                cfg["short"], disabled=True, key=f"ifs_switch_{part_key}_{i}",
            )
        else:
            if switch_cols[i].button(
                cfg["short"], key=f"ifs_switch_{part_key}_{i}",
            ):
                state.switch_ifs_part(
                    part_key, old_label=old_label, new_label=cfg["short"],
                )
                st.rerun()

    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Neue Session beginnen"):
            state.reset_ifs_session()
            st.rerun()
    with col2:
        if history:
            _render_download_button_single(history, current_part, situation)


def _render_triad_mode() -> None:
    """Phase 2 (Triad): Drei Spalten — jede Part hat eigenen Chat."""
    # UNVERÄNDERT GEGENÜBER v59 — siehe bestehende ifs_tab.py
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

    cols = st.columns(3)
    for i, (part_key, part_cfg) in enumerate(PARTS.items()):
        with cols[i]:
            _render_part_column(part_key, part_cfg, situation, histories.get(part_key, []))

    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Neue Session beginnen"):
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

    if part_cfg["exile"] and not st.session_state.get("ifs_exile_warned", False):
        st.info(
            "Diese Stimme kann tief gehen. Nimm dir Zeit. "
            "Telefonseelsorge: **0800 111 0 111**",
            icon="🟣",
        )
        st.session_state.ifs_exile_warned = True

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

    if not history:
        if st.button(
            "Mit dieser Stimme sprechen",
            key=f"start_{part_key}", type="primary",
        ):
            with st.spinner("Die Stimme meldet sich..."):
                _generate_opening(part_key, situation)
            st.rerun()
        return

    if turn_count >= MAX_TURNS:
        st.info(f"{MAX_TURNS} Fragen gestellt — Pause.", icon="⏸️")
        if not any(m.get("role") == "reflection" for m in history):
            reflection = st.text_area(
                "Was hat dich überrascht?",
                key=f"ifs_reflection_{part_key}",
                height=80,
            )
            if reflection and st.button(
                "Reflexion speichern", key=f"save_refl_{part_key}",
            ):
                state.append_ifs_message(part_key, "reflection", reflection)
                st.rerun()
        return

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
# v60.3 — PHASE 2: ANKER-MODUS (ersetzt TROST-MODUS)
# ==============================================================================

def _render_anker_intro() -> None:
    """v60.3.1 — Intro-Phase: Methodische Einordnung als eigene Seite.

    Wird angezeigt, wenn `anker_info_pending = True` (nach Klick auf
    "Anker-Modus öffnen", vor `anker_started = True`).

    Diese Phase existiert, weil Streamlit bei `st.rerun()` den gesamten
    UI-Baum neu aufbaut. Wenn der LLM-Call für die Eröffnungsnachricht
    parallel zum Info-Expander läuft, verschwindet die Info beim Rerun
    (nach ~2 Sekunden). Die Intro-Phase trennt Lesen und Modus-Start
    sauber: Erst liest der User die Einordnung (stabile Seite, kein
    paralleler LLM-Call), dann klickt er "Los" — erst dann startet der
    Modus inkl. LLM-Call.
    """

    st.markdown(
        "<div style='border-left: 4px solid #555; padding-left: 12px; "
        "margin-bottom: 16px; background: rgba(85, 85, 85, 0.05);'>"
        "<strong>⚫ Anker-Modus</strong><br/>"
        "<small style='color: #888;'>Ressourcen-Spiegel — keine simulierte "
        "Begegnung, keine Fragen, keine Validierung.</small>"
        "</div>",
        unsafe_allow_html=True,
    )

    st.subheader("Bevor du startest: Was ist der Anker-Modus (und was nicht)?")

    st.markdown(
        "Du bist gerade erschöpft, überfordert oder im Hamsterrad. "
        "Reflexion geht nicht mehr. IFS geht nicht mehr. Du brauchst "
        "etwas, das dich hält, ohne dich zu fordern.\n\n"
        "**Was dieser Modus ist:** Ein Spiegel. Das System wählt aus "
        "deiner eigenen Anker-Liste (`resonanzraum/anker_liste.md`) "
        "einen Eintrag aus und gibt ihn zurück — oder es greift etwas "
        "auf, das du selbst im Gespräch erwähnt hast. Es erfindet "
        "nichts. Es rät nicht. Es validiert nicht.\n\n"
        "**Was dieser Modus NICHT ist:** Keine IFS-Arbeit. Keine "
        "Co-Regulation. Kein Therapeut. Keine simulierte warme "
        "Präsenz. Ein LLM kann kein echtes Nervensystem-Attunement "
        "leisten — eine simulierte Wärme wäre Beschwichtigung als "
        "Trost verkauft. Die Kühle hier ist beabsichtigt, kein Mangel.\n\n"
        "**Reihenfolge:** 1. Anker jetzt → 2. IFS später, wenn dein "
        "Akku wieder voll ist.\n\n"
        "**Pflege deine Anker-Liste selbst:** Wenn du einen neuen "
        "Anker findest (etwas, das dir in einem schweren Moment "
        "geholfen hat), trage ihn in `resonanzraum/anker_liste.md` "
        "ein. Das System wird ihn dann künftig zur Verfügung haben.\n\n"
        "*Der Anker-Modus beendet Antworten nie mit einer Frage. "
        "Wenn du doch eine Frage gestellt bekommst, ist das ein Bug — "
        "bitte melden.*"
    )

    st.markdown("---")

    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button(
            "Los — Anker-Modus starten",
            type="primary",
            key="btn_anker_intro_los",
        ):
            # Modus wirklich starten — LLM-Call wird im nächsten Render
            # in `_render_anker_mode` ausgelöst.
            st.session_state["anker_info_pending"] = False
            st.session_state["anker_started"] = True
            st.session_state["anker_info_shown"] = True  # BC-Flag
            st.rerun()
    with col2:
        if st.button(
            "Zurück",
            key="btn_anker_intro_back",
        ):
            st.session_state["anker_info_pending"] = False
            st.rerun()


def _render_anker_mode() -> None:
    """Rendert den Anker-Modus (Ressourcen-Spiegel).

    Visuell und funktional klar vom IFS getrennt:
    - Eigene Farbe (Grau/Kühl statt Lila/IFS oder Orange/Trost-v60.2)
    - Kein Part-Selector
    - Keine Situation-Anzeige
    - Einfacher Single-Chat
    - Höheres Turn-Limit (niedrigere kognitive Last)

    v60.3-Unterschied zu v60.2-Trost-Modus:
    - Visuell kühl statt warm (bewusster Bruch mit Beschwichtigungs-Ästhetik)
    - Methodische Einordnung erklärt die Kühle als beabsichtigt
    - Verweis auf anker_liste.md zum Selber-Pflegen
    """

    # Kühle, klare optische Trennung — bewusst nicht-warm
    st.markdown(
        "<div style='border-left: 4px solid #555; padding-left: 12px; "
        "margin-bottom: 16px; background: rgba(85, 85, 85, 0.05);'>"
        "<strong>⚫ Anker-Modus</strong><br/>"
        "<small style='color: #888;'>Ressourcen-Spiegel — keine simulierte "
        "Begegnung, keine Fragen, keine Validierung.</small>"
        "</div>",
        unsafe_allow_html=True,
    )

    # v60.3.1 — Methodische Einordnung lebt jetzt in `_render_anker_intro`
    # (eigene Phase vor Modus-Start). Hier im Modus selbst wird sie nicht
    # mehr gerendert — das war die Quelle des "Verschwindet nach 2 Sekunden"-
    # Bugs (paralleler LLM-Call + st.rerun() hat den Expander weggerissen).
    # Wer die Info nochmal lesen will, kann "Session beenden" klicken und
    # den Modus neu öffnen — dann kommt die Intro-Phase wieder.

    history = _get_anker_history()

    # KI beginnt automatisch mit einem schlichten Satz
    if not history:
        with st.spinner("Bereit..."):
            _generate_anker_opening()
        st.rerun()

    # Chat-Verlauf
    for msg in history:
        role = msg.get("role", "user")
        text = msg.get("text", "")
        if role == "user":
            with st.chat_message("user"):
                st.write(text)
        else:
            with st.chat_message("assistant"):
                st.write(text)

    # Turn-Limit weicher als bei IFS — Anker darf länger dauern
    turn_count = len([m for m in history if m.get("role") == "user"])

    if turn_count >= MAX_ANKER_TURNS:
        st.info(
            f"Du bist {MAX_ANKER_TURNS} Nachrichten hier gewesen — das ist "
            "ein guter Moment, das Protokoll herunterzuladen und vielleicht "
            "eine Pause zu machen. Du kannst jederzeit wiederkommen."
        )
    else:
        user_input = st.chat_input(
            "Schreib, was da ist...",
            key="anker_chat_input",
        )
        if user_input:
            _append_anker_message("user", user_input)
            _generate_anker_response(user_input)
            st.rerun()

    # Footer
    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Session beenden"):
            _reset_anker_session()
            st.rerun()
    with col2:
        if history:
            _render_anker_download_button(history)


# ==============================================================================
# v60.3 — Backward-Kompatibilität: _render_trost_mode als Alias
# ==============================================================================
# Falls anderer Code noch _render_trost_mode aufruft, leitet es auf
# _render_anker_mode weiter. Wird in v61 entfernt.
_render_trost_mode = _render_anker_mode


# ==============================================================================
# LLM-INTEGRATION — IFS (bestehend, erweitert um Emergency-User-Check v60.2)
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
            # Notfall-Interceptor (Stufe 3, bestehend)
            if any(t in response.lower() for t in _NOTFALL_TRIGGER):
                st.session_state["ifs_emergency"] = True
            state.append_ifs_message(part, "assistant", response)
    except Exception as e:
        logger.error(f"IFS Opening Error: {e}")
        state.append_ifs_message(
            part, "assistant",
            "*(Verbindungsfehler — bitte Seite neu laden)*"
        )


def _generate_response(part: str, situation: str, user_message: str) -> None:
    """Generiert die Antwort der inneren Stimme auf eine User-Frage.

    v60.2: Mit Emergency-Check auf User-Input (zusätzlich zum bestehenden
    Model-Output-Check). Der IFSEngine selbst macht bereits beide Checks
    intern — aber zur Kompatibilität mit bestehendem Code behalten wir
    die äußere Prüfung bei.
    """
    try:
        from modules.ifs_engine import IFSEngine
        engine = IFSEngine()

        # v60.2/v613 — Emergency-Check auf User-Input ( redundanter Safety-Net
        # zum Engine-internen Check, da bestehender Code diese Funktion
        # direkt aufrufen kann).
        # v613: mode-abhängige Sensitivität (part.upper() = "IFS_FIGHT" / "IFS_CONTROL" / "IFS_FEAR").
        try:
            from modules.emergency_interceptor import check_user_input
            crisis_check = check_user_input(user_message, mode=part.upper())
            if crisis_check.is_crisis:
                from modules.emergency_interceptor import get_emergency_response
                st.session_state["ifs_emergency"] = True
                state.append_ifs_message(part, "assistant", get_emergency_response())
                return
        except ImportError:
            logger.warning("emergency_interceptor nicht verfügbar — nur YAML-Schutz aktiv.")

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
            # Notfall-Interceptor (Stufe 3, bestehend)
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

        # v60.2/v613 — Emergency-Check auf User-Input
        # v613: mode-abhängige Sensitivität (part.upper() = "IFS_FIGHT" / "IFS_CONTROL" / "IFS_FEAR").
        try:
            from modules.emergency_interceptor import check_user_input
            crisis_check = check_user_input(user_message, mode=part.upper())
            if crisis_check.is_crisis:
                from modules.emergency_interceptor import get_emergency_response
                st.session_state["ifs_emergency"] = True
                state.append_ifs_message(part, "assistant", get_emergency_response())
                return
        except ImportError:
            pass

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
# v60.3 — LLM-INTEGRATION: ANKER-MODUS (ersetzt TROST-MODUS)
# ==============================================================================

def _generate_anker_opening() -> None:
    """Generiert den Eröffnungssatz im Anker-Modus."""
    try:
        from modules.ifs_engine import AnkerEngine
        engine = AnkerEngine()
        response = engine.generate_opening()

        if response:
            # Notfall-Check (sicherheitshalber — eigentlich macht das
            # AnkerEngine.generate_response bereits intern)
            if any(t in response.lower() for t in _NOTFALL_TRIGGER):
                _set_anker_emergency(True)
            _append_anker_message("assistant", response)
    except Exception as e:
        logger.error(f"Anker Opening Error: {e}")
        _append_anker_message(
            "assistant",
            "*(Verbindungsfehler — bitte Seite neu laden)*"
        )


def _generate_anker_response(user_message: str) -> None:
    """Generiert eine Anker-Antwort auf eine User-Nachricht.

    Nutzt AnkerEngine (modules/ifs_engine.py), die intern:
    - Emergency-Check auf User-Input macht
    - LLM-Call mit ANKER-Prompt + Anker-Liste als Kontext macht
    - Emergency-Check auf Model-Output macht
    - Question-Stripper anwendet
    """
    try:
        from modules.ifs_engine import AnkerEngine
        engine = AnkerEngine()

        history = _get_anker_history()
        history_for_llm = [
            {"role": msg["role"], "content": msg["text"]}
            for msg in history[:-1]
            if msg.get("text") and msg.get("role") in ("user", "assistant")
        ]

        with st.spinner(""):
            response = engine.generate_response(
                user_message=user_message,
                conversation_history=history_for_llm,
            )

        if response:
            # Notfall-Interceptor (zur Sicherheit — AnkerEngine sollte
            # bereits alles abgefangen haben)
            if any(t in response.lower() for t in _NOTFALL_TRIGGER):
                _set_anker_emergency(True)
            _append_anker_message("assistant", response)
        else:
            _append_anker_message(
                "assistant",
                "*(Keine Antwort — bitte erneut versuchen)*"
            )
    except Exception as e:
        logger.error(f"Anker Response Error: {e}")
        _append_anker_message(
            "assistant",
            "*(Verbindungsfehler — bitte erneut versuchen)*"
        )


# Backward-Kompatibilität: Alte Funktionsnamen als Alias
_generate_trost_opening = _generate_anker_opening
_generate_trost_response = _generate_anker_response


# ==============================================================================
# DOWNLOAD — IFS (bestehend, unverändert)
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


def _render_download_button(histories: dict, situation: str) -> None:
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


# ==============================================================================
# v60.3 — DOWNLOAD: ANKER-MODUS (ersetzt TROST-MODUS-DOWNLOAD)
# ==============================================================================

def _render_anker_download_button(history: list) -> None:
    """Bietet Download des Anker-Protokolls als Markdown an.

    Eigenes Format, klar getrennt vom IFS-Protokoll. Enthält keine
    Part-Bezeichnungen, keine Situation, nur den Dialog.

    v60.3: Header benennt die Methode korrekt als Ressourcen-Spiegel,
    nicht als Co-Regulation. Verweis auf anker_liste.md im Protokoll.
    """

    ts = datetime.now().strftime("%Y-%m-%d_%H%M")
    session_id = str(uuid.uuid4())[:8]

    md = "# Anker-Modus Protokoll\n\n"
    md += f"**Datum:** {ts}\n"
    md += f"**Session-ID:** {session_id}\n"
    md += f"**Methode:** Ressourcen-Spiegel (keine IFS-Arbeit, keine Co-Regulation)\n"
    md += f"**Quelle der Anker:** `resonanzraum/anker_liste.md`\n"
    md += f"**Haltung:** Bleiben und wirklich hinhören — "
    md += "bewusst ohne Technik oder Analyse.\n\n"
    md += "---\n\n"

    for msg in history:
        role = msg.get("role", "user")
        text = msg.get("text", "")
        if role == "user":
            md += f"**Ich:**\n{text}\n\n"
        else:
            md += f"**Anker:**\n{text}\n\n"

    md += "\n---\n\n"
    md += (
        "*Dieses Protokoll ist keine therapeutische Dokumentation. "
        "Bei anhaltender Belastung: Telefonseelsorge 0800 111 0 111.*\n"
    )

    st.download_button(
        label="📥 Anker-Protokoll herunterladen",
        data=md,
        file_name=f"anker_modus_{ts}.md",
        mime="text/markdown",
        help="Wird nur lokal gespeichert — nie in der HRE-Datenbank.",
    )


# Backward-Kompatibilität: Alte Funktion als Alias
_render_trost_download_button = _render_anker_download_button
