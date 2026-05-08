"""
IFS Engine — Lightweight LLM-Wrapper für Resonanzraum.

D.S3.7: CitationRAG-Entkopplung für IFS-Calls.
Statt CitationRAG-Monolith mit VectorStore/Router/Reranker:
Direkte llm_call-Nutzung, nur Prompt-Manager bleibt.
"""

import logging
from typing import List, Dict, Any, Optional

from modules.llm_wrapper import llm_call, llm_call_streaming
from modules.prompt_manager import PromptManager
from modules.config import MAX_IFS_TOKENS

logger = logging.getLogger(__name__)


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
        base_sys = base_sys.replace("{situation}", situation)
        situation_block = f"AKTUELLE SITUATION (aus Tagebuch):\n\"\"\"{situation}\"\"\"\n\n"
        sys_instr = situation_block + base_sys

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
