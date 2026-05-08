"""ui/stilisierung_tab.py — Stilisierungs-Tab mit optionalem Agentic Loop.

HRE v52: Separater Tab für einzelnen Text mit Einfach-/Agentic-Modus.
"""

import logging
from datetime import datetime

import streamlit as st

from modules.citation_rag import CitationRAG

logger = logging.getLogger(__name__)


def render_stilisierung_tab():
    """Render den Stilisierungs-Tab.

    Eingabe: Ein einzelner Text (z. B. Master-Draft aus Destillation).
    Modus:   Einfach (Single-Shot) oder Agentic (Drafter → Critic → Editor).
    """
    st.header("🎭 Stilisierung")
    st.caption(
        "Verwandelt einen einzelnen Text in die hermeneutische Stimme. "
        "Optional mit Agentic Loop (Kritik + chirurgische Überarbeitung)."
    )

    # --- Eingabe ---
    input_text = st.text_area(
        "Text zur Stilisierung",
        value=st.session_state.get("stilisierung_input", ""),
        height=400,
        placeholder=(
            "Füge hier beliebigen Text ein — z. B. den Master-Draft "
            "aus dem Destillations-Tab per Copy & Paste."
        ),
    )

    # --- Modus-Auswahl ---
    use_agentic = st.toggle(
        "🔄 Agentic Loop (Drafter → Critic → Editor)",
        value=False,
        help="Höhere Qualität durch iterative Kritik und chirurgische Überarbeitung (~3× länger).",
    )

    # --- Ausführung ---
    if st.button("✨ Stilisieren", type="primary"):
        text = input_text.strip()
        if not text:
            st.warning("Bitte gib einen Text ein.")
            return

        # Eingabe speichern (bleibt beim Tab-Wechsel erhalten)
        st.session_state["stilisierung_input"] = input_text

        with st.spinner(
            "Agentic Loop läuft..." if use_agentic else "Stilisierung läuft..."
        ):
            try:
                rag = CitationRAG()
                iteration_texts = [text]

                if use_agentic:
                    # Drei-Stufen-Pipeline
                    with st.status(
                        "Agentic Pipeline: Entwurf → Kritik → Überarbeitung",
                        expanded=True,
                    ) as status:
                        status.write("📝 Schritt 1: Stilistischer Entwurf...")
                        result, trace = rag.generate_agentic_synthesis(
                            iteration_texts,
                            source_intent="STILISIERUNG",
                        )
                        critique_count = len(trace.get("critique", []))
                        status.write(
                            f"🔍 Schritt 2: Kritik — {critique_count} Punkte gefunden"
                        )
                        status.write("✂️ Schritt 3: Chirurgische Überarbeitung...")
                        status.update(label="Fertig!", state="complete")

                    st.session_state["stilisierung_result"] = result
                    st.session_state["stilisierung_trace"] = trace
                    st.session_state["stilisierung_agentic"] = True
                else:
                    # Einfacher Single-Shot
                    result = rag.generate_synthesis_best_of(
                        iteration_texts,
                        intent="STILISIERUNG",
                    )
                    st.session_state["stilisierung_result"] = result
                    st.session_state["stilisierung_trace"] = None
                    st.session_state["stilisierung_agentic"] = False

                st.session_state["stilisierung_timestamp"] = datetime.now().isoformat()
                st.success("✅ Stilisierung abgeschlossen!")

            except Exception as e:
                logger.error(f"Stilisierungsfehler: {e}")
                st.error(f"❌ Fehler bei der Stilisierung: {e}")

    # --- Ergebnisanzeige ---
    result = st.session_state.get("stilisierung_result")
    if result:
        st.markdown("---")
        mode_label = " (Agentic)" if st.session_state.get("stilisierung_agentic") else ""
        st.subheader(f"📝 Ergebnis — Stilisierung{mode_label}")
        st.markdown(result)

        # --- Agentic Review-Protokoll ---
        trace = st.session_state.get("stilisierung_trace")
        if trace and trace.get("critique"):
            with st.expander("🔍 Agentic Review Protokoll", expanded=False):
                st.markdown("**Kritikpunkte (Schritt 2):**")
                for i, point in enumerate(trace["critique"], 1):
                    st.markdown(f"**[{i}] Stelle:** `{point.get('stelle', '—')}`")
                    st.caption(f"**Kritik:** {point.get('problem', '—')}")
                    st.caption(f"**Vorschlag:** {point.get('vorschlag', '—')}")
                    st.markdown("---")

        # --- Markdown-Download (inkl. Protokoll) ---
        ts = st.session_state.get("stilisierung_timestamp", "")
        md_header = f"""---
Stilisierung{mode_label}
Erstellt: {ts}
Engine: HRE v52
---

"""
        md_body = result

        if trace and trace.get("critique"):
            md_header += "\n### Agentic Review Protokoll\n\n"
            for i, point in enumerate(trace["critique"], 1):
                md_header += (
                    f"**[{i}]** `{point.get('stelle', '—')}`  \n"
                    f"- **Kritik:** {point.get('problem', '—')}  \n"
                    f"- **Vorschlag:** {point.get('vorschlag', '—')}  \n\n"
                )

        download_text = md_header + "\n" + md_body
        st.download_button(
            label="📥 Als Markdown herunterladen",
            data=download_text,
            file_name=f"stilisierung_{ts[:10] if ts else 'unknown'}.md",
            mime="text/markdown",
        )
