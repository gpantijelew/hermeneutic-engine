"""
modules/emergency_interceptor.py — Krisen-Früherkennung für IFS & Trost-Modus.

ZWECK:
    Code-seitiger Pattern-Matcher auf User-Input (vor LLM-Call) und auf
    Model-Output (nach LLM-Call). Greift UNABHÄNGIG vom aktiven Modus —
    egal ob IFS_CONTROL, IFS_FIGHT, IFS_FEAR oder CO_REGULATION (Trost):
    Bei Erkennung einer akuten Krise wird die Krisen-Routine ausgelöst
    und der LLM-Call nicht ausgeführt (bzw. dessen Output verworfen).

WARUM CODE-EBENE, NICHT NUR PROMPT-EBENE:
    Das YAML-NOTFALL-PROTOKOLL ist eine Instruktion an das LLM. Aber das
    LLM kann die Rolle verlassen, kann die Instruktion ignorieren, kann
    in einer Krise itself unzuverlässig werden. Der Code-Interceptor ist
    die harte Sicherheitsschicht, die das LLM nicht umgehen kann.

ARCHITEKTUR:
    Zwei Checks, beide Pattern-basiert:
    - check_user_input(text): Vor dem LLM-Call. Bei Match → Krisen-Route.
    - check_model_output(text): Nach dem LLM-Call. Bei Match → Output
      verwerfen, Krisen-Route auslösen, in Log schreiben (Modell hat
      Krise erkannt vs. Modell hat Krise provoziert).

    Pattern-Sets sind absichtlich konservativ (Precision vor Recall):
    Ein False-Positive unterbricht eine legitime Reflexion, ein
    False-Negative lässt eine Krise durch. Beide sind schlimm — aber
    ein False-Positive ist weniger schlimm als ein False-Negative.
    Daher: mehrere Signale, gewichtetes Scoring statt einfachem Match.

VERSION: v60.2 — Eingeführt mit dem Trost-Modus-Bauauftrag (28.07.2026).
"""

import logging
import re
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


# =============================================================================
# KRISIS-SIGNAL-KATALOG
# =============================================================================
# Jedes Pattern hat ein Gewicht (1-3). Ab Score >= 3 wird ausgelöst.
# Hohe Gewichte (3): explizite Suizid-/SIV-Äußerungen.
# Mittlere Gewichte (2): Andeutungen, Phantasien, konkrete Methoden.
# Niedrige Gewichte (1): distalere Signale — nur in Kombination relevant.
# =============================================================================

_PATTERNS: list[tuple[int, str, re.Pattern]] = [
    # =====================================================================
    # GEWICHT 3: explizit — einzelnes Signal reicht für Trigger
    # =====================================================================

    # Suizid / Selbstmord (Substantiv, alle Konjugationen)
    (3, "suizid",
     re.compile(r"suizid", re.IGNORECASE)),
    (3, "selbstmord",
     re.compile(r"selbstmord", re.IGNORECASE)),
    (3, "lebensmuede",
     re.compile(r"lebensm[üu]d", re.IGNORECASE)),

    # Sich / mir / mich etwas antun (mit Optionalwörtern dazwischen)
    (3, "sich_etwas_antun",
     re.compile(r"(?:sich|mir|mich)\s+(?:\w+\s+){0,3}(?:etwas|das|nichts|alles)\s+antun",
                re.IGNORECASE)),

    # "nicht mehr leben" — mit optionalen Wörtern davor/wieder
    (3, "nicht_mehr_leben",
     re.compile(r"nicht\s+mehr\s+leben", re.IGNORECASE)),

    # "tot sein wollen" / "will tot sein" / "einfach tot sein" etc.
    (3, "tot_sein_wollen",
     re.compile(r"(?:will|wollte|möchte|möchte)\s+(?:\w+\s+){0,3}(?:tot|fort|weg)\s+(?:sein|werden)",
                re.IGNORECASE)),
    (3, "tot_sein_aussage",
     re.compile(r"(?:einfach\s+)?(?:tot|fort)\s+sein", re.IGNORECASE)),

    # "sich umbringen" / "mich umbringen" / "bringe mich um" (alle Konjugierungen)
    (3, "umbringen",
     re.compile(r"(?:sich|mir|mich)\s+(?:\w+\s+){0,2}umbring", re.IGNORECASE)),
    (3, "umbringen_konjugiert",
     re.compile(r"bring(?:e|st|en|t)?\s+(?:mich|sich|dich|uns)\s+um", re.IGNORECASE)),

    # Telefonseelsorge (z.B. im Output des LLM)
    (3, "telefonseelsorge_explicit",
     re.compile(r"telefonseelsorge|0800\s*111\s*0\s*111", re.IGNORECASE)),

    # =====================================================================
    # GEWICHT 2: Andeutungen — mehrere Signale nötig für Trigger
    # =====================================================================

    # "Schluss machen" im Kontext Lebensende / Beziehung
    (2, "schluss_machen",
     re.compile(r"schluss\s+mach(?:en|t)", re.IGNORECASE)),

    # "keinen Sinn mehr machen"
    (2, "keinen_sinn_mehr",
     re.compile(r"kein(?:en|e|er)?\s+sinn\s+(?:mehr\s+)?macht?", re.IGNORECASE)),

    # "Leben aufgeben"
    (2, "aufgeben_leben",
     re.compile(r"aufgeb(?:en|t)\s+(?:das\s+)?leben", re.IGNORECASE)),

    # "Schmerzen zufügen" (selbst)
    (2, "schmerzen_zufuegen",
     re.compile(r"schmerz(?:en)?\s+(?:selbst\s+)?zufüg(?:en|t)", re.IGNORECASE)),

    # "sich verletzen" / "mich verletzen" (auch konjugiert: "verletzt", "verletze")
    # Bis zu 4 Wörter zwischen Pronomen und Verb zulassen.
    # Variante mit "selbst" → Gewicht 3 (intentional, eindeutig SIV)
    # Variante ohne "selbst" → Gewicht 2 (kann Unfall sein)
    (3, "sich_selbst_verletzen",
     re.compile(r"(?:sich|mir|mich)\s+(?:\w+\s+){0,4}selbst\s+verletz(?:en|t|e)",
                re.IGNORECASE)),
    (2, "sich_verletzen",
     re.compile(r"(?:sich|mir|mich)\s+(?:\w+\s+){0,4}verletz(?:en|t|e)",
                re.IGNORECASE)),

    # "ritzen" — im deutschen Kontext fast immer SIV-Andeutung.
    # Gewicht 3, weil das Wort im Alltagssprachgebrauch bei Erwachsenen
    # praktisch nie in nicht-SIV-Kontext vorkommt (anders als "Schneiden",
    # das auch beim Kochen passiert).
    (3, "ritzen",
     re.compile(r"ritz(?:en|t|e)", re.IGNORECASE)),

    # "nicht mehr weiter wissen" / "nicht mehr weiter"
    (2, "nicht_mehr_weiter_wissen",
     re.compile(r"nicht\s+mehr\s+weiter(?:\s+wissen)?", re.IGNORECASE)),

    # "es wäre besser wenn ich gehe" / "besser ich wäre fort"
    (2, "besseres_gehen",
     re.compile(r"es\s+(?:w[äa]re|ist)\s+(?:besser|besseres)\s+"
                r"(?:wenn\s+)?ich\s+(?:gehe|fortgehe|fortbin|verschwind)",
                re.IGNORECASE)),

    # "ich will weg" / "einfach weg" — Gewicht 3 wenn "für immer" oder
    # ähnliche Verstärker dabei sind, sonst Gewicht 2.
    (3, "fuer_immer_weg_wollen",
     re.compile(r"(?:will|möchte|möchte)\s+(?:\w+\s+){0,3}(?:weg|fort).{0,30}(?:für\s+immer|für\s+immer|endgültig)",
                re.IGNORECASE)),
    (3, "fuer_immer_weg_wollen_v2",
     re.compile(r"(?:weg|fort).{0,30}(?:für\s+immer|für\s+immer|endgültig)",
                re.IGNORECASE)),
    (2, "einfach_weg_wollen",
     re.compile(r"(?:einfach\s+)?will\s+(?:einfach\s+)?(?:weg|fort)",
                re.IGNORECASE)),

    # =====================================================================
    # GEWICHT 1: distaler — nur in Kombination relevant
    # =====================================================================

    (1, "tod_gedanke",
     re.compile(r"(?:tod|tot)\s+(?:gedanke|gedanken|sehnsucht)", re.IGNORECASE)),
    (1, "verzweifelt",
     re.compile(r"verzweifelt", re.IGNORECASE)),
    (1, "hoffnungslos",
     re.compile(r"hoffnungslos", re.IGNORECASE)),
    (1, "aushalten_nicht_mehr",
     re.compile(r"nicht\s+mehr\s+aushalt(?:en|en_k[öo]nnen|en_kann)",
                re.IGNORECASE)),
    (1, "halte_nicht_aus",
     re.compile(r"halt(?:e|en)\s+(?:\w+\s+){0,3}nicht\s+(?:mehr\s+)?aus",
                re.IGNORECASE)),
    (1, "alles_sinnlos",
     re.compile(r"alles\s+ist\s+sinnlos|sinnlos", re.IGNORECASE)),
]

# Mindest-Score für Trigger — mode-abhängig (v613)
def get_crisis_threshold(mode: str) -> int:
    """
    Gibt den Krisen-Schwellwert für den jeweiligen Modus zurück.

    v613 — Mode-abhängige Sensitivität (Claude's direkter Auftrag):
        IFS_FIGHT   >= 2  (Fight ist hochaffektiv — niedrigere Schwelle)
        IFS_CONTROL >= 3  (Default-Baseline, konservativ)
        IFS_FEAR    >= 2  (Fear kann destruktiv eskalieren)
        NAMASTE     >= 2  (Anker-Modus ist niedrigschwellig — jede Andeutung zaehlt)

    Default bei unbekanntem oder fehlendem Mode: 3 (konservativ).
    """
    if not mode:
        return 3
    return {
        "IFS_FIGHT": 2,
        "IFS_CONTROL": 3,
        "IFS_FEAR": 2,
        "NAMASTE": 2,
    }.get(mode.upper(), 3)


# Legacy-Konstante für Code, der noch THRESHOLD direkt referenziert.
# Entspricht dem Default-Modus IFS_CONTROL.
THRESHOLD = 3


# =============================================================================
# KRISE-ERKENNUNGS-ERGEBNIS
# =============================================================================

@dataclass(frozen=True)
class CrisisCheck:
    """Ergebnis einer Krisen-Prüfung."""
    is_crisis: bool
    score: int
    matched_patterns: list[tuple[str, int]]  # [(name, weight), ...]

    def __bool__(self) -> bool:
        """`if CrisisCheck:` ist True bei is_crisis."""
        return self.is_crisis


# =============================================================================
# ÖFFENTLICHE API
# =============================================================================

def check_user_input(text: str, mode: str = "IFS_CONTROL") -> CrisisCheck:
    """
    Prüft User-Eingabe VOR dem LLM-Call.

    Warum User-Input prüfen?
    - Wenn der User bereits eine akute Krise äußert, darf das LLM
      nicht in der Rolle bleiben (z.B. als Kampf-Stimme, die die
      Wut verstärkt, oder als Trost-Stimme, die validiert).
    - Statt des LLM-Calls wird direkt die Krisen-Routine ausgelöst.
    - Das spart Token und verhindert potenziell schädliche KI-Antworten.

    Returns:
        CrisisCheck mit is_crisis=True, wenn Score >= THRESHOLD.
    """
    if not text or not text.strip():
        return CrisisCheck(is_crisis=False, score=0, matched_patterns=[])

    matched: list[tuple[str, int]] = []
    score = 0
    lowered = text.lower()

    for weight, name, pattern in _PATTERNS:
        if pattern.search(lowered):
            matched.append((name, weight))
            score += weight
            if score >= get_crisis_threshold(mode):
                # Früher Abbruch: Krise erkannt, kein Bedarf weiterzumatchen.
                break

    is_crisis = score >= get_crisis_threshold(mode)

    if is_crisis:
        logger.warning(
            f"🛑 KRISE in User-Input erkannt (Score={score}): "
            f"Patterns={matched}. User-Input-Anfang: "
            f"'{text[:80]}...'"
        )

    return CrisisCheck(is_crisis=is_crisis, score=score,
                       matched_patterns=matched)


def check_model_output(text: str, mode: str = "IFS_CONTROL") -> CrisisCheck:
    """
    Prüft Model-Output NACH dem LLM-Call.

    Warum Model-Output prüfen?
    - Das LLM kann in der Rolle bleiben (z.B. als Kampf-Stimme) und
      selbst krisenhafte Inhalte produzieren — entweder weil der User
      die Stimme dort hingetrieben hat, oder weil das Modell die Rolle
      übertrieben hat.
    - Auch Trost-Antworten können (selten) fehlerhaft validierend sein
      ("Du darfst loslassen, wenn du es nicht mehr aushältst" — was
      im Kontext einer Suizid-Andeutung falsch ist).
    - Bei Match: Output verwerfen, Krisen-Routine auslösen.

    Hinweis: Das LLM darf legitimerweise Krisen-Themen erwähnen, wenn
    es bereits im NOTFALL-PROTOKOLL-Modus ist (Rollenverlassen). In
    diesem Fall muss der Output dennoch durchgelassen werden. Das wird
    über das Flag `was_emergency_response` im aufrufenden Code gelöst,
    nicht hier — diese Funktion prüft nur Muster.
    """
    if not text or not text.strip():
        return CrisisCheck(is_crisis=False, score=0, matched_patterns=[])

    matched: list[tuple[str, int]] = []
    score = 0
    lowered = text.lower()

    for weight, name, pattern in _PATTERNS:
        if pattern.search(lowered):
            matched.append((name, weight))
            score += weight

    is_crisis = score >= get_crisis_threshold(mode)

    if is_crisis:
        logger.warning(
            f"🛑 KRISE in Model-Output erkannt (Score={score}): "
            f"Patterns={matched}. Model-Output-Anfang: "
            f"'{text[:80]}...'"
        )

    return CrisisCheck(is_crisis=is_crisis, score=score,
                       matched_patterns=matched)


# =============================================================================
# KRISEN-ROUTINE (Output, das angezeigt wird, wenn Krise erkannt)
# =============================================================================

EMERGENCY_RESPONSE_TEXT = (
    "🛑 **Pause.** Was du beschreibst, braucht echte menschliche Begleitung.\n\n"
    "**Telefonseelsorge: 0800 111 0 111** — kostenlos, rund um die Uhr, anonym.\n\n"
    "Das Gespräch hier ist jetzt beendet. Du kannst das Protokoll herunterladen "
    "und bei Bedarf eine neue Session beginnen.\n\n"
    "Wenn du in akuter Gefahr bist: **112** (Notruf)."
)


def get_emergency_response() -> str:
    """Gibt den Krisen-Aussteige-Text zurück."""
    return EMERGENCY_RESPONSE_TEXT


# =============================================================================
# SELF-TEST (kann mit `python -m modules.emergency_interceptor` gerufen werden)
# =============================================================================

if __name__ == "__main__":
    print("=== Self-Test: Emergency Interceptor ===\n")

    # Negativ-Beispiele (sollten NICHT triggern)
    neg_cases = [
        "Ich hatte einen furchtbaren Tag und fühle mich erschöpft.",
        "Ich bin wütend auf meinen Kollegen und möchte laut werden.",
        "Ich habe Angst vor der nächsten Stunde.",
        "Ich fühle mich überfordert und möchte mich verstecken.",
        "Ich bin traurig und möchte weinen.",
        "Mir fällt keine Lösung ein.",
    ]
    print("--- Negativ-Fälle (sollen NICHT triggern) ---")
    for t in neg_cases:
        r = check_user_input(t)
        flag = "🛑" if r.is_crisis else "✅"
        print(f"{flag} [{r.score}] {t[:60]}")

    # Positiv-Beispiele (SOLLEN triggern)
    print("\n--- Positiv-Fälle (sollen triggern) ---")
    pos_cases = [
        "Ich will nicht mehr leben.",
        "Ich habe Suizidgedanken und weiß nicht mehr weiter.",
        "Ich möchte mir etwas antun.",
        "Es macht keinen Sinn mehr, ich bin lebensmüde.",
        "Ich will mich ritzen, das hilft manchmal.",
        "Ich habe mich heute Morgen selbst verletzen wollen.",
    ]
    for t in pos_cases:
        r = check_user_input(t)
        flag = "🛑" if r.is_crisis else "✅"
        print(f"{flag} [{r.score}] {t[:60]}")

    # Edge-Case: distale Signale, die einzeln nicht triggern
    print("\n--- Edge-Cases (Score 1-2, einzelne Signale) ---")
    edge_cases = [
        "Ich bin verzweifelt.",                          # Score 1
        "Ich halte das nicht mehr aus.",                 # Score 1
        "Es ist alles so hoffnungslos.",                 # Score 1
    ]
    for t in edge_cases:
        r = check_user_input(t)
        flag = "🛑" if r.is_crisis else "✅"
        print(f"{flag} [{r.score}] {t[:60]}")

    print("\n=== Test abgeschlossen ===")
