# modules/intervision_engine.py
#
# IntervisionEngine v0.1 (STUB) - vorlaeufige, isolierte Grundstruktur.
# Steht parallel zu IFSEngine und AnkerEngine. Beruehrt keinen Bestandscode.
# Prompt-Spec fuer Mission D steht noch aus - dies ist nur Architektur.
#
# Siehe Stilvorlage: modules/ifs_engine.py (v611)
#
# Vorgaben erfuellt:
#   - Emergency-Direktimport (kein Streamlit-Import im Modulkopf)
#   - Platzhalter generate_response liefert STUB-String, kein LLM-Call
#   - Session-Konvention: intervision_history
#   - Keine Docstrings (keine dreifachen Anfuehrungszeichen)
#   - Keine Apostrophe in Texten (nur gerade Anfuehrungszeichen)
#   - Vollstaendig ASCII

import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


# =============================================================================
# Emergency Interceptor - Krisen-Frueherkennung auf Code-Ebene.
# Direktimport (gleicher Stil wie ifs_engine.py), kein Streamlit-Import.
# Wird vor und nach jedem (zukuenftigen) LLM-Call gerufen.
# =============================================================================
try:
    from modules.emergency_interceptor import (
        check_user_input as _check_crisis_user,
        check_model_output as _check_crisis_model,
        get_emergency_response as _get_emergency_text,
    )
    _EMERGENCY_AVAILABLE = True
except ImportError:
    _EMERGENCY_AVAILABLE = False
    _check_crisis_user = None
    _check_crisis_model = None
    _get_emergency_text = None


# =============================================================================
# Konstanten - vorlaeufig, solange die Spec fuer Mission D offen ist.
# =============================================================================
INTERVISION_HISTORY_KEY = "intervision_history"
INTERVISION_SESSION_KEY = "intervision_session_active"
INTERVISION_TURN_KEY = "intervision_turn_count"

# Vorlaeufiger Intent-Platzhalter. Spaeter: echte Intents aus YAML.
INTERVISION_PLACEHOLDER_INTENT = "INTERVISION_STUB"

# Temperatur-Map - Platzhalter. Spaeter: echte Werte aus YAML.
INTERVISION_TEMPERATURES = {
    "INTERVISION_STUB": 0.5,
}

# Maximale Turns in der Session-History, aehnlich IFS/Anker.
MAX_HISTORY_TURNS = 50


# =============================================================================
# Hilfsfunktionen - Emergency-Pruefung.
# Symmetrisch zu ifs_engine._check_emergency_user_input / _check_emergency_model_output.
# =============================================================================
def _check_user(text: str) -> tuple:
    # Prueft User-Input auf Krisen-Signale.
    # Returns: (is_crisis, response_text). Bei False ist response_text leer.
    if not _EMERGENCY_AVAILABLE:
        return False, ""
    if not text:
        return False, ""
    check = _check_crisis_user(text)
    if check is not None and check.is_crisis:
        return True, _get_emergency_text()
    return False, ""


def _check_model(text: str) -> tuple:
    # Prueft Model-Output auf Krisen-Signale.
    # Returns: (is_crisis, response_text). Bei False ist response_text der
    # Originaltext (unveraendert weiterreichen). Bei True wird der Original-
    # output verworfen und durch den Notfall-Text ersetzt.
    if not _EMERGENCY_AVAILABLE:
        return False, text
    if not text:
        return False, text
    check = _check_crisis_model(text)
    if check is not None and check.is_crisis:
        return True, _get_emergency_text()
    return False, text


# =============================================================================
# Session-State - Default-Initialisierung.
# Ohne Streamlit-Import: wir arbeiten auf einem dict-Interface, das vom
# Aufrufer (z.B. ifs_tab) uebergeben wird. Das entspricht der Konvention
# in ifs_engine.py, wo Session-State ebenfalls indirekt gehalten wird.
# =============================================================================
def init_session_state_defaults(session: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    # Initialisiert Default-Werte fuer eine Intervision-Session.
    # Wird vom Aufrufer (Tab-Schicht) gerufen, nicht vom Modul selbst.
    # Nimmt ein dict (Session-State-Proxy) und fuellt Defaults, falls sie
    # noch nicht gesetzt sind. Gibt das (ggf. veraenderte) dict zurueck.
    if session is None:
        session = {}

    if INTERVISION_HISTORY_KEY not in session:
        session[INTERVISION_HISTORY_KEY] = []
    if INTERVISION_SESSION_KEY not in session:
        session[INTERVISION_SESSION_KEY] = False
    if INTERVISION_TURN_KEY not in session:
        session[INTERVISION_TURN_KEY] = 0

    return session


def reset_session(session: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    # Setzt die Intervision-Session explizit zurueck.
    # Aenderung gegenueber init_session_state_defaults: loescht vorhandene
    # Werte, statt sie stehen zu lassen.
    if session is None:
        session = {}

    session[INTERVISION_HISTORY_KEY] = []
    session[INTERVISION_SESSION_KEY] = False
    session[INTERVISION_TURN_KEY] = 0

    return session


def append_turn(
    session: Dict[str, Any],
    role: str,
    content: str,
) -> None:
    # Haengt einen Turn an die Session-History an.
    # role: "user" oder "assistant". content: der jeweilige Text.
    # Wird von generate_response intern verwendet, kann aber auch vom
    # Aufrufer fuer Testzwecke direkt gerufen werden.
    history: List[Dict[str, str]] = session.get(INTERVISION_HISTORY_KEY, [])
    history.append({"role": role, "content": content})

    # Auf MAX_HISTORY_TURNS beschraenken (aelteste zuerst raus).
    if len(history) > MAX_HISTORY_TURNS:
        history = history[-MAX_HISTORY_TURNS:]

    session[INTERVISION_HISTORY_KEY] = history

    if role == "user":
        session[INTERVISION_TURN_KEY] = session.get(INTERVISION_TURN_KEY, 0) + 1


# =============================================================================
# IntervisionEngine - Stub-Klasse.
# Sieht aus wie IFSEngine/AnkerEngine (Konstruktor ohne Pflichtargs,
# generate_response als Haupteinstieg), macht aber keinen LLM-Call.
# =============================================================================
class IntervisionEngine:
    # Vorlaeufige Engine-Klasse fuer Mission D.
    # Name kann spaeter umbenannt werden. Beruehrt keinen Bestandscode.

    def __init__(self, prompt_manager: Optional[Any] = None):
        # prompt_manager: optional, spaeter fuer YAML-Anbindung.
        # Aktuell nicht verwendet - Spec steht aus.
        self._prompt_manager = prompt_manager

    def _prepare_call(
        self,
        user_message: str,
        intent: str = INTERVISION_PLACEHOLDER_INTENT,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        # Baut den ( Platzhalter- ) Kontext fuer einen zukuenftigen LLM-Call.
        # Aktuell: kein LLM-Call, nur Struktur. Wird von generate_response
        # gerufen, kann aber auch vom Aufrufer fuer Pre-Checks verwendet werden.
        return {
            "intent": intent,
            "user_message": user_message,
            "conversation_history": conversation_history or [],
            "temperature": INTERVISION_TEMPERATURES.get(intent, 0.5),
            "stub": True,
        }

    def generate_response(
        self,
        user_message: str,
        session: Optional[Dict[str, Any]] = None,
        intent: str = INTERVISION_PLACEHOLDER_INTENT,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        # Platzhalter - kein LLM-Call.
        #
        # Ablauf (symmetrisch zu AnkerEngine.generate_response, vereinfacht):
        #   1. Session-Defaults initialisieren.
        #   2. Emergency-Check auf User-Input.
        #      - Bei Krise: Notfall-Text zurueck, kein append_turn.
        #   3. ( Platzhalter ) _prepare_call aufrufen - kein LLM.
        #   4. Platzhalter-Antwort generieren.
        #   5. Emergency-Check auf Model-Output.
        #      - Bei Krise: Notfall-Text statt Platzhalter.
        #   6. Turn anhaengen (user + assistant).
        #   7. Antwort zurueckgeben.
        #
        # Returns: Antwort-String (Platzhalter oder Notfall-Text).

        # 1. Session-Defaults
        session = init_session_state_defaults(session)

        # 2. Emergency-Check User-Input
        is_crisis_user, emergency_text = _check_user(user_message)
        if is_crisis_user:
            logger.warning("Emergency in User-Input erkannt - Intervision-STUB bricht ab.")
            append_turn(session, "user", user_message)
            append_turn(session, "assistant", emergency_text)
            return emergency_text

        # 3. _prepare_call (Platzhalter, kein LLM)
        _ = self._prepare_call(
            user_message=user_message,
            intent=intent,
            conversation_history=conversation_history,
        )

        # 4. Platzhalter-Antwort
        response = "[INTERVISION-STUB] Kein LLM-Call - Spec ausstehend"

        # 5. Emergency-Check Model-Output
        is_crisis_model, safe_response = _check_model(response)
        if is_crisis_model:
            logger.warning("Emergency in Model-Output erkannt - Platzhalter verworfen.")
            response = safe_response

        # 6. Turn anhaengen
        append_turn(session, "user", user_message)
        append_turn(session, "assistant", response)

        # 7. Antwort
        return response


# =============================================================================
# Modul-Self-Test - kann mit  python -m modules.intervision_engine  gerufen
# werden. Prueft nur Struktur, keinen LLM-Call.
# =============================================================================
def _self_test() -> int:
    # Minimaler Self-Test: Engine instanziieren, Stub-Call ausfuehren.
    # Erwartet: Rueckgabe des Platzhalter-Strings, Session-State mit zwei
    # Turns (user + assistant), keine Exception.
    print("[SELF-TEST] IntervisionEngine v0.1 (STUB)")
    print(f"  Emergency-Interceptor verfuegbar: {_EMERGENCY_AVAILABLE}")

    engine = IntervisionEngine()
    session = init_session_state_defaults({})

    user_msg = "Test-Nachricht - Self-Test"
    response = engine.generate_response(user_msg, session=session)

    print(f"  Response: {response}")

    history = session.get(INTERVISION_HISTORY_KEY, [])
    print(f"  History-Laenge: {len(history)}")
    print(f"  Turn-Count: {session.get(INTERVISION_TURN_KEY, 0)}")

    ok = True
    if response != "[INTERVISION-STUB] Kein LLM-Call - Spec ausstehend":
        print("  [FAIL] Response-String nicht wie erwartet.")
        ok = False
    if len(history) != 2:
        print("  [FAIL] History sollte 2 Eintraege haben (user + assistant).")
        ok = False
    if session.get(INTERVISION_TURN_KEY, 0) != 1:
        print("  [FAIL] Turn-Count sollte 1 sein.")
        ok = False

    if ok:
        print("  [OK] Self-Test bestanden.")
        return 0
    print("  [FAIL] Self-Test fehlgeschlagen.")
    return 1


if __name__ == "__main__":
    import sys
    sys.exit(_self_test())
