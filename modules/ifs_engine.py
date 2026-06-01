"""
IFS Engine — Lightweight LLM-Wrapper für Resonanzraum.

D.S3.7: CitationRAG-Entkopplung für IFS-Calls.
Statt CitationRAG-Monolith mit VectorStore/Router/Reranker:
Direkte llm_call-Nutzung, nur Prompt-Manager bleibt.

v59.1 — Rollen-Disambiguierungs-Fix:
- Fix 3: Situation-Duplikation entfernt (situation_block prepend + {situation} placeholder)
- Fix 4: Rollen-Disambiguierungs-Header im System-Prompt für kleinere Modelle
"""

import logging
from typing import List, Dict, Any, Optional

from modules.llm_wrapper import llm_call, llm_call_streaming
from modules.prompt_manager import PromptManager
from modules.config import MAX_IFS_TOKENS

logger = logging.getLogger(__name__)

# v59.1 Fix 4 — Rollen-Disambiguierungs-Header
# Wird dem System-Prompt vorangestellt, damit kleinere Modelle (z.B. gemma-4-26b)
# die User/Model-Rollen nicht verwechseln. Explizite Zuordnung statt abstrakter Labels.
ROLE_DISAMBIGUATION_HEADER = (
    "ROLLEN-DEFINITION (LESE VOR DEM ANTWORTEN):\n"
    "Du bist ein innerer Anteil (eine innere Stimme) der Person, die mit dir spricht.\n"
    "Die Person, die dir Nachrichten schreibt, ist der USER.\n"
    "Du sprichst ALS innerer Anteil ZUM User.\n"
    "Der User spricht ALS Person (Ich/Self) ZU dir.\n"
    "Verwechsle niemals die Rollen: Du bist NIEMALS der User, der User ist NIEMALS du.\n"
    "Antworte immer aus der Ich-Perspektive des inneren Anteils, nie aus der Perspektive des Users.\n\n"
)


# v59.1 Fix 4 — IFS-Rollen-Karte für Supervisions-Kontext
# Erlaubt supervision_tab.py, die Rolle der inneren Stimme zu identifizieren
IFS_PART_MAP = {
    "IFS_CONTROL": "Kontrolle/Sicherheit",
    "IFS_FIGHT": "Kampf/Abwehr",
    "IFS_FEAR": "Überforderung/Angst",
}


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
        """Baut Sys-Prompt, History und Parameter für LLM-Call."""
        base_sys = self._prompt_manager.get_system_instruction(part_intent.upper())

        # v59.1 Fix 3 — Situation-Duplikation entfernt
        # Ursprung: situation_block wurde VOR base_sys geprependet, aber base_sys
        # enthält bereits {situation}-Placeholder → Situation erschien doppelt.
        # Lösung: Nur den Placeholder ersetzen, kein zusätzliches Prepend.
        base_sys = base_sys.replace("{situation}", situation)

        # v59.1 Fix 4 — Rollen-Disambiguierungs-Header voranstellen
        sys_instr = ROLE_DISAMBIGUATION_HEADER + base_sys

        temp_map = {
            "IFS_CONTROL": 0.5,
            "IFS_FIGHT": 0.8,
            "IFS_FEAR": 0.6,
        }
        temperature = temp_map.get(part_intent.upper(), 0.7)

        # v59.1 Fix 4 — Rollen-Disambiguierung in der History
        # Statt abstrakter role="user"/role="model" Labels, füge jedem
        # History-Eintrag eine Rollen-Kennzeichnung als Präfix hinzu.
        part_label = IFS_PART_MAP.get(part_intent.upper(), "innerer Anteil")
        history_formatted = []
        for msg in (conversation_history or [])[-10:]:
            content = msg.get("content", "")
            if not content:
                continue
            role = msg.get("role", "unknown")
            # Explizite Rollen-Kennzeichnung im Content für kleinere Modelle
            if role == "user":
                content = f"[PERSON/USER]: {content}"
            elif role == "model" or role == "assistant":
                content = f"[{part_label.upper()}]: {content}"
            history_formatted.append({"role": role, "content": content})

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

        Args:
            user_message: User-Eingabe (oder "__START__" für Eröffnung)
            part_intent: IFS_CONTROL | IFS_FIGHT | IFS_FEAR
            situation: Die beschriebene Situation aus dem Tagebuch
            conversation_history: Optional, max 10 Turns
        """
        user_message, sys_instr, temperature, history_formatted = self._prepare_call(
            user_message, part_intent, situation, conversation_history
        )

        from modules.config import DOMAIN_IFS
        return llm_call(
            user_message,
            task="ifs",
            system_instruction=sys_instr,
            temperature=temperature,
            max_tokens=MAX_IFS_TOKENS,
            history=history_formatted,
            domain=DOMAIN_IFS,
        )

    def generate_response_streaming(
        self,
        user_message: str,
        part_intent: str,
        situation: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
    ):
        """
        Streaming-Variante fuer IFS-Antworten (z.B. Fear-Part).
        Yields Text-Chunks.
        """
        user_message, sys_instr, temperature, history_formatted = self._prepare_call(
            user_message, part_intent, situation, conversation_history
        )

        from modules.config import DOMAIN_IFS
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
