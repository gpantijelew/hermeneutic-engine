# modules/stilistic_lab_pipeline.py — v57.7.5: Relationale Pipeline + Modus-Erkennung
"""
STILISTIC LAB — Etappe 2+3 (pro Quelle) + Globale Synthese.

ARCHITEKTUR (v57.4 Drei-Etappen):
- Etappe 1: Python SEZIEREN (modules/text_analyzer.py) — 0% LLM
- Etappe 2+3: pro Quelle, Flash-Modell — LLM charakterisiert auf Faktenbasis
- Globale Synthese: vergleichend über alle Quellen — Flash/Pro-Modell

ENTSCHEIDUNGEN (aus AGENTS.md):
- Etappe 2 pro Quelle: Fokus + Tiefe statt vorzeitiger Vergleich
- Etappe 2+3 im selben Call: Priming-Verstärkung, aber mit explizitem Bruch
- Expliziter Bruch zwischen Etappe 2 und 3: Verhindert Repetitions-Tendenz
- Separater Synthese-Call: Kognitive Trennung Tiefe vs. Breite
- Keine Schule/Namen in System-Instruction: Verhindert Confirmation-Bias
- Operative Haltung: Methoden-Anweisung, keine Rollenvorgabe

v57.7.1 VIER-SEKTIONEN-REFORM:
- DIE DOMINANTE (feminin, wie russisch доминанта, nach Jakobson):
  "Die Dominante ist die Leitkomponente eines Werks, die alle anderen
  Komponenten steuert, beeinflusst, transformiert."
- Prompt: 5 Sektionen → 4 Sektionen (kein STRUKTUR-Fazit mehr)
- BEOBACHTUNG: Fließ-Anweisung statt Formularfelder
- VERTIEFUNG: Eine scharfe Frage statt A/B-Fragen + Keyword-Wiederholung
- KENNZAHLEN-CHALLENGE → KENNZAHLEN-ÜBERRASCHUNG
- Synthese: Autor-für-Autor-Vergleich hinzugefügt

v57.7.5 RELATIONALE PIPELINE + MODUS-ERKENNUNG (2026-05-25):
- Horizont: Untersuchungsfrage + Autoren-Zuordnung in Etappe 2+3 (EINGRIFF 1)
- Modus-Erkennung: Text-Modus bestimmen vor der Analyse (EINGRIFF 2)
- Operations-Taxonomie: register-offen statt polemisch (EINGRIFF 3)
- Relationale Notiz: ein Satz pro Quelle im Vergleich (EINGRIFF 4)
- Verdichtungsschicht: KONZENTRAT (Dominante+Operation+Modus+Titel) vor Synthese (EINGRIFF 5)
- Synthese als Argument: HYPOTHESE→BEWEISFÜHRUNG→KENNZAHLEN→FREIER RAUM→FAZIT (EINGRIFF 6)
- Tynjanow als Methode: relationaler Methodenhinweis, kein Formvorbild (EINGRIFF 7)
- FREIER RAUM generisch: register-unabhängig
- Entscheidungen: Claude + Gemini Konsens (F1–F5)

ÖFFENTLICHE API:
    from modules.stilistic_lab_pipeline import run_stilistic_lab

    result = run_stilistic_lab(source_texts, source_labels)
    # result = {etappe1, etappen_2_3, globale_synthese}
"""

import logging
import re
import time
from typing import Dict, List, Optional

from modules.llm_wrapper import llm_call
from modules.config import (
    MAX_TOKENS_STILISIERUNG,
    get_model_for_task,
    STILISTIC_DISTILLATION_TEMPERATURE,
)

from modules.text_analyzer import (
    analyze_texts_comparative,
    format_stats_for_llm,
    format_comparison_table_for_llm,
)

logger = logging.getLogger(__name__)


# ==============================================================================
# SYSTEM-INSTRUCTION (Etappe 2+3)
# ==============================================================================

_ETAPPE_2_3_SYSTEM = """Beschreibe die Struktur, dann ihre Funktion im Text.
Erlaubt: strukturelle Funktion ("Diese Wiederholung erzeugt Verdichtung"),
         stilistische Klassifikation ("Das entspricht einer Anapher").
Verboten: Autorenabsichten ("Er wollte betonen"), Rezeptionsbehauptungen ("Der Leser fühlt").

Du bist ein Annotator — kein Interpretieren, kein Deuten, kein Werten.
Nenne keine Schulen, keine Methoden, keine Namen."""


# ==============================================================================
# ETAPPE 2+3: PROMPT (pro Quelle)
# ==============================================================================

def _build_etappe_2_3_prompt(
    source_label: str,
    source_text: str,
    stats_text: str,
    comparison_table_text: str,
    user_question: str = "",
    author_label: str = "",
    other_labels: str = "",
    lyrik_signal: str = "",
    klang_summary: str = "",
) -> str:
    """
    Baut den Prompt für Etappe 2+3 (pro Quelle).

    Aufbau (v57.7.5: Acht-Sektionen-Struktur mit Modus-Erkennung + Relationalem Horizont):
    1. Kontext: Python-Statistiken + Vergleichstabelle + Untersuchungsfrage
    2. Quelltext (auszugsweise: Hotspot-Sätze sind in Stats enthalten)
    3. MODUS → DIE DOMINANTE → DIE GRUNDOPERATION → BEOBACHTUNG → VERTIEFUNG → FREIER RAUM → RELATIONALE NOTIZ → STIL-TITEL
       (8 benannte Sektionen)

    Args:
        source_label:         Label der Quelle (z.B. "QUELLE 1: Herzen")
        source_text:          Originaltext der Quelle (gekürzt)
        stats_text:           Formatierte Etappe-1-Statistiken
        comparison_table_text: Formatierte Vergleichstabelle
        user_question:        Untersuchungsfrage (als Horizont, nicht als Filter)
        author_label:         Autoren-Name für diese Quelle (z.B. "Herzen 1849")
        other_labels:         Übtige Autoren/Quellen (z.B. "Lenin 1902, Lenin 1917")
        lyrik_signal:         Lyrik-Signal aus Etappe 1 ("stark"/"mittel"/"kein") (v59.1)
        klang_summary:        Kompakte Klang-Zusammenfassung aus Etappe 1 (v59.1)
    """
    # Quelltext kürzen: Max 4000 Zeichen (Hotspot-Sätze sind bereits in Stats)
    # Originaltext als Referenz, aber nicht komplett (Attention-Schutz)
    text_preview = source_text[:4000]
    if len(source_text) > 4000:
        text_preview += "\n[... Text gekürzt. Hotspot-Sätze siehe Statistiken oben ...]"

    # v59.2: Klang-Prominenz — Wenn Lyrik erkannt, Klang-Daten explizit anbieten
    # Gouvernante-konform: Messung wird angeboten, nicht die Deutung
    klang_prompt = ""
    if lyrik_signal in ("stark", "mittel") and klang_summary:
        klang_prompt = (
            "\n\nWICHTIG: Die Python-Analyse hat LYRIK erkannt und folgende "
            "Klangstrukturen gemessen:\n"
            f"  {klang_summary}\n"
            "Bei einem Gedicht suchst du Klangfügung — nicht nur Satzzeichen und Wortwahl.\n"
            "Berücksichtige diese Messdaten in deiner Beobachtung.\n"
            "Falls eine Klangfigur für die Dominante relevant ist: benutze sie.\n"
            "Falls nicht: erwähne sie nicht."
        )

    # Horizont-Instruktion: Frage als Beobachtungshorizont, nicht als Filter
    horizont = ""
    if user_question and user_question.strip():
        horizont = f"""Untersuchungsfrage: {user_question.strip()}
Diese Quelle: {author_label or source_label}
Übtige Quellen: {other_labels}

Du analysierst diesen Text — aber du weißt, in welchem Vergleich
er steht. Beobachte nicht nur, was der Text zeigt.
Beobachte auch, was er zeigt, das die anderen möglicherweise nicht zeigen.

"""

    prompt = f"""{horizont}DU ANALYSIERST: {source_label}

--- VORAB-DATEN (Python-Analyse, deterministisch) ---
{stats_text}

--- VERGLEICHSTABELLE (alle Quellen) ---
{comparison_table_text}

--- ORIGINALTEXT (Auszug) ---
{text_preview}

---

MODUS:
In welchem Modus spricht dieser Text?
Polemik, Beschwörung, Nachdenken, Erzählen, Spiel — oder etwas anderes?
Der Modus bestimmt, welche Operationen du suchst.
Bei einer Polemik suchst du Entlarvung;
bei einem Gedicht suchst du Klangfügung;
bei einem Essay suchst du den Übergang vom Beispiel zum Gesetz.
Benenne den Modus — und wähle deine Fragen danach.{klang_prompt}

DIE DOMINANTE:
Was ist das stilistische Mittel, ohne das die anderen
nicht funktionieren w\u00fcrden?
Nicht: was f\u00e4llt zuerst auf.
Sondern: was h\u00e4lt den Rest zusammen.
Nenne es in einem Wort oder einer kurzen Phrase.

Warum gerade dieses Mittel \u2014 und nicht eines seiner Werkzeuge?
Eine Antithese ist oft Werkzeug einer Dominante, nicht die Dominante selbst.

DIE GRUNDOPERATION:
Was tut dieser Text mit der Sprache?
Nicht: welche Figuren verwendet er.
Sondern: welchen Eingriff macht er.

Benenne die Operation, die dieser Text mit der Sprache vollzieht.
Der Modus bestimmt die Operation.
(Beispiele f\u00fcr Benennungen: Verschiebung, Entlarvung, Verdichtung,
Klangf\u00fcgung, Abschweifung, Verdunkelung, Aufdeckung \u2014 oder eine andere.)

Nenne eine Grundoperation.
Dann: wie verh\u00e4lt sich die Dominante zu dieser Operation \u2014
ist sie ihr Instrument oder ihr Ergebnis?

ERST DANN:

BEOBACHTUNG:
Lies den Text von der Dominante UND der Grundoperation aus.
2-3 Funde, je mit Beleg.
Beobachte unmittelbar am Text: Satzzeichen,
Satztypen, Wortwiederholungen, morphologische Muster.
Achte auf:
- Formelhafte Pr\u00e4gungen und ihre Wirkung
- Registerbr\u00fcche: Wo wird "hohe" F\u00e4rbung zerst\u00f6rt?
- Wortoperationen: Wo werden W\u00f6rter entlarvt, umgedeutet, ihres Scheins beraubt?
- Das Verh\u00e4ltnis zur gegnerischen Sprache
Schreibe in Flie\u00dftext. Beginne jeden Fund mit dem Satz:
"**[Auff\u00e4lligkeit]** \u2014 [Funktion]"
Dann Beleg. Dann n\u00e4chste Beobachtung im gleichen Modus.
Nicht in Stichpunkten und nicht mit Labels wie "Struktur:" / "Funktion:".

Beispiel:
  Die wiederholte Anapher "Sie, die..." verst\u00e4rkt die Dominante,
  indem sie die Anklage in parallele Bahnen zwingt.
  Beleg: "Sie, die Demut predigen und selbst im Luxus leben"

Eine Antithese ist eine Figur \u2014 kein Eingriff.
"Der Text stellt X und Y gegen\u00fcber" beschreibt Struktur.
"Der Text zerst\u00f6rt X durch die Ber\u00fchrung mit Y" beschreibt Operation.

\u2500\u2500\u2500 VERTIEFUNG \u2500\u2500\u2500

Was wird erst sichtbar, wenn man die Dominante wegdenkt?
Finde 2-3 neue Funde, die der Dominante widersprechen,
sie erg\u00e4nzen oder sie unterlaufen \u2014 keine Paraphrase.

FREIER RAUM:
Was zeigt dieser Text \u00fcber Sprache, das er nicht explizit thematisiert?
Welche Frage verlangt dieser Text, die er nicht selbst stellt?
Falls du etwas findest: was zeigt das \u00fcber den Stil?

RELATIONALE NOTIZ:
Wie unterscheidet sich die Grundoperation dieses Textes
von dem, was die Statistiken der anderen Quellen erwarten lassen?
Ein Satz.

STIL-TITEL:
Schreibe den TITEL dieses Stils.
Max 8 W\u00f6rter, ein Gedankenstrich. Wie ein Buchtitel.
          Bsp: \u201eDeklamatorischer Imperativ \u2014 kein Argument.\u201c """

    return prompt


# ==============================================================================
# GLOBALE SYNTHESE: SYSTEM-INSTRUCTION
# ==============================================================================

_GLOBALE_SYNTHESE_SYSTEM = """Du vergleichst Stile mehrerer Texte.
Beschreibe Konvergenzen und Divergenzen auf der Wort- und Satzebene.
Erlaubt: strukturelle Funktion ("Dieses Muster erzeugt Verdichtung"),
         stilistische Klassifikation ("Das entspricht einer Anapher").
Verboten: Autorenabsichten ("Er wollte betonen"), Rezeptionsbehauptungen ("Der Leser fühlt").

Du darfst die Autoren beim Namen nennen, wenn die Quellen-Bezeichnungen
Namen enthalten (z.B. "QUELLE 1: Herzen"). Verwende die Namen,
um die stilistischen Beziehungen zwischen den Autoren präzise
zu fassen. Nenne keine Schulen, keine Methoden."""


# ==============================================================================
# GLOBALE SYNTHESE: PROMPT
# ==============================================================================

def _build_globale_synthese_prompt(
    etappen_results: Dict[str, str],
    comparison_table_text: str,
    user_question: str = "",
    praegnanz_sentences: Optional[Dict[str, str]] = None,
    individual_stats: Optional[Dict[str, Dict]] = None,
    dominant_labels: Optional[Dict[str, str]] = None,
    grundoperation_labels: Optional[Dict[str, str]] = None,
    modus_labels: Optional[Dict[str, str]] = None,
) -> str:
    """
    Baut den Prompt für die Globale Synthese.

    Fünf-Schichten-Architektur (v57.7):
    Schicht 0: KONZENTRAT — Dominante + Grundoperation + Modus + Titel pro Quelle (v57.7.5)
    Schicht 1: (in KONZENTRAT integriert, v57.7.5)
    Schicht 2: KENNZAHLEN — Einzelstatistiken pro Quelle (v57.6.1, v57.7.5)
    Schicht 3: VERGLEICHSTABELLE — Python-Statistiken (aggregiert)
    Schicht 4: VOLLTEXT — Alle Etappe-2+3-Ergebnisse

    Args:
        etappen_results:       Dict {source_label: etappe_2_3_text}
        comparison_table_text: Formatierte Vergleichstabelle
        user_question:         Optionale benutzerdefinierte Frage (v57.5)
        praegnanz_sentences:   Dict {source_label: praegnanz_satz} (v57.6)
        individual_stats:      Dict {source_label: stats_dict} (v57.6.1)
        dominant_labels:       Dict {source_label: dominante} (v57.7.1)
    """
    # Schicht 0: KONZENTRAT — Dominante + Grundoperation + Modus + Titel pro Quelle (v57.7.5)
    konzentrat_block = "\n--- KONZENTRAT (Dominante | Grundoperation | Modus | Titel pro Quelle) ---\n"
    all_labels_list = list(set(
        list(dominant_labels.keys()) +
        list(grundoperation_labels.keys() if grundoperation_labels else []) +
        list(modus_labels.keys() if modus_labels else []) +
        list(praegnanz_sentences.keys() if praegnanz_sentences else [])
    ))
    for label in all_labels_list:
        dom = dominant_labels.get(label, "\u2014") if dominant_labels else "\u2014"
        op = grundoperation_labels.get(label, "\u2014") if grundoperation_labels else "\u2014"
        mod = modus_labels.get(label, "\u2014") if modus_labels else "\u2014"
        titel = praegnanz_sentences.get(label, "\u2014") if praegnanz_sentences else "\u2014"
        konzentrat_block += f"  {label}: Dominante: {dom} | Operation: {op} | Modus: {mod} | Titel: {titel}\n"
    konzentrat_block += "\n"

    # Schicht 1: (in KONZENTRAT integriert, v57.7.5)
    verdichtung_block = ""

    # Schicht 2: KENNZAHLEN — Einzelstatistiken pro Quelle (v57.6.1)
    kennzahlen_block = ""
    if individual_stats:
        kennzahlen_block = "\n--- EINZELSTATISTIKEN PRO QUELLE ---\n"
        for label, s in individual_stats.items():
            # Lyrik-Kennzahlen (v59 Klang-Durchgriff)
            lyrik_sig = s.get('lyrik_signal', '—')
            if lyrik_sig != '—':
                lyrik_str = (
                    f" | Lyrik {lyrik_sig}"
                    f" | Strophen {s.get('strophen', '—')}"
                    f" | Reim {s.get('reim_typ', '—')}"
                    f" | Ø {s.get('avg_silben', '—')} Silben"
                    f" | Enjamb. {s.get('enjambement', '—')}"
                )
            else:
                lyrik_str = " | Lyrik: —"

            kennzahlen_block += (
                f"  {label}: "
                f"{s.get('words', 0)} Wörter | "
                f"{s.get('sentences', 0)} Sätze | "
                f"Ø {s.get('avg_sent_len', 0)} | "
                f"HS {s.get('HS', 0)} / NS {s.get('NS', 0)} / Gemischt {s.get('gemischt', 0)} | "
                f"TTR {s.get('TTR', 0):.3f} | "
                f"Morph {s.get('morph', 0):.1f} | "
                f"Kommas {s.get('kommas', 0)}"
                f"{lyrik_str}\n"
            )
        kennzahlen_block += "\n"

    # Schicht 4: VOLLTEXT — Alle Etappe-2+3-Ergebnisse
    quellen_block = ""
    for label, text in etappen_results.items():
        quellen_block += f"\n--- {label} ---\n{text}\n"

    prompt = f"""VERGLEICHENDE STILBEOBACHTUNG

{konzentrat_block}{kennzahlen_block}--- VERGLEICHSTABELLE ---
{comparison_table_text}

--- EINZELBEOBACHTUNGEN PRO QUELLE ---
{quellen_block}

---

GLOBALE SYNTHESE:
Beziehe dich auf die Einzelbeobachtungen oben. Verkn\u00fcpfe die Funde
zu einem Argument \u2014 nicht zu einer Liste.
Wenn die Quellen-Bezeichnungen Autoren-Namen oder Gruppen enthalten,
nutze diese, um die Beobachtungen zu strukturieren.

HYPOTHESE:
Formuliere die k\u00fchnste, aber noch plausible Behauptung,
die dieser Vergleich ergibt.
Nicht: eine Beobachtung, die du schon gemacht hast.
Sondern: eine Behauptung, die stimmen k\u00f6nnte oder nicht \u2014
die aber, wenn sie stimmt, mehr erkl\u00e4rt als alle Einzelbeobachtungen.
Sie muss falsifizierbar sein: Was w\u00fcrde sie widerlegen?

Hinweis: Tynjanows Methode ist die relationale Frage.
Eine gute Hypothese entsteht nicht aus Beobachtung des Textes allein,
sondern aus einer relationalen Frage \u2014 einer Frage, die der Text an die anderen
stellt und die die anderen an ihn richten. Nicht: \u201eWas zeigt dieser Text?\u201c
Sondern: \u201eWas tut dieser Text mit der Sprache, das die anderen nicht tun?\u201c

BEWEISF\u00dcHRUNG:
Entfalte die Hypothese. Die Kategorien stehen als Werkzeuge
zur Verf\u00fcgung \u2014 nicht als Checkliste, sondern als
Argumentationsmittel. Du nutzt die, die die Hypothese
st\u00fctzen oder herausfordern. Die Hypothese bestimmt
die Reihenfolge, nicht umgekehrt.
Verf\u00fcgbare Werkzeuge:
  \u2014 Operations-Genealogie: Wie ver\u00e4ndert sich eine Operation \u00fcber die Quellen?
  \u2014 Dominanten-Verh\u00e4ltnisse: Gemeinsame, widerspr\u00fcchliche, \u00fcbergeordnete Dominanten
  \u2014 Konvergenzen: Gemeinsame stilistische Merkmale
  \u2014 Divergenzen: Stilistische Unterschiede
  \u2014 Wahlverwandtschaft: \u00dcberraschend nah trotz inhaltlicher Ferne
Belege jede Behauptung mit einem Zitat aus den Einzelanalysen.

KENNZAHLEN-\u00dcBERRASCHUNG:
Welche Zahl in den Einzelstatistiken st\u00fctzt oder irritiert die Hypothese?
Verwende mindestens 2 \u00dcberraschungsbefunde.
Erkl\u00e4re, warum die Zahl \u00fcberraschend ist \u2014
und was sie \u00fcber den Stil verr\u00e4t.

FREIER RAUM:
Was zeigt der Vergleich \u00fcber Sprache selbst?
Wenn die Operationen aus allen Quellen eine gemeinsame
Logik haben \u2014 wie lie\u00dfe sie sich in einem Satz benennen?
Nicht als Zusammenfassung. Sondern als Hypothese.

FAZIT:
Best\u00e4tigung, Revision oder Versch\u00e4rfung der Hypothese.
Nichts Neues mehr."""

    # Benutzerdefinierte Frage injizieren
    if user_question and user_question.strip():
        prompt += f"""

FRAGE: {user_question.strip()}
Beantworte diese Frage auf Basis der Beobachtungen oben."""

    return prompt


# ==============================================================================
# HAUPTFUNKTION: STILISTIC LAB PIPELINE
# ==============================================================================

def run_stilistic_lab(
    source_texts: Dict[str, str],
    progress_callback=None,
    user_question: str = "",
) -> Dict:
    """
    Führt die komplette STILISTIC LAB Pipeline aus.

    Drei-Etappen-Architektur:
    1. Etappe 1 (SEZIEREN): Python-Preprocessing, deterministisch
    2. Etappe 2+3 (pro Quelle): LLM-charakterisierung auf Faktenbasis
    3. Globale Synthese: Vergleichende Beobachtung über alle Quellen

    Args:
        source_texts:      Dict {source_label: text_content}
                           source_label sollte QUELLE-Nummer + Kurzname sein,
                           z.B. "QUELLE 1: Herzen" oder "QUELLE 2: Lenin"
        progress_callback: Optional: Callback(status_msg) für UI-Updates
        user_question:    Optionale Frage, die in der Globalen Synthese
                           injiziert wird (v57.5.1 Fix C)

    Returns:
        Dict mit:
        - etappe1: Dict aus analyze_texts_comparative()
        - etappen_2_3: Dict {source_label: llm_response}
        - globale_synthese: String
        - metadata: timing, model, etc.
    """
    start_time = time.time()
    metadata = {
        "source_count": len(source_texts),
        "sources": list(source_texts.keys()),
        "model_etappe_2_3": get_model_for_task("stilistic_distillation"),
        "model_synthese": get_model_for_task("synthesis"),
        "user_question": user_question if user_question else "",
    }

    # ==========================================================================
    # ETAPPE 1: SEZIEREN (Python, deterministisch)
    # ==========================================================================
    if progress_callback:
        progress_callback("Etappe 1: SEZIEREN (Python-Analyse)...")

    logger.info(f"🔬 Etappe 1: SEZIEREN — {len(source_texts)} Quellen")
    etappe1 = analyze_texts_comparative(source_texts)

    # Vergleichstabelle für LLM-Kontext formatieren
    comparison_table_text = format_comparison_table_for_llm(etappe1["comparison_table"])

    # ==========================================================================
    # ETAPPE 2+3: PRO QUELLE (LLM)
    # ==========================================================================
    etappen_2_3 = {}
    total_sources = len(etappe1["individual"])
    source_labels = list(etappe1["individual"].keys())

    for idx, label in enumerate(source_labels, 1):
        stats = etappe1["individual"][label]
        if "error" in stats:
            etappen_2_3[label] = f"FEHLER: Konnte {label} nicht analysieren."
            continue

        if progress_callback:
            progress_callback(
                f"Etappe 2+3: {label} analysieren ({idx}/{total_sources})..."
            )

        # Stats für diese Quelle formatieren
        stats_text = format_stats_for_llm(stats)

        # Originaltext holen
        source_text = source_texts.get(label, "")

        # v59.1: Klang-Zusammenfassung für Lyrik-Prominenz im Prompt
        vs = stats.get("verse_structure", {})
        vd = stats.get("verse_detail", {})
        lyrik_sig = vs.get("signal_strength", "kein")
        klang_sum = ""
        if lyrik_sig in ("stark", "mittel") and vd:
            # Kompakte Klang-Zusammenfassung (Gouvernante: Messung, keine Deutung)
            klang_parts = []
            rhyme = vd.get("rhyme", {})
            if rhyme.get("rhyme_type") and rhyme["rhyme_type"] != "Kein Reim":
                klang_parts.append(f"Reim: {rhyme['rhyme_type']}")
            sound = vd.get("sound_patterns", {})
            n_allit = len(sound.get("alliterations", []))
            n_asson = len(sound.get("assonances", []))
            n_innen = len(sound.get("internal_rhymes", []))
            if n_allit:
                klang_parts.append(f"{n_allit} Alliteration(en)")
            if n_asson:
                klang_parts.append(f"{n_asson} Assonanz(en)")
            if n_innen:
                klang_parts.append(f"{n_innen} Binnenreim(e)")
            rhythm = vd.get("rhythm", {})
            if rhythm.get("pattern_description"):
                klang_parts.append(f"Rhythmus: {rhythm['pattern_description']}")
            enjamb = vd.get("enjambement", {})
            if enjamb.get("count", 0) > 0:
                klang_parts.append(f"{enjamb['count']} Enjambement(s)")
            echoes_data = vd.get("vowel_echoes", {})
            echoes_list = echoes_data.get("echoes", []) if isinstance(echoes_data, dict) else echoes_data if isinstance(echoes_data, list) else []
            trivial_vowel = echoes_data.get("trivial_vowel") if isinstance(echoes_data, dict) else None
            if echoes_list:
                klang_parts.append(f"{len(echoes_list)} Vokal-Echo(s)")
            if trivial_vowel:
                klang_parts.append(f"Endvokal '{trivial_vowel}' dominiert (trivial)")
            if klang_parts:
                klang_sum = " | ".join(klang_parts)

        # Autor-Label f\u00fcr Horizont-Instruktion ableiten (v57.7.5)
        # Format: "QUELLE 1: Herzen 1849" \u2192 "Herzen 1849"
        author_lbl = label.split(": ", 1)[-1] if ": " in label else label
        other_lbls = ", ".join(
            l.split(": ", 1)[-1] if ": " in l else l
            for l in source_labels if l != label
        )

        # Prompt bauen (v57.7.5: user_question als Horizont, nicht als Filter)
        # v59.1: lyrik_signal + klang_summary für Klang-Prominenz
        prompt = _build_etappe_2_3_prompt(
            source_label=label,
            source_text=source_text,
            stats_text=stats_text,
            comparison_table_text=comparison_table_text,
            user_question=user_question,
            author_label=author_lbl,
            other_labels=other_lbls,
            lyrik_signal=lyrik_sig,
            klang_summary=klang_sum,
        )

        # LLM-Call
        logger.info(f"📝 Etappe 2+3: {label} ({idx}/{total_sources})")
        try:
            response = llm_call(
                prompt=prompt,
                task="stilistic_distillation",
                system_instruction=_ETAPPE_2_3_SYSTEM,
                temperature=STILISTIC_DISTILLATION_TEMPERATURE,
                max_tokens=MAX_TOKENS_STILISIERUNG,
                domain="stilisierung",
            )
            etappen_2_3[label] = response if response else "(Leere LLM-Antwort)"
        except Exception as e:
            logger.error(f"❌ Etappe 2+3 fehlgeschlagen für {label}: {e}")
            etappen_2_3[label] = f"FEHLER: {e}"

    # ==========================================================================
    # GLOBALE SYNTHESE
    # ==========================================================================
    if progress_callback:
        progress_callback("Globale Synthese: Vergleichende Beobachtung...")

    # Nur erfolgreiche Etappe-2+3-Ergebnisse verwenden
    valid_results = {k: v for k, v in etappen_2_3.items() if not v.startswith("FEHLER")}

    # —— TITEL/PRÄGNANZ-Sätze extrahieren (v57.7.1: STIL-TITEL-Sektion) ——
    # Die Verbindung: STIL-TITEL aus Etappe 2+3 = Schicht 1 der Synthese.
    # Regex matcht sowohl PRÄGNANZ: (legacy) als auch STIL-TITEL: (v57.7.1).
    praegnanz_sentences = {}
    for label, text in valid_results.items():
        # Versuche PRÄGNANZ-/STIL-TITEL-Zeile zu finden
        match = re.search(
            r'(?:PR[ÄA]GNANZ|STIL-TITEL):\s*(.+?)(?:\n\n|\n[A-Z]|$)',
            text,
            re.DOTALL
        )
        if match:
            praegnanz_text = match.group(1).strip()
            # Erste Zeile nehmen (falls Mehrzeiler)
            first_line = praegnanz_text.split('\n')[0].strip()
            # 'Jetzt komprimiere...' entfernen falls vorhanden
            skip_prefixes = ('Jetzt', 'Maximal', 'Format', 'Kein', 'Bsp', 'Schreibe', 'Nicht', 'Wie')
            if first_line.startswith(skip_prefixes):
                # Fallback: Nächste nicht-Instruction-Zeile
                lines = [l.strip() for l in praegnanz_text.split('\n') if l.strip()]
                for line in lines:
                    if not line.startswith(skip_prefixes) and not line.startswith('['):
                        first_line = line
                        break
            praegnanz_sentences[label] = first_line
        else:
            praegnanz_sentences[label] = "(Kein TITEL-Fazit)"

    logger.info(f"TITEL/PRÄGNANZ extrahiert: {len(praegnanz_sentences)} Quellen")

    # ── DOMINANTE extrahieren (v57.7.1) ──
    dominant_labels = {}
    for label, text in valid_results.items():
        dom_match = re.search(
            r'(?:DIE )?DOMINANTE:\s*(.+?)(?:\n\n|\n[A-ZÄÖÜ]|$)',
            text, re.DOTALL
        )
        if dom_match:
            dom_text = dom_match.group(1).strip()
            first_dom_line = dom_text.split('\n')[0].strip()
            dominant_labels[label] = first_dom_line
        else:
            dominant_labels[label] = "(Keine Dominante)"

    logger.info(f"Dominanten extrahiert: {len(dominant_labels)} Quellen")

    # ── GRUNDOPERATION extrahieren (v57.7.5) ──
    grundoperation_labels = {}
    for label, text in valid_results.items():
        op_match = re.search(
            r'(?:DIE )?GRUNDOPERATION:\\s*(.+?)(?:\\n\\n|\\n[A-ZÄÖÜ]|$)',
            text, re.DOTALL
        )
        if op_match:
            op_text = op_match.group(1).strip()
            first_op_line = op_text.split('\n')[0].strip()
            grundoperation_labels[label] = first_op_line
        else:
            grundoperation_labels[label] = "(Keine Grundoperation)"

    logger.info(f"Grundoperationen extrahiert: {len(grundoperation_labels)} Quellen")

    # ── MODUS extrahieren (v57.7.5) ──
    modus_labels = {}
    for label, text in valid_results.items():
        modus_match = re.search(
            r'MODUS:\\s*(.+?)(?:\\n\\n|\\n[A-ZÄÖÜ]|$)',
            text, re.DOTALL
        )
        if modus_match:
            modus_text = modus_match.group(1).strip()
            first_modus_line = modus_text.split('\n')[0].strip()
            modus_labels[label] = first_modus_line
        else:
            modus_labels[label] = "(Kein Modus)"

    logger.info(f"Modi extrahiert: {len(modus_labels)} Quellen")

    # ── Einzelstatistiken pro Quelle (v57.6.1: Item 4) ──
    # Kompakte Stats fuer die Synthese, damit das LLM nicht aus
    # der Vergleichstabelle piksen muss.
    individual_stats = {}
    for label, stats in etappe1.get("individual", {}).items():
        if "error" in stats:
            continue
        ss = stats.get("sentence_stats", {})
        st = stats.get("sentence_types", {})
        # ── Lyrik-Kennzahlen (v59 Klang-Durchgriff) ──
        vs = stats.get("verse_structure", {})
        vd = stats.get("verse_detail", {})
        rhyme = vd.get("rhyme", {}) if vd else {}
        stanzas = vd.get("stanzas", {}) if vd else {}
        rhythm = vd.get("rhythm", {}) if vd else {}
        enjamb = vd.get("enjambement", {}) if vd else {}
        sound = vd.get("sound_patterns", {}) if vd else {}

        individual_stats[label] = {
            "words": stats.get("text_length_words", 0),
            "sentences": stats.get("sentence_count", 0),
            "avg_sent_len": ss.get("avg_length", 0),
            "median_sent_len": ss.get("median_length", 0),
            "max_sent_len": ss.get("max_length", 0),
            "HS": st.get("HS", 0),
            "NS": st.get("NS", 0),
            "gemischt": st.get("gemischt", 0),
            "TTR": stats.get("type_token_ratio", 0),
            "STTR": stats.get("sttr", 0),
            "morph": stats.get("morphological_complexity", 0),
            "kommas": stats.get("punctuation", {}).get("Komma", 0),
            # Lyrik (v59)
            "lyrik_signal": vs.get("signal_strength", "—"),
            "strophen": stanzas.get("stanza_count", "—"),
            "reim_typ": rhyme.get("rhyme_type", "—"),
            "reim_schema": rhyme.get("scheme_notation", "—"),
            "avg_silben": rhythm.get("avg_syllables", "—"),
            "silben_sigma": rhythm.get("stdev_syllables", "—"),
            "enjambement": enjamb.get("count", "—"),
            "alliterationen": len(sound.get("alliterations", [])) if sound else "—",
            "assonanzen": len(sound.get("assonances", [])) if sound else "—",
        }

    logger.info(f"Kennzahlen aufbereitet: {len(individual_stats)} Quellen")

    if len(valid_results) >= 2:
        synthese_prompt = _build_globale_synthese_prompt(
            etappen_results=valid_results,
            comparison_table_text=comparison_table_text,
            user_question=user_question,
            praegnanz_sentences=praegnanz_sentences,
            individual_stats=individual_stats,
            dominant_labels=dominant_labels,
            grundoperation_labels=grundoperation_labels,
            modus_labels=modus_labels,
        )

        logger.info("🌐 Globale Synthese")
        try:
            globale_synthese = llm_call(
                prompt=synthese_prompt,
                task="synthesis",
                system_instruction=_GLOBALE_SYNTHESE_SYSTEM,
                temperature=0.3,
                max_tokens=MAX_TOKENS_STILISIERUNG,
                domain="stilisierung",
            )
        except Exception as e:
            logger.error(f"❌ Globale Synthese fehlgeschlagen: {e}")
            globale_synthese = f"FEHLER bei Globaler Synthese: {e}"
    else:
        globale_synthese = (
            "Globale Synthese nicht möglich: Weniger als 2 Quellen erfolgreich analysiert."
        )

    # ==========================================================================
    # ERGEBNIS ZUSAMMENSTELLEN
    # ==========================================================================
    elapsed = time.time() - start_time
    metadata["elapsed_seconds"] = round(elapsed, 1)
    metadata["valid_sources"] = len(valid_results)

    result = {
        "etappe1": etappe1,
        "etappen_2_3": etappen_2_3,
        "globale_synthese": globale_synthese,
        "metadata": metadata,
    }

    logger.info(
        f"✅ STILISTIC LAB abgeschlossen: {len(valid_results)}/{total_sources} "
        f"Quellen analysiert in {elapsed:.1f}s"
    )

    return result


# ==============================================================================
# META-VERGLEICH: Vergleich zweier analytischer Texte auf Methode & Leistung
# ==============================================================================

_META_VERGLEICH_SYSTEM = """Du bist ein Methoden-Vergleichs-Analyst.
Du vergleichst zwei analytische Verfahren auf ihre Methode und ihre Leistung.
Nicht: welcher ist besser.
Sondern: was sieht jeder, was der andere nicht sieht — und warum.

METHODISCHE GRUNDHALTUNG:
Du vergleichst WERKZEUGE, nicht ERGEBNISSE.
Ein Hammer ist nicht besser als ein Sägeblatt — aber er schlägt
Nägel ein, und das Sägeblatt nicht.
Die Frage ist nicht: Welches Verfahren gewinnt?
Die Frage ist: Welches Verfahren sieht was — und wo ist es blind?

STRIKTE REGELN:
- Jede Behauptung MUSS durch Zitat aus dem jeweiligen Text belegt sein
- Keine Harmonisierung: Wenn die Methoden widersprüchlich sind,
  benenne den Widerspruch
- Kein Rangieren: Nicht "A ist überlegen", sondern
  "A sieht X, B sieht Y"
- Keine Synthese am Ende: Der Vergleich IST das Ergebnis"""


def _build_meta_vergleich_prompt(
    text_a: str,
    label_a: str,
    text_b: str,
    label_b: str,
    user_question: str = "",
) -> str:
    """
    Baut den Prompt für den Meta-Vergleich.

    Fünf-Achsen-Architektur:
    1. KONVERGENZEN  — Wo sehen beide dasselbe?
    2. DIVERGENZEN   — Wo sieht die eine Seite, was die andere verfehlt?
    3. KOMPLEMENTARITÄT — Wo ergänzen sie sich methodisch?
    4. GRENZEN       — Wo versagt jedes Verfahren jeweils?
    5. SYSTEMATISCHER ERTRAG — Was bedeutet der Vergleich für beide Verfahren?

    Args:
        text_a:        Erster analytischer Text (z.B. Tynjanow Conclusio)
        label_a:       Label für Seite A (z.B. "Tynjanow")
        text_b:        Zweiter analytischer Text (z.B. HRE Best-of + Lab)
        label_b:       Label für Seite B (z.B. "HRE")
        user_question: Optionale benutzerdefinierte Frage
    """
    prompt = f"""META-VERGLEICH: METHODE UND LEISTUNG

--- SEITE A: {label_a} ---
{text_a}

--- SEITE B: {label_b} ---
{text_b}

---

VERGLEICHS-AUFGABE:

1. KONVERGENZEN:
Wo kommen beide Verfahren zu denselben oder ähnlichen Beobachtungen?
Welche Erkenntnisse sind gemeinsamer Besitz — unabhängig von der Methode?
Belege jede Konvergenz mit je einem Zitat aus beiden Seiten.

2. DIVERGENZEN:
Wo sieht die eine Methode etwas, das die andere nicht sieht?
Wo übersieht die eine Seite etwas, das die andere erfasst?
Benenne mindestens 2 Divergenzen.
Belege jede Divergenz mit Zitaten.

3. KOMPLEMENTARITÄT:
Wo ergänzen sich die Verfahren methodisch?
Wo liefert das eine, was dem anderen fehlt — nicht weil es besser ist,
sondern weil es anders vorgeht?
Ist die Komplementarität strukturell (verschiedene Gegenstände)
oder perspektivisch (verschiedene Blicke auf denselben Gegenstand)?

4. GRENZEN:
Wo versagt jedes Verfahren jeweils?
Welche Fragen kann Tynjanows relationale Methode nicht stellen —
und welche kann die HRE-Multi-Perspektiven-Analyse nicht beantworten?
Benenne die blinde Stelle JEDES Verfahrens mit je einem Beispiel.

5. SYSTEMATISCHER ERTRAG:
Was lehrt dieser Vergleich über beide Verfahren?
Nicht: welches ist besser. Sondern: was wird erst durch den Vergleich
sichtbar, das keine Methode allein sehen kann?
Formuliere eine These, die falsifizierbar ist:
Was würde sie widerlegen?"""

    if user_question and user_question.strip():
        prompt += f"""

FRAGE: {user_question.strip()}
Beantworte diese Frage auf Basis des Vergleichs oben."""

    return prompt


def run_meta_vergleich(
    text_a: str,
    label_a: str,
    text_b: str,
    label_b: str,
    progress_callback=None,
    user_question: str = "",
) -> Dict:
    """
    Führt einen Meta-Vergleich zweier analytischer Texte durch.

    Keine Etappe-1-Pipeline, keine pro-Quelle-Analyse.
    Einzelner LLM-Call mit 5-Achsen-Vergleichs-Prompt.

    Args:
        text_a:          Erster analytischer Text
        label_a:         Label für Seite A (z.B. "Tynjanow")
        text_b:          Zweiter analytischer Text
        label_b:         Label für Seite B (z.B. "HRE")
        progress_callback: Optional: Callback(status_msg) für UI-Updates
        user_question:    Optionale benutzerdefinierte Frage

    Returns:
        Dict mit:
        - vergleich: String (das Vergleichsergebnis)
        - metadata: timing, model, labels, etc.
    """
    start_time = time.time()
    metadata = {
        "mode": "meta_vergleich",
        "label_a": label_a,
        "label_b": label_b,
        "model": get_model_for_task("synthesis"),
        "user_question": user_question if user_question else "",
        "chars_a": len(text_a),
        "chars_b": len(text_b),
    }

    if progress_callback:
        progress_callback(f"Meta-Vergleich: {label_a} vs. {label_b}...")

    logger.info(f"🔬 Meta-Vergleich: {label_a} vs. {label_b}")

    prompt = _build_meta_vergleich_prompt(
        text_a=text_a,
        label_a=label_a,
        text_b=text_b,
        label_b=label_b,
        user_question=user_question,
    )

    try:
        vergleich = llm_call(
            prompt=prompt,
            task="synthesis",
            system_instruction=_META_VERGLEICH_SYSTEM,
            temperature=0.3,
            max_tokens=MAX_TOKENS_STILISIERUNG,
            domain="stilisierung",
        )
    except Exception as e:
        logger.error(f"❌ Meta-Vergleich fehlgeschlagen: {e}")
        vergleich = f"FEHLER bei Meta-Vergleich: {e}"

    elapsed = time.time() - start_time
    metadata["elapsed_seconds"] = round(elapsed, 1)

    result = {
        "vergleich": vergleich if vergleich else "(Leere LLM-Antwort)",
        "metadata": metadata,
    }

    logger.info(
        f"✅ Meta-Vergleich abgeschlossen: {label_a} vs. {label_b} in {elapsed:.1f}s"
    )

    return result


def format_meta_vergleich_as_markdown(result: Dict) -> str:
    """
    Formatiert das Ergebnis des Meta-Vergleichs als Markdown-Download.

    Args:
        result: Dict von run_meta_vergleich()

    Returns:
        Markdown-String.
    """
    meta = result.get("metadata", {})
    lines = []

    lines.append("---")
    lines.append("META-VERGLEICH — Methoden- und Leistungsvergleich")
    lines.append(f"Engine: HRE v59")
    lines.append(f"Seite A: {meta.get('label_a', '?')} ({meta.get('chars_a', '?')} Zeichen)")
    lines.append(f"Seite B: {meta.get('label_b', '?')} ({meta.get('chars_b', '?')} Zeichen)")
    lines.append(f"Modell: {meta.get('model', '?')}")
    lines.append(f"Dauer: {meta.get('elapsed_seconds', '?')}s")
    uq = meta.get('user_question', '')
    if uq:
        lines.append(f"Frage: {uq}")
    lines.append("---")
    lines.append("")
    lines.append(result.get("vergleich", ""))

    return "\n".join(lines)


# ==============================================================================
# FORMATIERUNG: ERGEBNIS ALS MARKDOWN
# ==============================================================================

def format_result_as_markdown(result: Dict) -> str:
    """
    Formatiert das Ergebnis der Pipeline als Markdown-Download.

    Args:
        result: Dict von run_stilistic_lab()

    Returns:
        Markdown-String.
    """
    meta = result.get("metadata", {})
    lines = []

    # Header
    lines.append("---")
    lines.append("STILISTIC LAB — Drei-Etappen-Analyse")
    lines.append(f"Engine: HRE v57.7.5")
    lines.append(f"Quellen: {meta.get('source_count', '?')}")
    lines.append(f"Modell Etappe 2+3: {meta.get('model_etappe_2_3', '?')}")
    lines.append(f"Modell Synthese: {meta.get('model_synthese', '?')}")
    lines.append(f"Dauer: {meta.get('elapsed_seconds', '?')}s")
    uq = meta.get('user_question', '')
    if uq:
        lines.append(f"Frage: {uq}")
    lines.append("---")
    lines.append("")

    # Etappe 1: Vergleichstabelle
    lines.append("## Etappe 1: SEZIEREN (Python-Analyse)")
    lines.append("")
    comparison = result.get("etappe1", {}).get("comparison_table", [])
    if comparison:
        # Markdown-Tabelle
        headers = ["Quelle", "Wörter", "Sätze", "Ø Satzl.", "HS", "NS", "Gem.", "TTR", "Morph", "Kommas", "Lyrik", "Stroph.", "Reim", "Ø Silb.", "Enjamb."]
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
        for row in comparison:
            values = [
                str(row.get("Quelle", "—")),
                str(row.get("Wörter", "—")),
                str(row.get("Sätze", "—")),
                str(row.get("Ø Satzlänge", "—")),
                str(row.get("HS", "—")),
                str(row.get("NS", "—")),
                str(row.get("Gemischt", "—")),
                f"{row.get('TTR', 0):.3f}",
                f"{row.get('Morph.Kompl.', 0):.1f}",
                str(row.get("Kommas", "—")),
                # Lyrik-Spalten (v59)
                str(row.get("Lyrik", "—")),
                str(row.get("Strophen", "—")),
                str(row.get("Reim", "—")),
                str(row.get("Ø Silben", "—")),
                str(row.get("Enjamb.", "—")),
            ]
            lines.append("| " + " | ".join(values) + " |")
    lines.append("")

    # Etappe 1: Individual-Statistiken (v57.5.1 Fix A)
    individual = result.get("etappe1", {}).get("individual", {})
    for lbl, stats in individual.items():
        if "error" in stats:
            continue
        lines.append(f"### {lbl} — Detail-Statistiken")
        lines.append("")

        ss = stats.get("sentence_stats", {})
        st_obj = stats.get("sentence_types", {})
        lines.append(f"- **Wörter:** {stats.get('text_length_words', '?')}")
        lines.append(f"- **Zeichen:** {stats.get('text_length_chars', '?')}")
        lines.append(f"- **Sätze:** {stats.get('sentence_count', '?')}")
        lines.append(f"- **Ø Satzlänge:** {ss.get('avg_length', '?')} Wörter")
        lines.append(f"- **Median Satzlänge:** {ss.get('median_length', '?')} Wörter")
        lines.append(f"- **Max Satzlänge:** {ss.get('max_length', '?')} Wörter")
        lines.append(f"- **HS:** {st_obj.get('HS', 0)} | **NS:** {st_obj.get('NS', 0)} | **Gemischt:** {st_obj.get('gemischt', 0)}")
        lines.append(f"- **TTR:** {stats.get('type_token_ratio', 0):.3f} | **STTR:** {stats.get('sttr', 0):.3f}")
        lines.append(f"- **Morphologische Komplexität:** {stats.get('morphological_complexity', 0):.1f}")

        # Interpunktion
        punct = stats.get("punctuation", {})
        punct_active = {k: v for k, v in punct.items() if v > 0}
        if punct_active:
            lines.append(f"- **Interpunktion:** {', '.join(f'{k}: {v}' for k, v in punct_active.items())}")

        # Inhaltswörter
        top_content = stats.get("top_content_words", [])
        if top_content:
            lines.append(f"- **Häufigste Inhaltswörter:** {' | '.join(f'{w} ({c}x)' for w, c in top_content[:8])}")

        # Bigramme
        bigrams = stats.get("bigrams", [])
        if bigrams:
            lines.append(f"- **Bigramme:** {' | '.join(f'{g} ({c}x)' for g, c in bigrams[:5])}")

        # Absätze
        ps = stats.get("paragraph_stats", {})
        if ps:
            lines.append(f"- **Absätze:** {ps.get('count', '?')} (Ø {ps.get('avg_chars', '?')} Zeichen, σ {ps.get('length_variance', '?')})")

        # Hotspot-Sätze
        hotspots = stats.get("hotspot_sentences", [])
        if hotspots:
            lines.append("")
            lines.append("**Hotspot-Sätze:**")
            for i, hs in enumerate(hotspots, 1):
                reasons = ", ".join(hs.get("reasons", ["—"]))
                sent_preview = hs["sentence"][:150] + ("..." if len(hs["sentence"]) > 150 else "")
                lines.append(f"{i}. Score {hs['score']:.2f} ({reasons}): \"{sent_preview}\"")

        # ── VERSSTRUKTUR / Klang-Analytik (v59 Klang-Durchgriff) ──
        vs = stats.get("verse_structure", {})
        vd = stats.get("verse_detail", {})
        if vs.get("is_likely_verse") and vd:
            lines.append("")
            lines.append("**── VERSSTRUKTUR ──**")
            lines.append(f"- **Lyrik-Signal:** {vs.get('signal_strength', '?')} "
                        f"(Ø {vs.get('avg_words_per_line', 0)} Wörter/Zeile, "
                        f"σ {vs.get('stdev_words_per_line', 0)})")

            # Strophen
            vstanzas = vd.get("stanzas", {})
            if vstanzas.get("stanza_count", 0) > 0:
                lines.append(f"- **Strophen:** {vstanzas['stanza_count']} "
                            f"({vstanzas.get('stanza_pattern', '')})")

            # Rhythmus
            vrhythm = vd.get("rhythm", {})
            if vrhythm.get("avg_syllables", 0) > 0:
                lines.append(f"- **Rhythmus:** {vrhythm.get('pattern_description', '')} "
                            f"(Ø {vrhythm['avg_syllables']} Silben, "
                            f"σ {vrhythm.get('stdev_syllables', 0)})")
                syl = vrhythm.get("syllables_per_line", [])
                if syl:
                    lines.append(f"  - Silben pro Vers: {syl}")

            # Reimschema
            vrhyme = vd.get("rhyme", {})
            if vrhyme.get("scheme_notation"):
                lines.append(f"- **Reimschema:** {vrhyme['scheme_notation']} "
                            f"({vrhyme.get('rhyme_type', '')})")
                for pair in vrhyme.get("rhyme_pairs", [])[:6]:
                    lines.append(f"  - {pair['label']}: {pair['word_a']} / {pair['word_b']} "
                                f"(V.{pair['line_a']}+V.{pair['line_b']})")

            # Enjambements
            venjamb = vd.get("enjambement", {})
            enj_count = venjamb.get("count", 0)
            if enj_count > 0:
                lines.append(f"- **Enjambements:** {enj_count} "
                            f"({venjamb.get('percentage', 0)}% der Zeilenübergänge)")
                for ej in venjamb.get("enjambements", [])[:4]:
                    lines.append(f"  - V.{ej['from_line']}→V.{ej['to_line']}: "
                                f"...{ej['fragment_a']} | {ej['fragment_b']}...")

            # v59.2: Vokalgerüste aus Markdown entfernt (unlesbar)

            # Vokal-Echos (v59.2: mit Trivial-Filter)
            vechoes_data = vd.get("vowel_echoes", {})
            vechoes = vechoes_data.get("echoes", []) if isinstance(vechoes_data, dict) else vechoes_data if isinstance(vechoes_data, list) else []
            trivial_vowel = vechoes_data.get("trivial_vowel") if isinstance(vechoes_data, dict) else None
            trivial_ratio = vechoes_data.get("trivial_ratio", 0.0) if isinstance(vechoes_data, dict) else 0.0

            if trivial_vowel:
                lines.append(f"- **Vokal-Hinweis:** Endvokal '{trivial_vowel}' dominiert "
                            f"({trivial_ratio:.0%} der Zeilenenden) — Echos daraus sind trivial und werden nicht gezeigt.")
            if vechoes:
                lines.append("- **Vokal-Echos (nicht-triviale Endvokal-Übereinstimmungen):**")
                for ve in vechoes[:8]:
                    lines.append(f"  - V.{ve['line_a']}→V.{ve['line_b']}: "
                                f"Endvokal '{ve['end_vowel']}' (Abstand {ve['distance']})")
            elif not trivial_vowel:
                lines.append("- **Vokal-Echos:** keine signifikanten Übereinstimmungen gefunden.")

            # Klangfiguren
            vsound = vd.get("sound_patterns", {})
            allit = vsound.get("alliterations", [])
            asson = vsound.get("assonances", [])
            innen = vsound.get("internal_rhymes", [])
            if allit or asson or innen:
                lines.append("- **Klangfiguren:**")
                for a in allit[:5]:
                    lines.append(f"  - Alliteration ({a['consonant'].upper()}): "
                                f"{', '.join(a['words'][:4])}  [V.{a['line']}]")
                for a in asson[:5]:
                    lines.append(f"  - Assonanz ({a['vowel_pattern']}): "
                                f"{a['word_a']} / {a['word_b']}  [V.{a['line']}]")
                for ir in innen[:3]:
                    lines.append(f"  - Binnenreim: {ir['word_a']} / {ir['word_b']}  [V.{ir['line']}]")

        lines.append("")
        lines.append("---")
        lines.append("")

    # Etappe 2+3: Pro Quelle
    lines.append("## Etappe 2+3: Beobachtungen pro Quelle")
    lines.append("")
    for label, text in result.get("etappen_2_3", {}).items():
        lines.append(f"### {label}")
        lines.append("")
        lines.append(text)
        lines.append("")
        lines.append("---")
        lines.append("")

    # Globale Synthese
    lines.append("## Globale Synthese")
    lines.append("")
    lines.append(result.get("globale_synthese", "(Keine Synthese verfügbar)"))
    lines.append("")

    return "\n".join(lines)
