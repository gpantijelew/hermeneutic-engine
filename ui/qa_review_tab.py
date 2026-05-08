# ui/qa_review_tab.py — A.7 Human-in-the-Loop Review Tab
"""
QA Review Tab für A.7 Human-in-the-Loop Sampling.
Zeigt gesampelte Enforcer-Claims für manuelle Validierung.
"""

import streamlit as st
import hashlib

from modules.database import (
    get_unreviewed_reviews,
    get_unreviewed_count,
    mark_reviewed,
    get_human_review_count,
)
from modules.config import (
    ENFORCER_CALIBRATION_TARGET,
    ENFORCER_VERSION,
    ENFORCER_SAMPLING_RATE_LOW,
)


def render_qa_review_tab() -> None:
    """Rendert den QA Reviews Tab."""
    st.title("🔬 QA Reviews — Human-in-the-Loop")
    st.markdown("Validiere Enforcer-Entscheidungen für Ground-Truth & Kalibrierung.")

    # --- Statistiken ---
    reviewed = get_human_review_count()
    pending = get_unreviewed_count()
    progress = min(reviewed / ENFORCER_CALIBRATION_TARGET, 1.0)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Reviews abgeschlossen", f"{reviewed}/{ENFORCER_CALIBRATION_TARGET}")
    with col2:
        st.metric("Noch offen", pending)
    with col3:
        st.metric("Enforcer-Version", ENFORCER_VERSION)

    st.progress(progress, text=f"Kalibrierung: {reviewed}/{ENFORCER_CALIBRATION_TARGET}")

    if reviewed >= ENFORCER_CALIBRATION_TARGET:
        st.success(f"✅ Kalibrierungs-Target erreicht! Sampling-Rate reduziert auf 1/{ENFORCER_SAMPLING_RATE_LOW}.")

    st.markdown("---")

    # --- Pagination ---
    page = st.session_state.get("qa_review_page", 0)
    per_page = 8

    reviews = get_unreviewed_reviews(limit=per_page, offset=page * per_page)

    if not reviews:
        st.info("🎉 Keine offenen Reviews. Der Enforcer arbeitet autonom weiter.")
        if st.button("🔄 Erneut prüfen"):
            st.rerun()
        return

    st.caption(f"Zeige {len(reviews)} offene Reviews (Seite {page + 1})")

    # --- Review Cards ---
    for review in reviews:
        with st.container():
            st.markdown(f"**Claim:** {review['claim_text']}")

            # Enforcer-Urteil
            valid_icon = "✅" if review['enforcer_valid'] else "❌"
            st.markdown(f"**Enforcer-Urteil:** {valid_icon} {'GÜLTIG' if review['enforcer_valid'] else 'UNGÜLTIG'}")
            if review.get('enforcer_reason'):
                st.caption(f"Begründung: {review['enforcer_reason']}")

            # Source-Content in Expander
            with st.expander("📄 Quelltext anzeigen"):
                st.text(review.get('source_content', '(kein Content)'))

                # Hash-Check
                current_hash = hashlib.sha256(
                    review.get('source_content', '').encode()
                ).hexdigest()
                if current_hash != review.get('source_content_hash', ''):
                    st.warning("⚠️ Quelldokument wurde seit dem Enforcer-Lauf geändert!")
                else:
                    st.caption("✅ Dokument unverändert (Hash stimmt)")

            # Quick-Verdict Buttons
            col_ok, col_nok, _ = st.columns([1, 1, 4])

            with col_ok:
                if st.button(
                    "✅ Korrekt",
                    key=f"ok_{review['id']}",
                    help="Enforcer-Entscheidung war richtig",
                    type="primary",
                ):
                    mark_reviewed(review['id'], valid=True, reviewer="grigori")
                    st.success("Als korrekt markiert!")
                    st.rerun()

            with col_nok:
                if st.button(
                    "❌ Falsch",
                    key=f"nok_{review['id']}",
                    help="Enforcer-Entscheidung war falsch (Falsch-Positiv oder Falsch-Negativ)",
                ):
                    mark_reviewed(review['id'], valid=False, reviewer="grigori")
                    st.error("Als falsch markiert!")
                    st.rerun()

        st.markdown("")  # Spacer

    # --- Pagination Controls ---
    if pending > per_page:
        col_prev, col_info, col_next = st.columns([1, 2, 1])

        with col_prev:
            if page > 0:
                if st.button("⬅️ Vorherige"):
                    st.session_state.qa_review_page = page - 1
                    st.rerun()

        with col_info:
            st.caption(f"Seite {page + 1} von {(pending // per_page) + 1}")

        with col_next:
            if (page + 1) * per_page < pending:
                if st.button("Nächste ➡️"):
                    st.session_state.qa_review_page = page + 1
                    st.rerun()
