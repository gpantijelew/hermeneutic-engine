"""
IFS Engine v611 — Lightweight LLM-Wrapper für Resonanzraum UND Anker-Modus.

D.S3.7: CitationRAG-Entkopplung für IFS-Calls.
Statt CitationRAG-Monolith mit VectorStore/Router/Reranker:
Direkte llm_call-Nutzung, nur Prompt-Manager bleibt.

v611 — ANKER: BLEIBEN UND ZUHÖREN (ersetzt v60.3 ANKER komplett):
  Haltungs-Prompt statt Technik-Prompt. Inspiriert von Grigori's
  Beobachtung: drei Frauen, denen er zugehört hat, ohne ihre Erfahrung
  infrage zu stellen. Übersetzt in eine System-Instruction für ein LLM.

  Was ENTFÄLLT (komplett entfernt):
    - Phrase-Stripper (_strip_forbidden_phrases, _FORBIDDEN_PHRASES,
      _FORBIDDEN_PHRASES_RE) — 24-Phrasen-Regex-Liste weg.
    - Question-Stripper (_strip_trailing_question, _QUESTION_STARTERS).
    - Fallback-Hacks (_TROST_FALLBACK_AFTER_STRIP, _ANKER_FALLBACK).
    - [ANKER-DEBUG]-Logging (war Diagnose-Hilfsmittel für v60.3.1).
    - _ROLE_CLARIFICATION-Prepend (war v60.3-spezifisch „Spiegel, nicht
      Ratgeber" — der neue YAML-Prompt definiert die Rolle selbst).
    - Self-Tests für Stripper (nur Emergency-Test bleibt).

  Was BLEIBT:
    - IFSEngine-Klasse (unverändert — IFS_CONTROL/IFS_FIGHT/IFS_FEAR).
    - AnkerEngine-Klasse (vereinfacht — nur noch LLM-Call + Emergency).
    - Anker-Liste-Injektion in System-Prompt (über anker_loader).
    - Emergency-Interceptor (vor und nach LLM-Call — harte Sicherheit).
    - IFS_PART_MAP, DEFAULT_HUMAN_LABEL, DEFAULT_MODEL_LABEL,
      IFS_CONTEXT_PATTERNS, is_ifs_context() — für Supervision-Tab.
    - generate_opening() — schickt "__START__" als Init.

  Was NEU ist:
    - AnkerEngine.generate_response(): Nur noch LLM-Call + Emergency.
      Was das LLM generiert, wird unverändert zurückgegeben. Kein Filter,
      kein Stripper, kein Fallback.
    - AnkerEngine._prepare_call(): Kein _ROLE_CLARIFICATION-Prepend
      mehr. Der YAML-Prompt steht für sich selbst.

  Pipeline (v611):
    1. Emergency-Check auf User-Input → bei Krise: Krisen-Text, return.
    2. _prepare_call: YAML-Prompt + Anker-Liste als Kontext.
    3. LLM-Call (Temperatur aus YAML, default 0.5).
    4. Emergency-Check auf Model-Output → bei Krise: Krisen-Text.
    5. Return (was auch immer das LLM generiert hat).

  Falls das LLM leeren Output liefert:
    Der Original-Code hatte einen Fallback („Auf deiner Liste steht:
    lang ausatmen."). Dieser Fallback ist ENTFERNT. Leerer Output wird
    als leerer String zurückgegeben. Wenn der User das erlebt, ist das
    ein ehrlicher Befund — kein Bug, den wir wegfiltern sollten.
    (Siehe MIGRATION_v611.md → Offene Punkt 1.)

v60.3 — ANKER ersetzt CO_REGULATION (historisch):
  Methodische Neuausrichtung nach Claude-Consult: Trost ist keine
  Beschwichtigung. Ein LLM kann kein echtes Polyvagal-Attunement leisten.
  ANKER war ein Werkzeug, das dem User seine selbst formulierten
  Ressourcen (anker_liste.md) zurückspiegelte. v611 geht einen Schritt
  weiter: Auch das Spiegeln fällt weg. Bleiben und Zuhören reicht.

v60.2 — Erweiterung um CO_REGULATION (Trost-Modus) [historisch]:
  Question-Stripper + Emergency-Interceptor. Beide waren Workarounds
  für Prompt-Limitationen. v611 macht den Question-Stripper obsolet —
  der neue Prompt erlaubt direkte Antworten auf Meta-Fragen („hörst du
  mir zu?"), statt sie syntaktisch wegzufiltern.
"""

import logging
import re
from typing import List, Dict, Any, Optional, Iterator

from modules.llm_wrapper import llm_call, llm_call_streaming
from modules.prompt_manager import PromptManager
from modules.config import MAX_IFS_TOKENS, DOMAIN_IFS

# Anker-Liste laden (für Kontext-Injektion — der YAML-Prompt referenziert
# „die Liste", das LLM muss sie sehen können, um sie am Anfang erwähnen zu
# können).
try:
    from modules.anker_loader import format_anker_list_for_prompt as _format_anker_list
    _ANKER_LOADER_AVAILABLE = True
except ImportError:
    _ANKER_LOADER_AVAILABLE = False
    _format_anker_list = None

# Emergency Interceptor (Krisen-Früherkennung auf Code-Ebene) — bleibt
# unverändert. Harte Sicherheitsschicht unabhängig vom YAML-Prompt.
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

# Echo Guard (Wortüberlappungs-Prüfung gegen Echo-Antworten) — v615
try:
    from modules.echo_guard import (
        is_echo as _is_echo,
        ECHO_RETRY_INSTRUCTION as _ECHO_RETRY_INSTRUCTION,
    )
    _ECHO_GUARD_AVAILABLE = True
except ImportError:
    _ECHO_GUARD_AVAILABLE = False
    _is_echo = None
    _ECHO_RETRY_INSTRUCTION = ""

logger = logging.getLogger(__name__)


# =============================================================================
# v59.1 Fix 6 — IFS-KONTEXT-ERKENNUNG (für Supervision)
# =============================================================================
# IFS_PART_MAP wird von supervision_tab.py importiert, um:
#   1. Zu erkennen, ob ein analysierter Chat IFS-Kontext enthält
#   2. IFS-spezifische Rollen-Labels anstelle von [USER]/[MODEL] zu verwenden
#
# Hintergrund: Die Supervision formatiert Chat-Historie als Text und reicht
# sie an LLM-Agenten (Manager/Exile/META). Abstrakte [USER]/[MODEL]-Labels
# werden von kleineren Modellen (z.B. gemma-4-26b) häufig falsch zugeordnet.
# Deskriptive Labels ([MENSCH]/[KI-MODELL]) und IFS-spezifische Labels
# ([STIMME DER KONTROLLE] etc.) reduzieren diese Verwirrung deutlich.
#
# Siehe auch: AGENTS.md → v59.1 Fix 1 + Fix 6.
# =============================================================================

# Mapping von IFS-Part-Identifiern (lowercase, wie in state.ifs_histories)
# zu deskriptiven deutschen Labels für die Supervisions-Ausgabe.
IFS_PART_MAP = {
    "ifs_control": "STIMME DER KONTROLLE",
    "ifs_fight": "STIMME DES KAMPFES",
    "ifs_fear": "STIMME DER FURCHT",
}

# Deskriptive Default-Labels (ersetzen abstrakte [USER]/[MODEL])
DEFAULT_HUMAN_LABEL = "MENSCH"
DEFAULT_MODEL_LABEL = "KI-MODELL"

# Regex-Muster zur Heuristik: Erkennt IFS-Kontext in beliebigem Chat-Text.
IFS_CONTEXT_PATTERNS = [
    re.compile(r"\b(Stimme der Kontrolle|Kontroll-Stimme|IFS_CONTROL)\b", re.IGNORECASE),
    re.compile(r"\b(Stimme des Kampfes|Kampf-Stimme|IFS_FIGHT)\b", re.IGNORECASE),
    re.compile(r"\b(Stimme der Furcht|Furcht-Stimme|IFS_FEAR)\b", re.IGNORECASE),
    re.compile(r"\b(Inneres Familiensystem|IFS-Resonanzraum|Resonanzraum)\b", re.IGNORECASE),
    re.compile(r"\b(Manager|Exile|Firefighter)\b", re.IGNORECASE),
]


def is_ifs_context(text: str) -> bool:
    """
    Heuristik: Erkennt, ob ein Text IFS-spezifische Marker enthält.

    Args:
        text: Beliebiger Text (z.B. formatierter Chat-Verlauf).

    Returns:
        True, wenn IFS-Marker gefunden wurden, sonst False.
    """
    if not text:
        return False
    for pattern in IFS_CONTEXT_PATTERNS:
        if pattern.search(text):
            return True
    return False


# =============================================================================
# v611 — EMERGENCY-CHECK-HELPER (unverändert aus v60.2/v60.3)
# =============================================================================

def _check_emergency_user_input(text: str, mode: str = "IFS_CONTROL") -> tuple[bool, str]:
    """
    Prüft User-Input auf Krisen-Signale.

    Returns:
        Tuple (is_crisis, response_text).
        Bei is_crisis=True ist response_text der Krisen-Aussteige-Text.
        Bei is_crisis=False ist response_text="" (leer — normale Verarbeitung).
    """
    if not _EMERGENCY_AVAILABLE:
        return False, ""
    check = _check_crisis_user(text, mode=mode)
    if check.is_crisis:
        return True, _get_emergency_text()
    return False, ""


def _check_emergency_model_output(text: str, mode: str = "IFS_CONTROL") -> tuple[bool, str]:
    """
    Prüft Model-Output auf Krisen-Signale.

    Returns:
        Tuple (is_crisis, response_text).
        Bei is_crisis=True ist response_text der Krisen-Aussteige-Text.
        Bei is_crisis=False ist response_text=text (unverändert weiterreichen).
    """
    if not _EMERGENCY_AVAILABLE:
        return False, text
    check = _check_crisis_model(text, mode=mode)
    if check.is_crisis:
        return True, _get_emergency_text()
    return False, text


# =============================================================================
# IFS ENGINE — bestehend (IFS Resonanzraum)
# =============================================================================

class IFSEngine:
    """
    Minimal-Engine für IFS Resonanzraum.
    Kein RAG, kein VectorStore, kein Router — nur LLM + Prompts.
    """

    def __init__(self):
        self._prompt_manager = PromptManager()

    def _prepare_call(
        self,
        user_message: str,
        part_intent: str,
        situation: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
    ) -> tuple:
        """Baut Sys-Prompt, History und Parameter für LLM-Call.

        v59.1: Situation wird NUR über den YAML-Platzhalter {situation}
        injiziert — die Duplizierung via situation_block wurde entfernt,
        da sie Token verschwendet und kleinere Modelle verwirrt.
        """
        base_sys = self._prompt_manager.get_system_instruction(part_intent.upper())
        base_sys = base_sys.replace("{situation}", situation)

        role_clarification = (
            "ROLLEN-KLÄRUNG: DU bist die innere Stimme und antwortest. "
            "Der MENSCH (User) stellt dir Fragen. "
            "Antworte immer als innere Stimme, niemals als Ratgeber.\n\n"
        )
        sys_instr = role_clarification + base_sys

        temp_map = {
            "IFS_CONTROL": 0.5,
            "IFS_FIGHT": 0.8,
            "IFS_FEAR": 0.6,
        }
        temperature = temp_map.get(part_intent.upper(), 0.7)

        history_formatted = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in (conversation_history or [])[-10:]
            if msg.get("content")
        ]

        return user_message, sys_instr, temperature, history_formatted

    def generate_response(
        self,
        user_message: str,
        part_intent: str,
        situation: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """
        Generiert IFS-Antwort aus reiner LLM-Interaktion.

        v60.2/v611: Mit Emergency-Interceptor auf User-Input (vor LLM-Call)
        und Model-Output (nach LLM-Call).

        Args:
            user_message: User-Eingabe (oder "__START__" für Eröffnung)
            part_intent: IFS_CONTROL | IFS_FIGHT | IFS_FEAR
            situation: Die beschriebene Situation aus dem Tagebuch
            conversation_history: Optional, max 10 Turns
        """
        # Emergency-Check VOR LLM-Call (außer bei __START__)
        if user_message != "__START__":
            is_crisis, crisis_response = _check_emergency_user_input(user_message, mode=part_intent)
            if is_crisis:
                logger.warning(
                    "IFS-Call abgebrochen: Krise im User-Input erkannt "
                    f"(part_intent={part_intent})."
                )
                return crisis_response

        user_message, sys_instr, temperature, history_formatted = self._prepare_call(
            user_message, part_intent, situation, conversation_history
        )

        response = llm_call(
            user_message,
            task="ifs",
            system_instruction=sys_instr,
            temperature=temperature,
            max_tokens=MAX_IFS_TOKENS,
            history=history_formatted,
            domain=DOMAIN_IFS,
        )

        # Emergency-Check NACH LLM-Call
        is_crisis, final_response = _check_emergency_model_output(response, mode=part_intent)
        if is_crisis:
            logger.warning(
                "IFS-Output verworfen: Krise im Model-Output erkannt "
                f"(part_intent={part_intent}). Krisen-Text statt dessen zurückgegeben."
            )
            return final_response

        # Echo-Check (v615): Wenn Antwort zu stark auf User-Worten basiert →
        # einmaliger Retry mit scharfer Zusatzanweisung. Läuft automatisch
        # im Hintergrund, keine manuelle Freigabe nötig.
        if _ECHO_GUARD_AVAILABLE and _is_echo(user_message, final_response):
            logger.warning(
                f"IFS-Output als Echo erkannt (part_intent={part_intent}, "
                f"User-Input-Anfang: '{user_message[:60]}'). "
                "Einmaliger Retry mit Echo-Schärfung."
            )
            retry_sys_instr = sys_instr + _ECHO_RETRY_INSTRUCTION
            retry_response = llm_call(
                user_message,
                task="ifs",
                system_instruction=retry_sys_instr,
                temperature=temperature,
                max_tokens=MAX_IFS_TOKENS,
                history=history_formatted,
                domain=DOMAIN_IFS,
            )
            # Emergency-Check auf Retry-Output
            is_crisis_retry, final_retry = _check_emergency_model_output(
                retry_response, mode=part_intent
            )
            if is_crisis_retry:
                logger.warning(
                    "IFS-Retry-Output verworfen: Krise erkannt. "
                    "Krisen-Text statt dessen zurückgegeben."
                )
                return final_retry
            # KEIN weiterer Echo-Check auf Retry (sonst Endlosschleife).
            # Wenn Retry immer noch echo-lastig ist, wird er trotzdem ausgeliefert —
            # aber das Log dokumentiert den Fall.
            if _is_echo(user_message, final_retry):
                logger.warning(
                    "IFS-Retry ist immer noch echo-lastig. "
                    "Trotzdem ausgeliefert (kein zweiter Retry)."
                )
            final_response = final_retry

        return final_response

    def generate_response_streaming(
        self,
        user_message: str,
        part_intent: str,
        situation: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
    ) -> Iterator[str]:
        """Streaming-Variante fuer IFS-Antworten (z.B. Fear-Part)."""
        if user_message != "__START__":
            is_crisis, crisis_response = _check_emergency_user_input(user_message, mode=part_intent)
            if is_crisis:
                logger.warning(
                    "IFS-Streaming abgebrochen: Krise im User-Input erkannt "
                    f"(part_intent={part_intent})."
                )
                yield crisis_response
                return

        user_message, sys_instr, temperature, history_formatted = self._prepare_call(
            user_message, part_intent, situation, conversation_history
        )

        yield from llm_call_streaming(
            user_message,
            task="ifs",
            system_instruction=sys_instr,
            temperature=temperature,
            max_tokens=MAX_IFS_TOKENS,
            history=history_formatted,
            domain=DOMAIN_IFS,
        )

    def generate_opening(self, part_intent: str, situation: str) -> str:
        """Erzeugt den Eröffnungssatz für einen Part."""
        return self.generate_response(
            user_message="__START__",
            part_intent=part_intent,
            situation=situation,
            conversation_history=[],
        )


# =============================================================================
# v611 — ANKER ENGINE („Bleiben und Zuhören")
# =============================================================================
# Eigenständige Klasse, nicht in IFSEngine integriert — weil ANKER KEIN IFS ist.
#
# v611 reduziert die AnkerEngine auf das Minimum: YAML-Prompt + Anker-Liste
# als Kontext + LLM-Call + Emergency-Interceptor. Keine Filter, keine
# Strippers, keine Fallbacks. Was das LLM generiert, kommt unverändert
# beim User an.
#
# Der YAML-Prompt (siehe ANKER_prompt_v611.yaml) trägt die ganze Haltung:
#   - „Du bist jemand, der bleibt und wirklich hinhört."
#   - Einmaliger Listenhinweis am Anfang, dann nie wieder.
#   - Konkretes Echo des User-Inputs.
#   - Direkte Antwort auf Meta-Fragen („hörst du mir zu?").
#   - Im Kreisen feststecken: kurz benennen, nicht wiederholen.
#   - Was du nie tust: keine Technik, keine Frage nach Bedarf, kein Fazit,
#     kein Satz zweimal, keine Relativierung.
#
# Der Code misstraut dem Prompt nicht. Der Prompt trägt die Haltung, der
# Code trägt die Notfall-Sicherheit. Das ist die Aufteilung.
# =============================================================================

class AnkerEngine:
    """
    Engine für den ANKER-Modus v611 („Bleiben und Zuhören").

    Methodische Einordnung:
    - KEIN IFS-Part. KEINE Co-Regulation im engeren Sinne. KEIN Ratgeber.
    - KEIN Spiegel mehr (v60.3-Spiegel-Logik entfernt).
    - Ein LLM, das bleibt und zuhört. Haltungs-Prompt, keine Technik.
    - Anker-Liste wird als Kontext injiziert (der Prompt referenziert sie).
    - Kein Filter, kein Stripper, kein Fallback — was das LLM sagt, kommt durch.
    - Emergency-Interceptor wie bei IFS (vor und nach LLM-Call).
    """

    def __init__(self):
        self._prompt_manager = PromptManager()

    def _prepare_call(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
    ) -> tuple:
        """Baut Sys-Prompt, History und Parameter für Anker-LLM-Call.

        v611: KEIN _ROLE_CLARIFICATION-Prepend mehr. Der YAML-Prompt
        definiert die Rolle selbst („Du bist niemand, der ein Problem
        löst. Du bist jemand, der bleibt und wirklich hinhört.").

        Die Anker-Liste wird weiterhin als Kontext angehängt — der
        YAML-Prompt referenziert „die Liste" und das LLM muss sie sehen
        können, um sie am Anfang erwähnen zu können.
        """
        base_sys = self._prompt_manager.get_system_instruction("ANKER")
        sys_instr = base_sys

        # Anker-Liste als Kontext anhängen (unverändert aus v60.3)
        if _ANKER_LOADER_AVAILABLE:
            try:
                anker_block = _format_anker_list()
                sys_instr = sys_instr + "\n\n" + anker_block
            except Exception as e:
                logger.warning(
                    f"Anker-Liste konnte nicht geladen werden: {e}. "
                    "Anker-Modus läuft ohne Liste — User muss "
                    "resonanzraum/anker_liste.md anlegen."
                )
                sys_instr = sys_instr + (
                    "\n\n---ANKER-LISTE---\n"
                    "(Liste konnte nicht geladen werden — User muss "
                    "resonanzraum/anker_liste.md anlegen.)\n"
                    "---ENDE ANKER-LISTE---"
                )
        else:
            logger.warning(
                "anker_loader nicht verfügbar. Anker-Modus ohne Liste."
            )
            sys_instr = sys_instr + (
                "\n\n---ANKER-LISTE---\n"
                "(anker_loader-Modul fehlt. Bitte modules/anker_loader.py "
                "installieren.)\n"
                "---ENDE ANKER-LISTE---"
            )

        # ANKER-Mode-Temperatur aus YAML über PromptManager abfragen
        # Fallback: 0.5
        try:
            mode_data = self._prompt_manager._data.get("mode_instructions", {}).get(
                "ANKER", {}
            )
            temperature = mode_data.get("temperature", 0.5)
        except Exception:
            temperature = 0.5

        history_formatted = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in (conversation_history or [])[-10:]
            if msg.get("content")
        ]

        return user_message, sys_instr, temperature, history_formatted

    def generate_response(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """
        Generiert eine Anker-Antwort. v611-Pipeline:

        1. Emergency-Check auf User-Input → bei Krise: Krisen-Text, return.
        2. _prepare_call: YAML-Prompt + Anker-Liste als Kontext.
        3. LLM-Call.
        4. Emergency-Check auf Model-Output → bei Krise: Krisen-Text, return.
        5. Return (was auch immer das LLM generiert hat — unverändert).

        Was ENTFÄLLT gegenüber v60.3.1:
          - Phrase-Stripper
          - Question-Stripper
          - [ANKER-DEBUG]-Logging
          - Fallback bei leerem Output (leerer Output kommt durch)

        Args:
            user_message: User-Eingabe (oder "__START__" für Eröffnung)
            conversation_history: Optional, max 10 Turns
        """
        # Emergency-Check VOR LLM-Call
        if user_message != "__START__":
            is_crisis, crisis_response = _check_emergency_user_input(user_message, mode="NAMASTE")
            if is_crisis:
                logger.warning(
                    "Anker-Call abgebrochen: Krise im User-Input erkannt."
                )
                return crisis_response

        user_message, sys_instr, temperature, history_formatted = self._prepare_call(
            user_message, conversation_history
        )

        response = llm_call(
            user_message,
            task="ifs",  # Gleiche Task-Kategorie (ifs Resonanzraum-Domain)
            system_instruction=sys_instr,
            temperature=temperature,
            max_tokens=MAX_IFS_TOKENS,
            history=history_formatted,
            domain=DOMAIN_IFS,
        )

        # Emergency-Check NACH LLM-Call
        is_crisis, final_response = _check_emergency_model_output(response, mode="NAMASTE")
        if is_crisis:
            logger.warning(
                "Anker-Output verworfen: Krise im Model-Output erkannt. "
                "Krisen-Text statt dessen zurückgegeben."
            )
            return final_response

        # Echo-Check (v615): Wenn Antwort zu stark auf User-Worten basiert →
        # einmaliger Retry mit scharfer Zusatzanweisung. Läuft automatisch
        # im Hintergrund, keine manuelle Freigabe nötig.
        if _ECHO_GUARD_AVAILABLE and _is_echo(user_message, final_response):
            logger.warning(
                f"Anker-Output als Echo erkannt "
                f"(User-Input-Anfang: '{user_message[:60]}'). "
                "Einmaliger Retry mit Echo-Schärfung."
            )
            retry_sys_instr = sys_instr + _ECHO_RETRY_INSTRUCTION
            retry_response = llm_call(
                user_message,
                task="ifs",  # Gleiche Task-Kategorie (ifs Resonanzraum-Domain)
                system_instruction=retry_sys_instr,
                temperature=temperature,
                max_tokens=MAX_IFS_TOKENS,
                history=history_formatted,
                domain=DOMAIN_IFS,
            )
            # Emergency-Check auf Retry-Output
            is_crisis_retry, final_retry = _check_emergency_model_output(
                retry_response, mode="NAMASTE"
            )
            if is_crisis_retry:
                logger.warning(
                    "Anker-Retry-Output verworfen: Krise erkannt. "
                    "Krisen-Text statt dessen zurückgegeben."
                )
                return final_retry
            # KEIN weiterer Echo-Check auf Retry (sonst Endlosschleife).
            if _is_echo(user_message, final_retry):
                logger.warning(
                    "Anker-Retry ist immer noch echo-lastig. "
                    "Trotzdem ausgeliefert (kein zweiter Retry)."
                )
            final_response = final_retry

        # v611: Kein Filter mehr. Was das LLM sagt, kommt unverändert durch.
        # Leerer Output wird als leerer String zurückgegeben — ehrlicher
        # Befund, kein Bug, den wir wegfiltern sollten.
        return final_response

    def generate_response_streaming(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
    ) -> Iterator[str]:
        """
        Streaming-Variante für Anker-Antworten.

        v611: Kein Post-Processing mehr — was das LLM streamt, kommt
        unverändert beim User an. Emergency-Check nur VOR dem Stream
        (auf User-Input); Model-Output-Check entfällt beim Streaming
        (zu spät pro-Chunk — Aufrufer ist verantwortlich, falls nötig).
        """
        if user_message != "__START__":
            is_crisis, crisis_response = _check_emergency_user_input(user_message, mode="NAMASTE")
            if is_crisis:
                logger.warning(
                    "Anker-Streaming abgebrochen: Krise im User-Input erkannt."
                )
                yield crisis_response
                return

        user_message, sys_instr, temperature, history_formatted = self._prepare_call(
            user_message, conversation_history
        )

        yield from llm_call_streaming(
            user_message,
            task="ifs",
            system_instruction=sys_instr,
            temperature=temperature,
            max_tokens=MAX_IFS_TOKENS,
            history=history_formatted,
            domain=DOMAIN_IFS,
        )

    def generate_opening(self) -> str:
        """Erzeugt den Eröffnungssatz im Anker-Modus.

        Schickt "__START__" als user_message. Der YAML-Prompt feuert dann
        die „GANZ AM ANFANG DIESES GESPRÄCHS"-Regel: knapp den Listenhinweis
        geben, dann nie wieder.
        """
        return self.generate_response(
            user_message="__START__",
            conversation_history=[],
        )


# Backward-Kompatibilität: TrostEngine als Alias auf AnkerEngine.
# Verhindert Crashs, falls UI-Code oder Tests noch auf TrostEngine referenzieren.
# Wird in v61 entfernt — sauberer Bruch dann.
TrostEngine = AnkerEngine


# =============================================================================
# SELF-TEST (reduziert — Stripper-Tests entfernt)
# =============================================================================

if __name__ == "__main__":
    print("=== Self-Test: ifs_engine.py v611 (Anker-Engine — Bleiben und Zuhören) ===\n")

    # Emergency-Interceptor Verfügbarkeit
    print("--- Emergency Interceptor ---")
    print(f"Available: {_EMERGENCY_AVAILABLE}")
    if _EMERGENCY_AVAILABLE:
        # Quick smoke test
        test_crisis = "Ich will nicht mehr leben."
        is_c, resp = _check_emergency_user_input(test_crisis)
        print(f"  Crisis-Test '{test_crisis}': is_crisis={is_c}")
        if is_c:
            print(f"  Response (ersten 80 Zeichen): {resp[:80]}")

    print()
    print("--- Anker-Liste Loader ---")
    print(f"Available: {_ANKER_LOADER_AVAILABLE}")

    print()
    print("--- Konstanten (Soll-Werte) ---")
    print(f"  IFS_PART_MAP keys: {list(IFS_PART_MAP.keys())}")
    print(f"  DEFAULT_HUMAN_LABEL: {DEFAULT_HUMAN_LABEL}")
    print(f"  DEFAULT_MODEL_LABEL: {DEFAULT_MODEL_LABEL}")
    print(f"  IFS_CONTEXT_PATTERNS count: {len(IFS_CONTEXT_PATTERNS)}")

    # Sanity-Check: is_ifs_context
    print()
    print("--- is_ifs_context Tests ---")
    ctx_tests = [
        ("Ich spreche mit der Stimme der Kontrolle.", True),
        ("Ein normaler Satz ohne IFS-Marker.", False),
        ("Resonanzraum ist offen.", True),
        ("", False),
    ]
    for text, expected in ctx_tests:
        result = is_ifs_context(text)
        match = "OK" if result == expected else "FAIL"
        print(f"  [{match}] '{text[:50]}...' → {result} (expected {expected})")

    print()
    print("--- Verifizierung: Stripper entfernt ---")
    # Diese Namen sollten NICHT mehr definiert sein.
    removed_symbols = [
        "_strip_forbidden_phrases",
        "_strip_trailing_question",
        "_FORBIDDEN_PHRASES",
        "_FORBIDDEN_PHRASES_RE",
        "_QUESTION_STARTERS",
        "_TROST_FALLBACK_AFTER_STRIP",
        "_ANKER_FALLBACK",
    ]
    for name in removed_symbols:
        defined = name in globals()
        status = "FAIL (noch definiert!)" if defined else "OK (entfernt)"
        print(f"  [{status}] {name}")

    print("\n=== Test abgeschlossen ===")
