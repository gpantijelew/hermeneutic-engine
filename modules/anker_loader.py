"""
modules/anker_loader.py — Lädt die persönliche Anker-Liste des Users.

v60.3 — Begleitmodul zum ANKER-Modus (ersetzt CO_REGULATION).

Die Anker-Liste ist eine einfache Markdown-Datei mit zwei Abschnitten:
  ## Ablenkung / Aktivierung — Dinge, die eine Handlung verlangen
  ## Downregulation — Dinge, die keine Handlung verlangen

Der User pflegt diese Liste selbst. Das LLM bekommt sie als Kontext
und spiegelt daraus Einträge zurück — es erfindet keine eigenen Ratschläge.

Pfade (Priorität: höchste zuerst):
  1. $HRE_ANKER_LISTE (Umgebungsvariable, falls gesetzt)
  2. ./resonanzraum/anker_liste.md (relativ zum Arbeitsverzeichnis)
  3. ./anker_liste.md (Fallback im Arbeitsverzeichnis)
  4. Modul-interne Vorlage (wird beim ersten Aufruf erzeugt)

Bei fehlender Datei: Module schreibt Vorlage an Pfad (2) und lädt sie.
So ist sichergestellt, dass der User immer eine Liste zum Bearbeiten hat.
"""

import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# =============================================================================
# KONSTANTEN
# =============================================================================

# Standard-Dateiname (relativ zum Arbeitsverzeichnis)
DEFAULT_ANKER_PATH = Path("resonanzraum") / "anker_liste.md"

# Vorlage, die beim ersten Aufruf erzeugt wird, falls die Datei fehlt.
# Sie ist bewusst spärlich — der User soll sie selbst füllen.
_ANKER_TEMPLATE = """# Anker-Liste

Persönliche Ressourcen-Sammlung für den ANKER-Modus der HRE.
Das LLM im ANKER-Modus spiegelt Einträge aus dieser Liste zurück.
Ergänze, was bei dir wirkt. Halte Einträge kurz.

## Ablenkung / Aktivierung

(Dinge, die eine Handlung verlangen — Eis holen, Radfahren, jemanden anrufen.)

- (träge hier ein)

## Downregulation

(Dinge, die keine Handlung verlangen — langes Ausatmen, Kälte im Gesicht,
Gewicht auf dem Bauch. Greifen auch im Bett, auch nachts.)

- (träge hier ein)
"""


# =============================================================================
# ÖFFENTLICHE API
# =============================================================================

def find_anker_list_path() -> Path:
    """
    Liefert den Pfad zur Anker-Liste.

    Priorität:
      1. $HRE_ANKER_LISTE (falls gesetzt)
      2. ./resonanzraum/anker_liste.md
      3. ./anker_liste.md

    Returns:
        Path-Objekt (Datei muss nicht existieren — use load_anker_list()
        zum Lesen/Erzeugen).
    """
    env_path = os.environ.get("HRE_ANKER_LISTE")
    if env_path:
        return Path(env_path)

    if DEFAULT_ANKER_PATH.exists():
        return DEFAULT_ANKER_PATH

    fallback = Path("anker_liste.md")
    return fallback


def load_anker_list() -> str:
    """
    Lädt die Anker-Liste als formatierten String für den LLM-Kontext.

    Bei fehlender Datei: erzeugt Vorlage an DEFAULT_ANKER_PATH und lädt sie.
    Bei Lesefehlern: liefert eine Mindest-Vorlage inline (damit der LLM-Call
    nicht scheitert, aber das LLM weiß, dass die Liste leer ist).

    Returns:
        Formatierter String mit beiden Abschnitten.
    """
    path = find_anker_list_path()

    if not path.exists():
        logger.warning(
            f"Anker-Liste nicht gefunden unter {path}. "
            "Erzeuge Vorlage. Bitte ergänze sie selbst."
        )
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(_ANKER_TEMPLATE, encoding="utf-8")
            logger.info(f"Anker-Listen-Vorlage erzeugt unter {path}.")
        except Exception as e:
            logger.error(
                f"Konnte Anker-Listen-Vorlage nicht erzeugen unter {path}: {e}. "
                "Verwende Inline-Vorlage."
            )
            return _ANKER_TEMPLATE

    try:
        content = path.read_text(encoding="utf-8")
        if not content.strip():
            logger.warning(f"Anker-Liste unter {path} ist leer.")
            return _ANKER_TEMPLATE
        return content
    except Exception as e:
        logger.error(f"Fehler beim Lesen der Anker-Liste {path}: {e}")
        return _ANKER_TEMPLATE


def format_anker_list_for_prompt() -> str:
    """
    Formatiert die Anker-Liste zur Injektion in den LLM-System-Prompt.

    Returns:
        Formatierter Block, z.B.:
            ---ANKER-LISTE---
            # Anker-Liste
            ...
            ---ENDE ANKER-LISTE---
    """
    content = load_anker_list()
    return f"---ANKER-LISTE---\n{content}\n---ENDE ANKER-LISTE---"


# =============================================================================
# SELF-TEST
# =============================================================================

if __name__ == "__main__":
    print("=== Self-Test: anker_loader.py ===\n")

    # Test 1: Pfad-Erkennung
    print("--- Test 1: Pfad-Erkennung ---")
    path = find_anker_list_path()
    print(f"  Pfad: {path}")
    print(f"  Existiert: {path.exists()}")

    # Test 2: Laden (erzeugt ggf. Vorlage)
    print("\n--- Test 2: Laden ---")
    content = load_anker_list()
    print(f"  Länge: {len(content)} Zeichen")
    print(f"  Erste 200 Zeichen:\n{content[:200]}...")

    # Test 3: Prompt-Format
    print("\n--- Test 3: Prompt-Format ---")
    formatted = format_anker_list_for_prompt()
    assert "---ANKER-LISTE---" in formatted
    assert "---ENDE ANKER-LISTE---" in formatted
    print(f"  Länge: {len(formatted)} Zeichen")
    print(f"  Format korrekt.")

    print("\n=== Test abgeschlossen ===")
