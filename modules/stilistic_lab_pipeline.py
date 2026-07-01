# modules/stilistic_lab_pipeline.py — v57.7.6: Autoren-Erkennung + B13b-Leerzeilen-Fix
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

import json
import logging
import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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
# AUTOREN-ERKENNUNG aus Originaltexten (v57.7.6)
# ==============================================================================
# Scannt die Originaltexte nach Übersetzer-/Autornamen und ordnet sie
# der richtigen QUELLE-Nummer zu. Wird in Etappe 2+3 und Globale Synthese
# injiziert, damit das LLM nicht raten muss.
#
# Motivation: Ohne explizite Autornamen im QUELLE-Label muss das LLM
# die Zuordnung aus Statistiken ableiten — und rät falsch, sobald die
# Stats verfälscht sind (z.B. B13-Leerzeilen-Bug: regelmäßig→frei).
# Siehe Forensik-Session 2026-06-15: Q1↔Q3-Vertauschung.

# Bekannte Autornamen für diese Domain — Whitelist als Validierung
_KNOWN_AUTHORS = {
    'Starikovskij', 'Starikovsky', 'Žukovskij', 'Zhukovskij',
    'Zhukovsky', 'Žukovsky', 'Veresaev', 'Veresayev',
    'Homer', 'Homeros',
    # Kyrillische Formen
    'Стариковский', 'Жуковский', 'Вересаев',
}

# Deutsche/Stil-Analyse-Begriffe die KEINE Autornamen sind
_AUTHOR_STOPWORDS = {
    'Quelle', 'DESTILLATION', 'Beweisführung', 'Hypothese',
    'Dominante', 'Operation', 'Vers', 'Satz', 'Stil',
    'Grundoperation', 'Kennzahl', 'Vergleich', 'Synthese',
    'Übersetzung', 'Original', 'Originals', 'Text', 'Werk',
    'Form', 'Lösung', 'Inhalt', 'Wort', 'Reim', 'Rhythmus',
    'Klang', 'Bild', 'Kraft', 'Stimme', 'Grund', 'Sinn',
    'Sprache', 'Dichtung', 'Poesie', 'Lyrik', 'Epik',
    'Morphologie', 'Enjambement', 'Komposita',
    'Verfahren', 'Prinzip', 'Methode', 'Technik', 'Strategie',
    'Haltung', 'Position', 'Modus', 'Funktion', 'Charakter',
    'Homers',  # Genitiv — "Homer" wird separat erkannt
}


def _is_likely_author_name(name: str) -> bool:
    """Prüft ob ein erkannter Name wahrscheinlich ein Autorname ist."""
    if not name or len(name) < 4:
        return False
    if name in _AUTHOR_STOPWORDS:
        return False
    # Genitiv-Filter
    if name.endswith('s') and len(name) > 3:
        stem_s = name[:-1]
        stem_es = name[:-2] if name.endswith('es') and len(name) > 4 else None
        if stem_s in _AUTHOR_STOPWORDS or (stem_es and stem_es in _AUTHOR_STOPWORDS):
            return False
    return True


# ==============================================================================
# AUTOREN-KONSOLIDIERUNG (v57.8.0 / Schnitt 1 — Claude+GLM Architektur 2026-06-20)
# ==============================================================================
# Vierstufige Prioritätskette:
#   (1) Explizites User-Metadatum (author_metadata Parameter)
#   (2) Sidecar vom Re-Run (falls existing_sidecar_path auf eine .md zeigt,
#       deren HTML-Kommentar-Sidecar bereits Autoren enthält)
#   (3) Erste Zeile des Quelltexts (konservative Heuristik)
#   (4) Fallback — PLATZHALTER in Schnitt 1, Implementierung in Schnitt 3
#       (Positions-Constraint-Regex). WICHTIG: In Schnitt 1 wird hier BEWUSST
#       nicht die alte _detect_authors_in_texts() aufgerufen, um den Bug
#       nicht durch die Hintertür zurückzuholen.
# ==============================================================================


def _resolve_author_map(
    source_texts: Dict[str, str],
    author_metadata: Optional[Dict[str, str]] = None,
    existing_sidecar_path: Optional[Path] = None,
) -> Dict[str, Dict[str, str]]:
    """
    Konsolidiert die Autorenzuordnung pro Quelle über die vierstufige
    Prioritätskette. Liefert sowohl die aufgelösten Autoren als auch
    die Herkunft jeder Entscheidung (resolution_chain).

    Args:
        source_texts:            Dict {source_label: text_content}
        author_metadata:         Optional: User-Input {source_label: author_name}
                                 (Stufe 1 — gewinnt immer)
        existing_sidecar_path:   Optional: Pfad zu einer bestehenden .md-Datei,
                                 deren HTML-Kommentar-Sidecar gelesen wird (Stufe 2).
                                 Idempotenz bei Re-Runs.

    Returns:
        {
          "authors": {"QUELLE 1": "Jesaia", ...},  # None-Werte möglich bei "unresolved"
          "resolution_chain": {"QUELLE 1": "user_metadata", ...}
        }
        Mögliche resolution_chain Werte:
          "user_metadata"   — Stufe 1
          "sidecar_rerun"   — Stufe 2
          "first_line"      — Stufe 3
          "unresolved"      — Stufe 4 (Schnitt 1 Platzhalter, Schnitt 3 implementiert)
    """
    authors: Dict[str, Optional[str]] = {}
    resolution_chain: Dict[str, str] = {}

    # Stufe 2 vorab laden, falls vorhanden
    existing_sidecar = None
    if existing_sidecar_path and existing_sidecar_path.exists():
        try:
            md_text = existing_sidecar_path.read_text(encoding="utf-8")
            existing_sidecar = _extract_authors_sidecar_from_md(md_text)
        except (OSError, ValueError):
            existing_sidecar = None  # korruptes Sidecar wird ignoriert, nicht eskaliert

    for quelle_key, text in source_texts.items():
        # Stufe 1: User-Metadatum
        if author_metadata and quelle_key in author_metadata and author_metadata[quelle_key]:
            authors[quelle_key] = author_metadata[quelle_key]
            resolution_chain[quelle_key] = "user_metadata"
            continue

        # Stufe 2: Sidecar vom Re-Run
        if existing_sidecar and quelle_key in existing_sidecar.get("authors", {}):
            authors[quelle_key] = existing_sidecar["authors"][quelle_key]
            resolution_chain[quelle_key] = "sidecar_rerun"
            continue

        # Stufe 3: Mini-LLM-Call (seit Schnitt 3 v2)
        # _extract_first_line_author() ist jetzt LLM-basiert, nicht mehr First-Line-Heuristik.
        # Variablenname first_line ist aus Kompatibilität geblieben, aber semantisch
        # ist es das LLM-Ergebnis.
        first_line = _extract_first_line_author(text)
        if first_line:
            authors[quelle_key] = first_line
            resolution_chain[quelle_key] = "mini_llm"
            continue

        # Stufe 4: Platzhalter — Schnitt 3 liefert hier die Regex-Korrektur.
        # In Schnitt 1 bewusst None/"unresolved", NICHT die alte
        # fehleranfällige _detect_authors_in_texts() aufrufen.
        authors[quelle_key] = None
        resolution_chain[quelle_key] = "unresolved"

    # v59.9.1 Fix 2026-06-21: Log-Zeile entfernt — duplicate mit der
    # 🖊️ Autoren konsolidiert-Zeile in run_stilistic_lab(). Reduziert Terminal-Noise.
    # Die Info ist in der aufrufenden Funktion sichtbar.
    return {"authors": authors, "resolution_chain": resolution_chain}


def _extract_first_line_author(text: str, source_label: str = "") -> Optional[str]:
    """
    Stufe-3-Heuristik (v57.8.2 / Schnitt 3 v2 — LLM-basiert 2026-06-20):
    Mini-LLM-Call statt Regex. Die Autoren-Erkennung ist eine semantische
    Aufgabe (variable Sprachen, variable Formate, Werk-Titel vs. Autor-
    Namen, Übersetzer-Marker in verschiedenen Konventionen). Regex versagt
    hier systematisch. Das LLM generalisiert.

    Prompt: „Lies die ersten 5 Zeilen. Wer ist der Autor/Übersetzer?
    Antworte NUR mit dem Namen, sonst nichts."

    1 Call pro Quelle, 4 Calls für 4 Quellen. Flash-Modell, max_tokens=20.

    Args:
        text:          Der Quelltext (oder die ersten N Zeilen davon).
        source_label:  Optional: QUELLE-Label für Logging.

    Returns:
        Autor-Name als String, oder None bei Fehler/leerem Input.
    """
    if not text:
        return None

    # Erste 5 nicht-leere Zeilen nehmen — mehr braucht das LLM nicht
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        lines.append(stripped)
        if len(lines) >= 5:
            break

    if not lines:
        return None

    text_for_llm = "\n".join(lines)

    # Mini-LLM-Call: Flash-Modell, kurze Antwort
    # v57.8.3: Prompt präzisiert — verlangt Nachname im Nominativ, latinisiert.
    # Vorher: LLM lieferte „В.А. Жуковского" (kyrillisch, Genitiv, mit Initialien)
    # Jetzt: LLM liefert „Žukovskij" (Nachname, Nominativ, latinisiert)
    prompt = (
        "Lies die folgenden Zeilen aus dem Anfang eines Textes. "
        "Identifiziere den Autor oder Uebersetzer. "
        "ANTWORTFORMAT: Nur der NACHNAME im NOMINATIV, LATINISIERT "
        "(kyrillische Namen in lateinischer Umschrift). "
        "BEISPIELE: Autor, Uebersetzer, Herausgeber, Mitverfasser. "
        "FALSCH wären: V.A. Zukovskogo, Жуковский, Григория Стариковского, "
        "Thomas Paine (mit Vorname). "
        "Wenn kein Autor erkennbar ist: antworte UNBEKANNT.\n\n"
        "--- TEXT-ANFANG ---\n"
        f"{text_for_llm}\n"
        "--- TEXT-ENDE ---"
    )

    system_instruction = (
        "Du extrahierst Autorennamen aus Textanfaengen. "
        "ANTWORTFORMAT: AUSSCHLIESSLICH der Nachname im Nominativ, "
        "latinisiert (kyrillische Namen in lateinischer Umschrift, "
        "z.B. Zukovskij statt Жуковский oder Жуковского). "
        "KEINE Vornamen, KEINE Initialien, KEINE Genitiv-Endungen, "
        "KEINE Satzzeichen, KEINE Erklaerung. "
        "Bei Uebersetzungen: gib den Uebersetzer an, nicht den Originalautor. "
        "Bei unbekanntem Autor: antworte UNBEKANNT."
    )

    label_tag = f" [{source_label}]" if source_label else ""
    logger.info(f"  🤖 Mini-LLM Autoren-Erkennung{label_tag}: {len(text_for_llm)} Zchn Input")

    try:
        response = llm_call(
            prompt=prompt,
            task="author_extraction",  # Config 2026-06-20: eigener Task für Mini-LLM-Calls
            system_instruction=system_instruction,
            temperature=0.0,
            max_tokens=200,  # Bug-Fix 2026-06-20: 20 war zu niedrig für Flash-Reasoning
            domain="stilisierung",
        )
    except Exception as e:
        logger.error(f"  ❌ Mini-LLM Autoren-Erkennung{label_tag} fehlgeschlagen: {e}")
        return None

    if not response:
        logger.warning(f"  ⚠️ Mini-LLM{label_tag} lieferte leere Antwort")
        return None

    # Antwort bereinigen: trimmen, Satzzeichen entfernen, UNBEKANNT filtern
    author = response.strip()
    author = author.strip(".\"'\n ")
    if not author or author.upper() == "UNBEKANNT":
        logger.info(f"  ℹ️ Mini-LLM{label_tag}: kein Autor erkannt (UNBEKANNT)")
        return None
    # Bug-Fix 2026-06-20: Mindestlängen-Check. Flash kann bei zu niedrigen
    # max_tokens manchmal nur 1 Token generieren (z.B. "В" statt "Вересаев").
    # Ein einzelner Buchstabe ist kein gültiger Autor.
    if len(author) < 2:
        logger.warning(f"  ⚠️ Mini-LLM{label_tag}: Antwort zu kurz ('{author}'), verworfen")
        return None

    logger.info(f"  ✅ Mini-LLM{label_tag}: Autor erkannt = '{author}'")
    return author

def _extract_authors_sidecar_from_md(md_text: str) -> Optional[Dict]:
    """
    Extrahiert das HTML-Kommentar-Sidecar aus einer .md-Datei.

    Sucht nach einem Kommentar der Form:
      <!-- HRE-AUTHORS-SIDECAR
      {...JSON...}
      -->

    V57.8.0 Claude-Review Fix: Suche nur in den ersten 500 Zeichen von md_text.
    Begründung: Ein find() über die gesamte Datei würde das ERSTE Vorkommen des
    Markers finden, egal wo. Wenn ein Korpus-Quelltext selbst diesen String
    enthält (z.B. ein zitierter Abschnitt aus einer früheren Analyse oder ein
    versehentlich eingefügter alter Sidecar-Kommentar), würde die Funktion den
    falschen Block parsen. Da der Sidecar laut Spezifikation garantiert am
    Dateianfang sitzt, ist die Suche in den ersten 500 Zeichen sicher und
    schließt diesen Edge Case aus.

    Returns:
        Geparstes Dict oder None, wenn kein Sidecar gefunden wurde.
    """
    if not md_text:
        return None
    # Claude-Review Fix: nur in den ersten 500 Zeichen suchen
    search_window = md_text[:500]
    marker = "HRE-AUTHORS-SIDECAR"
    idx = search_window.find(marker)
    if idx < 0:
        return None
    # Suche den schließenden --> nach dem Marker (im gesamten Text, da der
    # JSON-Block länger als 500 Zeichen sein kann)
    end_idx = md_text.find("-->", idx)
    if end_idx < 0:
        return None
    # Extrahiere den Block zwischen Marker und -->, finde { und }
    block = md_text[idx:end_idx]
    brace_start = block.find("{")
    brace_end = block.rfind("}")
    if brace_start < 0 or brace_end < 0 or brace_end <= brace_start:
        return None
    json_str = block[brace_start:brace_end + 1]
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        return None


def _embed_authors_sidecar_in_md(
    md_content: str,
    author_map: Dict[str, Optional[str]],
    resolution_chain: Dict[str, str],
) -> str:
    """
    Bettet die Autoren-Metadaten als HTML-Kommentar am Anfang des
    md_content-Strings ein. Wird in der UI-Schicht (stilistic_lab_tab.py)
    aufgerufen, bevor der md_content dem st.download_button übergeben wird.

    V57.8.0 Claude-Review Fix: Prüft vor dem Einbetten, ob md_content bereits
    einen Sidecar-Kommentar am Anfang enthält. Falls ja, wird md_content
    unverändert zurückgegeben (Idempotenz). Verhindert doppelte Sidecar-
    Kommentare bei wiederholtem Aufruf (z.B. Streamlit-Re-Render mit
    gecachtem result).

    Schema:
      <!-- HRE-AUTHORS-SIDECAR
      {"version": "1.0", "created_at": "...", "source_count": N,
       "authors": {...}, "resolution_chain": {...}}
      -->

      [regulärer md_content folgt]
    """
    # Claude-Review Fix: Idempotenz-Check — nicht doppelt einbetten
    if md_content.lstrip().startswith("<!-- HRE-AUTHORS-SIDECAR"):
        return md_content  # bereits eingebettet, nichts tun

    sidecar = {
        "version": "1.0",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "source_count": len(author_map),
        "authors": {k: v for k, v in author_map.items()},  # None-Werte bleiben als null
        "resolution_chain": dict(resolution_chain),
    }
    # Kompakte JSON-Darstellung, aber lesbar formatiert (2-Zeilen-Block im Kommentar)
    # Bug-Fix 2026-06-20: time.strftime statt datetime.now().isoformat —
    # `datetime` ist in stilistic_lab_pipeline.py nicht importiert (nur `time`).
    # Vermeidet NameError: name 'datetime' is not defined.
    json_str = json.dumps(sidecar, ensure_ascii=False, indent=2)
    comment = f"<!-- HRE-AUTHORS-SIDECAR\n{json_str}\n-->\n\n"
    return comment + md_content


def _detect_authors_in_texts(source_texts: Dict[str, str]) -> Dict[str, str]:
    """Erkennt Autornamen in den Originaltexten und ordnet sie der QUELLE zu.

    Scannt jeden Originaltext nach Übersetzer-/Autornamen:
    1. "перевод" + Genitiv-Name (zuverlässigstes Muster in russischen Texten)
    2. Kyrillische Autornamen (Nominativ + Genitiv-Suffixes)
    3. Lateinische Autornamen mit diakritischen Zeichen (Žukovskij etc.)
    4. Fallback: Bekannte Autornamen aus Whitelist

    Kyrillische Formen werden auf latinisierte Formen gemappt
    (z.B. Стариковский → Starikovskij) für konsistente Darstellung.

    Args:
        source_texts: Dict {source_label: text_content}

    Returns:
        Dict {source_label: author_name} — nur für Quellen mit erkanntem Autor.
        Quellen ohne erkennbaren Autor werden NICHT aufgenommen.
    """
    # Mapping kyrillisch → latinisiert (für konsistente Prompt-Darstellung)
    _CYR_TO_LAT = {
        'Стариковский': 'Starikovskij',
        'Стариковского': 'Starikovskij',   # Genitiv
        'Жуковский': 'Žukovskij',
        'Жуковского': 'Žukovskij',          # Genitiv
        'Вересаев': 'Veresaev',
        'Вересаева': 'Veresaev',            # Genitiv
    }

    author_map = {}

    for label, text in source_texts.items():
        if not text or not text.strip():
            continue

        found_cyr = set()   # Kyrillische Formen (für Mapping)
        found_lat = set()   # Lateinische Formen (direkt verwendbar)

        # Muster 1 (ZUVERLÄSSIGSTES): "перевод" + Name im Genitiv
        # z.B. "Перевод с древнегреческого Григория Стариковского"
        # z.B. "перевод Вересаева"
        for m in re.finditer(
            r'[Пп]еревод[а-яё]*\s+'
            r'(?:с\s+\S+\s+)?'        # optional: "с древнегреческого"
            r'([А-ЯЁ][а-яё]{2,}'      # Vorname (optional)
            r'(?:\s+[А-ЯЁ][а-яё]+)?'  # Nachname
            r'(?:ского|ского|вой|евой|на|ний|вич)'  # Genitiv-Endung
            r')',
            text
        ):
            full_name = m.group(1).strip()
            # Versuche Mapping über Nachnamen
            for Cyr, lat in _CYR_TO_LAT.items():
                if Cyr in full_name:
                    found_cyr.add(Cyr)
                    found_lat.add(lat)

        # Muster 2: Kyrillische Autornamen — Nominativ und Genitiv
        for m in re.finditer(
            r'([А-ЯЁ][а-яё]+(?:ский|ского|ская|ая|ий|ов|ова|ева|ева|ин|ына|на))',
            text
        ):
            name = m.group(1)
            if name in _CYR_TO_LAT:
                found_cyr.add(name)
                found_lat.add(_CYR_TO_LAT[name])
            elif name not in _AUTHOR_STOPWORDS and len(name) >= 5:
                found_cyr.add(name)

        # Muster 3: Lateinische Namen mit diakritischen Zeichen
        for m in re.finditer(
            r'([A-ZÁÀÂÄÅĂĄĆČĎĐÉÈÊËĖĘĚĞÍÌÎÏİĶĹĽŁŃŇÑÓÒÔÖŐŐŘŔŚŠŞŤŢÚÙÛÜŰŮŴÝŸŹŽŻ]'
            r'[a-záàâäăąćčďđéèêëęěğíìîïıķĺľłńňñóòôöőřŕśšşťţúùûüűůŵýÿźžż]+'
            r'(?:[vV]on)?'
            r'[a-záàâäăąćčďđéèêëęěğíìîïıķĺľłńňñóòôöőřŕśšşťţúùûüűůŵýÿźžż]*)',
            text
        ):
            name = m.group(1).strip()
            if _is_likely_author_name(name):
                found_lat.add(name)

        # Muster 4: Fallback — bekannte Autornamen im Text
        if not found_cyr and not found_lat:
            for known in _KNOWN_AUTHORS:
                if known in text and known not in _AUTHOR_STOPWORDS:
                    if re.match(r'[А-ЯЁ]', known):
                        found_cyr.add(known)
                    else:
                        found_lat.add(known)

        # Ergebnis: Latinisierte Form bevorzugen (konsistent im Prompt)
        if found_lat:
            author_map[label] = sorted(found_lat)[0]
        elif found_cyr:
            # Kyrillisch ohne Mapping — versuche Mapping
            for Cyr in sorted(found_cyr):
                if Cyr in _CYR_TO_LAT:
                    author_map[label] = _CYR_TO_LAT[Cyr]
                    break
            else:
                author_map[label] = sorted(found_cyr)[0]

    logger.info(f"  Erkannte Autoren pro Quelle: {author_map}")
    return author_map


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
# QUELLEN-GEGENPOSITION: SYSTEM-INSTRUCTION + PROMPT (v59.10.0 Schritt 2)
# ==============================================================================

_QUELLEN_GEGENPOSITION_SYSTEM = """Du bist ein kritischer Gegen-Analytiker.
Deine Aufgabe ist es, GEGEN die These zu argumentieren, die die bestaetigende
Analyse aufgestellt hat. Du suchst nach Befunden, die die These
widerlegen, modifizieren oder alternative Erklaerungen ermoeglichen.

STRIKTE REGELN:
- PFLICHT: Behandle JEDEN Autor/jede Quelle in einem eigenen Absatz.
  Ueberspringe keine Quelle - auch wenn du keine Gegenbefunde findest,
  schreibe explizit, warum fuer diese Quelle keine Gegenbefunde gefunden wurden.
- Beziehe dich auf konkrete Etappe-1-Kennzahlen (TTR, Satzlaenge, etc.)
- Formuliere mindestens eine alternative Erklaerung pro Autor
- Keine Harmonisierung: Wenn ein Gegenbefund stark ist, sage das.
- Keine Bestaetigung: Suche aktiv nach dem, was NICHT zur These passt.

ZENTRALE REGEL (v59.10.1 Schritt A):
- Die bestaetigende Analyse stuetzt sich auf KONKRETE ZITATE aus den Texten.
- Du MUSST dich mit diesen Zitaten auseinandersetzen — nicht mit abstrakten
  Framings. Wenn die These sagt "Brodskij verwendet imperiales Vokabular
  (Империя, еловое войско)", musst du argumentieren, WARUM diese Woerter
  NICHT imperial sind — oder zugeben, dass die These hier stark ist.
- VERBOTEN: Abstrakte Gegenlesarten ohne Textbezug (z.B. "Poetik der
  Deprivation" ohne Bezug zu konkreten Zitaten).
- PFLICHT: Zitiere die Woerter, gegen die du argumentierst.
- PFLICHT: Wenn du eine alternative Erklaerung formulierst, muss sie die
  KONKRETEN ZITATE ebenso gut erklaeren wie die These — nicht die abstrakte
  Zusammenfassung."""

_QUELLEN_GEGENPOSITION_PROMPT = """QUELLEN-GEGENPOSITION: Argumentiere GEGEN die These der bestaetigenden Analyse.

Die bestaetigende Globale Synthese hat folgende These aufgestellt:
{globale_synthese}

Die untersuchte Frage war:
{user_question}

PFLICHT: Behandle JEDEN der folgenden Autoren/Quellen in einem eigenen Absatz.
Format: ### [Autor/Quelle]
Ueberspringe KEINE Quelle. Wenn du fuer eine Quelle keine Gegenbefunde findest,
schreibe explizit: "Fuer [Quelle] wurden keine Gegenbefunde gefunden, weil..."
und erklaere, warum die These fuer diese Quelle besonders gut passt.

Fuer jede Quelle:
1. IDENTIFIZIERE Gegenbefunde: Welche sprachlichen oder rhetorischen Elemente
   sprechen GEGEN die These? Beziehe Etappe-1-Kennzahlen ein.
2. ALTERNATIVE ERKLAERUNG: Formuliere mindestens eine alternative Erklaerung,
   die die Daten ebenso gut erklaert wie die These.
3. FALSIFIKATIONS-BEDINGUNG: Was muesste in den Daten stehen, damit die
   These fuer diese Quelle eindeutig widerlegt waere?

Autoren/Quellen (aus Etappe-1-Daten):
{quellen_liste}

Etappe-1-Kennzahlen:
{kennzahlen_block}

Einzelbeobachtungen (Etappe 2+3, mit konkreten Zitaten):
{einzelbeobachtungen}

ZENTRALE ANWEISUNG (v59.10.1 Schritt A):
Die bestaetigende Analyse stuetzt sich auf konkrete Zitate aus den Texten.
Diese Zitate stehen in den Einzelbeobachtungen oben. Du MUSST dich mit
diesen Zitaten auseinandersetzen:

1. IDENTIFIZIERE die konkreten Zitate, auf die die These sich stuetzt.
2. ARGUMENTIERE GEGEN diese Zitate: Warum beweisen sie nicht, was die
   These behauptet? Sind sie anders interpretierbar?
3. Wenn du eine Zitat-Interpretation nicht widerlegen kannst: SAGE DAS.
   "Die These ist fuer dieses Zitat stark, weil..." ist ehrlicher als
   eine abstrakte Gegenlesart ohne Textbezug.

VERBOTEN: Abstrakte Gegenlesarten ohne Bezug zu konkreten Zitaten.
PFLICHT: Jeder Gegenbefund muss sich auf mindestens ein konkretes Zitat
aus dem Text beziehen.

WICHTIG: Dies ist eine GEGENPOSITION. Suche nicht nach Bestaetigung.
Suche nach dem, was die These herausfordert."""


def _build_quellen_gegenposition_prompt(
    globale_synthese: str,
    user_question: str,
    valid_results: Dict[str, str],
    individual_stats: Dict[str, Dict],
    author_map: Optional[Dict[str, str]] = None,
    comparison_table_text: str = "",
) -> str:
    """Baut den Prompt fuer die Quellen-Gegenposition."""
    quellen = []
    for label in valid_results.keys():
        author = author_map.get(label, "") if author_map else ""
        author_str = f" [{author}]" if author else ""
        quellen.append(f"- {label}{author_str}")
    quellen_liste = "\n".join(quellen)

    kennzahlen_lines = []
    for label, s in individual_stats.items():
        kennzahlen_lines.append(
            f"  {label}: {s.get('words', 0)} Woerter | "
            f"TTR {s.get('TTR', 0):.3f} | "
            f"O {s.get('avg_sent_len', 0)} | "
            f"Alliterationen {s.get('alliterationen', '-')} | "
            f"Enjamb. {s.get('enjambement', '-')}"
        )
    kennzahlen_block = "\n".join(kennzahlen_lines)

    einzel_lines = []
    for label, text in valid_results.items():
        einzel_lines.append(f"--- {label} ---\n{text[:3000]}\n")
    einzelbeobachtungen = "\n".join(einzel_lines)[:16000]

    prompt = _QUELLEN_GEGENPOSITION_PROMPT.format(
        globale_synthese=globale_synthese[:5000],
        user_question=user_question or "(keine spezifische Frage)",
        quellen_liste=quellen_liste,
        kennzahlen_block=kennzahlen_block,
        einzelbeobachtungen=einzelbeobachtungen,
    )

    if comparison_table_text:
        prompt += f"\n\nVergleichstabelle:\n{comparison_table_text}\n"

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

def _format_klang_table_for_synthese(individual_stats: Dict[str, Dict]) -> str:
    """v57.8.4: Formatiert Klang-Kennzahlen als Tabelle für den Synthese-Prompt.
    Analog zu format_comparison_table_for_llm, aber fokussiert auf Klang.
    Liefert numerische Werte, damit die Synthese BEWEISE führen kann
    (statt „dichte akustische Textur" — „15 Alliterationen").
    """
    if not individual_stats:
        return "(Keine Klang-Kennzahlen verfügbar)"

    headers = ["Quelle", "Alliterationen", "Assonanzen", "Binnenreime", "Vokal-Echos", "Reim", "Enjambement"]
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("|" + "|".join([" --- "] * len(headers)) + "|")

    for label, s in individual_stats.items():
        row = [
            str(label),
            str(s.get("alliterationen", "—")),
            str(s.get("assonanzen", "—")),
            str(s.get("binnenreime", "—")),
            str(s.get("vokalechos", "—")),
            str(s.get("reim_typ", "—")),
            str(s.get("enjambement", "—")),
        ]
        lines.append("| " + " | ".join(row) + " |")

    return "\n".join(lines)


def _build_globale_synthese_prompt(
    etappen_results: Dict[str, str],
    comparison_table_text: str,
    user_question: str = "",
    praegnanz_sentences: Optional[Dict[str, str]] = None,
    individual_stats: Optional[Dict[str, Dict]] = None,
    dominant_labels: Optional[Dict[str, str]] = None,
    grundoperation_labels: Optional[Dict[str, str]] = None,
    modus_labels: Optional[Dict[str, str]] = None,
    author_map: Optional[Dict[str, str]] = None,
    klang_table_text: str = "",  # v57.8.4: Klang-Kennzahlen-Tabelle für Beweisführung
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
        author_map:            Dict {source_label: author_name} (v57.7.6)
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
        # v57.7.6: Autornamen im KONZENTRAT anzeigen wenn verfügbar
        author_str = f" [{author_map[label]}]" if author_map and label in author_map else ""
        konzentrat_block += f"  {label}{author_str}: Dominante: {dom} | Operation: {op} | Modus: {mod} | Titel: {titel}\n"
    konzentrat_block += "\n"

    # v57.7.6: Explizite Autoren-Zuordnung als separates Block
    # Damit das LLM die Zuordnung QUELLE → Autor nicht raten muss
    if author_map and len(author_map) >= 2:
        konzentrat_block += "--- AUTOREN-ZUORDNUNG ---\n"
        for label, name in sorted(author_map.items()):
            konzentrat_block += f"  {label} = {name}\n"
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

--- KLANG-KENNZAHLEN (numerisch, für Beweisführung) ---
{klang_table_text}

WICHTIG - BEWEISFÜHRUNG mit KLANG-KENNZAHLEN:
- Wenn die UNTERSUCHUNGSFRAGE nach KLANG fragt: nutze die obige Tabelle für BEWEISE.
- In der Tabelle der UNTERSUCHUNGSFRAGE-Sektion: NUMERISCHE WERTE aus der KLANG-KENNZAHLEN-Tabelle übernehmen, nicht nur Adjektive.
- Statt „dichte Verwendung" schreibe „15 Alliterationen" (Zahl aus der Tabelle).
- Statt „Vorhanden" schreibe „2 Binnenreime" (Zahl aus der Tabelle).
- Im Urteil: NUMERISCHE VERGLEICHE führen. Beispiel:
  „Autor A: 15 Alliterationen (Autor B: 12, Autor C: 8, Autor D: 5)"
- BELEGE aus Etappe 2/3 als konkrete Wörter (z.B. „Alliteration 'выступают вперед взаимообразно' V.5-6").
- KEINE Synthese-eigenen Begriffe als Beleg (z.B. „Klangfügung als Dominante" ist Synthese-Vokabular, kein Beweis).

--- EINZELBEOBACHTUNGEN PRO QUELLE ---
{quellen_block}

---

Beziehe dich auf die Einzelbeobachtungen oben. Verkn\u00fcpfe die Funde
zu einem Argument \u2014 nicht zu einer Liste.
Wenn die Quellen-Bezeichnungen Autoren-Namen oder Gruppen enthalten,
nutze diese, um die Beobachtungen zu strukturieren.

HYPOTHESE:
Formuliere die sch\u00e4rfste Behauptung, die sich direkt aus den
KONZENTRAT-Feldern DOMINANTE und GRUNDOPERATION ableitet.
PFLICHT: Die Behauptung MUSS die Terminologie aus dem KONZENTRAT
verwenden \u2014 keine freien Metaphern, keine Bilder, die nicht
im KONZENTRAT stehen.
DESTILLATION: Bilde aus den KONZENTRAT-Feldern DOMINANTE
und GRUNDOPERATION je einen Stil-Terminus pro Quelle.
PRODUKTIONSBEDINGUNG: Die Termini m\u00fcssen paarweise
verschieden sein \u2014 jeder Terminus benennt eine Operation,
die diese Quelle von allen anderen unterscheidet.
Kriterium: Was tut dieser Text, das kein anderer tut?
Wenn zwei Termini dieselbe Operation beschreiben, ist
mindestens einer falsch destilliert.
Ausnahme: Wenn eine Quelle keine scharfe Abweichung zeigt,
benenne ihre Position im Vergleichsraum als das, was sie
ist — Verzicht, Mitte, Anpassung oder ein anderer
Beobachtungsterminus. Kein Urteil über die Intention
des Übersetzers.
Diese Termini sind das Vokabular des Fazits.
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

FAZIT: Verwende die destillierten Termini als das
Vokabular des Fazits. Die Termini d\u00fcrfen in Metaphern
eingebettet werden, aber nicht durch Metaphern ersetzt
werden. Eine Quelle ohne scharfe Abweichung verdient
gesonderte Erwähnung — ihre Position im Vergleichsraum
ist ein Befund, kein Mangel. Der letzte Satz beantwortet die
Untersuchungsfrage als Urteil."""

    # Benutzerdefinierte Frage injizieren
    if user_question and user_question.strip():
        prompt += f"""

UNTERSUCHUNGSFRAGE: {user_question.strip()}

WICHTIG - THEMABEZUG DER ANTWORT:
Beantworte diese Frage NUR mit Etappe-1-Kennzahlen, die zum THEMA der Frage passen.
Welche Kennzahlen thematisch passen, entscheidet sich nach dem Schwerpunkt der Frage:

- Wenn die Frage nach KLANG fragt: nutze Vokal-Echos, Alliterationen, Assonanzen,
  Binnenreime, Vokalverteilung, Klangfiguren. NICHT: Enjambement, Satzlänge, TTR.
- Wenn die Frage nach RHYTHMUS fragt: nutze Silbenzahl pro Vers, Silben-σ, 
  Strophenzahl, Reimstruktur, Metrum. NICHT: Vokal-Echos, Klangfiguren.
- Wenn die Frage nach SYNTAX/FLUSS fragt: nutze Satzlänge, Satzbau (HS/NS/gemischt),
  Enjambement-Rate, Kommas. NICHT: Vokal-Echos, Klangfiguren, Reim.
- Wenn die Frage nach WORTSCHATZ fragt: nutze TTR, Morphologie, Komposita,
  Hotspot-Wörter. NICHT: Enjambement, Silbenzahl.
- Bei Mischfragen (z.B. „Klang und Rhythmus"): gewichte die thematisch passenden
  Kennzahlen, ignoriere die anderen.

PRIMÄR thematisch passende Kennzahlen verwenden, SEKUNDÄR können auch andere
Kennzahlen als ergänzende Belege dienen, wenn sie die primäre Argumentation stützen.
Beispiel: Bei einer Klang-Frage sind Alliterationen/Assonanzen/Binnenreime/Vokal-Echos
primär. Enjambement oder Reim können als sekundäre Belege hinzukommen, wenn sie das
Klang-Urteil erhärten — aber sie dürfen nicht das HAUPTARGUMENT werden.
VERBOTEN ist nur: eine Frage NUR mit themenfremden Kennzahlen zu beantworten
(z.B. Klang-Frage NUR mit Enjambement, ohne jeglichen Klang-Bezug).

STRUKTUR DER ANTWORT:
Erstelle eine eigene Sektion ### UNTERSUCHUNGSFRAGE mit:
1. Tabelle: Welche thematisch passenden Kennzahlen hat jede Quelle?
   (Quelle | Kennzahl 1 | Kennzahl 2 | ... mit Werten)
2. Urteil (1-3 Sätze): Welche Quelle passt zur Frage am besten — und zwar
   BEGRÜNDET mit den thematisch passenden Kennzahlen, nicht mit anderen.

Der letzte Satz des FAZIT muss die Frage als klares Urteil beantworten,
konsistent mit dem Urteil in der UNTERSUCHUNGSFRAGE-Sektion."""

    return prompt


# ==============================================================================
# HAUPTFUNKTION: STILISTIC LAB PIPELINE
# ==============================================================================

def run_stilistic_lab(
    source_texts: Dict[str, str],
    progress_callback=None,
    user_question: str = "",
    author_metadata: Optional[Dict[str, str]] = None,
    existing_sidecar_path: Optional[Path] = None,
    enable_quellen_gegenposition: bool = False,
) -> Dict:
    """
    Führt die komplette STILISTIC LAB Pipeline aus.

    Drei-Etappen-Architektur:
    1. Etappe 1 (SEZIEREN): Python-Preprocessing, deterministisch
    2. Etappe 2+3 (pro Quelle): LLM-charakterisierung auf Faktenbasis
    3. Globale Synthese: Vergleichende Beobachtung über alle Quellen

    Args:
        source_texts:           Dict {source_label: text_content}
                                source_label sollte QUELLE-Nummer + Kurzname sein,
                                z.B. "QUELLE 1: Herzen" oder "QUELLE 2: Lenin"
        progress_callback:      Optional: Callback(status_msg) für UI-Updates
        user_question:          Optionale Frage, die in der Globalen Synthese
                                injiziert wird (v57.5.1 Fix C)
        author_metadata:        Optional (v57.8.0 / Schnitt 1): User-Input
                                {source_label: author_name}. Stufe 1 der
                                Prioritätskette — gewinnt immer, wenn gesetzt.
                                Vorerst nur Hook, kein UI-Eingabefeld.
        existing_sidecar_path:  Optional (v57.8.0 / Schnitt 1): Pfad zu einer
                                bestehenden .md-Datei, deren HTML-Kommentar-
                                Sidecar gelesen wird (Stufe 2, Idempotenz
                                bei Re-Runs).

    Returns:
        Dict mit:
        - etappe1: Dict aus analyze_texts_comparative()
        - etappen_2_3: Dict {source_label: llm_response}
        - globale_synthese: String
        - metadata: timing, model, etc.
        - author_map: Dict {source_label: author_name oder None}  (NEU v57.8.0)
        - author_resolution_chain: Dict {source_label: chain_value}  (NEU v57.8.0)
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
    # AUTOREN-KONSOLIDIERUNG (v57.8.0 / Schnitt 1 — Claude+GLM Architektur 2026-06-20)
    # ==========================================================================
    # Vierstufige Prioritätskette (siehe _resolve_author_map Docstring):
    #   (1) User-Metadatum  →  (2) Sidecar Re-Run  →  (3) First-Line  →  (4) Fallback
    # WICHTIG: Stufe 4 ist in Schnitt 1 nur Platzhalter (None / "unresolved").
    # Die alte _detect_authors_in_texts() wird NICHT aufgerufen — sie bleibt
    # im Code, bis Schnitt 3 sie zur Fallback-Funktion umbaut.
    # ==========================================================================
    resolution = _resolve_author_map(
        source_texts,
        author_metadata=author_metadata,
        existing_sidecar_path=existing_sidecar_path,
    )
    author_map_full = resolution["authors"]              # inkl. None-Werte
    author_resolution_chain = resolution["resolution_chain"]
    # V57.8.0 Claude-Review Fix: None-Werte herausfiltern, bevor author_map an die
    # bestehende Etappe-2/3-Logik übergeben wird. Die bestehende Logik tut
    # `if label in author_map: author_lbl = author_map[label]` und
    # `", ".join(other_parts)` — würde TypeError produzieren, wenn None-Werte
    # durchsickern. Mit Filterung verhält sich author_map wie früher: nur
    # resolved Autoren sind Keys. None-Werte sind in author_map_full (für das
    # Sidecar) und in author_resolution_chain (für Debugging) erhalten.
    author_map = {k: v for k, v in author_map_full.items() if v is not None}
    resolved_count = len(author_map)
    total_count = len(author_map_full)
    # v59.9.2 Fix 2026-06-21: Konsolidierungs-Zeile informativ machen.
    # Vorher: „4/4 resolved. Resolution: {... 'mini_llm' ...}" — Resolution-Chain
    # enthält keine Info (alle Werte gleich), sinnlos.
    # Neu: echte Autoren-Namen in Quellen-Reihenfolge + via-Info.
    # Resolution-Chain-Detail auf debug-Level verschoben.
    authors_str = " / ".join(
        str(author_map_full.get(label, "—"))
        for label in source_texts.keys()
    )
    # Bestimme verwendete Auflösungsstrategien (z.B. „Mini-LLM", „User-Metadatum")
    strategies = set(author_resolution_chain.values()) - {"unresolved"}
    strategy_str = " + ".join(sorted(strategies)) if strategies else "keine"
    logger.info(
        f"🖊️ Autoren konsolidiert: {authors_str} "
        f"({resolved_count}/{total_count} via {strategy_str})"
    )
    logger.debug(f"  Resolution-Chain: {dict(author_resolution_chain)}")

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

        # Autor-Label für Horizont-Instruktion ableiten (v57.7.5 + v57.7.6)
        # v57.7.5: Format "QUELLE 1: Herzen 1849" → "Herzen 1849"
        # v57.7.6: Wenn Autorenerkennung einen Namen fand, diesen verwenden
        #          (zuverlässiger als Label-Extraktion, die bei "QUELLE 1" ohne
        #           Doppelpunkt nur "QUELLE 1" liefert → LLM muss raten)
        if label in author_map:
            author_lbl = author_map[label]
        else:
            author_lbl = label.split(": ", 1)[-1] if ": " in label else label

        # Andere Autoren/Quellen für Horizont-Instruktion
        other_parts = []
        for l in source_labels:
            if l == label:
                continue
            if l in author_map:
                other_parts.append(author_map[l])
            else:
                other_parts.append(l.split(": ", 1)[-1] if ": " in l else l)
        other_lbls = ", ".join(other_parts)

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
            r'(?:DIE )?GRUNDOPERATION:\s*(.+?)(?:\n\n|\n[A-ZÄÖÜ]|$)',
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
            r'MODUS:\s*(.+?)(?:\n\n|\n[A-ZÄÖÜ]|$)',
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
            # v59.9.1 Fix: Nutze count-Felder (sound.get("alliterations_count"))
            # für echte Werte, nicht len() der getruncateten Liste.
            # Fallback auf len() für Abwärtskompatibilität mit ungepatchtem
            # text_analyzer.py.
            "alliterationen": sound.get("alliterations_count", len(sound.get("alliterations", []))) if sound else "—",
            "assonanzen": sound.get("assonances_count", len(sound.get("assonances", []))) if sound else "—",
            "binnenreime": sound.get("internal_rhymes_count", len(sound.get("internal_rhymes", []))) if sound else "—",  # v57.8.4
            # v59.9.2 Fix: Nutze echoes_count-Feld (analog zu alliterations_count).
            # Fallback auf len() der Liste für Abwärtskompatibilität.
            "vokalechos": (vd.get("vowel_echoes", {}).get("echoes_count", len(vd.get("vowel_echoes", {}).get("echoes", []))) if (vd and isinstance(vd.get("vowel_echoes"), dict)) else (len(vd.get("vowel_echoes", [])) if (vd and isinstance(vd.get("vowel_echoes"), list)) else "—")),  # v57.8.4
        }

    logger.info(f"Kennzahlen aufbereitet: {len(individual_stats)} Quellen")

    if len(valid_results) >= 2:
        # v57.8.4: Klang-Tabelle für Synthese generieren (analog zu comparison_table_text)
        klang_table_text = _format_klang_table_for_synthese(individual_stats)

        synthese_prompt = _build_globale_synthese_prompt(
            etappen_results=valid_results,
            comparison_table_text=comparison_table_text,
            user_question=user_question,
            praegnanz_sentences=praegnanz_sentences,
            individual_stats=individual_stats,
            dominant_labels=dominant_labels,
            grundoperation_labels=grundoperation_labels,
            modus_labels=modus_labels,
            author_map=author_map,  # v57.7.6: Autoren-Zuordnung
            klang_table_text=klang_table_text,  # v57.8.4: Klang-Beweisführung
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
    # QUELLEN-GEGENPOSITION (v59.10.0 Schritt 2 — Falsifizierungs-Architektur)
    # v59.10.3: Schlafen gelegt (Default: False). Claude-Beratung 2026-06-28:
    # Quellen-Gegenposition produziert Spitzfindigkeiten. Meta-Gegenposition
    # (Schritt 3) ist die aktive Falsifizierungsinstanz. Code bleibt fuer
    # spaeteren Umbau als Anomalie-Detektion.
    # ==========================================================================
    quellen_gegenposition = ""
    if enable_quellen_gegenposition and len(valid_results) >= 2:
        if progress_callback:
            progress_callback("Quellen-Gegenposition: Falsifizierende Analyse...")

        logger.info("🔄 Quellen-Gegenposition (Falsifizierung)")
        try:
            gegenposition_prompt = _build_quellen_gegenposition_prompt(
                globale_synthese=globale_synthese,
                user_question=user_question,
                valid_results=valid_results,
                individual_stats=individual_stats,
                author_map=author_map,
                comparison_table_text=comparison_table_text,
            )
            quellen_gegenposition = llm_call(
                prompt=gegenposition_prompt,
                task="synthesis",
                system_instruction=_QUELLEN_GEGENPOSITION_SYSTEM,
                temperature=0.3,
                max_tokens=MAX_TOKENS_STILISIERUNG,
                domain="stilisierung",
            )
            logger.info("✅ Quellen-Gegenposition abgeschlossen")
        except Exception as e:
            logger.error(f"❌ Quellen-Gegenposition fehlgeschlagen: {e}")
            quellen_gegenposition = f"FEHLER bei Quellen-Gegenposition: {e}"
    else:
        if not enable_quellen_gegenposition:
            logger.info("💤 Quellen-Gegenposition schlafen gelegt (Default: False)")
        quellen_gegenposition = ""

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
        "quellen_gegenposition": quellen_gegenposition,
        "metadata": metadata,
        # v57.8.0 / Schnitt 1: Autoren-Metadaten für Sidecar-Einbettung.
        # WICHTIG: Hier wird author_map_full (INKL. None-Werte) zurückgegeben,
        # damit das Sidecar die "unresolved"-Quellen dokumentiert. Die
        # Etappe-2/3-Logik oben bekommt stattdessen das gefilterte author_map
        # (nur resolved Autoren), um TypeError in ", ".join(other_parts) zu vermeiden.
        "author_map": author_map_full,
        "author_resolution_chain": author_resolution_chain,
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


    # ── Deepening-Interface: Strukturierte Profile pro Quelle ──
    # Kompatibel mit stil_profiles-Format der RAG-Distillation
    profiles = {}
    for label, etappe_text in result.get("etappen_2_3", {}).items():
        # Extrahiere MODUS, DOMINANTE, GRUNDOPERATION aus dem Etappe-Text
        modus_match = re.search(r'MODUS:\s*(.+?)(?:\n\n|\n[A-ZÄÖÜ]|$)', etappe_text, re.DOTALL)
        dom_match = re.search(r'(?:DIE )?DOMINANTE:\s*(.+?)(?:\n\n|\n[A-ZÄÖÜ]|$)', etappe_text, re.DOTALL)
        op_match = re.search(r'(?:DIE )?GRUNDOPERATION:\s*(.+?)(?:\n\n|\n[A-ZÄÖÜ]|$)', etappe_text, re.DOTALL)
        
        profiles[label] = {
            "modus": modus_match.group(1).strip() if modus_match else "(Kein Modus)",
            "dominante": dom_match.group(1).strip() if dom_match else "(Keine Dominante)",
            "grundoperation": op_match.group(1).strip() if op_match else "(Keine Grundoperation)",
            "volltext_analyse": etappe_text,
        }
    
    result["profiles"] = profiles

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

    # v57.8.4: Klang-Vergleichstabelle (numerisch, für Beweisführung in Synthese)
    # Analog zu Enjambement-Tabelle oben, aber fokussiert auf Klangfiguren
    lines.append("### Klang-Vergleichstabelle (v57.8.4)")
    lines.append("")
    individual_stats = result.get("metadata", {}).get("individual_stats", {})
    # Fallback: falls individual_stats nicht in metadata, versuche direkt aus etappe1
    if not individual_stats:
        individual_stats = {}
        for label, stats in result.get("etappe1", {}).get("individual", {}).items():
            if "error" in stats:
                continue
            vd = stats.get("verse_detail", {})
            sound = vd.get("sound_patterns", {}) if vd else {}
            echoes_data = vd.get("vowel_echoes", {}) if vd else None
            echoes_list = echoes_data.get("echoes", []) if isinstance(echoes_data, dict) else (echoes_data if isinstance(echoes_data, list) else [])
            individual_stats[label] = {
                "alliterationen": len(sound.get("alliterations", [])) if sound else "—",
                "assonanzen": len(sound.get("assonances", [])) if sound else "—",
                "binnenreime": len(sound.get("internal_rhymes", [])) if sound else "—",
                "vokalechos": len(echoes_list) if echoes_list else "—",
                "reim_typ": (vd.get("rhyme", {}).get("rhyme_type", "—") if vd else "—"),
                "enjambement": (vd.get("enjambement", {}).get("count", "—") if vd else "—"),
            }
    if individual_stats:
        klang_headers = ["Quelle", "Alliterationen", "Assonanzen", "Binnenreime", "Vokal-Echos", "Reim", "Enjamb."]
        lines.append("| " + " | ".join(klang_headers) + " |")
        lines.append("| " + " | ".join(["---"] * len(klang_headers)) + " |")
        for label, s in individual_stats.items():
            values = [
                str(label),
                str(s.get("alliterationen", "—")),
                str(s.get("assonanzen", "—")),
                str(s.get("binnenreime", "—")),
                str(s.get("vokalechos", "—")),
                str(s.get("reim_typ", "—")),
                str(s.get("enjambement", "—")),
            ]
            lines.append("| " + " | ".join(values) + " |")
    else:
        lines.append("(Keine Klang-Kennzahlen verfügbar)")
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

    # Quellen-Gegenposition (v59.10.0 Schritt 2 — nur wenn aktiviert)
    qp = result.get("quellen_gegenposition", "")
    if qp:
        lines.append("---")
        lines.append("")
        lines.append("## Quellen-Gegenposition (Falsifizierung)")
        lines.append("")
        lines.append(qp)
        lines.append("")

    return "\n".join(lines)
