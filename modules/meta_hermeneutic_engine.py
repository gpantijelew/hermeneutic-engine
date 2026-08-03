# modules/meta_hermeneutic_engine.py — v2.8
"""
Meta-Hermeneutic Engine — Rekursive Hermeneutik für die HRE.

Drei-Stufen-Architektur (Architektur-Entscheidungen #37-41):
  Stufe 1: META-SEZIEREN (#37)  — Python (deterministisch)
           Extrahiert Strukturdaten aus N Synthese-Outputs
  Stufe 2: META-BEOBACHTEN (#38 + #39) — LLM (Flash)
           Vergleicht, kodiert, bewertet Stabilität
  Stufe 3: META-DESTILLATION (#41) — LLM (Pro)
           Synthetisiert den harten Befund

Validiert durch: Manuelle Stabilitäts-Analyse von 17 Synthese-Runs (2026-06-13)

v2.8-Verbesserungen (2026-06-15):
- NEU: Meta-Meta-Ebene — SEZIEREN erkennt jetzt auch Meta-Hermeneutic-Outputs
  (META-DESTILLATION / META-BEOBACHTEN / META-SEZIEREN) als Eingabeformat,
  nicht nur Stilistic-Lab-Synthesen (GLOBALE SYNTHESE / KERNHYPOTHESE / FAZIT).
  Mapping: META-DESTILLATION → KERNHYPOTHESE, META-BEOBACHTEN → BEWEISFÜHRUNG,
  FREIER RAUM innerhalb BEOBACHTEN → FREIER RAUM, letzter Satz DESTILLATION → FAZIT.
- NEU: _detect_meta_hermeneutic_file() — Erkennung über META-DESTILLATION-Heading
- NEU: _extract_meta_header() — Extrahiert Version, Runs, Dauer, Modelle, Etappe-1
- NEU: Zusätzliche Felder in sezieren-results: source_type, meta_version,
  meta_runs, meta_dauer, meta_has_etappe1, meta_sezieren_table
- FIX: Abschnitts-Extraktion für META-Dateien mit korrekter End-Detection
  (META-BEOBACHTEN enthält ##-Unterüberschriften, die nicht als
  Sektionsgrenze gelten dürfen; Ende = META-DESTILLATION-Heading)

v2.7.1-Verbesserungen (2026-06-14):
- FIX: Etappe-1-Hinweis aktualisiert — BEOBACHTEN-Prompt informiert jetzt
  über die v59.9-Verbesserungen der griechischen Analyse (Kopula-Filter,
  Strophen-Korrektur, Funktionswort-Bigramme). Hilft dem LLM, die
  verbesserten Etappe-1-Daten korrekt zu interpretieren.

v2.7-Verbesserungen (2026-06-14):
- NEU: meta_freie_frage() — Beantwortet gezielte Fragen zu SEZIEREN-Daten auf
  Meta-Ebene. Nutzt dieselbe Modell-Konfig wie BEOBACHTEN (Flash).
  System-Prompt verlangt präzise Antworten mit konkreten Run-Nummern und
  Zitaten. Optional: Etappe-1-Kennzahlen + BEOBACHTEN-Befund als Kontext.
- NEU: Parameter freie_frage in run_meta_hermeneutic() — wenn übergeben,
  wird NUR SEZIEREN + TERMINI + FREIE FRAGE ausgeführt (KEINE VOLLANALYSE).
  metadata["mode"] = "meta_freie_frage". Ergebnis enthält Schlüssel
  "meta_freie_frage" mit der Antwort.
- NEU: FREIE FRAGE-Abschnitt in format_meta_result_as_markdown() — zeigt
  Frage + Antwort, wenn result["meta_freie_frage"] existiert.

v2.6-Verbesserungen (2026-06-13):
- FIX: ENTWICKLUNGSLINIE (Abschnitt 6b) — war zu unscharf, lieferte nur generelle
  Tendenz („entwickelt sich zu metatheoretischer Reflexion") statt konkreter
  Evidenz. NEU: Der Prompt fordert jetzt BELEGE aus konkreten Runs: WELCHE
  Akteure werden präziser? WELCHE Termini stabilisieren sich? Gibt es einen
  Wendepunkt? Statt „KURZ ABER PRÄZISE" jetzt „MIT BELEGEN AUS KONKRETEN RUNS".
  Die Engine muss mindestens 3 konkrete Beispiele geben (R-Nummern + Zitate).
  Form geändert von [KURZ ABER PRÄZISE] zu [MIT BELEGEN].
- FIX: Etappe-1-Daten erhalten jetzt einen neuen Abschnitt KOMPOSITA/WORTSCHÖPFUNGEN
  pro Quelle — systematisch extrahierte zusammengesetzte Wörter (Bindestrich-
  Komposita, Präfix-Komposita, ungewöhnliche Wortbildungen). Vorher fehlte
  diese Datensammlung komplett — die HRE musste Komposita mühsam aus
  Hotspot-Sätzen heraussuchen. Die text_analyzer_pipeline (v59.6) erzeugt
  jetzt diesen Abschnitt automatisch.
- FIX: Ursprungssprache-Statistiken — das Original (Quelle 4) hatte bisher
  Wörter:0, TTR:0.000, Morph:0.0 und keine Komposita. Die Pipeline erzeugt
  jetzt auch für das Original Wortstatistiken inkl. Komposita-Erkennung.

v2.5-Verbesserungen (2026-06-13):
- FIX: EBENE 2 arbeitet jetzt VERGLEICHEND — wenn ein Wort bei einer Übersetzung
  auffällt, MUSS es auch im Original und bei den anderen Übersetzungen gesucht
  werden. Die Etappe-1-Daten enthalten Hotspot-Sätze von ALLEN Quellen.
  „бронзово-острое" bei Starikovskij → Wie klingt das Original? Wie übersetzen
  die anderen? Vorher wurde jede Übersetzung isoliert befragt.
- NEU: Abschnitt 6b ENTWICKLUNGSLINIE — eigener Abschnitt zwischen Methodischer
  Diagnose und Beste Ergebnisse. Die Engine soll selbst entdecken und benennen,
  ob es eine Entwicklung von Run 1 zu Run N gibt. Keine Vorgabe welcher Akteur
  oder welche Art von Entwicklung. Aus Abschnitt 3 entfernt und eigenständig gemacht.
- FIX: Sprachregister-Framing von „Gelingen/Bewertung" zu „argumentierter Darstellung"
  umgestellt. Keine Wertung wie „gelingt/nicht gelingt" — stattdessen:
  WIE funktionieren Wortschöpfungen sprachlich? Morphologisch transparent/opak?
  Semantisch klar/dunkel? Motiviert durch das Original oder eigene Erfindung?
  Die Fakten sollen sprechen, nicht das Urteil.
- NEU: ZWEI FRAGEN an jede Wortschöpfung in EBENE 2:
  (i) MOTIVATION — Nachbildung einer poetischen Vorlage oder eigene Erfindung?
  (ii) ARGUMENTIERTE DARSTELLUNG — morphologisch, semantisch, rhythmisch.
  Nur eigene Erfindungen sind hermeneutisch riskant.
- FIX: Abschnitt 8(c) von „DISKREPANZ: Pipeline kritik" zu „WAS DIE META-EBENE SIEHT"
  umgestellt. Die Meta-Ebene liefert die Argumentation, die die einzelnen Runs nicht
  liefern — anstatt die Pipeline zu kritisieren. Wir kennen unsere Pipeline-Grenzen.
- FIX: „Epitheton" entfernt — zu konkret. Stattdessen: „poetische Vorlage des Originals".
- NEU: ENTWICKLUNGSLINIE in Abschnitt 3 — Die Engine soll selbst entdecken und benennen,
  ob es eine Entwicklung von Run 1 zu Run N gibt (schärfer, tiefer, stabiler).
  Keine Vorgabe welcher Akteur oder welche Art von Entwicklung.

v2.4.2-Verbesserungen (2026-06-13):
- FIX: Sprachregister-Prompt traditionsneutral — kein "Homer" / "Altgriechisch" mehr
  hardcodiert. Stattdessen: "das Original" / "die Ursprungssprache". Funktioniert
  jetzt für biblische, epische, poetische und jede andere Texttradition.
- FIX: Sprachregister-Framing von negativ („zumutbar") zu poetisch-positiv umgestellt:
  „Gelingen diese Wortschöpfungen poetisch? Klingen sie künstlerisch überzeugend,
  plausibel, lebendig — oder fremd und erzwungen?" Wortschöpfungen als poetische
  Akte, nicht als Last. „Künstlich" → „Wortschöpfung" wo möglich;
  „zumutbar" vollständig entfernt.

v2.4-Architektur-Verbesserungen (2026-06-13):
- NEU: Etappe-1-Daten (Sprachregister) in BEOBACHTEN — die Engine sieht jetzt
  die objektiven linguistischen Kennzahlen der ÜBERSETZUNGEN selbst:
  Morphologische Komplexität, TTR, Enjambement-Rate, Rhythmus, Klangfiguren,
  Hotspot-Sätze mit Originaltext. Damit kann BEOBACHTEN selbst entdecken,
  ob eine Übersetzung zugänglich oder künstlich, nah oder distanziert klingt.
- NEU: Abschnitt 8 "SPRACHREGISTER DER ÜBERSETZUNGEN" in BEOBACHTEN —
  zwei Perspektiven: (a) Beobachtung der Sprache (objektive Daten) und
  (b) Schlussfolgerung: Wie klingt die Übersetzung? (qualitative Wirkung).
  Keine Vorgabe was gefunden werden soll — die HRE entdeckt selbst.
- NEU: 9. Satz "DAS SPRACHREGISTER" in DESTILLATION — In welchem Register
  sprechen die Übersetzungen? Und gibt es eine Diskrepanz zwischen dem Register
  der Übersetzung und dem Register, in dem die Pipeline sie beschreibt?
- NEU: etappe1_text Parameter in run_meta_hermeneutic() — der vollständige
  Etappe-1-Text (Vergleichstabelle + Detail-Statistiken) wird direkt an
  BEOBACHTEN übergeben. Variante A: volle Daten, keine Verdichtung.
  Die HRE soll selbst entdecken, was relevant ist.

v2.3-Architektur-Verbesserungen (nach drittem Test 2026-06-13):
- NEU: Beweisführung (gekürzt, 400 Zchn/Run) in BEOBACHTEN — liefert Argumente,
  nicht nur Termini. Wichtig für Akteure deren Profil von der Pipeline inkonsistent
  erfasst wird (die HRE muss selbst entdecken WEN das betrifft).
- NEU: Abschnitt 7 "BESTE ERGEBNISSE" im BEOBACHTEN-Prompt — fragt nach den
  tiefsten, präzisesten Funden UNABHÄNGIG von Häufigkeit. Korrigiert den Bias,
  dass nur Häufiges = Wichtiges gilt.
- NEU: 8. Satz "DER BESTE FUND" in DESTILLATION — das aufschlussreichste
  Ergebnis der gesamten Analyse, auch wenn es nur 1/17 mal auftaucht.
- FIX: BEOBACHTEN max_tokens=32768 (vorher 16384 — Abschnitt 6 brach ab)

v2.2-Hotfixes:
- FIX: BEOBACHTEN max_tokens 8192→16384, Prompt KOMPAKT/AUSFÜHRLICH
- FIX: DESTILLATION max_tokens 4096, Lücken explizit benennen

v2.1-Hotfixes:
- FIX: DESTILLATION-Section → BEWEISFÜHRUNG, _detect_authors, 429 Rate Limit

ÖFFENTLICHE API:
    from modules.meta_hermeneutic_engine import run_meta_hermeneutic, meta_freie_frage

    result = run_meta_hermeneutic(synthesis_files, progress_callback=cb,
                                  etappe1_text=etappe1_str)
    # result = {meta_sezieren, meta_beobachten, meta_destillation, meta_freie_frage, metadata}

    # Oder: FREIE FRAGE-Modus
    result = run_meta_hermeneutic(synthesis_files, progress_callback=cb,
                                  freie_frage="Wird X in späteren Runs häufiger?")
    # result = {meta_sezieren, meta_freie_frage, metadata}  (kein beobachten/destillation)

    # Oder: meta_freie_frage() direkt aufrufen
    antwort = meta_freie_frage(frage="...", sezieren_results=[...],
                               etappe1_text=etappe1_str, beobachtung=beob_str)
"""

import json
import logging
import re
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional

from modules.llm_wrapper import llm_call
from modules.config import (
    get_model_for_task,
)

logger = logging.getLogger(__name__)

# v2.4: Eigene Token-Limits
_META_BEOBACHTEN_MAX_TOKENS = 32768  # v2.3: 16384 reichte nicht für 6+ Abschnitte
_META_DESTILLATION_MAX_TOKENS = 4096  # v2.4: 9 Sätze, ausführlich


# ==============================================================================
# STUFE 1: META-SEZIEREN (#37) — Python (deterministisch)
# ==============================================================================

def _extract_section(text: str, heading: str) -> str:
    """
    Extrahiert den Text unter einer Markdown-Überschrift bis zur
    nächsten Überschrift oder Dateiende.

    Robuste Version, erprobt in extract_kern_fazit.py (17/17 Erfolg).

    v2.1-FIX: End-Detection erkennt nur noch ###-Überschriften,
    nicht mehr **fettgedruckten** Inhalt (der BEWEISFÜHRUNG enthält
    fette Zwischenüberschriften die keine Sektionsgrenzen sind).

    Args:
        text:    Gesamter Markdown-Text
        heading: Überschrift ohne # (z.B. "GLOBALE SYNTHESE", "FAZIT")
    """
    pattern = (
        r'(?:^|\n)'
        r'(?:#{1,4}\s*)?'           # Optionale #-Präfixe
        r'\*{0,2}'                   # Optionale **-Präfixe
        + re.escape(heading) +
        r'\*{0,2}'                   # Optionale **-Suffixes
        r'[^\n]*\n'                  # Rest der Überschriftszeile
    )
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return ""

    rest = text[match.end():]

    # Ende: nächste ### oder ## Überschrift (NICHT **fett** im Inhalt!)
    end_match = re.search(r'\n#{1,4}\s', rest)
    if end_match:
        return rest[:end_match.start()].strip()
    return rest.strip()


def _extract_kernhypothese(text: str) -> str:
    """
    Extrahiert den ersten Absatz unter 'Globale Synthese'.

    Die Kernhypothese ist der ERSTE Absatz nach der Überschrift,
    vor der ersten Unterüberschrift (HYPOTHESE, BEWEISFÜHRUNG etc.).
    Nur dieser Absatz wie vom Benutzer explizit gefordert: 'Ausschliesslich!'

    v59.9.10 (Patch 2026-06-28 3c): STILISTIC-LAB Inline-Marker erkannt.
    Das STILISTIC-LAB-Format hat oft einen Inline-Marker, bei dem
    das Marker-Wort und der eigentliche Text im selben Absatz stehen,
    getrennt durch einen einfachen Zeilenumbruch. Die Vorverarbeitung
    wandelt solche Inline-Marker in alleinstehende Marker um, damit
    der bestehende Parser sie erkennt.
    """
    # v59.10.6 Fix: Doppelte Header-Struktur behandeln.
    # STILISTIC LAB produziert:
    #   ## Globale Synthese          (H2 — Sektions-Header in .md-Datei)
    #   ### GLOBALE SYNTHESE          (H3 — LLM-Output-Header)
    #   #### HYPOTHESE                (H4 — LLM-Output-Header)
    #   Die Texte von Autor A...      (Hypothese-Text)
    #
    # _extract_section("GLOBALE SYNTHESE") findet das H2 zuerst und
    # interpretiert das H3 als End-Marker — alles wird abgeschnitten.
    #
    # Lösung: Suche direkt nach dem H3-Header "### GLOBALE SYNTHESE"
    # und nehme alles danach. Falls nicht gefunden, falle zurück auf
    # _extract_section.
    content = ""
    # Suche nach H3-Header "### GLOBALE SYNTHESE"
    h3_match = re.search(r'^###\s+GLOBALE\s+SYNTHESE', text, re.MULTILINE | re.IGNORECASE)
    if h3_match:
        # Nehme alles nach dem H3-Header
        nl = text.find('\n', h3_match.end())
        content = text[nl+1:].strip() if nl >= 0 else text[h3_match.end():].strip()
    else:
        # Fallback: _extract_section
        content = _extract_section(text, "GLOBALE SYNTHESE")
    if not content:
        # Fallback: suche "Globale Synthese" irgendwo
        m = re.search(r'Globale\s+Synthese', text, re.IGNORECASE)
        if m:
            nl = text.find('\n', m.start())
            start = nl + 1 if nl >= 0 else m.end()
            rest = text[start:]
            # v2.1: Nur ### headings, nicht ** bold
            end = re.search(r'\n#{1,4}\s', rest)
            content = rest[:end.start()].strip() if end else rest.strip()

    if content:
        # v59.9.10: Vorverarbeitung fuer Inline-Marker.
        # Ein Inline-Marker ist ein Marker-Wort gefolgt von einem
        # einfachen Zeilenumbruch und dann Text (keine Leerzeile).
        # Die Vorverarbeitung fuegt eine zusaetzliche Leerzeile ein,
        # damit der Marker ein eigener Absatz wird.
        inline_marker_re = re.compile(
            r'(\*{0,2}\s*(?:HYPOTHESE|BEWEISFÜHRUNG|FAZIT|KENNZAHLEN[- ]ÜBERRASCHUNG|'
            r'FREIER RAUM|UNTERSUCHUNGSFRAGE|DESTILLATION)\s*[:*]*)\n(?!\n)',
            re.IGNORECASE
        )
        content = inline_marker_re.sub(r'\1\n\n', content)

        # Marker und Header ueberspringen, bis echter Absatz gefunden wird.
        paragraphs = content.split('\n\n')
        marker_pattern = re.compile(
            r'^\s*\*{0,2}\s*(HYPOTHESE|BEWEISFÜHRUNG|FAZIT|KENNZAHLEN[- ]ÜBERRASCHUNG|'
            r'FREIER RAUM|UNTERSUCHUNGSFRAGE|DESTILLATION)\s*[:*]*\s*$',
            re.IGNORECASE
        )
        header_pattern = re.compile(r'^#{1,6}\s+')
        for para in paragraphs:
            stripped = para.strip()
            if not stripped:
                continue
            # Marker-Wort oder Header? -> ueberspringen
            if marker_pattern.match(stripped):
                continue
            if header_pattern.match(stripped):
                continue
            # Echter Absatz gefunden -> zurueckgeben
            return stripped
        # Fallback: erster nicht-leerer Absatz
        for para in paragraphs:
            if para.strip():
                return para.strip()
    return ""


def _extract_fazit(text: str) -> str:
    """Extrahiert den FAZIT-Abschnitt (komplett, nicht nur ersten Absatz)."""
    return _extract_section(text, "FAZIT")


def _extract_beweisfuehrung(text: str) -> str:
    """Extrahiert den BEWEISFÜHRUNG-Abschnitt.
    
    v2.1: DESTILLATION existiert nicht als eigene Section in den 
    Synthese-Outputs. Die Termini sind in BEWEISFÜHRUNG eingebettet.
    """
    return _extract_section(text, "BEWEISFÜHRUNG")


def _extract_freier_raum(text: str) -> str:
    """Extrahiert den FREIER RAUM-Abschnitt."""
    return _extract_section(text, "FREIER RAUM")


def _extract_hypothese(text: str) -> str:
    """Extrahiert den HYPOTHESE-Abschnitt."""
    return _extract_section(text, "HYPOTHESE")


# ==============================================================================
# META-HERMENEUTIC FILE DETECTION & EXTRACTION (v2.8 — Meta-Meta-Ebene)
# ==============================================================================

def _detect_meta_hermeneutic_file(text: str) -> bool:
    """
    Erkennt, ob eine Datei ein Meta-Hermeneutic-Output ist
    (statt eines Stilistic-Lab-Synthese-Outputs).

    Kriterien (eines reicht):
    1. META-DESTILLATION als Ueberschrift (VOLLANALYSE-Modus)
    2. Header '# Meta-Hermeneutic Analyse' + Sektion 'FREIE FRAGE'
       (FREIE FRAGE-Modus — hat keine DESTILLATION)
    """
    # Kriterium 1: META-DESTILLATION (VOLLANALYSE)
    if re.search(r'(?:^|\n)(?:#{1,4}\s*)?META-DESTILLATION', text, re.IGNORECASE):
        return True
    # Kriterium 2: Header + FREIE FRAGE (FREIE FRAGE-Modus)
    has_header = bool(re.search(r'# Meta-Hermeneutic Analyse', text, re.IGNORECASE))
    has_freie_frage = bool(re.search(r'(?:^|\n)(?:#{1,4}\s*)?FREIE FRAGE', text, re.IGNORECASE))
    return has_header and has_freie_frage


def _extract_meta_destillation(text: str) -> str:
    """
    Extrahiert die META-DESTILLATION als Ganzes.
    In Meta-Hermeneutic-Dateien uebernimmt sie die Rolle der KERNHYPOTHESE
    (harter Befund = Kern der Meta-Analyse).

    v2.8.3 (2026-06-23): Bei FREIE FRAGE-Dateien (keine DESTILLATION)
    wird die FREIE FRAGE-Antwort als Kern extrahiert.

    Spezialbehandlung: Ende ist Dateiende oder der naechste META-Abschnitt.
    """
    # Versuch 1: META-DESTILLATION (VOLLANALYSE-Modus)
    start_pattern = (
        r'(?:^|\n)(?:#{1,4}\s*)?\*{0,2}META-DESTILLATION\*{0,2}[^\n]*\n'
    )
    start_match = re.search(start_pattern, text, re.IGNORECASE)
    if start_match:
        rest = text[start_match.end():]
        end_pattern = r'\n(?:#{1,4}\s*)?\*{0,2}(?:META-SEZIEREN|META-BEOBACHTEN|Nachträgliche FREIE FRAGE)\*{0,2}'
        end_match = re.search(end_pattern, rest, re.IGNORECASE)
        if end_match:
            return rest[:end_match.start()].strip()
        return rest.strip()

    # Versuch 2: FREIE FRAGE-Antwort (FREIE FRAGE-Modus)
    ff_start = re.search(
        r'(?:^|\n)(?:#{1,4}\s*)?FREIE FRAGE[^\n]*\n',
        text, re.IGNORECASE
    )
    if ff_start:
        rest = text[ff_start.end():]
        # Ende: Dateiende (FREIE FRAGE ist typischerweise der letzte Abschnitt)
        return rest.strip()

    return ""


def _extract_meta_destillation_last_sentence(text: str) -> str:
    """
    Extrahiert den letzten Satz der META-DESTILLATION.
    Funktional äquivalent zum FAZIT einer Stilistic-Lab-Synthese.
    """
    destill = _extract_meta_destillation(text)
    if not destill:
        return ""
    # Letzten Satz finden: alles nach dem letzten Satzzeichen (.!?)
    # das von einem Großbuchstaben oder Zeilenende gefolgt wird
    sentences = re.split(r'(?<=[.!?])\s+', destill.strip())
    return sentences[-1].strip() if sentences else ""


def _extract_meta_beobachten(text: str) -> str:
    """
    Extrahiert den META-BEOBACHTEN-Abschnitt als Ganzes.
    In Meta-Hermeneutic-Dateien übernimmt er die Rolle der BEWEISFÜHRUNG
    (Stabilitäts-Analyse = Beweis für den Kernbefund).

    Spezialbehandlung: META-BEOBACHTEN enthält Unterüberschriften
    (## 1. STABILER KERN etc.), die NICHT als Sektionsgrenze gelten.
    Ende ist stattdessen die META-DESTILLATION-Überschrift.
    """
    # Start finden
    start_pattern = (
        r'(?:^|\n)(?:#{1,4}\s*)?\*{0,2}META-BEOBACHTEN\*{0,2}[^\n]*\n'
    )
    start_match = re.search(start_pattern, text, re.IGNORECASE)
    if not start_match:
        return ""

    rest = text[start_match.end():]

    # Ende: META-DESTILLATION-Überschrift (nicht die Unterüberschriften!)
    end_pattern = r'\n(?:#{1,4}\s*)?\*{0,2}META-DESTILLATION\*{0,2}'
    end_match = re.search(end_pattern, rest, re.IGNORECASE)
    if end_match:
        return rest[:end_match.start()].strip()
    return rest.strip()


def _extract_meta_freier_raum(text: str) -> str:
    """
    Extrahiert den FREIER RAUM-Abschnitt innerhalb von META-BEOBACHTEN.
    Dieser entspricht funktional dem FREIER RAUM einer Synthese:
    die übergeordneten, meta-theoretischen Einsichten.
    """
    # Erst in META-BEOBACHTEN suchen
    beob = _extract_meta_beobachten(text)
    if not beob:
        return ""
    # Darin den Unterabschnitt "FREIER RAUM" finden
    match = re.search(
        r'(?:^|\n)(?:#{1,4}\s*)?\*{0,2}4\.\s*FREIER RAUM\*{0,2}',
        beob, re.IGNORECASE
    )
    if not match:
        # Fallback: ohne Nummerierung
        match = re.search(
            r'(?:^|\n)(?:#{1,4}\s*)?\*{0,2}FREIER RAUM\s*[-—]\s*STABILIT',
            beob, re.IGNORECASE
        )
    if not match:
        return ""
    rest = beob[match.end():]
    # Ende: nächste nummerierte Unterüberschrift (5. AUSREIßER etc.)
    end = re.search(r'\n(?:#{1,4}\s*)?(?:5|6|7|8)\.\s', rest)
    if end:
        return rest[:end.start()].strip()
    return rest.strip()


def _extract_meta_sezieren_table(text: str) -> str:
    """
    Extrahiert die META-SEZIEREN-Tabelle + FREIER RAUM-Auszug.
    Dies ist ein neues Feld, das nur bei Meta-Dateien existiert.
    Es liefert die Rohdaten: welche Runs eingeflossen sind,
    wie groß Kern/Fazit/Beweisführung waren.

    Spezialbehandlung: Ende ist META-BEOBACHTEN, nicht die
    nächste Unterüberschrift innerhalb SEZIEREN.
    """
    start_pattern = (
        r'(?:^|\n)(?:#{1,4}\s*)?\*{0,2}META-SEZIEREN\*{0,2}[^\n]*\n'
    )
    start_match = re.search(start_pattern, text, re.IGNORECASE)
    if not start_match:
        return ""

    rest = text[start_match.end():]

    # Ende: META-BEOBACHTEN-Überschrift
    end_pattern = r'\n(?:#{1,4}\s*)?\*{0,2}META-BEOBACHTEN\*{0,2}'
    end_match = re.search(end_pattern, rest, re.IGNORECASE)
    if end_match:
        return rest[:end_match.start()].strip()
    return rest.strip()


def _extract_meta_header(text: str) -> dict:
    """
    Extrahiert Metadaten aus dem Header einer Meta-Hermeneutic-Datei.
    Liefert: version, runs, dauer, modelle, etappe1_vorhanden, stufen_dauer.
    """
    header = {}
    # Version
    m = re.search(r'Meta-Hermeneutic Analyse\s*\((v[\d.]+(?:\.\d+)*)', text)
    if m:
        header["version"] = m.group(1)
    else:
        # Ohne Versionsnummer = frühe Version
        if "Meta-Hermeneutic Analyse" in text:
            header["version"] = "pre-v2.4"
    # Runs
    m = re.search(r'\*\*Runs?:\*\*\s*(\d+)', text)
    if m:
        header["runs"] = int(m.group(1))
    # Dauer
    m = re.search(r'\*\*Dauer:\*\*\s*([\d.]+)s', text)
    if m:
        header["dauer"] = float(m.group(1))
    # Modelle
    m = re.search(r'\*\*Modell Beobachten:\*\*\s*(\S+)', text)
    if m:
        header["model_beobachten"] = m.group(1)
    m = re.search(r'\*\*Modell Destillation:\*\*\s*(\S+)', text)
    if m:
        header["model_destillation"] = m.group(1)
    # Etappe-1-Daten
    m = re.search(r'\*\*Etappe-1-Daten:\*\*\s*(Ja|Nein)', text)
    if m:
        header["has_etappe1"] = m.group(1) == "Ja"
    # Stufen-Dauer
    m = re.search(r'\*\*Stufen-Dauer:\*\*\s*(.+)', text)
    if m:
        header["stufen_dauer"] = m.group(1).strip()
    return header


def _classify_variante(meta_header: dict) -> str:
    """
    Klassifiziert einen Meta-Hermeneutic-Test in Variante A/B/C.

    Kriterien (basierend auf Claude-Architekturberatung 2026-06-15):

    Variante A (pre-v2.4):
      - Keine Etappe-1-Daten im BEOBACHTEN-Prompt
      - DESTILLATION als Fließtext (keine nummerierten Sätze)
      - Methodische Diagnose oft unvollständig
      - Keine AUTOREN-ZUORDNUNG (stochastische Autoren-Swap möglich)

    Variante B (v2.4–v2.6):
      - Etappe-1-Daten integriert (Etappe-1-Daten: Ja)
      - DESTILLATION als 9 nummerierte Sätze
      - Sprachregister-Analyse mit Komposita-Befund
      - Expliziter Bestätigungs-Bias
      - Keine AUTOREN-ZUORDNUNG-FIX

    Variante C (v2.7+):
      - Alles aus B + FREIE FRAGE möglich
      - AUTOREN-ZUORDNUNG-FIX aktiv (Autoren-Stabilität 39/39)
      - Mögliche Duplikat-Inflation (identische Eingabedaten paarweise)
    """
    version = meta_header.get("version", "")

    if not version or version == "pre-v2.4":
        return "A"

    # Version parsen: "v2.7.1" → (2, 7, 1)
    try:
        parts = version.lstrip("v").split(".")
        major, minor = int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        return "A"  # Unbekanntes Format → konservativ A

    if major > 2:
        return "C"
    if major == 2:
        if minor >= 7:
            return "C"
        if minor >= 4:
            return "B"
    return "A"


def _is_likely_author_name(name: str) -> bool:
    """
    v2.4.1: Prüft ob ein erkannter Name wahrscheinlich ein Autorname ist
    und kein deutsches Gemeinwort, Genitiv, oder Analyseterminus.

    Filterkriterien:
    - Umfassende Stopwortliste (deutsche Gemeinwörter + Analysetermini)
    - Genitiv-Erkennung (Wörter auf -s, -es die im Nominativ kein Name sind)
    - Minimallänge 4 Zeichen (Autornamen sind selten kürzer)
    - Keine reinen deutschen Komposita die wie Analysekategorien klingen
    """
    if not name or len(name) < 4:
        return False

    # Umfassende Stopwortliste — v2.4.1 erweitert um alle bekannten False Positives
    _STOPWORDS = {
        # Artikel / Pronomen / Funktionswörter
        'Die', 'Der', 'Das', 'Ein', 'Eine', 'Keine', 'Seine', 'Ihre',
        'Diese', 'Jede', 'Alle', 'Auch', 'Dabei', 'Zudem', 'Hierbei',
        'Welche', 'Während', 'Weder', 'Wenige', 'Manche', 'Eigene',
        # Analysetermini und Pipeline-Begriffe
        'Quelle', 'DESTILLATION', 'Beweisführung', 'Hypothese',
        'Dominante', 'Operation', 'Vers', 'Satz', 'Stil',
        'Grundoperation', 'Kennzahl', 'Kennzahlen', 'Vergleich',
        'Kernhypothese', 'Synthese', 'Analyse', 'Ergebnis',
        'Übersetzung', 'Original', 'Originals', 'Text', 'Werk',
        # Deutsche Gemeinwörter die nach "Quelle N" stehen können
        'Form', 'Lösung', 'Inhalt', 'Inhalts', 'Weg', 'Wort',
        'Reim', 'Rhythmus', 'Klang', 'Bild', 'Kraft', 'Stimme',
        'Flusses', 'Fluss', 'Grund', 'Sinn', 'Art', 'Weise',
        'Mittel', 'Werkzeug', 'Zeichen', 'Ausdruck', 'Wirkung',
        'Natur', 'Seele', 'Geist', 'Welt', 'Raum', 'Zeit',
        'Sprache', 'Dichtung', 'Poesie', 'Lyrik', 'Epik',
        # Typische Etappe-1-Felder
        'Morphologie', 'Morphologische', 'Lexik', 'Syntax',
        'Enjambement', 'TTR', 'Satzlänge', 'Satzlängen',
        'Komposita', 'Kompositum', 'Fremdwort', 'Fremdwörter',
        'Hotspot', 'Statistik', 'Vergleichstabelle',
        # Abstrakta die oft nach "Quelle N" stehen
        'Verfahren', 'Prinzip', 'Methode', 'Technik', 'Strategie',
        'Haltung', 'Position', 'Perspektive', 'Ansatz', 'Modus',
        'Funktion', 'Rolle', 'Wert', 'Bedeutung', 'Effekt',
        'Charakter', 'Typus', 'Profil', 'Muster', 'Struktur',
        'Spannung', 'Kontrast', 'Differenz', 'Beziehung',
        # Verborgene False Positives aus Test 17
        'Homers',  # Genitiv von Homer — "Homer" wird separat erkannt
        # Puschkin/Blok/Brodsky-Analysevokabular (Patch 2026-06-27):
        # Diese Begriffe tauchen als DESTILLATION-Termini auf und dürfen
        # NICHT als Autoren-Namen extrahiert werden.
        'Demontage', 'Gemeinschaftsbildung', 'Machtdemonstration',
        'Selbstexpansion', 'Mobilisierung', 'Exklusion',
        'Verklärung', 'Verdichtung', 'Fragmentierung', 'Zertrümmerung',
        'Entgrenzung', 'Transzendierung', 'Expansion',
        'Diskreditierung', 'Delegitimierung', 'Entwertung',
        'Redefinition', 'Rekonfiguration', 'Subsumption',
        'Imperativ', 'Imperativbildung', 'Appell',
        'Vision', 'Visionär', 'Prophetie', 'Prophezeiung',
        'Polemik', 'Polemische', 'Polemischer',
        'Agency', 'Intentional', 'Intentionale', 'Intentionaler',
        'Responsiv', 'Responsive', 'Responsive',
        'Entbündelnd', 'Entbündelnde', 'Entbündelnder',
        'Keim', 'Keime', 'Vorbereitung',
        'Hegemonie', 'Hegemoniale', 'Imperiale', 'Imperialer',
        'Wendung', 'Entwicklung', 'Transformation',
        'Operation', 'Grundoperation', 'Dominante',
        # Allgemeine Nomen, die kein Autor sein können
        'Gedicht', 'Gedichts', 'Gedichte',
        'Stil', 'Stils', 'Stile',
        'Text', 'Texte', 'Texten',
        'Werk', 'Werks', 'Werke',
        'Autor', 'Autors', 'Autoren',
        'Dichter', 'Dichters',
        'Lyriker', 'Lyrikers',
        # Räumliche/zeitliche Begriffe
        'Phase', 'Phasen', 'Periode', 'Perioden',
        'Stadium', 'Stadien', 'Stufe', 'Stufen',
        'Schritt', 'Schritte',
        # Analytische Begriffe, die als Autoren extrahiert werden (v59.10.8)
        'Identifikation', 'Identifizierung', 'Klassifikation',
        'Kategorisierung', 'Interpretation', 'Analyse',
        'Untersuchung', 'Vergleich', 'Vergleichs',
        'Transformation', 'Radikalisierung', 'Eskalation',
        'Konstitution', 'Konstruktion', 'Dekonstruktion',
        'Dispersion', 'Genealogie', 'Kontinuität',
        'Stabilität', 'Instabilität', 'Variabilität',
        'Validierung', 'Falsifikation', 'Verifikation',
        'Adjudikation', 'Gegenposition', 'Bestätigung',
    }

    if name in _STOPWORDS:
        return False

    # Genitiv-Filter: Wörter auf -s oder -es die ohne Suffix in der Stopliste stehen
    # z.B. "Originals" → Stamm "Original", "Inhalts" → Stamm "Inhalt"
    if name.endswith('s') and len(name) > 3:
        stem_es = name[:-2] if name.endswith('es') and len(name) > 4 else None
        stem_s = name[:-1]
        if stem_s in _STOPWORDS or (stem_es and stem_es in _STOPWORDS):
            return False
        # Auch wenn der Stamm ein deutsches Gemeinwort ist (nicht in Stopliste
        # aber typisch kein Autorname): Kurzname < 6 Zeichen mit Genitiv-s
        if len(name) <= 6 and name[0].isupper():
            # Kurze Wörter mit -s sind fast nie Autornamen
            # Ausnahme: z.B. "Homer" → "Homers" (aber Homer wird ohnehin erkannt)
            return False

    # Keine reinen deutschen Wörter die mit Großbuchstabe beginnen
    # (Kriterium: Nur ASCII-Buchstaben, keine diakritischen Zeichen,
    # und sieht wie ein deutsches Substantiv aus)
    _GERMAN_PATTERNS = re.compile(
        r'^(?:Auf|Bei|Durch|Für|Gegen|In|Mit|Nach|Über|Um|Unter|Vom|Von|Vor|Zu)'
        r'[A-ZÄÖÜ][a-zäöüß]+'
    )
    if _GERMAN_PATTERNS.match(name):
        return False

    # v60 (Patch 2026-07-03): Whitelist-Filter entfernt — blockierte neue Autoren.
    #
    # Problem (v59.9.6–v59.10.x): Kyrillische Wörter wurden PAUSCHAL abgelehnt,
    # wenn sie nicht in _KNOWN_AUTHORS-Whitelist standen. Das blockierte alle
    # neuen kyrillischen Autoren (außer Puschkin/Blok/Brodsky/Homer etc.).
    # Ursprüngliches Ziel: Verhindern, dass Zitat-Wörter wie "Миров", "Черная"
    # als Autoren extrahiert werden.
    #
    # NEU (v60): Statt harter Whitelist-Filterung verwenden wir eine weichere
    # Heuristik: Blockiere nur Adjektiv-Endungen, die NIEMALS Nachnamen sind.
    # Endungen wie -ий, -ый, -ой, -ов, -ин, -ева werden ALLOWED, weil viele
    # russische Nachnamen diese Endungen haben (Маяковский, Толстой, etc.).
    # Die _KNOWN_AUTHORS-Whitelist bleibt für Canonical-Name-Normalisierung,
    # aber nicht mehr als Filter.
    _CYR_NEVER_SURNAMES = (
        'ая', 'яя', 'ое', 'ее',          # fem/neut adjective endings
        'ого', 'его', 'ому', 'ему',       # genitive/dative
        'ыми', 'ими',                     # instrumental plural
    )
    if any(name.endswith(ending) for ending in _CYR_NEVER_SURNAMES):
        if re.search(r'[А-Яа-яЁё]', name):
            return False

    return True


# Bekannte Autornamen für diese Domain — Whitelist als Validierung
# v59.9.6 (Patch 2026-06-27): Puschkin/Blok/Brodsky hinzugefügt
_KNOWN_AUTHORS = {
    'Starikovskij', 'Starikovsky', 'Žukovskij', 'Zhukovskij', 'Žukovskij',
    'Zhukovsky', 'Žukovsky', 'Veresaev', 'Veresaev', 'Veresayev',
    'Homer', 'Homeros',
    # Kyrillische Formen (Homer)
    'Стариковский', 'Жуковский', 'Вересаев',
    # Puschkin/Blok/Brodsky (Patch 2026-06-27):
    'Puschkin', 'Pushkin', 'Puškin', 'Пушкин',
    'Blok', 'Блок',
    'Brodskij', 'Brodsky', 'Бродский',
    # Varianten aus Sidecar-Erkennung (Mini-LLM liefert manchmal PUSKIN/Puskin)
    'PUSKIN', 'Puskin',
    'Brodskij',  # latinisierte Form
}


# v59.9.9 (Patch 2026-06-27 kumulativ): Canonical-Name-Normalisierung
# Problem: Dieselbe Person wurde in verschiedenen Schreibweisen als
# verschiedene Autoren extrahiert (z.B. „Puschkin" + „Puskin" + „Пушкин").
# Lösung: Mapping aller bekannten Schreibweisen auf eine kanonische Form.
_AUTHOR_CANONICAL = {
    # Puschkin
    'Puschkin': 'Puschkin', 'Pushkin': 'Puschkin', 'Puškin': 'Puschkin',
    'PUSKIN': 'Puschkin', 'Puskin': 'Puschkin',
    'Пушкин': 'Puschkin',
    # Blok
    'Blok': 'Blok', 'Блок': 'Blok',
    # Brodsky
    'Brodskij': 'Brodskij', 'Brodsky': 'Brodskij', 'Бродский': 'Brodskij',
    # Homer
    'Homer': 'Homer', 'Homeros': 'Homer',
    # Žukovskij
    'Žukovskij': 'Žukovskij', 'Zhukovskij': 'Žukovskij',
    'Zhukovsky': 'Žukovskij', 'Žukovsky': 'Žukovskij',
    'Жуковский': 'Žukovskij',
    # Veresaev
    'Veresaev': 'Veresaev', 'Veresayev': 'Veresaev',
    'Вересаев': 'Veresaev',
    # Starikovskij
    'Starikovskij': 'Starikovskij', 'Starikovsky': 'Starikovskij',
    'Стариковский': 'Starikovskij',
}


def _normalize_author_name(name: str) -> str:
    """
    v59.9.9 (Patch 2026-06-27 kumulativ): Normalisiert Autoren-Namen auf
    eine kanonische Form. Verhindert Duplikate wie „Puschkin" + „Puskin".

    Args:
        name: Extrahierter Autoren-Name (beliebige Schreibweise)

    Returns:
        Kanonische Form des Namens, oder der Original-Name falls kein
        Mapping existiert (z.B. bei neuen, unbekannten Autoren).
    """
    if not name:
        return name
    return _AUTHOR_CANONICAL.get(name, name)


def _detect_authors(sezieren_results: List[Dict]) -> List[str]:
    """
    Erkennt automatisch die Autor/Quelle-Namen aus den Synthese-Outputs.

    v60 (Patch 2026-07-03): Vollständig überarbeitet — ohne Whitelist-Fallback.

    Frühere Probleme:
    - Fallback-Whitelist (_KNOWN_AUTHORS) füllte <3 Autoren mit alten Namen auf.
      Das verdeckte das Problem, anstatt es zu lösen — neue Autoren tauchten
      nie in der Analyse auf.
    - Regex ohne Bindestrich-Unterstützung (Мамин-Сибиряк wurde nicht gefunden).
    - Regex fand nur den Nachnamen, wenn ein Vorname davor stand.
      "Thomas Mann (Quelle 1)" → fand nur "Thomas".
    - Kyrillische Muster hatten nur 6 Endungen; viele Nachnamen enden anders.

    Neue Strategie:
    1. "Autor (Quelle N)" — zuverlässigstes Muster (1-2 Wörter, Bindestrich OK)
    2. "Quelle N: Autor" — häufig im Sidecar-Format
    3. Kyrillische Autornamen direkt im Text (erweiterte Endungen)
    4. KEIN Whitelist-Fallback. Wenn <3 Autoren gefunden werden, ist das ein
       Befund — der User muss die Quelldaten prüfen, nicht die Engine.

    Returns:
        Liste der erkannten Autor-Namen (sortiert, dedupliziert)
    """
    authors = set()
    debug_counts = {"muster1": 0, "muster2": 0, "muster3": 0}

    # Sammle alle Texte (Kernhypothese + Fazit + BEWEISFÜHRUNG)
    all_text = ""
    for run in sezieren_results:
        # v2.4.1-FIX: Klammern um `or` — sonst wertet Python `"" + "\n"` vor `or`
        all_text += (run.get("kernhypothese", "") or "") + "\n"
        all_text += (run.get("fazit", "") or "") + "\n"
        all_text += (run.get("beweisfuehrung", "") or "") + "\n"

    # Buchstaben-Klassen (Latin + Kyrillisch, mit Diakritika)
    _LATIN_UPPER = (
        r"A-ZÁÀÂÄÅĂĄĆČĎĐÉÈÊËĖĘĚĞÍÌÎÏİĶĹĽŁŃŇÑÓÒÔÖŐŘŔŚŠŞŤŢÚÙÛÜŰŮŴÝŸŹŽŻ"
    )
    _LATIN_LOWER = (
        r"a-záàâäăąćčďđéèêëęěğíìîïıķĺľłńňñóòôöőřŕśšşťţúùûüűůŵýÿźžż"
    )
    _CYR_UPPER = r"А-ЯЁ"
    _CYR_LOWER = r"а-яё"

    # Muster 1 (ZUVERLÄSSIGSTES): 'Autor (Quelle N)' — 1-2 Wörter vor "(Quelle N)"
    # Erlaubt: "Mann", "Thomas Mann", "Мамин-Сибиряк", "von Kleist"
    # Pattern: 1-2 Wörter (mit optionalem Bindestrich), gefolgt von "(Quelle N)"
    pattern1 = re.compile(
        r'([' + _LATIN_UPPER + _CYR_UPPER + r']'
        r'[' + _LATIN_LOWER + _CYR_LOWER + r'\-]+'
        r'(?:\s+[' + _LATIN_UPPER + _CYR_UPPER + r']'
        r'[' + _LATIN_LOWER + _CYR_LOWER + r'\-]+)?)'  # optional 2. Wort
        r'\s*\(\s*Quelle\s*\d+\s*\)',
        re.IGNORECASE
    )
    for m in pattern1.finditer(all_text):
        name = m.group(1).strip()
        if _is_likely_author_name(name):
            if name not in authors:
                debug_counts["muster1"] += 1
            authors.add(name)

    # Muster 2: 'Quelle N: Autor' oder 'Quelle N [Autor]' oder 'Quelle N Autor'
    # v60 (Patch 2026-07-03): NUR 1 Wort — kein optionales 2. Wort mehr.
    # Problem: Bei "Quelle 2: Kafka zeigt Verfremdung" hat das optionale 2. Wort
    # das Verb "zeigt" eingesaugt → "Kafka zeigt" wurde als Autor erkannt.
    # Lösung: Nur 1 Wort erfassen. 2-Wort-Namen (z.B. "Thomas Mann") müssen
    # im Format "Thomas Mann (Quelle 1)" stehen — das wird von Muster 1
    # zuverlässig erkannt, weil die Klammer als Begrenzer dient.
    pattern2 = re.compile(
        r'Quelle\s*(\d+)\s*[\[\]:]?\s*'
        r'([' + _LATIN_UPPER + _CYR_UPPER + r']'
        r'[' + _LATIN_LOWER + _CYR_LOWER + r'\-]+)',
        re.IGNORECASE
    )
    for m in pattern2.finditer(all_text):
        name = m.group(2).strip()
        if _is_likely_author_name(name):
            if name not in authors:
                debug_counts["muster2"] += 1
            authors.add(name)

    # Muster 3: Kyrillische Autornamen direkt im Text (erweiterte Endungen)
    # v60 (Patch 2026-07-03): Endungen erweitert und nach Länge sortiert.
    #   Längste Endungen zuerst (sonst matcht -ов vor -ова → "Ахматов" statt "Ахматова").
    #   -ский / -ская / -ина / -ова / -ева / -ов / -ев / -ин / -ий / -ый / -ой
    #   -ко / -юк / -ук / -ич
    #   WICHTIG: _is_likely_author_name filtert noch Adjektiv-Endungen
    #   (-ая, -яя, -ое, -ее, -ого, -его, -ому, -ему, -ыми, -ими)
    pattern3 = re.compile(
        r'([' + _CYR_UPPER + r']'
        r'[' + _CYR_LOWER + r']+'
        r'(?:ский|ская|ина|ова|ева|ов|ев|ин|ий|ый|ой|ко|юк|ук|ич))',
    )
    for m in pattern3.finditer(all_text):
        name = m.group(1)
        if _is_likely_author_name(name):
            if name not in authors:
                debug_counts["muster3"] += 1
            authors.add(name)

    # v60 (Patch 2026-07-03): KEIN Whitelist-Fallback mehr.
    # Wenn <3 Autoren gefunden werden, ist das ein Befund — der User muss
    # die Quelldaten prüfen, nicht die Engine mit alten Namen auffüllen.
    # Früherer Code (entfernt):
    #   if len(authors) < 3:
    #       for known in _KNOWN_AUTHORS:
    #           if known in all_text and known not in authors:
    #               authors.add(known)

    # Logging: Wie viele Autoren wurden über welches Muster gefunden?
    logger.info(
        f"  📊 Autor-Erkennung: {len(authors)} Autoren gefunden "
        f"(M1={debug_counts['muster1']}, M2={debug_counts['muster2']}, "
        f"M3={debug_counts['muster3']})"
    )
    if len(authors) < 3:
        logger.warning(
            f"  ⚠️ Nur {len(authors)} Autoren erkannt (erwartet: mind. 3). "
            f"Bitte Quelldaten prüfen — sind die Autoren im Format "
            f"'Autor (Quelle N)' im Synthese-Text?"
        )

    # v59.9.9: Canonical-Name-Normalisierung (behalten — nützlich für Duplikate)
    normalized_authors = set()
    for author in authors:
        normalized = _normalize_author_name(author)
        normalized_authors.add(normalized)

    return sorted(normalized_authors)


def meta_sezieren(synthesis_files: List[Path]) -> List[Dict]:
    """
    META-SEZIEREN: Extrahiert Strukturdaten aus N Synthese-Outputs.

    v2.4.1-FIX: Filtert Nicht-Synthese-Dateien per Dateinamen-Muster:
    - etappe1.md (Etappe-1-Daten, keine Synthese)
    - uebersicht.tsv (Zusammenfassung)
    - Dateien ohne _synthese im Namen die auch keine
      Globale-Synthese-Überschrift enthalten

    Returns:
        Liste von Dicts, eines pro Run
    """
    # v2.4.1: Dateinamen-Muster die KEINE Synthese-Dateien sind
    _SKIP_NAMES = {'etappe1.md', 'uebersicht.tsv', 'etappe1_text.md'}
    _SKIP_PREFIXES = ('etappe1', 'uebersicht')

    results = []
    valid_files = []

    for filepath in sorted(synthesis_files):
        # Bug-1-FIX: Per Dateinamen filtern — etappe1.md etc. NIEMALS verarbeiten
        fname = filepath.name.lower()
        if fname in _SKIP_NAMES:
            logger.info(f"  ÜBERSPRUNGEN (Nicht-Synthese): {filepath.name}")
            continue
        if any(fname.startswith(p) for p in _SKIP_PREFIXES):
            logger.info(f"  ÜBERSPRUNGEN (Nicht-Synthese-Präfix): {filepath.name}")
            continue
        valid_files.append(filepath)

    for i, filepath in enumerate(valid_files, 1):
        try:
            text = filepath.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning(f"Kann {filepath.name} nicht lesen: {e}")
            continue

        # v2.8: Meta-Hermeneutic-Datei erkennen und anders parsen
        is_meta_file = _detect_meta_hermeneutic_file(text)

        if is_meta_file:
            # --- META-HERMENEUTIC FORMAT ---
            # META-DESTILLATION → KERNHYPOTHESE (harter Befund = Kern)
            # Letzter Satz DESTILLATION → FAZIT
            # META-BEOBACHTEN → BEWEISFÜHRUNG (Stabilitäts-Analyse = Beweis)
            # FREIER RAUM innerhalb BEOBACHTEN → FREIER RAUM
            kern = _extract_meta_destillation(text)
            fazit = _extract_meta_destillation_last_sentence(text)
            beweis = _extract_meta_beobachten(text)
            hypothese = ""  # Nicht in Meta-Dateien vorhanden
            freier_raum = _extract_meta_freier_raum(text)
            meta_header = _extract_meta_header(text)
            meta_sezieren_table = _extract_meta_sezieren_table(text)
            variante = _classify_variante(meta_header)

            if not kern and not fazit:
                # v2.8.3: Bei FREIE FRAGE-Dateien ist fazit oft leer
                # (kein letzter Satz der DESTILLATION), aber kern kann
                # die FREIE FRAGE-Antwort enthalten. Nur abbrechen wenn
                # BEIDES leer ist.
                logger.warning(
                    f"  [{i}/{len(valid_files)}] {filepath.name} — "
                    f"Meta-Datei erkannt, aber keine DESTILLATION oder "
                    f"FREIE FRAGE-Antwort extrahierbar"
                )
                continue

            result_entry = {
                "nr": i,
                "datei": filepath.name,
                "kernhypothese": kern,
                "fazit": fazit,
                "beweisfuehrung": beweis,
                "hypothese": hypothese,
                "freier_raum": freier_raum,
                "laenge_kern": len(kern),
                "laenge_fazit": len(fazit),
                # v2.8: Zusätzliche Meta-Hermeneutic-Felder
                "source_type": "meta_hermeneutic",
                "variante": variante,
                "meta_version": meta_header.get("version", "unknown"),
                "meta_runs": meta_header.get("runs", 0),
                "meta_dauer": meta_header.get("dauer", 0),
                "meta_has_etappe1": meta_header.get("has_etappe1", False),
                "meta_sezieren_table": meta_sezieren_table,
            }
        else:
            # --- STILISTIC-LAB SYNTHESE FORMAT (bestehend) ---
            kern = _extract_kernhypothese(text)
            fazit = _extract_fazit(text)
            beweis = _extract_beweisfuehrung(text)
            hypothese = _extract_hypothese(text)
            freier_raum = _extract_freier_raum(text)

            # v2.4-FIX: Dateien ohne Kernhypothese UND Fazit überspringen
            # (z.B. etappe1.md — keine Synthese, sondern Etappe-1-Daten)
            if not kern and not fazit:
                logger.warning(
                    f"  [{i}/{len(valid_files)}] {filepath.name} — "
                    f"keine Globale Synthese erkannt, übersprungen"
                )
                continue

            result_entry = {
                "nr": i,
                "datei": filepath.name,
                "kernhypothese": kern,
                "fazit": fazit,
                "beweisfuehrung": beweis,
                "hypothese": hypothese,
                "freier_raum": freier_raum,
                "laenge_kern": len(kern),
                "laenge_fazit": len(fazit),
                # v2.8: Kennzeichnung als Stilistic-Lab-Quelle
                "source_type": "stilistic_lab",
                "variante": "S",  # S = Stilistic-Lab-Synthese
            }

        results.append(result_entry)

        # Logging mit Typ-Kennzeichnung
        src_tag = "[META]" if is_meta_file else "[SYN]"
        var_tag = result_entry.get("variante", "?")
        logger.info(
            f"  [{i}/{len(valid_files)}] {src_tag}[V{var_tag}] {filepath.name} "
            f"(Kern:{len(kern)} Fazit:{len(fazit)} Bew:{len(beweis)} FR:{len(freier_raum)})"
        )

    # Diagnose
    kern_ok = sum(1 for r in results if r["kernhypothese"])
    fazit_ok = sum(1 for r in results if r["fazit"])
    meta_count = sum(1 for r in results if r.get("source_type") == "meta_hermeneutic")
    syn_count = sum(1 for r in results if r.get("source_type") == "stilistic_lab")
    varianten = {}
    for r in results:
        v = r.get("variante", "?")
        varianten[v] = varianten.get(v, 0) + 1
    var_str = ", ".join(f"V{v}:{c}" for v, c in sorted(varianten.items()))
    logger.info(
        f"  META-SEZIEREN: {len(results)} Runs "
        f"({meta_count} Meta, {syn_count} Syn | {var_str}), "
        f"Kernhypothesen: {kern_ok}/{len(results)}, "
        f"Fazits: {fazit_ok}/{len(results)}"
    )

    return results


# ==============================================================================
# STUFE 1b: TERMINI-EXTRAKTION via Mini-LLM (Flash)
# ==============================================================================

_TERMINI_EXTRACTION_SYSTEM = """Du extrahierst DESTILLATION-Termini aus einem Analyse-Text.
Antworte AUSSCHLIESSLICH im JSON-Format. Keine Erklärungen."""

_TERMINI_EXTRACTION_PROMPT = """Extrahiere aus dem folgenden Text die DESTILLATION-Termini
für jede genannte Quelle/Autor. DESTILLATION-Termini sind die fettgedruckten
Substantiv-Phrasen, die als KERNBEGRIFF für jede Quelle dienen.

Beispiel: 'Žukovskij ... **Klangfügung**' → Terminus = 'Klangfügung'

Format (strikt):
```json
{{
  "Autor1": "Terminus oder null",
  "Autor2": "Terminus oder null"
}}
```

Erwartete Autoren: {authors}

Regeln:
- Extrahiere die fettgedruckten (**...**) Termini aus Kernhypothese und Beweisführung
- Wenn kein Terminus für eine Quelle: null
- Keine Sätze, nur Substantiv-Phrasen (max 8 Wörter)
- Falls zusätzliche Autoren im Text auftauchen, die nicht in der Liste stehen: ebenfalls extrahieren

--- KERNHYPOTHESE ---
{kernhypothese}

--- BEWEISFÜHRUNG ---
{beweisfuehrung}

--- FAZIT ---
{fazit}"""


# ==============================================================================
# STUFE 1b-2: AGENCY-EXTRAKTION via Mini-LLM (Flash)
# ============================================================================
# v59.10.0 (Schritt 1 der Falsifizierungs-Architektur, Claude-Beratung 2026-06-28):
# Extrahiert die Agency-Qualitaet (intentional/responsiv/entbuendelnd) pro
# Autor pro Run. Separate Funktion, nicht in extract_termini_per_run integriert,
# weil Agency-Qualitaeten kontrollierte Vokabular-Werte sind, keine freien
# Substantiv-Phrasen wie Termini.
#
# WICHTIG: Runs ohne Agency-Information (aeltere Engine-Varianten) geben null
# zurueck. null ist selbst ein Befund (diese Runs kennen die Agency-Kategorien
# noch nicht).

_AGENCY_EXTRACTION_SYSTEM = """Du extrahierst Agency-Qualitaeten aus einem Analyse-Text.
Antworte AUSSCHLIESSLICH im JSON-Format. Keine Erklaerungen."""

_AGENCY_EXTRACTION_PROMPT = """Lies die folgende Fazit- und Beweisfuehrungs-Sektion.
Extrahiere die Agency-Qualitaet fuer jeden genannten Autor.

Moegliche Werte (strikt):
- "intentional" — der Autor waehlt und steuert die Rhetorik aktiv
- "responsiv" — der Autor antwortet auf etwas, das ihn uebersteigt; formt in Resonanz
- "entbuendelnd" — der Autor entzieht Steuerung kalkuliert
- null — wenn die Agency-Qualitaet fuer diesen Autor nicht erwaehnt wird

WICHTIG: Extrahiere NUR explizit genannte Agency-Qualitaeten. Wenn der Text
"intentional", "responsiv" oder "entbuendelnd" (oder aehnliche Formulierungen
wie "responsiv auf", "intentionale Agency", "Akt der entbuendelnden Agency")
explizit verwendet, extrahiere den entsprechenden Wert. Wenn der Text die
Agency-Qualitaet fuer einen Autor NICHT erwaehnt, setze null.

Format (strikt):
```json
{{
  "Autor1": "intentional" | "responsiv" | "entbuendelnd" | null,
  "Autor2": "intentional" | "responsiv" | "entbuendelnd" | null
}}
```

Erwartete Autoren: {authors}

--- FAZIT ---
{fazit}

--- BEWEISFUEHRUNG ---
{beweisfuehrung}"""


def extract_agency_per_run(
    sezieren_results: List[Dict],
    progress_callback: Optional[Callable] = None,
) -> Dict[int, Dict[str, Optional[str]]]:
    """
    Extrahiert Agency-Qualitaeten pro Autor pro Run via Mini-LLM.

    v59.10.0 (Schritt 1 der Falsifizierungs-Architektur):
    Separate Funktion, parallel zu extract_termini_per_run().
    Agency-Qualitaeten sind kontrollierte Vokabular-Werte (intentional/
    responsiv/entbuendelnd), keine freien Substantiv-Phrasen.

    Args:
        sezieren_results: Output von meta_sezieren()
        progress_callback: Optionaler Callback

    Returns:
        Dict {run_nr: {autor: agency_qualitaet | None}
        agency_qualitaet ist einer von: "intentional", "responsiv",
        "entbuendelnd", oder None (wenn nicht erwaehnt).
    """
    detected_authors = _detect_authors(sezieren_results)
    authors_str = ", ".join(detected_authors) if detected_authors else "(automatisch erkennen)"

    logger.info(f"  Agency-Extraktion fuer Autoren: {authors_str}")

    agency_table: Dict[int, Dict[str, Optional[str]]] = {}

    for i, run in enumerate(sezieren_results):
        if progress_callback:
            progress_callback(
                f"Agency-Extraktion: Run {run['nr']}/{len(sezieren_results)}..."
            )

        beweis = run.get("beweisfuehrung", "") or ""
        prompt = _AGENCY_EXTRACTION_PROMPT.format(
            authors=authors_str,
            fazit=run["fazit"][:1500] if run["fazit"] else "(kein Fazit)",
            beweisfuehrung=beweis[:2000] if beweis else "(kein BEWEISFUEHRUNG-Abschnitt)",
        )

        try:
            response = llm_call(
                prompt=prompt,
                task="meta_termini_extraction",  # Task aus Config (Flash-Modell)
                system_instruction=_AGENCY_EXTRACTION_SYSTEM,
                temperature=0.0,  # Deterministisch — Agency ist kontrolliertes Vokabular
                max_tokens=1024,  # Erhöht: 256 war zu niedrig, LLM wurde abgeschnitten
                domain="stilisierung",
            )

            agency_per_author = _parse_agency_json(response or "")
            agency_table[run["nr"]] = agency_per_author

            # Auch in sezieren_results schreiben (fuer spaetere Verwendung)
            run["agency_qualities"] = agency_per_author

            # Debug: Zeige die LLM-Antwort (erste 200 Zeichen)
            logger.info(f"  Run {run['nr']}: LLM-Antwort (erste 200 Zchn): {(response or '')[:200]}")

            # Logging
            agency_str = ", ".join(
                f"{a}={v or 'null'}" for a, v in sorted(agency_per_author.items())
            )
            logger.info(f"  Run {run['nr']}: Agency: {agency_str}")

            # Rate-Limit-Schutz
            time.sleep(1.5)

        except Exception as e:
            logger.error(f"Agency-Extraktion fehlgeschlagen fuer {run['datei']}: {e}")
            agency_table[run["nr"]] = {}
            run["agency_qualities"] = {}
            time.sleep(2.0)

    # Agency-Zusammenfassung loggen
    if sezieren_results and agency_table:
        all_authors_in_agency = set()
        for run_agency in agency_table.values():
            all_authors_in_agency.update(run_agency.keys())

        for author in sorted(all_authors_in_agency):
            values = []
            for run_nr in sorted(agency_table.keys()):
                run_agency = agency_table[run_nr]
                val = run_agency.get(author)
                values.append(val if val else "null")
            non_null = [v for v in values if v != "null"]
            logger.info(
                f"  Agency '{author}': {len(non_null)}/{len(values)} Runs mit Agency-Zuordnung"
            )

    return agency_table


def _parse_agency_json(text: str) -> Dict[str, Optional[str]]:
    """
    Parst die LLM-Antwort als JSON-Dict fuer Agency-Qualitaeten.

    v59.10.0 Fix: Robuster Parser — funktioniert auch bei:
    - Code-Fence ohne schliessendes ```
    - Abgeschnittenem JSON (missing closing brace)
    - JSON mit zusaetzlichem Text davor/danach
    """
    raw = None

    # Strategie 1: Code-Fence mit schliessendem ```
    json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if json_match:
        try:
            raw = json.loads(json_match.group(1))
        except Exception:
            pass

    # Strategie 2: Code-Fence ohne schliessendes ``` (abgeschnitten)
    if raw is None:
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})', text, re.DOTALL)
        if json_match:
            try:
                raw = json.loads(json_match.group(1))
            except Exception:
                pass

    # Strategie 3: Raw JSON ohne Code-Fence
    if raw is None:
        # Suche nach erstem { und letztem }
        start = text.find('{')
        end = text.rfind('}')
        if start >= 0 and end > start:
            json_str = text[start:end+1]
            try:
                raw = json.loads(json_str)
            except Exception:
                # Versuche: Schließe fehlende braces
                try:
                    # Zaehle offene und geschlossene braces
                    open_count = json_str.count('{')
                    close_count = json_str.count('}')
                    if open_count > close_count:
                        json_str += '}' * (open_count - close_count)
                    raw = json.loads(json_str)
                except Exception:
                    pass

    # Strategie 4: Direkter json.loads Versuch
    if raw is None:
        try:
            raw = json.loads(text)
        except Exception:
            return {}

    # Kontrolliertes Vokabular
    _VALID_AGENCY = {"intentional", "responsiv", "entbuendelnd"}

    result = {}
    if isinstance(raw, dict):
        for k, v in raw.items():
            if v is None:
                # null ist gueltig — bedeutet "Agency nicht erwaehnt"
                result[k] = None
            elif isinstance(v, str) and v.strip().lower() in _VALID_AGENCY:
                result[k] = v.strip().lower()
            else:
                # Ungueltiger Wert — als None behandeln
                result[k] = None
    return result


def extract_termini_per_run(
    sezieren_results: List[Dict],
    progress_callback: Optional[Callable] = None,
) -> List[Dict]:
    """
    Extrahiert DESTILLATION-Termini pro Run via Mini-LLM.
    Fügt die Termini in die sezieren_results ein.
    """
    detected_authors = _detect_authors(sezieren_results)
    authors_str = ", ".join(detected_authors) if detected_authors else "(automatisch erkennen)"

    logger.info(f"  Erkannte Autoren für Termini-Extraktion: {authors_str}")

    for i, run in enumerate(sezieren_results):
        if progress_callback:
            progress_callback(
                f"Termini-Extraktion: Run {run['nr']}/{len(sezieren_results)}..."
            )

        beweis = run.get("beweisfuehrung", "") or ""
        prompt = _TERMINI_EXTRACTION_PROMPT.format(
            authors=authors_str,
            kernhypothese=run["kernhypothese"][:2000],
            beweisfuehrung=beweis[:2000] if beweis else "(kein BEWEISFÜHRUNG-Abschnitt)",
            fazit=run["fazit"][:1500] if run["fazit"] else "(kein Fazit)",
        )

        try:
            response = llm_call(
                prompt=prompt,
                task="meta_termini_extraction",
                system_instruction=_TERMINI_EXTRACTION_SYSTEM,
                temperature=0.1,
                max_tokens=512,
                domain="stilisierung",
            )

            termini = _parse_termini_json(response or "")
            run["termini"] = termini

            # Rate-Limit-Schutz
            time.sleep(1.5)

        except Exception as e:
            logger.error(f"Termini-Extraktion fehlgeschlagen für {run['datei']}: {e}")
            run["termini"] = {}
            time.sleep(2.0)

    # Termini-Zusammenfassung loggen
    if sezieren_results:
        all_authors = set()
        for r in sezieren_results:
            all_authors.update(r.get("termini", {}).keys())
        for author in sorted(all_authors):
            # v2.4.1-FIX: None-Werte (aus JSON null) als "—" behandeln
            terms = [r["termini"].get(author) or "—" for r in sezieren_results if r.get("termini")]
            unique_terms = set(t for t in terms if t and t != "—")
            logger.info(f"  Terminus '{author}': {len(unique_terms)} verschiedene / {len(terms)} Runs")

    return sezieren_results


def _parse_termini_json(text: str) -> Dict[str, str]:
    """
    Parst die LLM-Antwort als JSON-Dict.

    v2.4.1-FIX: None-Werte (aus JSON null) werden herausgefiltert,
    damit sie bei String-Operationen (join, format) keinen NoneType-Fehler erzeugen.
    """
    raw = None
    json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if json_match:
        try:
            raw = json.loads(json_match.group(1))
        except Exception:
            pass

    if raw is None:
        try:
            raw = json.loads(text)
        except Exception:
            return {}

    # v2.4.1: None-Werte herausfiltern — nur String-Werte behalten
    if isinstance(raw, dict):
        return {k: str(v) for k, v in raw.items() if v is not None and isinstance(v, str)}
    return {}


# ==============================================================================
# STUFE 1c: ETAPPE-1-TEXT BEREITSTELLEN (für SPRACHREGISTER in BEOBACHTEN)
# ==============================================================================
# v2.4 Variante A: Der vollständige Etappe-1-Text wird direkt übergeben.
# Keine Verdichtung — die HRE soll selbst entdecken, was relevant ist.
# Der Text wird aus der etappe1.md-Datei gelesen, die von
# extract_globale_synthese.py erzeugt wird.


# ==============================================================================
# STUFE 2: META-BEOBACHTEN (#38 + #39) — LLM (Flash)
# ==============================================================================

_META_BEOBACHTEN_SYSTEM = """Du bist ein methodologischer Analytiker der Hermeneutic Reconstruction Engine.
Du vergleichst Pipeline-Outputs — nicht Quelltexte, sondern die Ergebnisse der Pipeline selbst.

Deine Aufgabe: Den STABILEN KERN identifizieren — und die BESTEN ERGEBNISSE finden — 
und das SPRACHREGISTER der Übersetzungen beobachten.

Was bleibt über N Runs konstant? Was variiert? Was ist Rauschen?
Und vor allem: Was ist das tiefste, präziseste Ergebnis — auch wenn es nur selten auftaucht?
Und: Wie klingen die Übersetzungen selbst? Zugänglich oder künstlich? Nah oder distanziert?

STRIKTE REGELN:
- Jede Aussage MUSS mit einer Häufigkeit versehen werden (z.B. "17/17", "14/17")
- Inhalt und Terminologie sind VERSCHIEDENE Dimensionen:
  Inhaltlich stabil = dieselbe Behauptung, verschiedene Worte
  Terminologisch stabil = dasselbe Wort
- Unterscheide: STABIL (≥88%), HÄUFIG (59-87%), VARIABEL (<59%)
- Markiere qualitative Ausreißer (Runs, die inhaltlich abweichen)
- Prüfe auf Bestätigungs-Bias: Wurde die Hypothese jemals gefährdet?
- Der FREIER RAUM enthält oft die stärksten Funde — beachte ihn besonders

ZWEI MODI der Bewertung:
1. STABILITÄT — Was ist häufig? (Die Basis)
2. QUALITÄT — Was ist das tiefste, präziseste Ergebnis?
   Ein Fund der nur 1/17 mal auftaucht kann der WICHTIGSTE sein.
   Häufigkeit ≠ Qualität. Ein tiefer Fund aus einem einzelnen Run
   kann mehr erklären als eine banale Wahrheit die 17/17 mal auftaucht.

DREI SCHICHTEN DES SPRACHREGISTERS (v2.4.1, generifiziert v59.9.5 Schnitt B):
Wenn Etappe-1-Daten vorliegen, analysiere das Sprachregister der TEXTE.
Achtung: Die Daten enthalten sowohl ZAHLEN (TTR, Morphologie, Enjambement) als auch
WORT-BELEGE (Hotspot-Sätze, konkrete Wörter der Texte). Beide Ebenen sind wichtig.

(a) BEOBACHTUNG DER SPRACHE — Zwei Ebenen:
    EBENE 1 — Die Zahlen: Morphologische Komplexität, TTR, Enjambement-Rate, Rhythmus, Klangfiguren.
    Was sagen die Zahlen über die sprachliche Textur?
    EBENE 2 — Die Wörter: Welche konkreten Wörter fallen auf? Gibt es Wortschöpfungen,
    Neologismen, ungewöhnliche Komposita, Wörter die es im normalen Sprachgebrauch
    nicht geben würde?
    VERGLEICHEND ARBEITEN: Wenn ein Wort in einem Text auffällt,
    MUSS es auch in den ANDEREN Texten gesucht werden!
    Ist es in mehreren Texten präsent → geteiltes Merkmal des Korpus.
    Ist es nur in einem Text präsent → quellenspezifisches Merkmal dieser Stimme.
    Die Etappe-1-Daten enthalten Hotspot-Sätze von ALLEN Quellen —
    nutze sie, um Wörter vergleichend zu befragen!
    ZWEI FRAGEN an jede Wortschöpfung:
    (i) MOTIVATION: Ist sie motiviert durch eine poetische Vorlage (Nachbildung
    einer Tradition, Anspielung auf ein Vorbild) — oder eine eigene Erfindung
    des Autors (ohne direktes Vorbild)?
    Nur eigene Erfindungen sind hermeneutisch riskant.
    (ii) ARGUMENTIERTE DARSTELLUNG: Wie funktioniert das Wort sprachlich?
    Ist es morphologisch transparent (aus bekannten Elementen zusammengesetzt)
    oder opak (schwer durchschaubar)? Semantisch klar oder mehrdeutig?
    Rhythmisch eingebettet oder isoliert? Im normalen Sprachgebrauch denkbar
    oder nur im literarischen Kontext?
    KEINE BEWERTUNG wie "gelingt/nicht gelingt" — sondern faktenreiche,
    argumentierte Darstellung der sprachlichen Lage. Die Fakten sollen sprechen.
    UND: Verwendet ein anderer Text desselben Autors oder derselben Tradition
    ähnliche Wortschöpfungen? Wenn ja: Wie funktionieren sie dort?
    Dann wäre die Wortschöpfung kein Spezifikum eines einzelnen Textes, sondern
    ein poetisches Mittel des Originals — und die Übersetzung folgt ihm.
(b) SCHLUSSFOLGERUNG: WIE KLINGEN DIE TEXTE? — Die qualitative Wirkung:
    Zugänglich oder unnatürlich? Nah oder distanziert? Episch-verfremdend oder direkt?
    Bildhaft oder abstrakt? Ordnend oder auflösend?
    ACHTE AUF DEN UNTERSCHIED: Eine Übersetzung kann auf der Klangebene zugänglich
    wirken (fließender Rhythmus), aber auf der Wortebene Wortschöpfungen verwenden.
    Wie funktionieren diese sprachlich? Sind sie morphologisch transparent und
    semantisch klar — oder opak und fremd? Das wäre ein SPANNUNGSFELD zwischen
    Klang und Lexik. Dies ist keine Bewertung — sondern eine Beschreibung des Registers.
(c) WAS DIE META-EBENE SIEHT — Die einzelnen Runs identifizieren Wortschöpfungen
    als Merkmale (morphologische Komplexität, Hotspot-Sätze). Die Meta-Ebene kann
    mehr: Sie kann argumentieren, WIE diese Wörter sprachlich funktionieren.
    Welche Wortschöpfungen sind morphologisch transparent (aus bekannten Elementen
    zusammengesetzt) und welche opak? Welche sind motiviert durch das Original
    und welche sind eigene Erfindungen? Welche sind semantisch klar und welche
    mehrdeutig? Gibt es Wortschöpfungen die nur im literarischen Kontext funktionieren
    — und welche wären auch im normalen Sprachgebrauch denkbar?
    WICHTIG: Wortschöpfungen sind ein legitimes poetisches Mittel vieler Texttraditionen.
    Die Frage ist nicht OB sie da sind, sondern WIE sie funktionieren.
    Die Meta-Ebene liefert die Argumentation, die die einzelnen Runs nicht liefern.

WICHTIG: Schreibe JEDEN Abschnitt KOMPLETT aus. Kein Abschnitt darf
abgebrochen werden. Abschnitt 3 (Terminologische Streuung), 
Abschnitt 6b (Entwicklungslinie — MIT BELEGEN aus konkreten Runs!),
Abschnitt 7 (Beste Ergebnisse) und Abschnitt 8 (Sprachregister) 
sind die HERZSTÜCKE und MÜSSEN vollständig sein.
ENTWICKLUNGSLINIE: NICHT nur generelle Tendenz! Mindestens 3 KONKRETE 
BELEGE mit R-Nummern: R1: „X" → R12: „Y" (Terminus wechselt/wird präziser)."""

_META_BEOBACHTEN_PROMPT = """META-BEOBACHTEN: Stabilitäts- und Qualitäts-Analyse über {n_runs} Synthese-Runs

Du erhältst die Kernhypothesen, Beweisführungen, Fazits und FREIE RÄUME von {n_runs} Pipeline-Runs,
die alle dieselben Quellen analysiert haben. Deine Aufgabe:

1. AUSSAGEN-KODIERUNG: Zerlege jede Kernhypothese in atomare Aussagen (A1, A2, ...).
   Zähle, in wie vielen Runs jede Aussage vorkommt.

2. STABILITÄTS-MESSUNG: Bewerte jede Aussage:
   - STABIL (≥{threshold_stabil}/{n_runs}): Harter Befund
   - HÄUFIG ({threshold_haeufig}–{threshold_stabil_minus}/{n_runs}): Tendenz
   - VARIABEL (<{threshold_haeufig}/{n_runs}): Instabil

2b. ENGINE-VARIABLEN-KENNZEICHNUNG (Pflicht seit v59.9.8 Patch 2026-06-27):
   WICHTIG: „X/N Runs" kann zwei verschiedene Signale mischen:
   (1) Inhaltliche Stabilität (der Befund ist wirklich instabil)
   (2) Engine-Evolution (der Befund taucht erst ab einem bestimmten Run
       auf, weil die Engine-Prompts zwischenzeitlich geändert wurden)

   PFLICHT-PRÜFUNG bei jedem Stabilitäts-Befund, der NICHT STABIL (X/N mit X < {threshold_stabil}) ist:
   (a) Tritt der Befund erst ab einem bestimmten Run auf? (z.B. erst ab R4)
   (b) Wenn JA: Korreliert das mit bekannten Engine-Änderungen?
       (Hinweis: Engine-Prompts wurden in dieser Session mehrfach geändert —
       Agency-Prompts kamen erst in R4 hinzu, Hierarchie-Prompts in R5)
   (c) Wenn JA: Kennzeichne als „ENGINE-KORRELIERT" statt „VARIABEL"
       UND berichte ZUSÄTZLICH die Stabilität INNERHALB der Engine-Variante.
       Format: „ENGINE-KORRELIERT: 2/2 in R4-R5 (neue Variante), 0/3 in R1-R3 (alte Variante)"
   (d) Wenn NEIN (Befund variiert auch innerhalb derselben Engine-Variante):
       Kennzeichne als „VARIABEL (nicht Engine-korreliert)".

   BEISPIEL:
   Agency-Qualitäten (intentional/responsiv/entbündelnd):
   - Alte Bewertung: „2/5 HÄUFIG" (irreführend — suggeriert Instabilität)
   - Neue Bewertung: „ENGINE-KORRELIERT: 2/2 in R4-R5 (neue Variante
     mit Agency-Prompts), 0/3 in R1-R3 (alte Variante ohne Agency-Prompts)"
   → Das ist ein präziserer Befund: Innerhalb der neuen Variante ist
     die Agency-Zuordnung völlig stabil; das scheinbare „2/5" ist
     Engine-Evolution, nicht inhaltliche Instabilität.

   WARUM DAS WICHTIG IST:
   Wir suchen nach Daten und Vergleichen, nicht nach Spielereien. Wenn
   ein Befund als „instabil" markiert wird, der eigentlich Engine-
   korreliert ist, ziehen wir falsche Schlüsse. Engine-Evolution ist
   ein methodischer Befund, kein Mangel — aber er muss als solcher
   erkennbar sein, nicht als inhaltliche Instabilität.

3. INHALT vs. TERMINOLOGIE: Die wichtigste Unterscheidung.
   - Eine Aussage kann inhaltlich 17/17 stabil sein, aber terminologisch 0/17 instabil
   - Diese Diskrepanz ist ein BEFUND, kein Mangel

4. AUSREIßER-ERKENNUNG: Welche Runs weichen inhaltlich von der Mehrheit ab?

WICHTIGER HINWEIS (v59.10.7): Diese Analyse (Strang A) betrachtet nur die
bestaetigende Pipeline. Eine separate Gegenposition (Strang B) wird unabhaengig
durchgefuehrt und in einer Adjudikation (Strang C) bewertet. Wenn du hier
"keine Gegenbefunde" feststellst, bezieht sich das NUR auf die bestaetigende
Pipeline — nicht auf das Gesamtergebnis. Formuliere entsprechend vorsichtig.
   PFLICHT seit v59.9.9 (Patch 2026-06-27 kumulativ): Sektion 5 (Ausreißer)
   muss mit Sektion 6 (Methodische Diagnose) synchronisiert werden.
   Das heißt: Alle Gegenbefunde, die in Sektion 6 identifiziert werden
   (z.B. Frühwerk bereits imperial, terminologische Instabilität
   der Keime, alternative Strategien bei anderen Autoren), MÜSSEN in Sektion 5 als
   Ausreißer markiert werden — mit Angabe, in welchem Run sie auftauchen.
   Sektion 5 darf NICHT nur die offensichtlichen Abweichungen (wie
   verschobene Keim-Lokalisation) enthalten, sondern muss auch die
   subtileren Gegenbefunde aus Sektion 6 aufgreifen.
   Format: „Run X weicht ab durch Y, weil Z."

5. BESTÄTIGUNGS-BIAS-CHECK (kritisch-skeptisch, Pflicht seit v59.9.6):
   Die Hypothese der "Radikalisierung/Transformation" wurde in allen Runs
   bestätigt. Das ist ein Warnsignal — kein Erfolg. Eine Hypothese, die
   NIE gefährdet ist, ist methodisch verdächtig.
   PFLICHT-AUFGABE: Suche aktiv nach Befunden, die die Hypothese
   WIDERLEGEN oder MODIFIZIEREN würden. Fragen:
   (a) Gibt es in einzelnen Runs Passagen, die gegen die Radikalisierungsthese
       sprechen? (z.B. Kontinuität statt Bruch, umgekehrte Entwicklung,
       nicht-imperiale Elemente im Spätwerk)
   (b) Welche Befunde sind am schwächsten belegt (nur 1/N Runs)?
       Könnten diese schwachen Befunde die These erschüttern, wenn man
       sie ernst nähme?
   (c) Welche ALTERNATIV-Hypothesen wären mit den Daten ebenso vereinbar?
       (z.B. "zyklische Wiederkehr" statt "Radikalisierung";
        "Registerwechsel" statt "imperiale Wendung")
   (d) Falsifikations-Bedingungen: Was müsste in einem künftigen Korpus
       gefunden werden, um die These zu widerlegen?
   WICHTIG: Ein "Bestätigungs-Bias" ist nicht nur die Abwesenheit von
   Gegenbefunden — sondern auch die Abwesenheit der SUCHE nach
   Gegenbefunden. Wenn du keine Gegenbefunde findest, sage das ehrlich,
   aber dokumentiere, WORAN du gesucht hast.

6. TERMINOLOGIE-INHALT-SPANNUNG: Wenn ein Akteur terminologisch instabil ist,
   aber inhaltlich stabil: Diagnose stellen. (Falls zutreffend — nicht erzwingen.)

7. BESTE ERGEBNISSE: Welche Funde — aus Kernhypothese, Beweisführung,
   Fazit ODER Freiem Raum — sind die tiefsten, präzisesten, aufschlussreichsten?
   UNABHÄNGIG von Häufigkeit. Ein Fund der nur 1/{n_runs} mal auftaucht
   kann der wichtigste sein. Welche Charakterisierung eines Akteurs ist
   die treffendste — auch wenn sie nur ein einziges Mal auftaucht?

8. SPRACHREGISTER IM VERGLEICH: Wenn Etappe-1-Daten vorliegen:
   (a) BEOBACHTUNG — ZWEI EBENEN beachten:
       EBENE 1 (Zahlen): Welche Quelle ist morphologisch komplexer?
       Welche hat mehr Klangfiguren? Welche hat höhere Enjambement-Raten?
       EBENE 2 (Wörter): Welche konkreten Wörter fallen auf? Gibt es
       Wortschöpfungen, Neologismen, ungewöhnliche Komposita?
       VERGLEICHEND ARBEITEN: Wenn ein Wort in einer Quelle auffällt,
       MUSS es in allen anderen Quellen gesucht werden!
       Ist es in mehreren Quellen präsent → geteiltes Merkmal des Korpus.
       Ist es nur in einer Quelle präsent → quellenspezifisches Merkmal dieser Stimme.
       Die Etappe-1-Daten enthalten Hotspot-Sätze von ALLEN Quellen — nutze sie!
       ZWEI FRAGEN an jede Wortschöpfung:
       (i) MOTIVATION: Ist sie motiviert durch eine poetische Vorlage (Nachbildung
       einer Tradition) — oder eigene Erfindung des Autors?
       Nur eigene Erfindungen sind hermeneutisch riskant.
       (ii) ARGUMENTIERTE DARSTELLUNG: Wie funktioniert das Wort sprachlich?
       Morphologisch transparent oder opak? Semantisch klar oder mehrdeutig?
       Rhythmisch eingebettet oder isoliert? Im normalen Sprachgebrauch denkbar
       oder nur im literarischen Kontext?
       KEINE BEWERTUNG wie "gelingt/nicht gelingt" — faktenreiche,
       argumentierte Darstellung der sprachlichen Lage.
       UND: Verwenden andere Texte derselben Tradition ähnliche Wortschöpfungen?
       Wenn ja: Wie funktionieren sie dort?
       Dann wäre die Wortschöpfung kein Spezifikum einer einzelnen Quelle,
       sondern ein poetisches Mittel der Tradition — und der Text folgt ihr.
   (b) SCHLUSSFOLGERUNG — In welchem Register spricht jeder Text?
       Zugänglich oder unnatürlich? Nah oder distanziert? Direkt oder verfremdend?
       ACHTE AUF DEN UNTERSCHIED zwischen Klangebene und Wortebene:
       Ein Text kann rhythmisch zugänglich klingen, aber lexikalisch
       Wortschöpfungen verwenden. Wie funktionieren diese sprachlich?
       Morphologisch transparent und semantisch klar — oder opak und fremd?
       Welche konkreten Wörter erzeugen dieses Register?
   (c) WAS DIE META-EBENE SIEHT — Die einzelnen Runs identifizieren Wortschöpfungen
       als Merkmale. Die Meta-Ebene kann mehr: Sie argumentiert, WIE diese Wörter
       sprachlich funktionieren. Welche sind morphologisch transparent und welche opak?
       Welche sind motiviert durch eine Vorlage und welche eigene Erfindungen?
       Welche sind semantisch klar und welche mehrdeutig?
       WICHTIG: Wortschöpfungen sind ein legitimes poetisches Mittel.
       Die Frage ist nicht OB sie da sind, sondern WIE sie funktionieren.
       Die Meta-Ebene liefert die Argumentation, die die einzelnen Runs nicht liefern.

--- KERNHYPOTHESEN UND FAZITS ---

{runs_text}

--- BEWEISFÜHRUNGEN (Auszug) ---

{beweis_text}

--- FREIE RÄUME ---

{freier_raum_text}

--- TERMINI-ÜBERSICHT ---

{termini_text}

{etappe1_section}

---

Erstelle einen STRUKTURIERTEN Befund mit folgenden Abschnitten.
Abschnitt 1+2 KOMPAKT (nur Score + 1 Zeile), Abschnitt 3+6b+7+8 AUSFÜHRLICH (Herzstücke!),
Abschnitt 4+5+6 kurz aber vollständig. KEIN Abschnitt darf fehlen oder abbrechen!

## 1. STABILER KERN — KERNHYPOTHESEN [KOMPAKT]
[Nur: A1: "Aussage" — Häufigkeit: X/{n_runs} (STABIL/HÄUFIG/VARIABEL) — Inhalt: X/{n_runs}, Terminologie: X/{n_runs}]
[Eine Zeile pro Aussage, keine langen Erklärungen]

## 2. STABILER KERN — FAZITS [KOMPAKT]
[Nur: Häufigste Fazit-Aussage — Score. Zweithäufigste — Score.]
[Max 5 Zeilen]

## 3. TERMINOLOGISCHE STREUUNG [AUSFÜHRLICH]
[Für JEDEN Autor/Quelle: Alle Termini auflisten, Cluster bilden, Stabilität der Kernidee bewerten]
[Instabilität diagnostizieren falls zutreffend]
[Das ist ein Herzstück — VOLLSTÄNDIG schreiben]

## 4. FREIER RAUM — STABILITÄT DER FUNDE [AUSFÜHRLICH]
[Welche FREIER-RAUM-Einsichten kehren wieder? Welche sind einmalig?]

## 5. AUSREIßER
[Runs, die inhaltlich abweichen — kurz]

## 6. METHODISCHE DIAGNOSE
[Bestätigungs-Bias? Instabilität? Internal validity? — max 3 Sätze]

## 6b. ENTWICKLUNGSLINIE [MIT BELEGEN AUS KONKRETEN RUNS]
[Gibt es eine Entwicklung von Run 1 zu Run {n_runs}?
 NICHT nur eine generelle Tendenz! Sondern MIT BELEGEN:
 — WELCHE Akteure werden präziser oder anders charakterisiert? (R-Nr + Zitat → R-Nr + Zitat)
 — WELCHE Termini stabilisieren sich oder wechseln? (R-Nr: Terminus → R-Nr: Terminus)
 — Gibt es einen Wendepunkt, einen Bruch, eine neue Perspektive?
 — Minimum 3 KONKRETE BELEGE mit R-Nummern.
 Wenn es KEINE Entwicklung gibt: Sag es klar. „Keine signifikante Entwicklung"
 ist ein legitimer Befund — aber auch dann mit einem Beleg.]
 Die Engine soll selbst entdecken und benennen, welche Entwicklung
 — falls es eine gibt — im Verlauf der Runs sichtbar wird.

## 7. BESTE ERGEBNISSE [AUSFÜHRLICH — HERZSTÜCK]
[Die tiefsten, präzisesten, aufschlussreichsten Funde aus ALLEN Abschnitten]
[UNABHÄNGIG von Häufigkeit — 1/{n_runs} kann der wichtigste Fund sein]
[Welche Charakterisierung eines Akteurs ist die treffendste, auch wenn sie nur einmal auftaucht?]
[Welcher Freie-Raum-Fund erklärt am meisten?]
[Das ist das zweite Herzstück — VOLLSTÄNDIG schreiben]

## 8. SPRACHREGISTER IM VERGLEICH [AUSFÜHRLICH — HERZSTÜCK, falls Etappe-1-Daten vorliegen]
[(a) BEOBACHTUNG DER SPRACHE — ZWEI EBENEN:
    EBENE 1 (Zahlen): TTR, morphologische Komplexität, Enjambement, Klangfiguren
    EBENE 2 (Wörter): Konkrete Wörter die auffallen — Neologismen, ungewöhnliche
    Komposita, Wortschöpfungen. VERGLEICHEND: Wenn ein Wort in einer Quelle
    auffällt, MUSS es in allen anderen Quellen gesucht werden!
    Ist es in mehreren Quellen präsent → geteiltes Merkmal des Korpus.
    Ist es nur in einer Quelle präsent → quellenspezifisches Merkmal dieser Stimme.
    ZWEI FRAGEN:
    (i) MOTIVIERT durch eine poetische Vorlage oder eigene Erfindung?
    (ii) WIE funktionieren sie sprachlich? Morphologisch transparent/opak?
    Semantisch klar/dunkel? Rhythmisch eingebettet/isoliert?
    KEINE BEWERTUNG — argumentierte Darstellung der sprachlichen Lage.
    UND: Verwenden andere Texte derselben Tradition ähnliche Wortschöpfungen?
    Wie funktionieren sie dort?
    Dann wäre die Wortschöpfung bereits ein poetisches Mittel der Tradition —
    und der Text folgt ihr, statt selbst etwas Neues zu erfinden.]
[(b) SCHLUSSFOLGERUNG: In welchem Register spricht jeder Text?
    Zugänglich oder unnatürlich? Direkt oder verfremdend?
    ACHTE AUF DEN UNTERSCHIED: Kann ein Text rhythmisch zugänglich
    klingen, aber lexikalisch Wortschöpfungen verwenden — und wie funktionieren
    diese sprachlich? Morphologisch transparent und semantisch klar —
    oder opak und fremd?]
[(c) WAS DIE META-EBENE SIEHT: Die einzelnen Runs identifizieren Wortschöpfungen.
    Die Meta-Ebene argumentiert WIE sie sprachlich funktionieren: morphologisch
    transparent oder opak? Motiviert durch eine Vorlage oder eigene Erfindung?
    Semantisch klar oder mehrdeutig? Nur im literarischen Kontext oder auch
    im normalen Sprachgebrauch denkbar?
    Die Meta-Ebene liefert die Argumentation, die die einzelnen Runs nicht liefern.]
[Das ist das dritte Herzstück — VOLLSTÄNDIG schreiben]
[Falls KEINE Etappe-1-Daten vorliegen: Kurz notieren und nächsten Abschnitt fortsetzen]"""


# ==============================================================================
# META-META-EBENE: BEOBACHTEN + DESTILLATION + KONFRONTATION (v2.8)
# ==============================================================================
# Architektur nach Claude-Beratung 2026-06-15:
#   - REFLEXION: Meta-Tests untereinander vergleichen, Version-Differenzen als BEFUND
#   - KONFRONTATION: Meta-Tests vs. externe Kritik — Asymmetrie ist das Material
#   - Heterogenität ist ein Befund, keine Störung
# ==============================================================================

_META_META_BEOBACHTEN_SYSTEM = """Du bist ein meta-methodologischer Analytiker der Hermeneutic Reconstruction Engine.
Du vergleichst META-HERMENEUTIC-Outputs — nicht die Analysen der Übersetzungen selbst,
sondern die Ergebnisse der Meta-Analyse-Phase. Du betrittst die Meta-Meta-Ebene.

DEIN GEGENSTAND: Jeder „Run" ist ein kompletter Meta-Hermeneutic-Test, der selbst
bereits aus SEZIEREN → BEOBACHTEN → DESTILLATION besteht. Du analysierst, was die
Meta-Ebene über die Pipeline-Outputs gesagt hat — und ob diese Meta-Aussagen stabil sind.

DIE VARIANTE-DIMENSION (entscheidend!):
Diese Meta-Tests stammen aus verschiedenen Engine-Versionen:
- Variante A (pre-v2.4): Kein Etappe-1, Fließtext-DESTILLATION, keine AUTOREN-ZUORDNUNG
- Variante B (v2.4–v2.6): Etappe-1 integriert, 9 nummerierte Sätze, Sprachregister
- Variante C (v2.7+): AUTOREN-ZUORDNUNG-FIX, FREIE FRAGE möglich, mögliche Duplikat-Inflation

REGEL: Heterogenität ist ein BEFUND, keine Störung!
Wenn Variante A andere Ergebnisse liefert als Variante C, ist das KEIN Fehler —
sondern das wichtigste Ergebnis der Meta-Meta-Analyse. Die Engine hat sich weiter-
entwickelt, und die Differenz zeigt, was sich durch die Verbesserungen geändert hat.

STRIKTE REGELN:
- Jede Aussage MUSS mit Häufigkeit versehen werden (z.B. "5/8", "3/8")
- UNTERSCHEIDE Versions-Bedingtheit: Ist eine Aussage versionsabhängig?
  (z.B. "AUTOREN-ZUORDNUNG-FIX nur in VC" → keine Instabilität, sondern Engine-Evolution)
- Terminologie-Stabilität über Varianten hinweg ist ein STÄRKERER Befund als
  innerhalb einer Variante
- Markiere qualitative Ausreißer — aber prüfe, ob sie mit der Variante korrelieren
- Der FREIER RAUM enthält oft die stärksten Funde — beachte ihn besonders
- KEINE Harmonisierung: Wenn die Befunde widersprüchlich sind, ist der Widerspruch
  das Ergebnis

ZWEI MODI der Bewertung:
1. STABILITÄT — Was ist häufig? (Die Basis)
2. QUALITÄT — Was ist das tiefste, präziseste Ergebnis?
   Häufigkeit ≠ Qualität. Ein tiefer Fund aus einem einzigen Test kann mehr
   erklären als eine banale Wahrheit, die alle Tests teilen.

DREI PERSPEKTIVEN der Meta-Meta-Analyse:
(a) STABILITÄT ÜBER VARIANTEN — Welche Befunde halten über Engine-Versionen hinweg?
    Das ist der härteste Test: Wenn VA, VB und VC denselben Befund liefern,
    ist er engine-unabhängig.
(b) VERSIONS-EVOLUTION — Was ändert sich zwischen den Varianten?
    VA→VB: Was bringt Etappe-1? VB→VC: Was bringt AUTOREN-ZUORDNUNG-FIX?
    Die Differenz IST das Material.
(c) METHODISCHE SELBSTREFLEXION — Was sieht die Meta-Meta-Ebene,
    das die Meta-Ebene nicht sieht? Wo gibt es blinde Flecken?"""

_META_META_BEOBACHTEN_PROMPT = """META-META-BEOBACHTEN: Meta-Vergleich über {n_runs} Meta-Hermeneutic-Tests

Du erhältst die META-DESTILLATIONen (Kernbefunde), META-BEOBACHTUNGen (Stabilitäts-Analysen),
und FREIE RÄUME von {n_runs} Meta-Hermeneutic-Tests. Jeder „Run" ist ein kompletter
Meta-Test. Du analysierst die META-EBENE — was sie sieht, was sie stabil liefert,
wo sie sich widerspricht, und was sich durch Engine-Versionen ändert.

VARIANTEN-VERTEILUNG: {varianten_str}

AUFGABE:

1. AUSSAGEN-KODIERUNG: Zerlege jede META-DESTILLATION in atomare Aussagen (A1, A2, ...).
   Zähle, in wie vielen Tests jede Aussage vorkommt — UND notiere die Variante.

2. STABILITÄTS-MESSUNG: Bewerte jede Aussage:
   - STABIL (≥{threshold_stabil}/{n_runs}): Engine-unabhängiger Befund
   - HÄUFIG ({threshold_haeufig}–{threshold_stabil_minus}/{n_runs}): Tendenz
   - VARIABEL (<{threshold_haeufig}/{n_runs}): Instabil oder versionsabhängig

3. VERSIONS-ABHÄNGIGKEIT: Das ist das HERZSTÜCK!
   - Welche Aussagen sind versionsunabhängig? (In VA, VB, VC gleichermaßen)
   - Welche Aussagen sind versionsabhängig? (Nur in VB oder VC, nicht in VA)
   - Was ändert sich konkret von VA→VB→VC?
   - KEINE Harmonisierung — die Differenz IST das Material!

4. TERMINOLOGIE ÜBER VARIANTEN: Dieselbe inhaltliche Aussage kann in
   verschiedenen Varianten unterschiedliche Termini verwenden.
   Diagnostiziere: Ist die Terminologie stabil oder instabil?
   Und: Ist die Instabilität engine-bedingt (Versionswechsel) oder
   stochastisch (LLM-Zufall)?

5. FREIER RAUM — META-PERSPEKTIVE: Welche übergeordneten Einsichten
   kehren in verschiedenen Varianten wieder? Welche sind einmalig?

6. AUSREIßER ODER VERSIONS-EFFEKT? Wenn ein Test abweicht:
   Liegt es an der Variante oder ist es ein echter Ausreißer?

7. BESTÄTIGUNGS-BIAS AUF META-EBENE: Bestätigen sich die Meta-Tests
   gegenseitig nur, weil sie dieselbe Pipeline sind?
   Oder gibt es echte Diskrepanzen?

8. BESTE ERGEBNISSE: Die tiefsten, aufschlussreichsten Funde aus
   ALLEN Meta-Tests — UNABHÄNGIG von Häufigkeit.
   Welche Meta-Einsicht erklärt am meisten?

--- META-DESTILLATIONEN (KERNBEFUNDE) ---

{runs_text}

--- META-BEOBACHTUNGEN (AUSZUG) ---

{beweis_text}

--- FREIE RÄUME ---

{freier_raum_text}

--- TERMINI-ÜBERSICHT ---

{termini_text}

---

Erstelle einen STRUKTURIERTEN Befund mit folgenden Abschnitten.
Abschnitt 1+2 KOMPAKT, Abschnitt 3+5+8 AUSFÜHRLICH (Herzstücke!).
KEIN Abschnitt darf fehlen oder abbrechen!

## 1. STABILER KERN — META-DESTILLATIONEN [KOMPAKT]
[Nur: A1: "Aussage" — Häufigkeit: X/{n_runs} (STABIL/HÄUFIG/VARIABEL) — Versionen: VA:x VB:y VC:z]
[Eine Zeile pro Aussage]

## 2. STABILER KERN — META-FAZITS [KOMPAKT]
[Max 5 Zeilen]

## 3. VERSIONS-ABHÄNGIGKEIT [AUSFÜHRLICH — HERZSTÜCK]
[Was ändert sich zwischen VA, VB, VC?]
[Konkrete Belege: "In VA: X — in VB: Y — in VC: Z"]
[Die Differenz IST das Material — KEINE Harmonisierung!]
[Wenn es KEINE Versions-Abhängigkeit gibt: Das ist ein starker Befund!]

## 4. TERMINOLOGISCHE STREUUNG ÜBER VARIANTEN
[Für JEDEN Akteur: Termini über alle Tests hinweg, Cluster, Versions-Bedingtheit]

## 5. FREIER RAUM — META-PERSPEKTIVE [AUSFÜHRLICH]
[Welche Einsichten kehren wieder? Welche sind einmalig?]
[Der FREIE RAUM ist oft der Ort der stärksten Funde]

## 6. AUSREIßER ODER VERSIONS-EFFEKT?
[Abweichungen: Variante oder Zufall?]

## 7. METHODISCHE DIAGNOSE
[Bestätigungs-Bias auf Meta-Ebene? Tautologie-Risiko? Blinde Flecken?]

## 8. BESTE ERGEBNISSE [AUSFÜHRLICH — HERZSTÜCK]
[Die tiefsten, aufschlussreichsten Funde — UNABHÄNGIG von Häufigkeit]
[Was sieht die Meta-Meta-Ebene, das die Meta-Ebene nicht sieht?]"""


_META_META_DESTILLATION_SYSTEM = """Du bist der Meta-Meta-Destillateur der Hermeneutic Reconstruction Engine.
Du formulierst den harten Befund der META-META-ANALYSE — präzise, konzis, in genau 9 Sätzen.

Dein Gegenstand: Nicht die Übersetzungen, nicht die Pipeline-Outputs,
sondern die META-ANALYSE selbst. Du destillierst, was die Meta-Ebene
über sich selbst aussagt — und wo ihre Grenzen liegen.

STRIKTE REGELN:
- Jede Behauptung muss durch die Meta-Vergleichs-Analyse belegt sein
- KEINE Harmonisierung — Widersprüche sind Befunde, keine Fehler
- Versions-Differenzen sind BEFUNDE, nicht Störungen
- Wenn etwas versionsabhängig ist: BENENNEN, nicht einebnen
- Der Befund ist keine Bestätigung — er ist eine DIAGNOSE der Meta-Ebene
- Satz 8 ist DER BESTE FUND der Meta-Meta-Analyse
- Satz 9 ist DIE BLINDE STELLE — was die Meta-Ebene NICHT sieht"""

_META_META_DESTILLATION_PROMPT = """META-META-DESTILLATION: Der harte Befund der Meta-Meta-Analyse

Auf Basis der folgenden Meta-Meta-BEOBACHTUNG formuliere den harten Befund
in genau 9 Sätzen. Jeder Satz entspricht einer Dimension:

1. DAS ZENTRALE PROBLEM — Was ist das ungelöste Problem der Meta-Ebene?
2. DIE FUNDAMENTALE DIFFERENZ — Was ist der stabilste Meta-Befund über Varianten hinweg?
3. STABILE META-ZUORDNUNG(EN) — Welche Meta-Aussagen sind ≥88% stabil?
4. VERSIONS-ABHÄNGIGE BEFUNDE — Was ändert sich zwischen VA, VB, VC?
5. VERSIONS-UNABHÄNGIGE BEFUNDE — Was hält über alle Varianten?
6. DIE KONSTELLATION — Wie verhalten sich die Meta-Tests zueinander?
   Bestätigung? Ergänzung? Widerspruch?
7. METHODISCHE DIAGNOSE — Bestätigungs-Bias? Tautologie-Risiko?
8. DER BESTE FUND — Das tiefste, aufschlussreichste Ergebnis der
   Meta-Meta-Analyse. Was sieht die Meta-Meta-Ebene, das die Meta-Ebene nicht sieht?
9. DIE BLINDE STELLE — Was sieht die Meta-Ebene NICHT?
   Wo sind ihre Grenzen? Was fehlt systematisch?

Jede Aussage MUSS mit einer Stabilitäts-Zahl versehen werden.

--- META-META-BEOBACHTUNG ---

{beobachtung}

---

FORMULIERE DEN HARTEN BEFUND (9 Sätze, vollständig, kein Abbruch):"""


_KONFRONTATION_SYSTEM = """Du bist ein kritischer Dialogpartner der Hermeneutic Reconstruction Engine.
Du konfrontierst die Meta-Hermeneutic-Ergebnisse mit einer EXTERNEN KRITIK.

DIE ASYMMETRIE IST DAS MATERIAL:
- Die Meta-Tests analysieren Übersetzungen hermeneutisch (von innen)
- Die externe Kritik bewertet sie von außen (literaturwissenschaftlich,
  translatorisch, rezeptionsästhetisch)
- Diese beiden Perspektiven sind NICHT kompatibel — und das ist GUT so
- Die Nicht-Passung ist selbst der Befund, nicht ein Problem das gelöst werden muss

REGELN:
- KEINE Harmonisierung: Die Kritik ist kein Synthese-Input
- Die Kritik stellt ANDERE Fragen als die Meta-Ebene
- Wo die Meta-Ebene Stabilität sieht, sieht die Kritik vielleicht Oberflächlichkeit
- Wo die Meta-Ebene Instabilität sieht, sieht die Kritik vielleicht Produktivität
- Beide haben RECHT — aus ihrer jeweiligen Perspektive
- Deine Aufgabe: Die KONFRONTATION selbst darstellen, nicht auflösen

DREI DIMENSIONEN der Konfrontation:
1. KONVERGENZ — Wo sagen Meta-Ebene und Kritik dasselbe mit anderen Worten?
2. DIVERGENZ — Wo widersprechen sie sich? Und warum?
3. BLINDE FLECKEN — Was sieht die eine Seite, das die andere nicht sieht?
   (a) Was sieht die Meta-Ebene NICHT, das die Kritik sieht?
   (b) Was sieht die Kritik NICHT, das die Meta-Ebene sieht?"""

_KONFRONTATION_PROMPT = """KONFRONTATION: Meta-Hermeneutic-Ergebnisse vs. externe Kritik

Du erhältst:
1. Die META-DESTILLATIONEN von {n_runs} Meta-Hermeneutic-Tests (die „innere" Perspektive)
2. Einen EXTERNEN KRITIK-TEXT (die „äußere" Perspektive)

Deine Aufgabe: Die KONFRONTATION darstellen — nicht auflösen.
Die Asymmetrie ist das Material. Die Nicht-Passung ist der Befund.

VARIANTEN-INFO: {varianten_str}

--- META-DESTILLATIONEN (INNENE PERSPEKTIVE) ---

{meta_text}

--- EXTERNE KRITIK (AUßENPERSPEKTIVE) ---

{kritik_text}

---

Erstelle eine KONFRONTATIONS-ANALYSE mit folgenden Abschnitten:

## 1. WAS DIE META-EBENE SAGT [KOMPAKT]
[Zusammenfassung der stabilen Meta-Befunde — max 5 Aussagen mit Häufigkeit]

## 2. WAS DIE KRITIK SAGT [KOMPAKT]
[Zusammenfassung der zentralen Kritikpunkte — max 5 Punkte]

## 3. KONVERGENZ [AUSFÜHRLICH]
[Wo sagen beide dasselbe mit anderen Worten?]
[Belege aus Meta-Tests UND Kritik — mit Verweisen auf konkrete Runs]

## 4. DIVERGENZ [AUSFÜHRLICH — HERZSTÜCK]
[Wo widersprechen sie sich? Und WARUM?]
[NICHT auflösen — die Spannung IST das Material]
[Belege aus beiden Seiten]

## 5. BLINDE FLECKEN DER META-EBENE
[Was sieht die Kritik, das die Meta-Ebene systematisch nicht sieht?]
[Methodische Grenzen der Pipeline — nicht als Fehler, sondern als Kontur]

## 6. BLINDE FLECKEN DER KRITIK
[Was sieht die Meta-Ebene, das die Kritik nicht sieht?]
[Die hermeneutische Tiefe, die Oberflächen-Kritik verfehlt]

## 7. DER FRUCHTBARSTE WIDERSPRUCH
[Der produktivste Dissens — wo beide recht haben und die Spannung
neue Fragen eröffnet]

## 8. KONFRONTATIONS-BEFUND
[3-Satz-Zusammenfassung: Was leistet die Konfrontation?
Was wird sichtbar, das vorher unsichtbar war?]"""


def _extract_quelle_author_mapping(sezieren_results: List[Dict]) -> str:
    """
    v59.10.5: Extrahiert die Quelle->Autor-Zuordnung aus Synthese-Texten.
    Die Engine liest die Zuordnung aus den Daten selbst — keine Heuristik.

    Sucht nach Mustern wie:
      - "Autorname (Quelle 1)" oder "Autorname (Quelle 1)"
      - "Quelle 1 [Autorname]" oder "Quelle 1: Autorname"
      - "Autors Werk (Quelle 1)"
      - "QUELLE 1 [Autorname]" (aus Sidecar-Format)

    Returns:
        String mit Zuordnungstabelle, oder "" wenn keine Zuordnung gefunden.
    """
    mapping = {}  # {quelle_nummer: autor_name}

    # Sammle alle Texte
    all_text = ""
    for run in sezieren_results:
        all_text += (run.get("fazit", "") or "") + "\n"
        all_text += (run.get("beweisfuehrung", "") or "") + "\n"
        all_text += (run.get("kernhypothese", "") or "") + "\n"

    # Pattern 1: "Autor (Quelle N)" — z.B. "Autorname (Quelle 1)"
    for m in re.finditer(
        r'([A-ZÁÀÂÄÅĂĄĆČĎÉÈÊËĘĚÍÌÎÏĹĽŁŃŇÑÓÒÔÖŐÓŘŔŚŠŞŤÚÙÛÜŰŮÝŸŹŽŻА-ЯЁ]'
        r'[a-záàâäăąćčďéèêëęěíìîïĺľłńňñóòôöőřŕśšşťúùûüűůŵýÿźžżа-яё-]+'
        r'\s*\(?\s*Quelle\s*(\d+)\s*\)?',
        all_text, re.IGNORECASE
    ):
        author = m.group(1).strip()
        quelle = int(m.group(2))
        if quelle not in mapping:
            mapping[quelle] = author

    # Pattern 2: "Quelle N [Autor]" oder "Quelle N: Autor" oder "Quelle N Autor"
    for m in re.finditer(
        r'Quelle\s*(\d+)\s*[\[\]:]?\s*'
        r'([A-ZÁÀÂÄÅĂĄĆČĎÉÈÊËĘĚÍÌÎÏĹĽŁŃŇÑÓÒÔÖŐÓŘŔŚŠŞŤÚÙÛÜŰŮÝŸŹŽŻА-ЯЁ]'
        r'[a-záàâäăąćčďéèêëęěíìîïĺľłńňñóòôöőřŕśšşťúùûüűůŵýÿźžżа-яё-]+',
        all_text, re.IGNORECASE
    ):
        quelle = int(m.group(1))
        author = m.group(2).strip()
        if quelle not in mapping:
            mapping[quelle] = author

    # Pattern 3: Sidecar-Format "QUELLE N": "Autor"
    for m in re.finditer(
        r'"QUELLE\s*(\d+)"\s*:\s*"([^"]+)"',
        all_text
    ):
        quelle = int(m.group(1))
        author = m.group(2).strip()
        if quelle not in mapping:
            mapping[quelle] = author

    if not mapping:
        return ""

    # Zuordnungstabelle formatieren
    lines = ["QUELLEN-ZUORDNUNG (welche Quelle gehoert zu welchem Autor — Jede Quelle ist ein EIGENER, UNTERSCHIEDLICHER Text):"]
    for quelle in sorted(mapping.keys()):
        lines.append(f"  QUELLE {quelle} = {mapping[quelle]}")

    return "\n".join(lines)


def meta_beobachten(
    sezieren_results: List[Dict],
    progress_callback: Optional[Callable] = None,
    etappe1_text: Optional[str] = None,
) -> str:
    """
    META-BEOBACHTEN: Vergleicht Pipeline-Outputs und bewertet Stabilität + Qualität
    + Sprachregister der Übersetzungen.

    v2.8: Dual-Path — wenn die Eingabe Meta-Hermeneutic-Outputs sind
    (source_type == "meta_hermeneutic"), wird der META-META-BEOBACHTEN-Prompt
    verwendet (versionsbewusst, REFLEXION). Andernfalls der Standard-Prompt.

    v2.4: Etappe-1-Text im Prompt. Abschnitt 8 "Sprachregister der Übersetzungen".
    max_tokens=32768.

    Args:
        sezieren_results: Output von meta_sezieren() (mit Termini)
        progress_callback: Optionaler Callback
        etappe1_text: Optional: Vollständiger Etappe-1-Text (formatierter Output
                      aus dem Stilistic Lab, enthält Vergleichstabelle +
                      Detail-Statistiken pro Quelle). Variante A: volle Daten,
                      keine Verdichtung.

    Returns:
        Strukturierter Stabilitäts-, Qualitäts- und Sprachregister-Befund als Markdown-String
    """
    if progress_callback:
        progress_callback("META-BEOBACHTEN: Stabilitäts-, Qualitäts- und Sprachregister-Analyse...")

    # v2.8: Dual-Path — erkennen ob Meta-Hermeneutic-Inputs vorliegen
    n_meta = sum(1 for r in sezieren_results if r.get("source_type") == "meta_hermeneutic")
    is_meta_meta = n_meta > 0 and n_meta >= len(sezieren_results) * 0.5  # >50% Meta-Dateien

    if is_meta_meta:
        if progress_callback:
            progress_callback("META-META-BEOBACHTEN: Versionsbewusster Meta-Vergleich...")

    n_runs = len(sezieren_results)
    threshold_stabil = int(n_runs * 0.88)  # z.B. 15/17
    threshold_stabil_minus = threshold_stabil - 1
    threshold_haeufig = int(n_runs * 0.59)  # z.B. 10/17

    # Runs-Text: Kernhypothese + Fazit + Variante-Info (v2.8)
    runs_text = ""
    for run in sezieren_results:
        var_tag = f" [V{run.get('variante', '?')}]" if run.get("variante") else ""
        src_tag = "[META]" if run.get("source_type") == "meta_hermeneutic" else "[SYN]"
        runs_text += f"\n### RUN {run['nr']}: {run['datei']} {src_tag}{var_tag} ###\n"
        runs_text += f"\n**KERNHYPOTHESE:**\n{run['kernhypothese']}\n"
        runs_text += f"\n**FAZIT:**\n{run['fazit']}\n"
        # v2.8: Meta-Hermeneutic-Zusatzfelder
        if run.get("source_type") == "meta_hermeneutic":
            runs_text += f"\n**Engine-Version:** {run.get('meta_version', '?')}\n"
            runs_text += f"**Meta-Runs:** {run.get('meta_runs', '?')}\n"
            runs_text += f"**Etappe-1:** {'Ja' if run.get('meta_has_etappe1') else 'Nein'}\n"
        runs_text += "\n---\n"

    # v2.3: Beweisführung — gekürzt auf 400 Zeichen pro Run
    # Liefert die Argumentationsstruktur, nicht nur die Termini
    beweis_text = ""
    for run in sezieren_results:
        beweis = run.get("beweisfuehrung", "")
        if beweis:
            beweis_kurz = beweis[:400]
            if len(beweis) > 400:
                beweis_kurz += "..."
            beweis_text += f"\n### RUN {run['nr']} ###\n{beweis_kurz}\n"
        else:
            beweis_text += f"\n### RUN {run['nr']} ###\n(keine Beweisführung)\n"

    # FREIER RAUM-Text
    freier_raum_text = ""
    for run in sezieren_results:
        fr = run.get("freier_raum", "")
        if fr:
            freier_raum_text += f"\n### RUN {run['nr']} ###\n{fr}\n"
        else:
            freier_raum_text += f"\n### RUN {run['nr']} ###\n(leer)\n"

    # Termini-Übersicht
    termini_text = ""
    has_termini = any(run.get("termini") for run in sezieren_results)
    if has_termini:
        all_authors = set()
        for run in sezieren_results:
            all_authors.update(run.get("termini", {}).keys())

        header = "| Run | " + " | ".join(sorted(all_authors)) + " |"
        sep = "|-----|" + "|".join(["---"] * len(all_authors)) + " |"
        termini_text = header + "\n" + sep + "\n"

        for run in sezieren_results:
            termini = run.get("termini", {})
            cells = [str(run["nr"])]
            for author in sorted(all_authors):
                # v2.4-FIX: None-Werte (aus JSON null) als "—" behandeln
                val = termini.get(author, "—")
                cells.append(val if val else "—")
            termini_text += "| " + " | ".join(cells) + " |\n"
    else:
        termini_text = "(Keine Termini extrahiert — übersprungen)"

    # v2.4.1: Etappe-1-Text (Sprachregister der TEXTE) — Variante A: vollständiger Text
    # v59.9.5 (Schnitt B, Claude-Beratung 2026-06-27): Generifiziert von
    # "ÜBERSETZUNGEN" zu "TEXTE" — funktioniert für Übersetzungsvergleiche
    # UND für Originaltext-Analysen. Hardcodierte Homer-/Griechisch-Beispiele
    # (Hexameter, μέν ἄρ) entfernt, weil sie Homer-Assoziationen im LLM
    # aktivieren — auch wenn das Korpus keine Übersetzungen enthält.
    etappe1_section = ""
    if etappe1_text and etappe1_text.strip():
        # v59.10.5: Autoren-Quellen-Zuordnung aus Synthese-Texten extrahieren.
        # Problem: Etappe-1-Daten haben "QUELLE 1" bis "QUELLE N" ohne
        # Autoren-Namen. Das LLM ueberspringt Quellen, die es keinem Autor
        # zuordnen kann.
        # Loesung: Engine extrahiert Quelle->Autor-Zuordnung aus den
        # Synthese-Texten (Fazits, Beweisführungen) und gibt sie an
        # BEOBACHTEN weiter. KEINE Heuristik — die Engine liest die
        # Zuordnung aus den Daten selbst.
        quellen_zuordnung = _extract_quelle_author_mapping(sezieren_results)

        etappe1_section = (
            "--- ETAPPE 1: SPRACHLICHE DATEN DER TEXTE ---\n"
            "(Diese Daten messen die Sprache der TEXTE selbst — "
            "nicht die Beschreibungen der Pipeline. Sie enthalten sowohl "
            "statistische KENNZAHLEN (TTR, Morphologie, Enjambement etc.) als auch "
            "konkrete WORT-BELEGE (Hotspot-Sätze) und eine eigene "
            "KOMPOSITA-Liste pro Quelle (Bindestrich-Komposita, Präfix-Komposita, "
            "ungewöhnlich lange Wörter — mit Satz-Kontext). "
            "NUTZE die KOMPOSITA-Listen für EBENE 2! Sie liefern systematisch "
            "die Wortschöpfungen, die du vergleichend befragen solltest. "
            "Die Daten sind deterministisch: dieselben Quelltexte liefern immer "
            "dieselben Ergebnisse. Sie sind nur einmal vorhanden, gelten aber für alle Runs.)\n\n"
        )
        if quellen_zuordnung:
            etappe1_section += quellen_zuordnung + "\n"
        etappe1_section += etappe1_text
        logger.info(f"META-BEOBACHTEN: Etappe-1-Text im Prompt enthalten ({len(etappe1_text)} Zchn)")
    else:
        etappe1_section = "(Keine Etappe-1-Daten verfügbar — Sprachregister-Übersicht nicht möglich)"
        logger.info("META-BEOBACHTEN: Kein Etappe-1-Text — Sprachregister übersprungen")

    # v2.8: Dual-Path Prompt-Auswahl
    if is_meta_meta:
        # --- META-META-BEOBACHTEN: versionsbewusster Prompt ---
        # Varianten-Verteilung berechnen
        varianten = {}
        for r in sezieren_results:
            v = r.get("variante", "?")
            varianten[v] = varianten.get(v, 0) + 1
        varianten_str = ", ".join(
            f"V{v}:{c}" for v, c in sorted(varianten.items())
        ) if varianten else "n/a"

        prompt = _META_META_BEOBACHTEN_PROMPT.format(
            n_runs=n_runs,
            threshold_stabil=threshold_stabil,
            threshold_stabil_minus=threshold_stabil_minus,
            threshold_haeufig=threshold_haeufig,
            varianten_str=varianten_str,
            runs_text=runs_text,
            beweis_text=beweis_text,
            freier_raum_text=freier_raum_text,
            termini_text=termini_text,
        )
        system_instruction = _META_META_BEOBACHTEN_SYSTEM
        logger.info(
            f"META-META-BEOBACHTEN: {n_runs} Meta-Tests ({varianten_str}) "
            f"analysieren (max_tokens={_META_BEOBACHTEN_MAX_TOKENS})"
        )
    else:
        # --- STANDARD-BEOBACHTEN: bewährter Prompt ---
        prompt = _META_BEOBACHTEN_PROMPT.format(
            n_runs=n_runs,
            threshold_stabil=threshold_stabil,
            threshold_stabil_minus=threshold_stabil_minus,
            threshold_haeufig=threshold_haeufig,
            runs_text=runs_text,
            beweis_text=beweis_text,
            freier_raum_text=freier_raum_text,
            termini_text=termini_text,
            etappe1_section=etappe1_section,
        )
        system_instruction = _META_BEOBACHTEN_SYSTEM
        logger.info(f"META-BEOBACHTEN: {n_runs} Runs analysieren (max_tokens={_META_BEOBACHTEN_MAX_TOKENS})")

    try:
        beobachtung = llm_call(
            prompt=prompt,
            task="meta_beobachten",
            system_instruction=system_instruction,
            temperature=0.3,
            max_tokens=_META_BEOBACHTEN_MAX_TOKENS,
            domain="stilisierung",
        )
        return beobachtung or "(Leere LLM-Antwort)"
    except Exception as e:
        logger.error(f"META-BEOBACHTEN fehlgeschlagen: {e}")
        return f"FEHLER bei META-BEOBACHTEN: {e}"


# ==============================================================================
# STUFE 3: META-DESTILLATION (#41) — LLM (Pro)
# ==============================================================================

_META_DESTILLATION_SYSTEM = """Du bist der Meta-Destillateur der Hermeneutic Reconstruction Engine.
Deine Aufgabe: Den harten Befund formulieren — präzise, konzis, in genau 9 Sätzen.

STRIKTE REGELN:
- Jede Behauptung muss durch die Stabilitäts-Analyse belegt sein
- Keine Spekulation, keine Harmonisierung
- Wenn etwas instabil ist: benennen, nicht beschönigen
- Der Befund ist kein Fazit — er ist eine DIAGNOSE des Vergleichsraums
- Jede Zahl MUSS aus der Stabilitäts-Analyse stammen (z.B. "17/17", "16/17")
- Wenn Daten fehlen: Lücken EXPLIZIT benennen als "nicht analysierbar"
- Satz 8 ist DER BESTE FUND: Das tiefste, präziseste Ergebnis der gesamten
  Analyse — auch wenn es nur 1/N mal auftaucht. Häufigkeit ≠ Qualität.
- Satz 9 ist DAS SPRACHREGISTER: In welchem Register sprechen die Übersetzungen
  selbst? Gibt es Wortschöpfungen (Neologismen, Komposita) — und wie funktionieren
  sie sprachlich? Morphologisch transparent oder opak? Motiviert durch das Original
  oder eigene Erfindung?
  Und: Verwendet das Original selbst Wortschöpfungen? Wie funktionieren sie
  in der Ursprungssprache? Dann wäre die Wortschöpfung bereits ein poetisches
  Mittel des Originals, dem die Übersetzung folgt.
  Die Meta-Ebene argumentiert WIE die Wortschöpfungen sprachlich funktionieren —
  das liefern die einzelnen Runs nicht."""

_META_DESTILLATION_PROMPT = """META-DESTILLATION: Der harte Befund

Auf Basis der folgenden Stabilitäts-, Qualitäts- und Sprachregister-Analyse formuliere den harten Befund
in genau 9 Sätzen. Jeder Satz entspricht einer Dimension:

1. DAS ZENTRALE PROBLEM — Was ist das ungelöste Problem, das alle Runs identifizieren?
2. DIE FUNDAMENTALE DIFFERENZ — Was ist die stärkste, stabilste Behauptung?
3. STABILE ZUORDNUNG(EN) — Welche Zuordnungen sind ≥88% stabil?
   (Falls keine Daten: "Keine quantifizierten Zuordnungen verfügbar")
4. NAHEZU STABILE ZUORDNUNG(EN) — Welche sind 59-87%?
   (Falls keine Daten: "Keine Daten für nahezu stabile Zuordnungen")
5. INSTABILE POSITION — Welche Position entzieht sich der Terminologie?
6. DIE KONSTELLATION — Spannungsfeld, Genealogie, Cluster oder Dispersion?
7. METHODISCHE DIAGNOSE — Bestätigungs-Bias? Instabilität? Ausreißer?
8. DER BESTE FUND — Das tiefste, präziseste, aufschlussreichste Ergebnis
   der gesamten Analyse, auch wenn es nur 1/N mal auftaucht.
   Häufigkeit ≠ Qualität. Der beste Fund erklärt mehr als der häufigste.
HINWEIS ZUM SPRACHREGISTER (v59.10.8): Wenn in den Daten keine
Informationen zum Sprachregister enthalten sind (z.B. weil die Analyse
auf Meta-Meta-Ebene läuft und keine Etappe-1-Sprachregister-Daten hat),
dann ERWÄHNE das Sprachregister NICHT. Überspringe es einfach.
Schreibe nicht "nicht analysierbar" — erwähne es gar nicht.

9. DAS SPRACHREGISTER — In welchem Register sprechen die Übersetzungen selbst?
   Zugänglich oder unnatürlich? Nah oder distanziert? Bildhaft oder abstrakt?
   Gibt es Wortschöpfungen (Neologismen, Komposita) — und wie funktionieren sie
   sprachlich? Morphologisch transparent oder opak? Motiviert durch das Original
   oder eigene Erfindung?
   Und: Verwendet das Original selbst Wortschöpfungen? Wie funktionieren sie
   in der Ursprungssprache? Dann wäre die Wortschöpfung bereits ein poetisches
   Mittel des Originals, dem die Übersetzung folgt.
   Die Meta-Ebene argumentiert WIE die Wortschöpfungen sprachlich funktionieren —
   das liefern die einzelnen Runs nicht.
   (Falls keine Sprachregister-Daten vorliegen: "Sprachregister nicht analysierbar")

Jede Aussage MUSS mit einer Stabilitäts-Zahl versehen werden.
Wenn keine konkreten Zahlen vorliegen: EXPLIZIT sagen.

--- STABILITÄTS-, QUALITÄTS- UND SPRACHREGISTER-ANALYSE ---

{beobachtung}

---

FORMULIERE DEN HARTEN BEFUND (9 Sätze, vollständig, kein Abbruch):"""


# ==============================================================================
# STUFE 2b: META-GEGENPOSITION (Strang B — falsifizierend)
# ============================================================================
# v59.10.2 (Schritt 3 der Falsifizierungs-Architektur, Claude-Beratung 2026-06-28)
#
# Parallele Struktur zu meta_beobachten(), aber mit reduziertem Input:
# - Input: SEZIEREN + Agency-Tabelle + Etappe-1
# - KEIN BEOBACHTEN-Input (vermeidet Bestaetigungsdruck)
# - Bekommt FRAGESTELLUNG der Quellen-Gegenposition als Kontext, nicht Antworten
# - Pro Autor: argumentiere gegen die These, nutze Agency-Qualitaet als
#   Ausgangspunkt
#
# WICHTIG (Claude-Empfehlung):
# - Agency-Tabelle als STRUKTURIERTEN Input, nicht als Fliesstext
# - Pro Autor ein Pflicht-Absatz mit Gegenargument
# - Nutze quantitativen Ankerpunkt (falls aus Agency-Tabelle ablesbar)

_META_GEGENPOSITION_SYSTEM = """Du bist ein kritischer Meta-Analytiker.
Deine Aufgabe: Argumentiere GEGEN die These der bestätigenden Pipeline.
Du arbeitest auf META-EBENE — nicht auf Textebene, sondern auf Pipeline-Ebene.

STRIKTE REGELN:
- PFLICHT: Behandle JEDEN Autor in einem eigenen Absatz.
  Ueberspringe keinen Autor — auch wenn du keine Gegenbefunde findest,
  schreibe explizit, warum.
- Nutze die Agency-Qualitaet als Ausgangspunkt des Gegenarguments.
- Beziehe dich auf Stabilitaetsmuster ueber Runs hinweg.
- Formuliere mindestens eine alternative Erklaerung pro Autor.
- Keine Harmonisierung: Wenn ein Gegenbefund stark ist, sage das.
- Keine Bestaetigung: Suche aktiv nach dem, was NICHT zur These passt.
- Beziehe dich auf KONKRETE Kennzahlen und Befunde aus den Synthesen."""

_META_GEGENPOSITION_PROMPT = """META-GEGENPOSITION: Argumentiere GEGEN die These der bestätigenden Pipeline.

Die bestätigende Pipeline hat folgende Kernbefunde erhoben:
{kernbefunde}

Die Agency-Qualitaeten pro Autor (aus den Synthese-Runs):
{agency_tabelle}

Etappe-1-Kennzahlen:
{etappe1_kennzahlen}

PFLICHT: Behandle JEDEN der folgenden Autoren in einem eigenen Absatz.
Format: ### [Autor]

Fuer jeden Autor:
1. AGENCY-ANALYSE: Nutze die Agency-Qualitaet als Ausgangspunkt.
   - Wenn "intentional": Ist die bewusste Steuerung wirklich "Radikalisierung"
     oder "Strategiewechsel"?
   - Wenn "responsiv": Ist die Reaktion auf externe Umstaende wirklich
     "Radikalisierung" oder "Anpassung"?
   - Wenn "entbuendelnd": Ist der Steuerungsentzug wirklich "Radikalisierung"
     oder "Enthuellung einer Konstanten"?
2. STABILITAETS-ANALYSE: Wie stabil ist der Befund fuer diesen Autor
   ueber die Runs hinweg? Ist die Instabilitaet ein Zeichen von Schwaeche
   der These?
3. ALTERNATIVE ERKLAERUNG: Formuliere mindestens eine alternative Erklaerung,
   die die Daten ebenso gut erklaert wie die These.
4. FALSIFIKATIONS-BEDINGUNG: Was muesste in den Daten stehen, damit die
   These fuer diesen Autor eindeutig widerlegt waere?

WICHTIG: Dies ist eine GEGENPOSITION auf META-EBENE.
- Argumentiere nicht auf Textebene (das macht die Quellen-Gegenposition).
- Argumentiere auf Pipeline-Ebene: Stabilitaet, Agency, Indikator-Typen.
- Suche nach dem, was die These herausfordert."""


def meta_gegenposition(
    sezieren_results: List[Dict],
    agency_table: Dict[int, Dict[str, Optional[str]]],
    etappe1_text: Optional[str] = None,
    progress_callback: Optional[Callable] = None,
) -> str:
    """
    META-GEGENPOSITION (Strang B): Argumentiert GEGEN die These der
    bestätigenden Pipeline auf Meta-Ebene.

    v59.10.2 (Schritt 3 der Falsifizierungs-Architektur):
    - Input: SEZIEREN + Agency-Tabelle + Etappe-1
    - KEIN BEOBACHTEN-Input (vermeidet Bestaetigungsdruck)
    - Pro Autor: Gegenargument mit Agency-Qualitaet als Ausgangspunkt

    Args:
        sezieren_results: Output von meta_sezieren() (mit termini + agency)
        agency_table: Output von extract_agency_per_run()
        etappe1_text: Optional Etappe-1-Kennzahlen
        progress_callback: Optionaler Callback

    Returns:
        String mit der Gegenpositions-Analyse
    """
    n_runs = len(sezieren_results)

    # Kernbefunde aus Fazits extrahieren
    fazit_text = ""
    for run in sezieren_results:
        fazit = run.get("fazit", "")
        if fazit:
            fazit_text += f"--- Run {run['nr']} ---\n{fazit[:800]}\n\n"

    # Agency-Tabelle als strukturierten Text formatieren
    agency_lines = []
    all_authors = set()
    for run_agency in agency_table.values():
        all_authors.update(run_agency.keys())

    for author in sorted(all_authors):
        values = []
        for run_nr in sorted(agency_table.keys()):
            run_agency = agency_table[run_nr]
            val = run_agency.get(author)
            values.append(val if val else "null")
        agency_lines.append(f"  {author}: {', '.join(f'R{run_nr}={v}' for run_nr, v in zip(sorted(agency_table.keys()), values))}")
    agency_tabelle = "\n".join(agency_lines) if agency_lines else "(keine Agency-Daten)"

    # Etappe-1-Kennzahlen (gekuerzt)
    etappe1_kennzahlen = (etappe1_text or "(keine Etappe-1-Daten)")[:5000]

    prompt = _META_GEGENPOSITION_PROMPT.format(
        kernbefunde=fazit_text[:5000],
        agency_tabelle=agency_tabelle,
        etappe1_kennzahlen=etappe1_kennzahlen,
    )

    if progress_callback:
        progress_callback("Meta-Gegenposition: Falsifizierende Analyse...")

    logger.info(f"META-GEGENPOSITION: {n_runs} Runs analysieren (Strang B)")

    try:
        response = llm_call(
            prompt=prompt,
            task="meta_destillation",  # Pro-Modell fuer Gegenposition
            system_instruction=_META_GEGENPOSITION_SYSTEM,
            temperature=0.3,
            max_tokens=8192,
            domain="stilisierung",
        )
        logger.info("META-GEGENPOSITION abgeschlossen")
        return response if response else "(Leere Antwort)"
    except Exception as e:
        logger.error(f"❌ META-GEGENPOSITION fehlgeschlagen: {e}")
        return f"FEHLER bei META-GEGENPOSITION: {e}"


# ==============================================================================
# STUFE 2c: META-ADJUDIKATION (Strang C — bewertend)
# ============================================================================
# v59.10.4 (Schritt 4 der Falsifizierungs-Architektur, Claude-Beratung 2026-06-28)
#
# Bewertet: Was von den Befunden aus Strang A (BEOBACHTEN) haelt der
# Gegenprobe aus Strang B (GEGENPOSITION) stand? Was nicht?
#
# Input: BEOBACHTEN + GEGENPOSITION (beide roh, gleichwertig)
# Output: Adjudizierte Befundliste — pro Argument ein Urteil:
#   - HAELT STAND: Gegenargument widerlegt den Befund nicht
#   - TEILWEISE: Gegenargument modifiziert den Befund
#   - HAELT NICHT STAND: Gegenargument widerlegt den Befund
#
# WICHTIG (Claude-Empfehlung):
# - Adjudikation bekommt BEIDE rohen Stroeme (nicht verdichtet)
# - Adjudikation ist KEINE Harmonisierung — Spannung bleibt bestehen
# - Die adjudizierte Befundliste ist Input fuer die revidierte Destillation

_META_ADJUDIKATION_SYSTEM = """Du bist ein adjudizierender Meta-Analytiker.
Du bewertest, welche Argumente aus der bestätigenden Analyse (Strang A)
der Gegenprobe aus der falsifizierenden Analyse (Strang B) standhalten.

STRIKTE REGELN:
- PFLICHT: Behandle JEDEN Autor in einem eigenen Absatz.
- Pro Befund aus Strang A: Urteile ob er der Gegenprobe standhaelt.
- Drei Urteile: HAELT STAND / TEILWEISE / HAELT NICHT STAND.
- Begruende jedes Urteil mit konkreten Daten.
- KEINE Harmonisierung: Wenn die Gegenposition stark ist, sage das.
- KEINE Bestaetigung: Wenn die Gegenposition schwach ist, sage das auch."""

_META_ADJUDIKATION_PROMPT = """META-ADJUDIKATION: Bewerte, was der Gegenprobe standhaelt.

STRANG A (bestaetigend — BEOBACHTEN):
{beobachtung}

STRANG B (falsifizierend — GEGENPOSITION):
{gegenposition}

PFLICHT: Behandle JEDEN der drei Autoren in einem eigenen Absatz.
Format: ### [Autor]

Fuer jeden Autor:
1. IDENTIFIZIERE die Hauptbefunde aus Strang A fuer diesen Autor.
2. IDENTIFIZIERE die Gegenargumente aus Strang B fuer diesen Autor.
3. ADJUDIZIERE: Pro Befund ein Urteil:
   - HAELT STAND: Das Gegenargument widerlegt den Befund nicht.
     Begruendung: Warum haelt der Befund der Gegenprobe stand?
   - TEILWEISE: Das Gegenargument modifiziert den Befund.
     Begruendung: Was bleibt vom Befund, was wird modifiziert?
   - HAELT NICHT STAND: Das Gegenargument widerlegt den Befund.
     Begrundung: Warum ist das Gegenargument staerker?

4. GESAMTURTEIL pro Autor: Wie stark ist die These fuer diesen
   Autor nach der Gegenprobe? (stark / moderat / schwach)

WICHTIG: Dies ist eine ADJUDIKATION — keine Harmonisierung.
- Wenn die Gegenposition stark ist, anerkenne das.
- Wenn die Gegenposition schwach ist, anerkenne das auch.
- Die Spannung zwischen Strang A und Strang B MUSS sichtbar bleiben."""


def meta_adjudikation(
    beobachtung: str,
    gegenposition: str,
    progress_callback: Optional[Callable] = None,
) -> str:
    """
    META-ADJUDIKATION (Strang C): Bewertet, was der Gegenprobe standhaelt.

    v59.10.4 (Schritt 4 der Falsifizierungs-Architektur):
    - Input: BEOBACHTEN (Strang A, roh) + GEGENPOSITION (Strang B, roh)
    - Output: Adjudizierte Befundliste pro Autor
    - Pro Befund: HAELT STAND / TEILWEISE / HAELT NICHT STAND

    Args:
        beobachtung: Output von meta_beobachten() (Strang A)
        gegenposition: Output von meta_gegenposition() (Strang B)
        progress_callback: Optionaler Callback

    Returns:
        String mit der adjudizierten Befundliste
    """
    if progress_callback:
        progress_callback("Meta-Adjudikation: Gegenprobe bewerten...")

    logger.info("META-ADJUDIKATION: Strang A vs Strang B (Strang C)")

    prompt = _META_ADJUDIKATION_PROMPT.format(
        beobachtung=beobachtung[:8000],
        gegenposition=gegenposition[:8000],
    )

    try:
        response = llm_call(
            prompt=prompt,
            task="meta_destillation",  # Pro-Modell fuer Adjudikation
            system_instruction=_META_ADJUDIKATION_SYSTEM,
            temperature=0.2,
            max_tokens=8192,
            domain="stilisierung",
        )
        logger.info("META-ADJUDIKATION abgeschlossen")
        return response if response else "(Leere Antwort)"
    except Exception as e:
        logger.error(f"❌ META-ADJUDIKATION fehlgeschlagen: {e}")
        return f"FEHLER bei META-ADJUDIKATION: {e}"


def meta_destillation(
    beobachtung: str,
    progress_callback: Optional[Callable] = None,
    is_meta_meta: bool = False,
) -> str:
    """
    META-DESTILLATION: Synthetisiert den harten Befund.

    v2.8: Dual-Path — is_meta_meta=True verwendet den Meta-Meta-Destillations-Prompt
    (Satz 9 = DIE BLINDE STELLE statt DAS SPRACHREGISTER).

    v2.4: 9 Sätze statt 8. Satz 9 = DAS SPRACHREGISTER.

    Args:
        beobachtung: Output von meta_beobachten()
        progress_callback: Optionaler Callback
        is_meta_meta: Wenn True, Meta-Meta-Destillation verwenden

    Returns:
        9-Satz-Befund als String
    """
    if progress_callback:
        if is_meta_meta:
            progress_callback("META-META-DESTILLATION: Harter Befund der Meta-Meta-Analyse (9 Sätze)...")
        else:
            progress_callback("META-DESTILLATION: Harter Befund (9 Sätze)...")

    # v2.8: Dual-Path Prompt-Auswahl
    if is_meta_meta:
        prompt = _META_META_DESTILLATION_PROMPT.format(beobachtung=beobachtung)
        system_instruction = _META_META_DESTILLATION_SYSTEM
        logger.info(f"META-META-DESTILLATION: Harter Befund (max_tokens={_META_DESTILLATION_MAX_TOKENS})")
    else:
        prompt = _META_DESTILLATION_PROMPT.format(beobachtung=beobachtung)
        system_instruction = _META_DESTILLATION_SYSTEM
        logger.info(f"META-DESTILLATION: Harter Befund (max_tokens={_META_DESTILLATION_MAX_TOKENS})")

    try:
        destillat = llm_call(
            prompt=prompt,
            task="meta_destillation",
            system_instruction=system_instruction,
            temperature=0.2,
            max_tokens=_META_DESTILLATION_MAX_TOKENS,
            domain="stilisierung",
        )
        return destillat or "(Leere LLM-Antwort)"
    except Exception as e:
        logger.error(f"META-DESTILLATION fehlgeschlagen: {e}")
        return f"FEHLER bei META-DESTILLATION: {e}"


def meta_destillation_revidiert(
    adjudikation: str,
    sprachregister_auszug: str = "",
    progress_callback: Optional[Callable] = None,
) -> str:
    """
    META-DESTILLATION (revidiert — v59.10.4 Schritt 4):
    Synthetisiert, was der Gegenprobe standgehalten hat.

    v59.10.4: Die revidierte Destillation bekommt die adjudizierte
    Befundliste als Input — nicht mehr die rohe BEOBACHTEN. Sie
    synthetisiert, was der Gegenprobe standgehalten hat, nicht was
    die bestaetigende Pipeline allein produziert hat.

    Args:
        adjudikation: Output von meta_adjudikation() (adjudizierte Befundliste)
        progress_callback: Optionaler Callback

    Returns:
        9-Satz-Befund als String — synthetisiert aus adjudizierten Befunden
    """
    if progress_callback:
        progress_callback("META-DESTILLATION (revidiert): Was haelt stand? (9 Saetze)...")

    # v59.10.5: Sprachregister-Auszug aus BEOBACHTEN hinzufuegen,
    # falls vorhanden. Die adjudizierte Befundliste enthaelt nicht den
    # Sprachregister-Teil aus Sektion 8 — der geht verloren, wenn wir
    # nur die Adjudikation weitergeben.
    full_input = adjudikation[:10000]
    if sprachregister_auszug:
        full_input += "\n\n--- SPRACHREGISTER (aus BEOBACHTEN, Sektion 8) ---\n" + sprachregister_auszug[:4000]

    prompt = _META_DESTILLATION_PROMPT.format(beobachtung=full_input)

    logger.info(f"META-DESTILLATION (revidiert): Adjudizierte Befundliste als Input")

    try:
        destillat = llm_call(
            prompt=prompt,
            task="meta_destillation",
            system_instruction=_META_DESTILLATION_SYSTEM,
            temperature=0.2,
            max_tokens=_META_DESTILLATION_MAX_TOKENS,
            domain="stilisierung",
        )
        return destillat or "(Leere LLM-Antwort)"
    except Exception as e:
        logger.error(f"META-DESTILLATION (revidiert) fehlgeschlagen: {e}")
        return f"FEHLER bei META-DESTILLATION (revidiert): {e}"


# ==============================================================================
# STUFE 2b: FREIE FRAGE — LLM (Flash)
# ==============================================================================

_FREIE_FRAGE_SYSTEM = """Du bist ein Expertensystem für hermeneutische Meta-Analyse.

HINWEIS ZUR PIPELINE-ARCHITEKTUR (v59.10.8): Die Pipeline hat eine
Falsifizierungs-Architektur mit drei Straengen:
- Strang A (BEOBACHTEN): Bestaetigende Analyse
- Strang B (GEGENPOSITION): Falsifizierende Gegenanalyse
- Strang C (ADJUDIKATION): Bewertung was der Gegenprobe standhaelt
Die Destillation synthetisiert, was standhaelt. Wenn nach Engine-Entwicklung
gefragt wird, beruecksichtige auch diese Architektur-Erweiterung.

Du beantwortest gezielte Fragen zu einer Reihe von Synthese-Runs,
gestützt auf die SEZIEREN-Daten und – falls vorhanden – den
BEOBACHTEN-Befund und Etappe-1-Kennzahlen.
Antworte präzise, belegt mit konkreten Run-Nummern und Zitaten.
Keine Spekulation ohne Evidenz.

VALIDIERUNGS-GRENZE (Claude-Review 2026-06-22): Wenn ein Begriff
aus einer Synthese nicht als definierte Kennzahl in Etappe 1 steht,
darfst du ihn NICHT retroaktiv definieren und dann validieren.
VERBOT: Eigene Berechnungen auf Basis selbst gewählter Definitionen.
Die Meta-Ebene definiert keine Kennzahlen — sie prüft nur, ob
vorhandene Kennzahlen korrekt verwendet wurden.

TYPISIERUNG (statt bloß "nicht prüfbar"):
Wenn ein Begriff nicht in Etappe 1 definiert ist, typisiere ihn:

(a) QUANTITATIV (suggeriert Messbarkeit, z.B. "Dichte", "Intensität",
    "Häufigkeit")?
    → Diagnose: "Pseudo-Kennzahl — Begriff suggeriert Quantifizierung,
      die in Etappe 1 nicht existiert."

(b) QUALITATIV-INTERPRETATIV (kein Quantifizierungsanspruch, z.B.
    "operative Logik", "poetologische Entscheidung")?
    → Diagnose: "Abstrakter Begriff — nicht direkt prüfbar. Kein
      Versuch, ihn mit Etappe-1-Kennzahlen zu verbinden, da jede
      Verbindung eine eigene Definition wäre."
    → Zusatz (nur wenn der Run selbst den Begriff an eine Kennzahl
      bindet, z.B. "operative Logik, definiert als Enjambement-Rate"):
      "Der Run definiert den Begriff selbst als [X]. Prüfe NUR diese
      explizite Bindung — nicht eine selbst gewählte."

ENGINE-EVOLUTION (wenn Runs aus verschiedenen Pipeline-Versionen stammen):
Wenn ein Begriff oder eine Aussage in frühen Runs auftaucht, aber in
späteren Runs nicht mehr (oder umgekehrt), markiere dies als BEFUND
über Engine-Evolution — nicht als Instabilität. Benenne die Richtung:

- Wurde der Begriff durch eine konkrete Etappe-1-Kennzahl ERSETZT?
  → "Verbesserung: Pseudo-Kennzahl durch Datenbindung abgelöst."
- Wurde er einfach weggelassen ohne Ersatz?
  → "Offen: Begriff verschwunden, aber kein Ersatz sichtbar."
- Erscheint er in anderer Form wieder?
  → "Transformation: Begriff umformuliert — prüfe ob neue Form
    definiert ist."

Informiere den Leser: was bedeutet dieser Befund für die
Verlässlichkeit der Analyse? Hat sich die Engine verbessert,
verschlechtert, oder nur verschoben?

FÜR JEDE quantifizierende oder vergleichende Aussage - einzeln und
vollständig prüfen, dann weiter zur nächsten:

(a) PSEUDO-KENNZAHL:
    1. Diagnose aussprechen.
    2. Begriff in ALLEN anderen Runs suchen - vorhanden oder verschwunden?
    3. Falls verschwunden: ENGINE-EVOLUTION benennen (Verbesserung /
       offen / Transformation).
    4. Validierung dieser Aussage beenden. Keine Proxy-Berechnung.
       "Korrekt" oder "falsch" darf nicht folgen. Nächste Aussage.

(b) ABSTRAKT-INTERPRETATIV:
    1. Diagnose aussprechen.
    2. ZWINGEND pruefen: Definiert der Run den Begriff selbst
       (explizite Bindung an eine Kennzahl)?
    3. Falls ja: zitiere die Definition, pruefe NUR diese Bindung.
    4. Falls nein: Diagnose beenden. Keine eigene Bruecke zu Kennzahlen
       bauen. Nächste Aussage.

"Nächste Aussage" als Reset-Anker: stellt sicher, dass das LLM nach
jeder Typisierung zur naechsten Aussage weitergeht, statt die gesamte
Pruefung abzubrechen."""

_FREIE_FRAGE_PROMPT = """## AUFGABE
Beantworte die folgende FRAGE auf Basis der bereitgestellten Daten.
Belege deine Antwort mit konkreten Run-Nummern (R-1, R-2 etc.) und Zitaten.

## FRAGE
{frage}

## SEZIEREN-DATEN
{sezieren_text}

{etappe1_section}{beobachtung_section}{adjudikation_section}## ANTWORT"""


def _precompute_klang_summen(etappe1_text: str) -> str:
    """
    v2.8.2 (Claude Schnitt 2, 2026-06-22): Parst die Klang-Vergleichstabelle
    aus etappe1_text und berechnet Klangfiguren-Summen in Python.

    Grund: Das LLM hat 396+38+4+42 falsch summiert (479 statt 480).
    Zahlenvergleiche muessen in Python passieren, nicht im LLM-Prompt.

    Sucht nach der Klang-Vergleichstabelle (Marker: "Klang-Vergleichstabelle"
    oder "Alliterationen" in Tabellen-Header), parst die Zahlen-Spalten
    und berechnet die Summe pro Quelle.

    Returns:
        Formatierter String mit vorberechneten Summen, oder "" wenn
        keine Klang-Tabelle gefunden wurde.
    """
    if not etappe1_text:
        return ""

    # Suche nach der Klang-Vergleichstabelle-Sektion
    klang_start = etappe1_text.find("Klang-Vergleichstabelle")
    if klang_start < 0:
        # Fallback: suche nach "Alliterationen" als Header
        klang_start = etappe1_text.find("Alliterationen")
        if klang_start < 0:
            return ""

    # Begrenze auf die naechsten 2000 Zeichen nach der Klang-Tabelle
    klang_section = etappe1_text[klang_start:klang_start + 2000]

    # Parse table rows: | QUELLE N | num | num | num | num | ... |
    # Matcht 4 Zahlen nach QUELLE (Alliterationen, Assonanzen, Binnenreime, Vokal-Echos)
    klang_rows = []
    for m in re.finditer(
        r'\|\s*(QUELLE\s*\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|',
        klang_section
    ):
        quelle = m.group(1)
        allit = int(m.group(2))
        asson = int(m.group(3))
        binnen = int(m.group(4))
        echoes = int(m.group(5))
        summe = allit + asson + binnen + echoes
        klang_rows.append((quelle, allit, asson, binnen, echoes, summe))

    if not klang_rows:
        return ""

    # Tabelle mit vorberechneten Summen
    lines = ["--- VORBERECHNETE KLANG-KENNZAHLEN (Python, nicht LLM) ---"]
    lines.append("| Quelle | Allit + Asson + Binnenr + Vokalechos = Summe |")
    lines.append("| --- | --- |")
    for quelle, allit, asson, binnen, echoes, summe in klang_rows:
        lines.append(f"| {quelle} | {allit} + {asson} + {binnen} + {echoes} = {summe} |")
    lines.append("")
    lines.append("Hinweis: Diese Summen wurden in Python berechnet, nicht vom LLM.")
    lines.append("Verwende diese Zahlen fuer Vergleiche — berechne NICHT selbst.")
    lines.append("")

    return "\n".join(lines)


def meta_freie_frage(
    frage: str,
    sezieren_results: List[Dict],
    etappe1_text: Optional[str] = None,
    beobachtung: Optional[str] = None,
    adjudikation: Optional[str] = None,
    progress_callback: Optional[Callable] = None,
) -> str:
    """
    FREIE FRAGE: Beantwortet eine gezielte Frage auf Basis der SEZIEREN-Daten.

    v2.7: Neue Funktion für den FREIE FRAGE-Modus.

    Bereitet SEZIEREN-Daten (Kernhypothese, Fazit, Termini, Beweisführung
    gekürzt auf 300 Zchn) als Kontext auf. Optional: Etappe-1-Kennzahlen
    (max 4000 Zchn) + BEOBACHTEN-Befund (max 3000 Zchn).

    Ruft llm_call() mit task="meta_beobachten" (gleiche Modell-Konfig wie
    BEOBACHTEN, Flash). temperature=0.3, max_tokens=8192.

    Args:
        frage:            Die Frage des Users
        sezieren_results: Output von meta_sezieren() (mit Termini)
        etappe1_text:     Optional: Etappe-1-Kennzahlen (max 4000 Zchn)
        beobachtung:      Optional: BEOBACHTEN-Befund (max 3000 Zchn)
        progress_callback: Optionaler Callback

    Returns:
        Antwort-String oder "FEHLER bei FREIER FRAGE: {e}"
    """
    if progress_callback:
        progress_callback("FREIE FRAGE: Antwort wird generiert...")

    # SEZIEREN-Daten aufbereiten
    sezieren_parts = []
    for run in sezieren_results:
        part = f"R-{run['nr']}: {run['datei']}\n"
        part += f"Kernhypothese: {run.get('kernhypothese', '')}\n"
        part += f"Fazit: {run.get('fazit', '')}\n"
        # Beweisführung gekürzt auf 300 Zchn
        beweis = run.get('beweisfuehrung', '') or ''
        if beweis:
            beweis_kurz = beweis[:300]
            if len(beweis) > 300:
                beweis_kurz += "..."
            part += f"Beweisführung: {beweis_kurz}\n"
        # Termini
        termini = run.get('termini', {})
        if termini:
            termini_str = ", ".join(
                f"{autor}: {term}"
                for autor, term in sorted(termini.items())
                if term
            )
            part += f"Termini: {termini_str}\n"
        sezieren_parts.append(part)

    sezieren_text = "\n---\n".join(sezieren_parts)

    # Etappe-1-Sektion
    # v2.8.1 Fix 2026-06-21: Truncation von 4000 auf 20000 erhoeht.
    # Vorher: etappe1_text[:4000] schnitt die Klang-Vergleichstabelle ab.
    # Die etappe1.md hat typischerweise ~18000 Zeichen (Vergleichstabelle +
    # Klang-Tabelle + Detail-Statistiken). 20000 ist ausreichend + Puffer.
    etappe1_section = ""
    if etappe1_text and etappe1_text.strip():
        etappe1_section = (
            "## ETAPPE-1-KENNZAHLEN\n"
            + etappe1_text[:20000]
            + ("..." if len(etappe1_text) > 20000 else "")
            + "\n\n"
        )

    # v2.8.2 (Claude Schnitt 2): Klangfiguren-Summen in Python vorberechnen
    # Grund: LLM hat Summen falsch berechnet (479 statt 480).
    # Python rechnet korrekt — LLM darf nur lesen, nicht rechnen.
    klang_summen = _precompute_klang_summen(etappe1_text) if etappe1_text else ""
    if klang_summen:
        etappe1_section += klang_summen

    # BEOBACHTEN-Sektion (max 3000 Zchn)
    beobachtung_section = ""
    if beobachtung and beobachtung.strip():
        beobachtung_section = (
            "## BEOBACHTEN-BEFUND\n"
            + beobachtung[:3000]
            + ("..." if len(beobachtung) > 3000 else "")
            + "\n\n"
        )

    # v59.10.7: Adjudikation-Sektion (falls vorhanden)
    # Die FREIE FRAGE soll wissen, dass eine Adjudikation existiert,
    # und diese beruecksichtigen — statt eigene Gegenargumente von vorne
    # zu produzieren.
    adjudikation_section = ""
    if adjudikation and adjudikation.strip():
        adjudikation_section = (
            "## ADJUDIKATION-BEFUND (Strang C — Was haelt der Gegenprobe stand?)\n"
            "WICHTIG: Eine Gegenposition (Strang B) und Adjudikation (Strang C) wurden "
            "bereits durchgefuehrt. Beruecksichtige diese Ergebnisse, statt eigene "
            "Gegenargumente von vorne zu produzieren.\n\n"
            + adjudikation[:4000]
            + ("..." if len(adjudikation) > 4000 else "")
            + "\n\n"
        )

    prompt = _FREIE_FRAGE_PROMPT.format(
        frage=frage,
        sezieren_text=sezieren_text,
        etappe1_section=etappe1_section,
        beobachtung_section=beobachtung_section,
        adjudikation_section=adjudikation_section,
    )

    # v2.8.1 Fix 2026-06-21: Log meldet tatsaechlich verwendete Laenge
    # (etappe1_section, nicht etappe1_text). Vorher: Log sagte 17660 Zchn,
    # aber Prompt bekam nur 4000 Zchn (Truncation).
    logger.info(f"FREIE FRAGE: Frage gestellt ({len(frage)} Zchn), "
                f"Kontext: {len(sezieren_text)} Zchn SEZIEREN"
                + (f" + {len(etappe1_section)} Zchn ETAPPE1 (used)" if etappe1_section else "")
                + (f" of {len(etappe1_text)} total" if etappe1_text and len(etappe1_text) > 20000 else "")
                + (f" + {len(beobachtung)} Zchn BEOBACHTEN" if beobachtung else ""))

    try:
        antwort = llm_call(
            prompt=prompt,
            task="meta_beobachten",
            system_instruction=_FREIE_FRAGE_SYSTEM,
            temperature=0.3,
            max_tokens=8192,
            domain="stilisierung",
        )
        return antwort or "(Leere LLM-Antwort)"
    except Exception as e:
        logger.error(f"FREIE FRAGE fehlgeschlagen: {e}")
        return f"FEHLER bei FREIER FRAGE: {e}"


# ==============================================================================
# STUFE 2c: KONFRONTATION — Meta-Tests vs. externe Kritik (v2.8)
# ==============================================================================

def meta_konfrontation(
    sezieren_results: List[Dict],
    kritik_text: str,
    progress_callback: Optional[Callable] = None,
) -> str:
    """
    KONFRONTATION: Konfrontiert Meta-Hermeneutic-Ergebnisse mit externer Kritik.

    Die Kritik ist KEIN Synthese-Input — sie ist eine asymmetrische
    Außenperspektive. Die Nicht-Passung ist selbst der Befund.

    Nach Claude-Architektur-Entscheidung (2026-06-15):
    "Kritik als FREIE FRAGE, nicht als Pseudo-Synthese.
    Das non-fit ist selbst das Material."

    Args:
        sezieren_results: Output von meta_sezieren() (mit Termini)
        kritik_text:      Der externe Kritik-Text (Artikel, Rezension etc.)
        progress_callback: Optionaler Callback

    Returns:
        Konfrontations-Analyse als Markdown-String
    """
    if progress_callback:
        progress_callback("KONFRONTATION: Meta-Ergebnisse vs. externe Kritik...")

    n_runs = len(sezieren_results)

    # META-DESTILLATIONEN als Text zusammenstellen
    meta_parts = []
    for run in sezieren_results:
        var_tag = f" [V{run.get('variante', '?')}]" if run.get("variante") else ""
        part = f"### Test {run['nr']}: {run['datei']}{var_tag} ###\n"
        part += f"KERNHYPOTHESE: {run.get('kernhypothese', '')}\n"
        # Fazit = letzter Satz DESTILLATION
        if run.get("fazit"):
            part += f"FAZIT: {run['fazit']}\n"
        # Beweisführung gekürzt
        beweis = run.get("beweisfuehrung", "") or ""
        if beweis:
            part += f"BEWEISFÜHRUNG (Auszug): {beweis[:300]}{'...' if len(beweis) > 300 else ''}\n"
        meta_parts.append(part)

    meta_text = "\n---\n".join(meta_parts)

    # Varianten-Verteilung
    varianten = {}
    for r in sezieren_results:
        v = r.get("variante", "?")
        varianten[v] = varianten.get(v, 0) + 1
    varianten_str = ", ".join(
        f"V{v}:{c}" for v, c in sorted(varianten.items())
    ) if varianten else "n/a"

    # Kritik-Text kürzen falls nötig (max 8000 Zchn)
    kritik_capped = kritik_text[:8000]
    if len(kritik_text) > 8000:
        kritik_capped += "\n... (Kritik-Text gekürzt)"

    prompt = _KONFRONTATION_PROMPT.format(
        n_runs=n_runs,
        varianten_str=varianten_str,
        meta_text=meta_text,
        kritik_text=kritik_capped,
    )

    logger.info(
        f"KONFRONTATION: {n_runs} Meta-Tests vs. Kritik "
        f"({len(kritik_text)} Zchn Kritik, {varianten_str})"
    )

    try:
        konfrontation = llm_call(
            prompt=prompt,
            task="meta_beobachten",  # Gleiche Modell-Konfig wie BEOBACHTEN (Flash)
            system_instruction=_KONFRONTATION_SYSTEM,
            temperature=0.3,
            max_tokens=_META_BEOBACHTEN_MAX_TOKENS,
            domain="stilisierung",
        )
        return konfrontation or "(Leere LLM-Antwort)"
    except Exception as e:
        logger.error(f"KONFRONTATION fehlgeschlagen: {e}")
        return f"FEHLER bei KONFRONTATION: {e}"


# ==============================================================================
# HAUPTFUNKTION: META-HERMENEUTIC PIPELINE
# ==============================================================================

def run_meta_hermeneutic(
    synthesis_files: List[Path],
    progress_callback: Optional[Callable] = None,
    skip_termini: bool = False,
    etappe1_text: Optional[str] = None,
    freie_frage: Optional[str] = None,
) -> Dict:
    """
    Führt die komplette Meta-Hermeneutic Pipeline aus.

    Zwei Modi:
    - VOLLANALYSE (freie_frage=None): Drei-Stufen-Architektur
      1. META-SEZIEREN: Extrahiert Strukturdaten (Python)
      2. META-BEOBACHTEN: Vergleicht und bewertet Stabilität + Qualität + Sprachregister (LLM Flash)
      3. META-DESTILLATION: Synthetisiert den harten Befund inkl. bestem Fund + Sprachregister (LLM Pro)
    - FREIE FRAGE (freie_frage=str): Nur SEZIEREN + TERMINI + FREIE FRAGE
      Keine VOLLANALYSE. metadata["mode"] = "meta_freie_frage".

    Args:
        synthesis_files:    Liste von Pfaden zu .md-Dateien mit Globalen Synthesen
        progress_callback:  Optional: Callback(status_msg) für UI-Updates
        skip_termini:       Wenn True, überspringe LLM-basierte Termini-Extraktion
        etappe1_text:       Optional: Vollständiger Etappe-1-Text (formatierter Output
                            aus dem Stilistic Lab). Enthält Vergleichstabelle +
                            Detail-Statistiken pro Quelle. Variante A: volle Daten,
                            keine Verdichtung. Die HRE soll selbst entdecken, was
                            für das Sprachregister relevant ist.
                            Wird von extract_globale_synthese.py als etappe1.md
                            erzeugt und kann als String übergeben werden.
        freie_frage:        Optional: Wenn übergeben, wird NUR SEZIEREN + TERMINI +
                            FREIE FRAGE ausgeführt (KEINE VOLLANALYSE).
                            metadata["mode"] = "meta_freie_frage".
                            Ergebnis enthält Schlüssel "meta_freie_frage".

    Returns:
        Dict mit:
        - meta_sezieren:    Liste der extrahierten Strukturdaten pro Run
        - meta_beobachten:  String (nur im VOLLANALYSE-Modus)
        - meta_destillation: String (nur im VOLLANALYSE-Modus)
        - meta_freie_frage: String (nur im FREIE FRAGE-Modus)
        - metadata:         timing, model, stage_durations, mode, etc.
    """
    start_time = time.time()
    n_files = len(synthesis_files)
    stage_durations = {}

    # ==========================================================================
    # v2.4.1: ETAPPE-1-TEXT AUTOMATISCH EINLESEN
    # Wenn etappe1_text nicht explizit übergeben wurde, suche etappe1.md
    # im Verzeichnis der Synthese-Dateien. Die Datei wird von
    # extract_globale_synthese.py erzeugt und liegt typischerweise
    # neben den Synthese-Dateien oder im gleichen Ordner.
    # ==========================================================================
    if not etappe1_text:
        # Suche etappe1.md in den übergebenen Dateien
        # v2.8.1 Fix 2026-06-27 (Schnitt A, Claude-Beratung): Auto-Loader
        # auf Same-Directory beschränkt. Die frühere Parent-Parent-Suche
        # hat stale etappe1.md-Dateien aus anderen Sessions gefunden und
        # zur Kontamination geführt (Homer-Daten in Puschkin/Blok/Brodsky-
        # Meta-Analyse). Dateisystem als Wahrheit: Wer verschiedene Sessions
        # sauber trennen will, muss verschiedene Ordner nutzen.
        etappe1_file = None
        for f in synthesis_files:
            if f.name.lower() in ('etappe1.md', 'etappe1_text.md'):
                etappe1_file = f
                break

        # Falls nicht in der Liste: Suche NUR im Verzeichnis der ersten
        # Synthese-Datei (Same-Directory). Keine Parent-Parent-Suche mehr.
        if not etappe1_file and synthesis_files:
            parent_dir = synthesis_files[0].parent
            for candidate_name in ('etappe1.md', 'etappe1_text.md'):
                candidate = parent_dir / candidate_name
                if candidate.exists():
                    etappe1_file = candidate
                    break

        if etappe1_file:
            try:
                etappe1_text = etappe1_file.read_text(encoding="utf-8")
                # Logging mit VOLLSTÄNDIGEM Pfad — bei Debugging sofort
                # sichtbar, welche Datei geladen wurde (Transparenz-Pflicht
                # für DOI-Paper-Reproduzierbarkeit).
                resolved_path = etappe1_file.resolve()
                logger.info(
                    f"Etappe-1-Text automatisch geladen: {resolved_path} "
                    f"({len(etappe1_text)} Zchn)"
                )
            except Exception as e:
                logger.warning(f"Kann Etappe-1-Datei nicht lesen: {etappe1_file}: {e}")
                etappe1_text = None
        else:
            logger.info(
                "Keine etappe1.md im Same-Directory gefunden — "
                "Sprachregister-Analyse nicht verfügbar. "
                "(Hinweis: etappe1.md muss im selben Ordner liegen wie die "
                "Synthese-Dateien. Parent-Parent-Suche wurde in Schnitt A "
                "entfernt, um Session-Kontamination zu verhindern.)"
            )

    # ==========================================================================
    # FREIE FRAGE-Modus: Nur SEZIEREN + TERMINI + FREIE FRAGE
    # ==========================================================================
    is_freie_frage = freie_frage is not None and freie_frage.strip() != ""

    metadata = {
        "mode": "meta_freie_frage" if is_freie_frage else "meta_hermeneutic",
        "version": "2.8",
        "n_synthesis_files": n_files,
        "model_beobachten": get_model_for_task("meta_beobachten"),
        "model_destillation": get_model_for_task("meta_destillation"),
        "skip_termini": skip_termini,
        "has_etappe1_text": etappe1_text is not None and len(etappe1_text.strip()) > 0,
    }

    if is_freie_frage:
        metadata["freie_frage"] = freie_frage

    logger.info(f"META-HERMENEUTIC v2.8: {n_files} Synthese-Dateien"
                + (f" — FREIE FRAGE-Modus" if is_freie_frage else "")
                + (f" + Etappe-1-Text ({len(etappe1_text)} Zchn)" if etappe1_text else ""))

    # ==========================================================================
    # STUFE 1: META-SEZIEREN (Python, deterministisch)
    # ==========================================================================
    if progress_callback:
        if is_freie_frage:
            progress_callback("Stufe 1/2: META-SEZIEREN — Strukturdaten extrahieren...")
        else:
            progress_callback("Stufe 1/3: META-SEZIEREN — Strukturdaten extrahieren...")

    t0 = time.time()
    sezieren_results = meta_sezieren(synthesis_files)
    stage_durations["sezieren"] = round(time.time() - t0, 1)

    if not sezieren_results:
        empty_result = {
            "meta_sezieren": [],
            "meta_beobachten": "FEHLER: Keine Synthese-Dateien konnten gelesen werden.",
            "meta_destillation": "",
            "metadata": {**metadata, "stage_durations": stage_durations},
        }
        if is_freie_frage:
            empty_result["meta_freie_frage"] = "FEHLER: Keine Synthese-Dateien konnten gelesen werden."
        return empty_result

    # Stufe 1b: Termini-Extraktion via Mini-LLM (optional)
    if not skip_termini and len(sezieren_results) >= 2:
        if progress_callback:
            progress_callback("Stufe 1b: DESTILLATION-Termini extrahieren (LLM)...")

        t0 = time.time()
        sezieren_results = extract_termini_per_run(
            sezieren_results,
            progress_callback=progress_callback,
        )
        stage_durations["termini"] = round(time.time() - t0, 1)
    else:
        for run in sezieren_results:
            run["termini"] = {}

    # Stufe 1b-2: Agency-Extraktion via Mini-LLM (v59.10.0 Schritt 1)
    # Immer aktiv — Falsifikation ist kein optionaler Modus.
    if len(sezieren_results) >= 2:
        if progress_callback:
            progress_callback("Stufe 1b-2: Agency-Qualitaeten extrahieren (LLM)...")

        t0 = time.time()
        agency_table = extract_agency_per_run(
            sezieren_results,
            progress_callback=progress_callback,
        )
        stage_durations["agency"] = round(time.time() - t0, 1)
    else:
        agency_table = {}
        for run in sezieren_results:
            run["agency_qualities"] = {}

    # v59.10.0 Fix: has_agency_table NACH Agency-Extraktion hinzufuegen
    # (nicht in der initialen metadata-Definition, weil agency_table dort
    # noch nicht existiert)
    metadata["has_agency_table"] = bool(agency_table)

    # ==========================================================================
    # FREIE FRAGE-Modus: Nur SEZIEREN + FREIE FRAGE, dann beenden
    # ==========================================================================
    if is_freie_frage:
        if progress_callback:
            progress_callback("FREIE FRAGE: Antwort wird generiert...")

        t0 = time.time()
        freie_frage_antwort = meta_freie_frage(
            frage=freie_frage,
            sezieren_results=sezieren_results,
            etappe1_text=etappe1_text,
            beobachtung=None,  # Im FREIE FRAGE-Modus gibt es noch keinen BEOBACHTEN-Befund
            adjudikation=None,  # Im FREIE FRAGE-Modus gibt es noch keine Adjudikation
            progress_callback=progress_callback,
        )
        stage_durations["freie_frage"] = round(time.time() - t0, 1)

        elapsed = time.time() - start_time
        metadata["elapsed_seconds"] = round(elapsed, 1)
        metadata["valid_runs"] = len(sezieren_results)
        metadata["stage_durations"] = stage_durations

        result = {
            "meta_sezieren": sezieren_results,
            "meta_beobachten": "",
            "meta_destillation": "",
            "meta_freie_frage": freie_frage_antwort,
            "metadata": metadata,
        }

        logger.info(
            f"META-HERMENEUTIC v2.8 FREIE FRAGE abgeschlossen: {len(sezieren_results)} Runs "
            f"in {elapsed:.1f}s (Stufen: {stage_durations})"
        )

        return result

    # ==========================================================================
    # VOLLANALYSE-Modus: BEOBACHTEN + DESTILLATION
    # ==========================================================================

    # ==========================================================================
    # STUFE 2: META-BEOBACHTEN (LLM Flash)
    # ==========================================================================
    if len(sezieren_results) >= 2:
        t0 = time.time()
        beobachtung = meta_beobachten(
            sezieren_results,
            progress_callback=progress_callback,
            etappe1_text=etappe1_text,
        )
        stage_durations["beobachten"] = round(time.time() - t0, 1)
    else:
        beobachtung = "META-BEOBACHTEN nicht möglich: Weniger als 2 Synthese-Runs."

    # v2.8: Erkennen ob Meta-Meta-Analyse
    is_meta_meta = any(
        r.get("source_type") == "meta_hermeneutic" for r in sezieren_results
    )
    if is_meta_meta:
        metadata["is_meta_meta"] = True
        logger.info("META-META-ANALYSE erkannt — Meta-Meta-Prompts aktiviert")

    # ==========================================================================
    # STUFE 2b: META-GEGENPOSITION (Strang B — v59.10.2 Schritt 3)
    # Immer aktiv — Falsifikation ist kein optionaler Modus.
    # Input: SEZIEREN + Agency-Tabelle + Etappe-1
    # KEIN BEOBACHTEN-Input (vermeidet Bestaetigungsdruck)
    # ==========================================================================
    if len(sezieren_results) >= 2:
        t0 = time.time()
        gegenposition = meta_gegenposition(
            sezieren_results,
            agency_table=agency_table,
            etappe1_text=etappe1_text,
            progress_callback=progress_callback,
        )
        stage_durations["gegenposition"] = round(time.time() - t0, 1)
    else:
        gegenposition = "META-GEGENPOSITION nicht möglich: Weniger als 2 Runs."

    # ==========================================================================
    # STUFE 2c: META-ADJUDIKATION (Strang C — v59.10.4 Schritt 4)
    # Bewertet: Was haelt der Gegenprobe stand?
    # Input: BEOBACHTEN (Strang A) + GEGENPOSITION (Strang B), beide roh
    # ==========================================================================
    if (not beobachtung.startswith("FEHLER")
        and not beobachtung.startswith("META-BEOBACHTEN nicht")
        and not gegenposition.startswith("FEHLER")
        and not gegenposition.startswith("META-GEGENPOSITION nicht")):
        t0 = time.time()
        adjudikation = meta_adjudikation(
            beobachtung,
            gegenposition,
            progress_callback=progress_callback,
        )
        stage_durations["adjudikation"] = round(time.time() - t0, 1)
    else:
        adjudikation = "META-ADJUDIKATION übersprungen: BEOBACHTEN oder GEGENPOSITION fehlgeschlagen."

    # ==========================================================================
    # STUFE 3: META-DESTILLATION (LLM Pro) — revidiert (v59.10.4)
    # v59.10.4: Destillation bekommt adjudizierte Befundliste als Input,
    # nicht mehr rohe BEOBACHTEN. Synthetisiert, was der Gegenprobe
    # standgehalten hat — nicht was die bestaetigende Pipeline allein
    # produziert hat.
    # ==========================================================================
    if not adjudikation.startswith("FEHLER") and not adjudikation.startswith("META-ADJUDIKATION übersprungen"):
        t0 = time.time()
        # v59.10.5: Sprachregister-Auszug aus BEOBACHTEN extrahieren
        # (Sektion 8 des BEOBACHTEN-Befunds)
        sprachregister_auszug = ""
        if beobachtung:
            # Suche nach Sektion 8 im BEOBACHTEN-Befund
            sr_start = beobachtung.find("## 8.")
            if sr_start < 0:
                sr_start = beobachtung.find("8. SPRACHREGISTER")
            if sr_start >= 0:
                # Nehme alles ab Sektion 8 bis zum Ende oder zur naechsten ---
                sr_end = beobachtung.find("\n---\n", sr_start)
                if sr_end < 0:
                    sr_end = len(beobachtung)
                sprachregister_auszug = beobachtung[sr_start:sr_end]

        destillat = meta_destillation_revidiert(
            adjudikation,
            sprachregister_auszug=sprachregister_auszug,
            progress_callback=progress_callback,
        )
        stage_durations["destillation"] = round(time.time() - t0, 1)
    else:
        destillat = "META-DESTILLATION übersprungen: Adjudikation fehlgeschlagen."

    # ==========================================================================
    # ERGEBNIS ZUSAMMENSTELLEN
    # ==========================================================================
    elapsed = time.time() - start_time
    metadata["elapsed_seconds"] = round(elapsed, 1)
    metadata["valid_runs"] = len(sezieren_results)
    metadata["stage_durations"] = stage_durations

    result = {
        "meta_sezieren": sezieren_results,
        "meta_beobachten": beobachtung,
        "meta_gegenposition": gegenposition,
        "meta_adjudikation": adjudikation,
        "meta_destillation": destillat,
        "metadata": metadata,
    }

    # ==========================================================================
    # STUFE 4: FREIE FRAGE (nachträglich — v59.10.8)
    # v59.10.8: Die FREIE FRAGE läuft NACH der VOLLANALYSE und bekommt
    # die Adjudikation als Input. So kann sie die Falsifizierungs-Ergebnisse
    # berücksichtigen — statt nur SEZIEREN-Daten zu sehen.
    # ==========================================================================
    if freie_frage and freie_frage.strip():
        if progress_callback:
            progress_callback("FREIE FRAGE (nachträglich): Antwort wird generiert...")

        t0 = time.time()
        freie_frage_antwort = meta_freie_frage(
            frage=freie_frage,
            sezieren_results=sezieren_results,
            etappe1_text=etappe1_text,
            beobachtung=beobachtung,
            adjudikation=adjudikation,
            progress_callback=progress_callback,
        )
        stage_durations["freie_frage"] = round(time.time() - t0, 1)
        result["meta_freie_frage"] = freie_frage_antwort

    logger.info(
        f"META-HERMENEUTIC v2.8 VOLLANALYSE abgeschlossen: {len(sezieren_results)} Runs "
        f"{'(META-META) ' if is_meta_meta else ''}"
        f"in {elapsed:.1f}s (Stufen: {stage_durations})"
    )

    return result


# ==============================================================================
# FORMATIERUNG FÜR DOWNLOAD
# ==============================================================================

def format_meta_result_as_markdown(result: Dict) -> str:
    """Formatiert das Meta-Hermeneutic Ergebnis als Markdown-Datei.

    v2.7: Unterstützt FREIE FRAGE-Modus — wenn result["meta_freie_frage"]
    existiert, wird der FREIE FRAGE-Abschnitt (Frage + Antwort) ausgegeben
    statt BEOBACHTEN + DESTILLATION.
    """

    meta = result.get("metadata", {})
    stages = meta.get("stage_durations", {})
    is_freie_frage = meta.get("mode") == "meta_freie_frage"

    modus_label = "FREIE FRAGE" if is_freie_frage else "VOLLANALYSE"

    # v2.8: Varianten-Verteilung ermitteln
    varianten = {}
    for r in result.get("meta_sezieren", []):
        v = r.get("variante", "?")
        varianten[v] = varianten.get(v, 0) + 1
    var_str = ", ".join(f"V{v}:{c}" for v, c in sorted(varianten.items())) if varianten else "n/a"

    lines = [
        f"# Meta-Hermeneutic Analyse (v2.8 — {modus_label})",
        "",
        f"**Modus:** {modus_label}",
        f"**Runs:** {meta.get('valid_runs', '?')}",
        f"**Dauer:** {meta.get('elapsed_seconds', '?')}s",
        f"**Varianten:** {var_str}",
    ]

    if not is_freie_frage:
        lines.extend([
            f"**Modell Beobachten:** {meta.get('model_beobachten', '?')}",
            f"**Modell Destillation:** {meta.get('model_destillation', '?')}",
        ])

    lines.extend([
        f"**Etappe-1-Daten:** {'Ja' if meta.get('has_etappe1_text') else 'Nein'}",
    ])

    # Stufen-Dauer
    stage_parts = []
    for stage_name in ("sezieren", "termini", "agency", "beobachten", "gegenposition", "adjudikation", "destillation", "freie_frage"):
        if stages.get(stage_name) is not None:
            stage_parts.append(f"{stage_name.upper()} {stages[stage_name]}s")
    if stage_parts:
        lines.append(f"**Stufen-Dauer:** {', '.join(stage_parts)}")

    lines.extend([
        "",
        "---",
        "",
        "## META-SEZIEREN: Übersicht",
        "",
    ])

    # Tabelle der Runs
    lines.append("| Run | Datei | Var | Kern (Zchn) | Fazit (Zchn) | Bew | FR |")
    lines.append("|-----|-------|-----|-------------|-------------|-----|-----|")
    for run in result.get("meta_sezieren", []):
        variante = run.get("variante", "?")
        lines.append(
            f"| {run['nr']} | {run['datei']} | {variante} | {run['laenge_kern']} | "
            f"{run['laenge_fazit']} | {len(run.get('beweisfuehrung', ''))} | "
            f"{len(run.get('freier_raum', ''))} |"
        )

    # Termini-Tabelle
    termini_runs = [r for r in result.get("meta_sezieren", []) if r.get("termini")]
    if termini_runs:
        alle_autoren = set()
        for r in termini_runs:
            alle_autoren.update(r["termini"].keys())

        lines.append("")
        lines.append("### DESTILLATION-Termini pro Run")
        lines.append("")

        header = "| Run | " + " | ".join(sorted(alle_autoren)) + " |"
        sep = "|-----|" + "|".join(["---"] * len(alle_autoren)) + " |"
        lines.append(header)
        lines.append(sep)

        for r in termini_runs:
            cells = [str(r["nr"])]
            for autor in sorted(alle_autoren):
                # v2.4.1-FIX: None-Werte (aus JSON null) als "—" behandeln
                val = r["termini"].get(autor)
                cells.append(val if val else "—")
            lines.append("| " + " | ".join(cells) + " |")

    # FREIER RAUM-Zusammenfassung
    freier_raum_runs = [r for r in result.get("meta_sezieren", []) if r.get("freier_raum")]
    if freier_raum_runs:
        lines.append("")
        lines.append("### FREIER RAUM (Auszug)")
        lines.append("")
        for r in freier_raum_runs:
            fr_short = r["freier_raum"][:200]
            if len(r["freier_raum"]) > 200:
                fr_short += "..."
            lines.append(f"**Run {r['nr']}:** {fr_short}")
            lines.append("")

    # FREIE FRAGE-Abschnitt oder VOLLANALYSE
    if is_freie_frage:
        frage_text = meta.get("freie_frage", "")
        antwort = result.get("meta_freie_frage", "(Keine Antwort)")
        lines.extend([
            "",
            "---",
            "",
            "## FREIE FRAGE",
            "",
            f"**Frage:** {frage_text}",
            "",
            antwort,
        ])
    else:
        lines.extend([
            "",
            "---",
            "",
            "## META-BEOBACHTEN: Stabilitäts-, Qualitäts- und Sprachregister-Analyse",
            "",
            result.get("meta_beobachten", "(nicht verfügbar)"),
            "",
            "---",
            "",
            "## META-GEGENPOSITION: Gegenargumente zur These (Strang B)",
            "",
            result.get("meta_gegenposition", "(nicht verfügbar)"),
            "",
            "---",
            "",
            "## META-ADJUDIKATION: Was hält der Gegenprobe stand? (Strang C)",
            "",
            result.get("meta_adjudikation", "(nicht verfügbar)"),
            "",
            "---",
            "",
            "## META-DESTILLATION: Der harte Befund (9 Sätze — revidiert)",
            "",
            result.get("meta_destillation", "(nicht verfügbar)"),
        ])

    return "\n".join(lines)
