# modules/llm_wrapper.py — v50.9: Universeller LLM-Wrapper
"""
Zentraler Einstiegspunkt für alle LLM-Aufrufe in der HRE.

PHILOSOPHIE:
Alle Module rufen ausschließlich llm_call() oder llm_call_json() auf.
Der Wrapper übersetzt intern in den konfigurierten Backend-Dialekt.
Backend-Wechsel (LM Studio → Claude API) erfordert NULL Änderungen
in den aufrufenden Modulen.

VERWENDUNG:
    from modules.llm_wrapper import llm_call, llm_call_json

    # Einfacher Text-Aufruf:
    result = llm_call("Analysiere diesen Text...", task="enforcer")

    # JSON-Aufruf (für strukturierte Outputs):
    data = llm_call_json("Extrahiere Fakten...", task="fact_extraction")

TASKS (aus config.py MODEL_REGISTRY):
    chat, synthesis, enforcer, fact_extraction,
    query_expansion, router, reranker,
    bulk_labeling, title_gen, question_conv
"""

import os
import json
import logging
import re
from typing import Optional, Dict, Any

from modules.config import (
    LLM_BACKEND,
    get_llm_client,
    get_model_for_task,
)

logger = logging.getLogger(__name__)

# ==============================================================================
# SYSTEM INSTRUCTION
# ==============================================================================

def _get_system_instruction() -> str:
    """
    Zentrale System-Instruction für alle LLM-Aufrufe.
    /no_think deaktiviert Qwen3-Reasoning (bei anderen Modellen ignoriert).
    """
    base = os.getenv(
        "LLM_SYSTEM_PREFIX",
        "/no_think"
    )
    hre_context = (
        "Du bist ein präziser Forschungsassistent der "
        "Hermeneutic Reconstruction Engine (HRE). "
        "Antworte prägnant, analytisch und ohne Ausweichen."
    )
    return f"{base}\n{hre_context}"


# ==============================================================================
# KERN-FUNKTIONEN
# ==============================================================================

def llm_call(
    prompt: str,
    task: str = "synthesis",
    system_instruction: Optional[str] = None,
    temperature: float = 0.3,
    max_tokens: int = 2048,
    history: Optional[list] = None,
) -> str:
    """
    Universeller LLM-Aufruf — gibt Text zurück.

    Args:
        prompt:             Der eigentliche Prompt / User-Turn
        task:               Task-Key für Modellauswahl (aus config.py)
        system_instruction: Überschreibt Standard-Instruction (optional)
        temperature:        Sampling-Temperatur (default: 0.3)
        max_tokens:         Max Output-Tokens (default: 2048)
        history:            Konversationshistorie für Multi-Turn
                            Format: [{"role": "user"|"assistant",
                                      "content": "..."}]

    Returns:
        Antwort-Text als String. Bei Fehler: leerer String.

    Raises:
        Kein raise — Fehler werden geloggt und als "" zurückgegeben.
        Aufrufende Module müssen auf leeren String prüfen.
    """
    try:
        client, model = get_llm_client()
        sys_msg = system_instruction or _get_system_instruction()

        # Messages aufbauen
        messages = [{"role": "system", "content": sys_msg}]

        # Konversationshistorie einfügen (falls vorhanden)
        if history:
            for turn in history:
                role = turn.get("role", "user")
                if role == "model":     # Gemini-Relikt - OpenAI normalisieren
                     role = "assistant"
                content = turn.get("content", "") or \
                          _extract_text_from_parts(turn)
                if content:
                    messages.append({"role": role, "content": content})

        messages.append({"role": "user", "content": prompt})

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        result = response.choices[0].message.content.strip()

        # Token-Logging (hilfreich für Debugging)
        usage = response.usage
        reasoning = getattr(
            usage.completion_tokens_details, 'reasoning_tokens', 0
        ) or 0
        logger.debug(
            f"[{task}] Tokens — "
            f"Prompt: {usage.prompt_tokens}, "
            f"Completion: {usage.completion_tokens}, "
            f"Reasoning: {reasoning}"
        )
        if reasoning > 500:
            logger.warning(
                f"⚠️ [{task}] Hoher Reasoning-Overhead: "
                f"{reasoning} Tokens. "
                f"Erwäge /no_think in LLM_SYSTEM_PREFIX."
            )

        return result

    except Exception as e:
        logger.error(f"❌ LLM-Aufruf fehlgeschlagen [{task}]: {e}")
        return ""


def llm_call_json(
    prompt: str,
    task: str = "fact_extraction",
    system_instruction: Optional[str] = None,
    temperature: float = 0.1,
    max_tokens: int = 2048,
    fallback: Any = None,
) -> Any:
    """
    LLM-Aufruf mit JSON-Rückgabe.

    Fordert das Modell explizit auf, reines JSON zu liefern.
    Versucht mehrfach zu parsen (mit Fence-Stripping).

    Args:
        prompt:             Der eigentliche Prompt
        task:               Task-Key für Logging
        system_instruction: Überschreibt Standard-Instruction (optional)
        temperature:        Niedrig für deterministische JSON-Ausgabe
        max_tokens:         Max Output-Tokens
        fallback:           Rückgabewert bei Parse-Fehler (default: None)

    Returns:
        Geparste Python-Struktur (dict/list) oder fallback bei Fehler.
    """
    json_instruction = (
        "\n\nWICHTIG: Antworte AUSSCHLIESSLICH mit validem JSON. "
        "Kein Text davor oder danach. Keine Markdown-Backticks."
    )

    full_prompt = prompt + json_instruction
    sys_msg = (system_instruction or _get_system_instruction())

    raw = llm_call(
        prompt=full_prompt,
        task=task,
        system_instruction=sys_msg,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    if not raw:
        return fallback

    # JSON aus Response extrahieren
    return _parse_json_safe(raw, fallback=fallback)


def llm_call_streaming(
    prompt: str,
    task: str = "chat",
    system_instruction: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
    history: Optional[list] = None,
):
    """
    Streaming-Variante für das Chat-Interface (Streamlit).

    Yields:
        Text-Chunks (str) aus dem Stream.

    Verwendung in Streamlit:
        for chunk in llm_call_streaming(prompt, task="chat"):
            st.write(chunk)
    """
    try:
        client, model = get_llm_client()
        sys_msg = system_instruction or _get_system_instruction()

        messages = [{"role": "system", "content": sys_msg}]

        if history:
            for turn in history:
                role = turn.get("role", "user")
                if role == "model":            # Gemini-Relikt - OpenAI normalisieren
                     role = "assistant"
                content = turn.get("content", "") or \
                          _extract_text_from_parts(turn)
                if content:
                    messages.append({"role": role, "content": content})

        messages.append({"role": "user", "content": prompt})

        stream = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )

        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    except Exception as e:
        logger.error(f"❌ Streaming-Fehler [{task}]: {e}")
        print(f"STREAMING EXCEPTION: {type(e).__name__}: {e}")  # ← temporär
        yield ""


# ==============================================================================
# HILFSFUNKTIONEN
# ==============================================================================

def _extract_text_from_parts(msg: dict) -> str:
    """
    Extrahiert Text aus dem Firestore/Gemini-Format:
    {'role': ..., 'parts': [{'text': ...}]}
    Für Rückwärtskompatibilität mit gespeicherten Historien.
    """
    parts = msg.get("parts", [])
    if parts and isinstance(parts, list):
        return parts[0].get("text", "") if parts else ""
    return ""


def _parse_json_safe(raw: str, fallback: Any = None) -> Any:
    """
    Robustes JSON-Parsing mit mehreren Fallback-Strategien.

    Strategie 1: Direktes Parsing
    Strategie 2: Markdown-Fences entfernen (```json ... ```)
    Strategie 3: Erstes { } oder [ ] Paar extrahieren
    """
    # Strategie 1: Direktes Parsing
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Strategie 2: Markdown-Fences entfernen
    cleaned = re.sub(r"```(?:json)?\s*", "", raw).replace("```", "").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Strategie 3: JSON-Block extrahieren
    for pattern in [r"\{.*\}", r"\[.*\]"]:
        match = re.search(pattern, cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

    logger.warning(f"⚠️ JSON-Parsing fehlgeschlagen. Raw: {raw[:200]}...")
    return fallback