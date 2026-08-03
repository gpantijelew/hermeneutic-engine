"""
modules/echo_guard.py — Echo-Detection für IFS & Anker-Antworten (v615)
======================================================================

ZWECK:
    Code-seitige Prüfung, ob eine generierte LLM-Antwort zu stark auf den
    Wörtern der letzten User-Nachricht basiert. Bei Überschreitung eines
    Schwellenwerts wird die Antwort als "Echo" klassifiziert.

    Claude's Brief (03.08.2026, Punkt 1):
        "Eine Wortüberlappungs-Prüfung zwischen der letzten User-Nachricht
         und der generierten Antwort — Anteil gemeinsamer inhaltstragender
         Wörter (Funktionswörter rausgerechnet). Bei Überschreitung eines
         Schwellenwerts (Vorschlag: 60%) wird die Antwort nicht ausgeliefert,
         sondern einmal automatisch neu generiert, mit einer scharfen
         Zusatzanweisung nur für diesen einen Retry."

METRIK:
    Anteil der inhaltstragenden Wörter der ANTWORT, die auch in der
    USER-NACHRICHT vorkommen.

    0.0 = keine Überlappung (kein Echo)
    1.0 = alle inhaltstragenden Wörter der Antwort stammen aus der
          User-Nachricht (vollständiges Echo)

LIMITATIONEN:
    Diese Metrik ist lexikalisch, nicht semantisch. Sie erfasst wörtliche
    oder fast-wörtliche Echos, aber keine semantischen Echos (Paraphrasen
    mit komplett anderen Wörtern). Das ist ein akzeptabler Tradeoff:
    - Semantische Echo-Erkennung würde ein zweites LLM erfordern (teuer,
      langsam, unzuverlässig).
    - Lexikalische Echo-Erkennung ist deterministisch, schnell, testbar.
    - Claude's Testbefund (v613 Turn 5/21, v614 Turn 6→8) zeigte wörtliche
      Echos — das ist genau das, was diese Metrik erfasst.

VERWENDUNG:
    from modules.echo_guard import is_echo, compute_echo_overlap, ECHO_RETRY_INSTRUCTION

    score = compute_echo_overlap(user_msg, response)  # 0.0 - 1.0
    if is_echo(user_msg, response):
        # Retry mit ECHO_RETRY_INSTRUCTION an sys_instr angehängt
        ...

SELF-TEST:
    python -m modules.echo_guard
"""

import re
import logging
from typing import Set, List

logger = logging.getLogger(__name__)


# =============================================================================
# KONSTANTEN
# =============================================================================

# Schwellwert: 60% der inhaltstragenden Wörter der Antwort müssen in der
# User-Nachricht vorkommen, um als Echo zu gelten.
# Claude's Vorschlag (Brief 03.08.2026): 60%.
ECHO_THRESHOLD = 0.6

# Mindestlänge für inhaltstragende Wörter (kürzer = wahrscheinlich Füllwort)
MIN_CONTENT_WORD_LENGTH = 3

# Zusatzinstruction für den Retry-Call (wird an sys_instr angehängt).
# Claude's Formulierung (Brief 03.08.2026).
ECHO_RETRY_INSTRUCTION = (
    "\n\nWICHTIG — DEINE LETZTE ANTWORT WAR REINES ECHO: "
    "Du hast die Worte der Person fast identisch wiederholt. "
    "Komplett neu formulieren. Andere Wörter, gleicher Kern. "
    "Kein einziges Verb, kein Nomen der Person wörtlich übernehmen."
)


# =============================================================================
# DEUTSCHE STOPPWORD-LISTE (Funktionswörter)
# =============================================================================
# Diese Wörter werden bei der Echo-Berechnung NICHT gezählt — sie sind
# grammatisch notwendig, aber nicht inhaltstragend.
# Liste ist bewusst konservativ: Lieber ein Wort zu viel als zu wenig als
# "inhaltstragend" klassifizieren.
# =============================================================================

_STOPWORDS: Set[str] = {
    # Artikel
    "der", "die", "das", "ein", "eine", "einer", "eines", "einem", "einen",
    # Pronomen
    "ich", "du", "er", "sie", "es", "wir", "ihr", "mich", "dich", "sich",
    "mir", "dir", "uns", "euch", "mein", "dein", "sein", "unser", "euer",
    "dieser", "diese", "dieses", "jener", "jene", "jenes", "welcher", "welche",
    "man", "einer", "irgend",
    # Präpositionen
    "in", "auf", "mit", "bei", "zu", "von", "für", "an", "aus", "durch", "um",
    "über", "unter", "vor", "nach", "neben", "zwischen", "hinter", "ohne",
    "statt", "trotz", "wegen", "während", "innerhalb", "außerhalb",
    # Konjunktionen
    "und", "oder", "aber", "sondern", "weil", "dass", "wenn", "als", "ob",
    "damit", "bevor", "nachdem", "seit", "bis", "sobald", "solange",
    # Hilfsverben
    "bin", "bist", "ist", "sind", "war", "waren", "werde", "wirst", "wird",
    "werden", "habe", "hast", "hat", "haben", "hatte", "hatten",
    # Partikel
    "nicht", "auch", "noch", "schon", "nur", "sehr", "mehr", "etwas",
    "alles", "nichts", "wieder", "immer", "vielleicht", "ja", "nein", "doch",
    "halt", "eben", "mal",
    # Fragewörter
    "was", "wer", "wo", "wann", "warum", "wie", "woher", "wohin",
    # Konjunktionaladverbien
    "deshalb", "trotzdem", "allerdings", "jedoch", "denn", "nämlich",
    # Verbkürzungen / häufige Verben (inhaltlich leer in Kontext der Echo-Prüfung)
    "geht", "gehe", "gehen", "mache", "machst", "macht", "machen",
    "will", "willst", "wollen", "möchte", "möchten", "soll", "sollen",
    "kann", "kannst", "können", "muss", "musst", "müssen", "darf", "dürfen",
    "brauche", "brauchst", "brauchen",
    # Häufige Füllwörter
    "so", "da", "hier", "dort", "drin", "rein", "raus", "rum",
    "echt", "wirklich", "ganz", "total", "voll",
    # Bindewörter mit Bezug
    "diese", "dieses", "jene", "jenes", "welche", "welches",
}


# =============================================================================
# TOKENIZER
# =============================================================================

# Regex für Wörter: Buchstaben (inkl. Umlaute), mindestlänge 1
_TOKEN_RE = re.compile(r"[a-zA-ZäöüÄÖÜß]+")


def _tokenize(text: str) -> List[str]:
    """
    Tokenisiert Text in lowercase Wörter.

    Args:
        text: Eingabetext.

    Returns:
        Liste von lowercase Wörtern (ohne Satzzeichen).
    """
    if not text:
        return []
    return [w.lower() for w in _TOKEN_RE.findall(text)]


def _content_words(tokens: List[str]) -> Set[str]:
    """
    Filtert Funktionswörter (Stoppwörter) heraus.

    Args:
        tokens: Liste von lowercase Wörtern.

    Returns:
        Set der inhaltstragenden Wörter (Stoppwörter entfernt,
        Wörter kürzer als MIN_CONTENT_WORD_LENGTH entfernt).
    """
    return {
        t for t in tokens
        if t not in _STOPWORDS and len(t) >= MIN_CONTENT_WORD_LENGTH
    }


# =============================================================================
# ÖFFENTLICHE API
# =============================================================================

def compute_echo_overlap(user_message: str, model_response: str) -> float:
    """
    Berechnet die Wortüberlappung zwischen User-Nachricht und Model-Antwort.

    Metrik:
        Anteil der inhaltstragenden Wörter der ANTWORT, die auch in der
        USER-NACHRICHT vorkommen.

    Beispiele:
        User: "Die Gedanken lassen mich nicht in Ruhe."
        Resp: "Die Gedanken lassen dich nicht in Ruhe."
        → Inhaltstragend Antwort: {"gedanken", "lassen", "ruhe"}
        → Inhaltstragend User: {"gedanken", "lassen", "ruhe"}
        → Overlap: 3/3 = 1.0 (Echo)

        User: "Ich bin verzweifelt."
        Resp: "Es klingt, als wäre dieser Tag schwer für dich."
        → Inhaltstragend Antwort: {"klingt", "tag", "schwer"}
        → Inhaltstragend User: {"verzweifelt"}
        → Overlap: 0/3 = 0.0 (kein Echo)

    Args:
        user_message: Die letzte User-Nachricht.
        model_response: Die generierte Antwort des LLM.

    Returns:
        Überlappungs-Score 0.0 - 1.0.
        0.0 bei leerem Input/Output.
    """
    if not model_response or not user_message:
        return 0.0

    user_tokens = _tokenize(user_message)
    response_tokens = _tokenize(model_response)

    user_content = _content_words(user_tokens)
    response_content = _content_words(response_tokens)

    if not response_content:
        # Antwort hat keine inhaltstragenden Wörter (z.B. nur "Ja.")
        # → kein Echo im Wortsinn, aber auch keine echte Antwort.
        # Wir geben 0.0 zurück, damit kein Retry ausgelöst wird.
        return 0.0

    overlap = response_content & user_content
    return len(overlap) / len(response_content)


def is_echo(
    user_message: str,
    model_response: str,
    threshold: float = ECHO_THRESHOLD,
) -> bool:
    """
    Prüft, ob eine Antwort als Echo der User-Nachricht zu klassifizieren ist.

    Args:
        user_message: Die letzte User-Nachricht.
        model_response: Die generierte Antwort.
        threshold: Schwellwert ab dem ein Echo angenommen wird (Default 0.6).

    Returns:
        True, wenn die Wortüberlappung >= threshold.
    """
    score = compute_echo_overlap(user_message, model_response)
    if score >= threshold:
        logger.info(
            f"🔊 ECHO erkannt (Overlap={score:.2f}, Threshold={threshold:.2f}). "
            f"User-Input-Anfang: '{user_message[:80]}...'. "
            f"Model-Output-Anfang: '{model_response[:80]}...'."
        )
        return True
    return False


# =============================================================================
# SELF-TEST
# =============================================================================

if __name__ == "__main__":
    print("=== Self-Test: echo_guard.py ===\n")

    test_cases = [
        # (User, Response, Expected Echo, Description)
        (
            "Die Gedanken lassen mich nicht in Ruhe.",
            "Die Gedanken lassen dich nicht in Ruhe.",
            True,
            "Wörtliches Echo (v613-Test Turn 5 Muster)",
        ),
        (
            "Ich habe zusätzlich noch den Magnesium/Melatonin Stick genommen. Ich möchte nicht mehr schlecht schlafen.",
            "Du hast zusätzlich noch den Magnesium/Melatonin Stick genommen. Du willst einfach raus aus diesem Hamsterrad und nicht mehr schlecht schlafen.",
            True,
            "Echo mit Pronomen-Tausch (v613 Turn 2 Muster)",
        ),
        (
            "Ich bin verzweifelt und alles wird zu viel.",
            "Es klingt, als wäre dieser Tag wirklich schwer für dich gewesen.",
            False,
            "Legitime Antwort mit eigenen Worten",
        ),
        (
            "Ich will nicht mehr leben.",
            "Was du beschreibst, braucht echte menschliche Begleitung. Telefonseelsorge: 0800 111 0 111.",
            False,
            "Krisen-Antwort (kein Echo)",
        ),
        (
            "Ich bin unruhig.",
            "Du sagst, du bist unruhig. Wie geht es dir gerade?",
            False,
            "Echo mit legitimer Beziehungsfrage (Wortüberlappung niedrig)",
        ),
        (
            "Die Lestrigonen lassen mich nicht in Ruhe, sobald ich allein bin.",
            "Diese Lestrigonen, wie du sie nennst, lassen dich nicht in Ruhe, sobald du allein bist.",
            True,
            "Echo mit hochspezifischem Begriff (Lestrigonen)",
        ),
        (
            "Die Lestrigonen lassen mich nicht in Ruhe, sobald ich allein bin.",
            "Sie drängen sich rein, sobald es still wird. Andere Wörter, aber denselben Kern.",
            False,
            "Kein Echo trotz gleichem Inhalt (v614 YAML-Beispiel)",
        ),
        (
            "",
            "Was auch immer.",
            False,
            "Leerer User-Input → kein Echo",
        ),
        (
            "Hallo",
            "",
            False,
            "Leere Antwort → kein Echo",
        ),
        (
            "Ja.",
            "Gerne.",
            False,
            "Sehr kurze Antwort ohne inhaltstragende Wörter",
        ),
    ]

    passed = 0
    failed = 0
    for user, response, expected, desc in test_cases:
        score = compute_echo_overlap(user, response)
        result = is_echo(user, response)
        ok = result == expected
        status = "✅" if ok else "❌"
        if ok:
            passed += 1
        else:
            failed += 1
        print(f"{status} Overlap={score:.2f}, is_echo={result} (expected {expected})")
        print(f"   {desc}")
        print(f"   User:  '{user[:80]}'")
        print(f"   Resp:  '{response[:80]}'")
        print()

    print(f"=== Test abgeschlossen: {passed} bestanden, {failed} fehlgeschlagen ===")
    if failed > 0:
        import sys
        sys.exit(1)
