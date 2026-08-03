"""ui/meta_hermeneutic_tab.py — Meta-Hermeneutic Tab (v3.2)

Rekursive Hermeneutik: Die Pipeline analysiert ihre eigenen Outputs.
Drei-Stufen-Architektur:
  Stufe 1: META-SEZIEREN (#37)  — Python extrahiert Strukturdaten
  Stufe 2: META-BEOBACHTEN (#38 + #39) — LLM vergleicht, kodiert Stabilität
  Stufe 3: META-DESTILLATION (#41) — LLM synthetisiert den harten Befund

Architektur-Entscheidungen #36-41, validiert durch manuelle
Stabilitäts-Analyse von 17 Synthese-Runs (2026-06-13).

v3.0 — MODUS-WÄHLER:
  META-ANALYSE: Der bekannte Weg — SEZIEREN → BEOBACHTEN → DESTILLATION
  FREIE FRAGE:  User stellt eine Frage → Meta-Ebene antwortet gezielt
                auf Basis der gleichen Daten (SEZIEREN + Etappe-1)

  Der User entscheidet VOR dem Lauf, welcher Modus verwendet wird.
  Beide Modi nutzen dieselben hochgeladenen Dateien.

v2.0-Verbesserungen:
- ZIP-Upload-Unterstützung (für Batch-Dateien)
- Stufen-Fortschritt mit Timing
- Erweiterte SEZIEREN-Anzeige inkl. BEWEISFÜHRUNG + FREIER RAUM
- Kontrast-Einfärbung für Stabilitäts-Scores
"""

import logging
import zipfile
from datetime import datetime
from pathlib import Path

import streamlit as st

from modules.meta_hermeneutic_engine import (
    run_meta_hermeneutic,
    meta_freie_frage,
    meta_konfrontation,
    format_meta_result_as_markdown,
)

logger = logging.getLogger(__name__)

# Temporäres Verzeichnis für entpackte/zwischengespeicherte Dateien
_TEMP_DIR = Path("hre_data") / "meta_hermeneutic_temp"


def _extract_zip_to_temp(uploaded_zip) -> list:
    """
    Entpackt ein hochgeladenes ZIP-Archiv ins temporäre Verzeichnis
    und gibt die Liste der .md-Dateien zurück.
    """
    _TEMP_DIR.mkdir(parents=True, exist_ok=True)
    file_paths = []

    with zipfile.ZipFile(uploaded_zip, 'r') as z:
        for name in z.namelist():
            if name.endswith('.md') and not name.startswith('__MACOSX'):
                # Nur .md-Dateien, keine macOS-Metadaten
                data = z.read(name)
                # Flatten: Nur den Dateinamen, nicht den Pfad
                basename = Path(name).name
                temp_path = _TEMP_DIR / basename
                temp_path.write_bytes(data)
                file_paths.append(temp_path)

    return file_paths


def _save_uploaded_files(uploaded_files) -> list:
    """
    Speichert hochgeladene Dateien ins temporäre Verzeichnis
    und gibt die Liste der Pfade zurück.
    """
    _TEMP_DIR.mkdir(parents=True, exist_ok=True)
    file_paths = []

    for f in uploaded_files:
        temp_path = _TEMP_DIR / f.name
        temp_path.write_bytes(f.getvalue())
        file_paths.append(temp_path)

    return file_paths


def _cleanup_temp(file_paths: list):
    """Räumt temporäre Dateien auf."""
    for p in file_paths:
        try:
            p.unlink(missing_ok=True)
        except Exception:
            pass


def render_meta_hermeneutic_tab():
    """Render den Meta-Hermeneutic Tab."""

    st.header("Meta-Hermeneutic")
    st.caption(
        "Rekursive Hermeneutik: Die Pipeline analysiert ihre eigenen Outputs. "
        "Stabiler Kern, Instabilitäts-Diagnose, Bestätigungs-Bias-Check. "
        "Architektur-Entscheidungen #36-41."
    )

    # ======================================================================
    # MODUS-WÄHLER — META-ANALYSE vs FREIE FRAGE
    # ======================================================================
    st.subheader("Modus")

    modus = st.radio(
        "Analyse-Modus wählen:",
        ["META-ANALYSE", "FREIE FRAGE", "META-META-ANALYSE"],
        horizontal=True,
        key="mh_modus",
        help=(
            "META-ANALYSE: Die bewährte Dreistufen-Pipeline "
            "(SEZIEREN → BEOBACHTEN → DESTILLATION). "
            "FREIE FRAGE: Du stellst eine Frage — die Meta-Ebene antwortet "
            "gezielt auf Basis derselben Daten. "
            "META-META-ANALYSE: Meta-Hermeneutic-Outputs als Eingabe — "
            "die Meta-Ebene analysiert sich selbst."
        ),
    )

    # Modus-Beschreibung
    if modus == "META-ANALYSE":
        st.info(
            "**META-ANALYSE** — Die vollständige Dreistufen-Pipeline:\n\n"
            "1. **SEZIEREN**: Python extrahiert Strukturdaten\n"
            "2. **BEOBACHTEN**: LLM vergleicht, kodiert, bewertet Stabilität\n"
            "3. **DESTILLATION**: LLM synthetisiert den harten Befund (9 Sätze)\n\n"
            "Empfohlen für: Erstanalyse, Überblick, methodische Diagnose."
        )
    elif modus == "META-META-ANALYSE":
        st.info(
            "**META-META-ANALYSE** — Die Meta-Ebene analysiert sich selbst:\n\n"
            "1. **SEZIEREN**: Erkennt Meta-Hermeneutic-Outputs automatisch\n"
            "   (META-DESTILLATION → KERNHYPOTHESE, META-BEOBACHTEN → BEWEISFÜHRUNG)\n"
            "2. **BEOBACHTEN**: Vergleicht Meta-Tests, berücksichtigt Varianten (A/B/C)\n"
            "3. **DESTILLATION**: Synthetisiert den Meta-Meta-Befund\n\n"
            "Lade Meta-Hermeneutic-Outputs (.md) hoch. "
            "Variante wird automatisch aus Header-Version erkannt.\n\n"
            "Nach der VOLLANALYSE: FREIE FRAGE mit Kritik-Text als KONFRONTATION."
        )
    else:
        st.info(
            "**FREIE FRAGE** — Gezielte Antwort auf deine Frage:\n\n"
            "1. **SEZIEREN**: Python extrahiert Strukturdaten (immer)\n"
            "2. **FREIE FRAGE**: LLM beantwortet deine Frage auf Basis von "
            "SEZIEREN + Etappe-1-Daten\n\n"
            "Schneller als META-ANALYSE (überspringt BEOBACHTEN + DESTILLATION). "
            "Empfohlen für: Gezielte Nachfragen, Hypothesen-Prüfung, "
            "einzelne Aspekte vertiefen."
        )

    # --- FREIE FRAGE: Frage-Input ---
    freie_frage_text = None
    if modus == "FREIE FRAGE":
        freie_frage_text = st.text_area(
            "Deine Frage an die Meta-Ebene:",
            placeholder=(
                "z.B. Wird бронзово-острое in späteren Runs häufiger? "
                "Oder: Gibt es einen Wendepunkt bei Veresaevs Terminologie?"
            ),
            height=100,
            key="mh_freie_frage_input",
            help=(
                "Stelle eine konkrete Frage. Die Meta-Ebene antwortet "
                "auf Basis der SEZIEREN-Daten und Etappe-1-Statistiken. "
                "Belege mit konkreten Runs (R1, R2, ...)."
            ),
        )
        if freie_frage_text and freie_frage_text.strip():
            st.caption(
                f"Frage: „{freie_frage_text.strip()[:80]}{'...' if len(freie_frage_text.strip()) > 80 else ''}\""
            )

    # ======================================================================
    # EINGABE: Synthese-Dateien
    # ======================================================================
    st.subheader("Synthese-Dateien")

    input_mode = st.radio(
        "Eingabe-Modus:",
        ["Einzelne .md-Dateien", "ZIP-Archiv"],
        horizontal=True,
        key="mh_input_mode",
    )

    file_paths = []
    n_uploaded = 0

    if input_mode == "Einzelne .md-Dateien":
        uploaded_files = st.file_uploader(
            "Synthese-Dateien (.md)",
            type=["md"],
            accept_multiple_files=True,
            key="mh_files",
        )

        if uploaded_files:
            n_uploaded = len(uploaded_files)
            file_paths = _save_uploaded_files(uploaded_files)

    else:  # ZIP-Archiv
        uploaded_zip = st.file_uploader(
            "ZIP-Archiv mit Synthese-Dateien",
            type=["zip"],
            key="mh_zip",
        )

        if uploaded_zip:
            file_paths = _extract_zip_to_temp(uploaded_zip)
            n_uploaded = len(file_paths)

    # --- Optionen ---
    col1, col2, col3 = st.columns(3)
    with col1:
        skip_termini = st.checkbox(
            "Termini-Extraktion überspringen",
            value=False,
            help="Überspringt die LLM-basierte Termini-Extraktion (schneller, weniger Detail)",
        )
    with col2:
        show_raw = st.checkbox(
            "Rohdaten anzeigen",
            value=False,
            help="Zeigt die extrahierten Kernhypothesen und Fazits pro Run",
        )
    with col3:
        show_freier_raum = st.checkbox(
            "FREIER RAUM anzeigen",
            value=False,
            help="Zeigt die FREIER RAUM-Abschnitte pro Run",
        )

    # --- Datei-Übersicht ---
    if n_uploaded > 0:
        st.info(f"{n_uploaded} Datei(en) geladen")

        with st.expander("Datei-Übersicht", expanded=False):
            for p in sorted(file_paths):
                size_kb = p.stat().st_size / 1024 if p.exists() else 0
                st.markdown(f"- **{p.name}** ({size_kb:.1f} KB)")

        # Warnung bei wenigen Runs
        if n_uploaded < 3:
            st.warning(
                f"{n_uploaded} Datei(en). Mindestens 3 empfohlen für "
                f"aussagekräftige Stabilitäts-Analyse."
            )
        if n_uploaded < 2:
            st.error("Mindestens 2 Dateien für Vergleich nötig.")
    else:
        st.markdown(
            "Lade .md-Dateien hoch, die Globale-Synthese-Abschnitte enthalten, "
            "oder ein ZIP-Archiv mit mehreren Synthesen. "
            "Mindestens 3 Runs empfohlen für aussagekräftige Stabilitäts-Analyse."
        )

    # ======================================================================
    # START-BUTTON
    # ======================================================================
    can_start = n_uploaded >= 2

    # FREIE FRAGE braucht auch eine Frage
    if modus == "FREIE FRAGE" and not (freie_frage_text and freie_frage_text.strip()):
        can_start = False

    button_label = (
        "Meta-Hermeneutic Analyse starten"
        if modus == "META-ANALYSE"
        else "META-META-ANALYSE starten"
        if modus == "META-META-ANALYSE"
        else "FREIE FRAGE starten"
    )

    if st.button(
        button_label,
        type="primary",
        disabled=not can_start,
    ):
        spinner_msg = (
            "META-HERMENEUTIC läuft..."
            if modus == "META-ANALYSE"
            else "META-META-ANALYSE läuft..."
            if modus == "META-META-ANALYSE"
            else "FREIE FRAGE läuft..."
        )
        with st.spinner(spinner_msg):
            progress_placeholder = st.empty()

            def update_progress(msg):
                progress_placeholder.info(f"... {msg}")

            try:
                result = run_meta_hermeneutic(
                    synthesis_files=file_paths,
                    progress_callback=update_progress,
                    skip_termini=skip_termini,
                    freie_frage=freie_frage_text if modus == "FREIE FRAGE" else None,
                )

                st.session_state["mh_result"] = result
                st.session_state["mh_timestamp"] = datetime.now().isoformat()
                # mh_modus wird bereits durch st.radio(key="mh_modus") gesetzt
                # und darf nach Widget-Instanziierung nicht mehr manuell zugewiesen werden

                progress_placeholder.empty()

                if modus == "FREIE FRAGE":
                    st.success("FREIE FRAGE abgeschlossen!")
                else:
                    st.success("META-HERMENEUTIC abgeschlossen!")

            except Exception as e:
                logger.error(f"META-HERMENEUTIC Fehler: {e}")
                st.error(f"Fehler: {e}")

        # Aufräumen
        _cleanup_temp(file_paths)

    # ======================================================================
    # ERGEBNIS-ANZEIGE
    # ======================================================================
    result = st.session_state.get("mh_result")
    if not result:
        return

    # Modus aus Ergebnis oder Session-State
    active_modus = st.session_state.get("mh_modus", "META-ANALYSE")
    is_freie_frage = result.get("metadata", {}).get("mode") == "meta_freie_frage"

    st.markdown("---")

    # Metadaten
    meta = result.get("metadata", {})
    n_runs = meta.get("valid_runs", 0)
    stages = meta.get("stage_durations", {})

    # --- META-SEZIEREN (immer) ---
    with st.expander("Stufe 1: META-SEZIEREN — Übersicht", expanded=True):
        sezieren_data = result.get("meta_sezieren", [])

        if sezieren_data:
            import pandas as pd

            # Übersichtstabelle
            rows = []
            for run in sezieren_data:
                row = {
                    "Run": run["nr"],
                    "Datei": run["datei"],
                    "Kern (Zchn)": run["laenge_kern"],
                    "Fazit (Zchn)": run["laenge_fazit"],
                    "Bew": len(run.get("beweisfuehrung", "")),
                    "FR": len(run.get("freier_raum", "")),
                }
                # v2.8: Variante-Spalte für Meta-Dateien
                variante = run.get("variante")
                if variante:
                    row["Var"] = variante
                # v2.8: Meta-Hermeneutic-Zusatzfelder
                if run.get("source_type") == "meta_hermeneutic":
                    row["Meta-Runs"] = run.get("meta_runs", "")
                    row["Meta-Ver"] = run.get("meta_version", "")
                # Termini hinzufügen falls vorhanden
                for autor, terminus in run.get("termini", {}).items():
                    row[f"T: {autor}"] = terminus or "---"
                rows.append(row)

            df = pd.DataFrame(rows)
            st.dataframe(df, width='stretch', hide_index=True)

            # Stufen-Dauer
            if stages.get("sezieren"):
                st.caption(f"SEZIEREN: {stages['sezieren']}s")
            if stages.get("termini"):
                st.caption(f"TERMINI-Extraktion: {stages['termini']}s")

        else:
            st.info("Keine SEZIEREN-Daten verfügbar.")

    # --- Rohdaten: Kernhypothesen + Fazits (optional) ---
    if show_raw and sezieren_data:
        with st.expander("Rohdaten: Kernhypothesen + Fazits", expanded=False):
            for run in sezieren_data:
                st.markdown(f"### Run {run['nr']}: {run['datei']}")
                st.markdown("**KERNHYPOTHESE:**")
                st.markdown(run["kernhypothese"] or "(leer)")
                st.markdown("**FAZIT:**")
                st.markdown(run["fazit"] or "(leer)")
                st.divider()

    # --- FREIER RAUM (optional) ---
    if show_freier_raum and sezieren_data:
        with st.expander("Rohdaten: FREIER RAUM", expanded=False):
            for run in sezieren_data:
                fr = run.get("freier_raum", "")
                if fr:
                    st.markdown(f"### Run {run['nr']}: {run['datei']}")
                    st.markdown(fr)
                    st.divider()
                else:
                    st.markdown(f"### Run {run['nr']}: (kein FREIER RAUM)")

    # ==================================================================
    # MODUS-SPEZIFISCHE ERGEBNISSE
    # ==================================================================
    if is_freie_frage:
        # ── FREIE FRAGE Ergebnis ──
        st.subheader("FREIE FRAGE — Antwort der Meta-Ebene")

        frage_text = meta.get("freie_frage", "")
        if frage_text:
            st.markdown(f"**Frage:** {frage_text}")

        antwort = result.get("meta_freie_frage", "(Keine Antwort)")

        if antwort.startswith("FEHLER"):
            st.error(antwort)
        else:
            # Hervorgehoben darstellen
            antwort_safe = (
                antwort
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace("\n", "<br>")
            )
            import re as _re
            antwort_safe = _re.sub(
                r'\*\*(.+?)\*\*', r'<strong>\1</strong>', antwort_safe
            )
            st.markdown(
                f'<div style="background-color: #f0f2f6; padding: 1.5rem; '
                f'border-radius: 0.5rem; border-left: 4px solid #2196F3; '
                f'color: #1a1a2e; line-height: 1.7; font-size: 1.02rem;">'
                f'{antwort_safe}'
                f'</div>',
                unsafe_allow_html=True,
            )

        if stages.get("freie_frage"):
            st.caption(f"FREIE FRAGE: {stages['freie_frage']}s")

    else:
        # ── META-ANALYSE Ergebnis (VOLLANALYSE) ──

        # --- META-BEOBACHTEN ---
        st.subheader("Stufe 2: META-BEOBACHTEN — Stabilitäts-Analyse")
        beobachtung = result.get("meta_beobachten", "(nicht verfügbar)")

        if beobachtung.startswith("FEHLER"):
            st.error(beobachtung)
        else:
            st.markdown(beobachtung)

        if stages.get("beobachten"):
            st.caption(f"BEOBACHTEN: {stages['beobachten']}s")

        # --- META-DESTILLATION ---
        st.markdown("---")
        st.subheader("Stufe 3: META-DESTILLATION — Der harte Befund")
        destillat = result.get("meta_destillation", "(nicht verfügbar)")

        if destillat.startswith("FEHLER"):
            st.error(destillat)
        else:
            # Hervorgehoben darstellen — Lesbar auf allen Themes
            destillat_safe = (
                destillat
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace("\n", "<br>")
            )
            # **fett** → <strong>fett</strong> rendern
            import re as _re
            destillat_safe = _re.sub(
                r'\*\*(.+?)\*\*', r'<strong>\1</strong>', destillat_safe
            )
            st.markdown(
                f'<div style="background-color: #f0f2f6; padding: 1.5rem; '
                f'border-radius: 0.5rem; border-left: 4px solid #e94560; '
                f'color: #1a1a2e; line-height: 1.7; font-size: 1.02rem;">'
                f'{destillat_safe}'
                f'</div>',
                unsafe_allow_html=True,
            )

        if stages.get("destillation"):
            st.caption(f"DESTILLATION: {stages['destillation']}s")

    # ==================================================================
    # NACHTRÄGLICHE FREIE FRAGE (nur nach VOLLANALYSE)
    # ==================================================================
    if not is_freie_frage and sezieren_data:
        st.markdown("---")
        st.subheader("Nachträgliche FREIE FRAGE")
        st.caption(
            "Stelle eine gezielte Frage an die Meta-Ebene. "
            "Die Antwort basiert auf den bereits berechneten SEZIEREN-Daten "
            "und dem BEOBACHTEN-Befund."
        )

        nachtr_frage = st.text_input(
            "Frage an die Meta-Ebene:",
            placeholder="z.B. Wird бронзово-острое in späteren Runs häufiger?",
            key="mh_nachtr_frage",
        )

        if st.button(
            "FREIE FRAGE beantworten",
            key="mh_nachtr_frage_btn",
            disabled=not (nachtr_frage and nachtr_frage.strip()),
        ):
            with st.spinner("FREIE FRAGE wird beantwortet..."):
                try:
                    antwort = meta_freie_frage(
                        frage=nachtr_frage.strip(),
                        sezieren_results=sezieren_data,
                        etappe1_text=None,  # Wird aus session_state geladen falls vorhanden
                        beobachtung=result.get("meta_beobachten"),
                        progress_callback=lambda msg: None,
                    )
                    st.session_state["mh_nachtr_antwort"] = antwort
                    st.session_state["mh_nachtr_frage_text"] = nachtr_frage.strip()
                except Exception as e:
                    logger.error(f"Nachträgliche FREIE FRAGE Fehler: {e}")
                    st.error(f"Fehler: {e}")

        # Nachträgliche Antwort anzeigen
        nachtr_antwort = st.session_state.get("mh_nachtr_antwort")
        nachtr_frage_text = st.session_state.get("mh_nachtr_frage_text", "")
        if nachtr_antwort and nachtr_frage_text:
            st.markdown(f"**Frage:** {nachtr_frage_text}")

            if nachtr_antwort.startswith("FEHLER"):
                st.error(nachtr_antwort)
            else:
                antwort_safe = (
                    nachtr_antwort
                    .replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;")
                    .replace("\n", "<br>")
                )
                import re as _re2
                antwort_safe = _re2.sub(
                    r'\*\*(.+?)\*\*', r'<strong>\1</strong>', antwort_safe
                )
                st.markdown(
                    f'<div style="background-color: #f0f2f6; padding: 1.5rem; '
                    f'border-radius: 0.5rem; border-left: 4px solid #2196F3; '
                    f'color: #1a1a2e; line-height: 1.7; font-size: 1.02rem;">'
                    f'{antwort_safe}'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    # ==================================================================
    # KONFRONTATION: Meta-Tests vs. externe Kritik (nur nach VOLLANALYSE)
    # ==================================================================
    if not is_freie_frage and sezieren_data:
        # Prüfe ob Meta-Hermeneutic-Dateien vorliegen
        has_meta = any(
            r.get("source_type") == "meta_hermeneutic" for r in sezieren_data
        )
        if has_meta:
            st.markdown("---")
            st.subheader("KONFRONTATION — Meta-Ergebnisse vs. externe Kritik")
            st.caption(
                "Lade einen Kritik-Text hoch (Artikel, Rezension, wissenschaftliche Stellungnahme). "
                "Die Kritik wird NICHT als Synthese-Input behandelt — sie ist eine asymmetrische "
                "Außenperspektive. Die Nicht-Passung ist selbst der Befund."
            )

            kritik_file = st.file_uploader(
                "Kritik-Text (.md oder .txt)",
                type=["md", "txt"],
                key="mh_kritik_file",
                help="Externer Text, der die Meta-Hermeneutic-Ergebnisse konfrontiert",
            )

            kritik_text = None
            if kritik_file:
                try:
                    kritik_text = kritik_file.getvalue().decode("utf-8")
                    n_chars = len(kritik_text)
                    st.info(f"Kritik-Text geladen: {kritik_file.name} ({n_chars} Zeichen)")
                except Exception as e:
                    st.error(f"Kann Kritik-Text nicht lesen: {e}")

            if st.button(
                "KONFRONTATION starten",
                key="mh_konfrontation_btn",
                disabled=not kritik_text,
            ):
                with st.spinner("KONFRONTATION: Meta-Ergebnisse vs. Kritik..."):
                    try:
                        konfrontation_result = meta_konfrontation(
                            sezieren_results=sezieren_data,
                            kritik_text=kritik_text,
                            progress_callback=lambda msg: None,
                        )
                        st.session_state["mh_konfrontation"] = konfrontation_result
                    except Exception as e:
                        logger.error(f"KONFRONTATION Fehler: {e}")
                        st.error(f"Fehler: {e}")

            # Konfrontation-Ergebnis anzeigen
            konfrontation = st.session_state.get("mh_konfrontation")
            if konfrontation:
                if konfrontation.startswith("FEHLER"):
                    st.error(konfrontation)
                else:
                    # Hervorgehoben darstellen
                    konf_safe = (
                        konfrontation
                        .replace("&", "&amp;")
                        .replace("<", "&lt;")
                        .replace(">", "&gt;")
                        .replace("\n", "<br>")
                    )
                    import re as _re3
                    konf_safe = _re3.sub(
                        r'\*\*(.+?)\*\*', r'<strong>\1</strong>', konf_safe
                    )
                    st.markdown(
                        f'<div style="background-color: #f0f2f6; padding: 1.5rem; '
                        f'border-radius: 0.5rem; border-left: 4px solid #9C27B0; '
                        f'color: #1a1a2e; line-height: 1.7; font-size: 1.02rem;">'
                        f'{konf_safe}'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

    # ==================================================================
    # METADATEN
    # ==================================================================
    with st.expander("Metadaten", expanded=False):
        st.markdown(f"- **Modus:** {'FREIE FRAGE' if is_freie_frage else 'META-ANALYSE'}")
        if meta.get("is_meta_meta"):
            st.markdown("- **Meta-Meta-Analyse:** Ja (Meta-Meta-Prompts aktiviert)")
        st.markdown(f"- **Runs:** {n_runs}")
        st.markdown(f"- **Modell Beobachten:** {meta.get('model_beobachten', '?')}")
        st.markdown(f"- **Modell Destillation:** {meta.get('model_destillation', '?')}")
        st.markdown(f"- **Gesamtdauer:** {meta.get('elapsed_seconds', '?')}s")
        st.markdown(f"- **Termini übersprungen:** {meta.get('skip_termini', '?')}")
        st.markdown(f"- **Etappe-1-Daten:** {'Ja' if meta.get('has_etappe1_text') else 'Nein'}")

        if stages:
            stage_lines = " | ".join(
                f"{k}: {v}s" for k, v in stages.items()
            )
            st.markdown(f"- **Stufen:** {stage_lines}")

    # ==================================================================
    # DOWNLOAD
    # ==================================================================
    ts = st.session_state.get("mh_timestamp", "")
    md_content = format_meta_result_as_markdown(result)

    # Nachträgliche FREIE FRAGE an Download anhängen
    nachtr_antwort = st.session_state.get("mh_nachtr_antwort")
    nachtr_frage_text = st.session_state.get("mh_nachtr_frage_text", "")
    if nachtr_antwort and nachtr_frage_text and not is_freie_frage:
        md_content += (
            f"\n\n---\n\n"
            f"## Nachträgliche FREIE FRAGE\n\n"
            f"**Frage:** {nachtr_frage_text}\n\n"
            f"{nachtr_antwort}"
        )

    # KONFRONTATION an Download anhängen
    konfrontation = st.session_state.get("mh_konfrontation")
    if konfrontation and not konfrontation.startswith("FEHLER"):
        md_content += (
            f"\n\n---\n\n"
            f"## KONFRONTATION — Meta-Ergebnisse vs. externe Kritik\n\n"
            f"{konfrontation}"
        )

    st.download_button(
        label="Als Markdown herunterladen",
        data=md_content,
        file_name=f"meta_hermeneutic_{ts[:10] if ts else 'unknown'}.md",
        mime="text/markdown",
    )
