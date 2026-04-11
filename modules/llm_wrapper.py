# modules/llm_wrapper.py — v52: Universeller LLM-Wrapper (Local-First)
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
import time
from typing import Optional, Dict, Any
import streamlit as st

from modules.config import (
    LLM_BACKEND,
    get_llm_client,
    get_model_for_task,
    MAX_TOKENS_PER_CALL,
)

# Session-Statistik (wird nicht persistiert)
# TEMPORÄR: Nur für Terminal-Debugging.
# Für persistente UI-Statistik → st.session_state['call_stats'] (Ticket 1b)
# Wird bei jedem Modul-Reload geleert.

def get_session_stats() -> list:
    """Gibt alle LLM-Calls der aktuellen Session zurück."""
    return st.session_state.call_stats

def print_session_summary():
    """Druckt eine lesbare Zusammenfassung in die Konsole."""
    if not st.session_state.call_stats:
        print("Keine Calls in dieser Session.")
        return
    from collections import Counter
    tasks = Counter(s["task"] for s in st.sesion_state.call_stats)
    backends = Counter(s["backend"] for s in st.session_state.call_stats)
    total_prompt = sum(s.get("prompt_tokens", 0) for s in st.session_state.call_stats)
    total_completion = sum(s.get("completion_tokens", 0) for s in st.session_state.call_stats)
    print(f"\n📊 SESSION-STATISTIK")
    print(f"Calls gesamt: {len(st.session_state.call_stats)}")
    print(f"Nach Task: {dict(tasks)}")
    print(f"Nach Backend: {dict(backends)}")
    print(f"Tokens Prompt: {total_prompt} | Completion: {total_completion}")

logger = logging.getLogger(__name__)

# ==============================================================================
# SYSTEM INSTRUCTION
# ==============================================================================

def _get_system_instruction() -> str:
    prefix = ""
    if LLM_BACKEND == "lmstudio":
        prefix = os.getenv("LLM_SYSTEM_PREFIX", "/no_think") + "\n"
    
    hre_context = (
        "Du bist ein präziser Forschungsassistent der "
        "Hermeneutic Reconstruction Engine (HRE). "
        "Antworte prägnant, analytisch und ohne Ausweichen."
    )
    return f"{prefix}{hre_context}"

# ==============================================================================
# VERTEX AI BACKEND
# ==============================================================================

def _vertex_call(
    client,
    model: str,
    sys_msg: str,
    messages: list,
    temperature: float,
    max_tokens: int,
) -> str:
    """Übersetzt den OpenAI-Message-Stack in Vertex AI generate_content()."""
    from google.genai.types import (
        GenerateContentConfig,
        Content,
        Part,
    )

    contents = []
    for msg in messages:
        if msg["role"] == "system":
            continue  # System-Instruction geht in config, nicht contents
        role = "user" if msg["role"] == "user" else "model"
        contents.append(
            Content(role=role, parts=[Part(text=msg["content"])])
        )

    # --- TICKET 11: Prompt-Monitoring (Claudes sichere Version) ---
    total_chars = sum(
        len(part.text) 
        for c in contents 
        for part in c.parts 
        if hasattr(part, 'text') and part.text
    )
    print(f"📋 [PROMPT-MONITOR] Turns: {len(contents)} | Zeichen: {total_chars}")
    logger.info(f"📋 [PROMPT-MONITOR] Turns: {len(contents)} | Zeichen: {total_chars}")
    if total_chars > 50000:
        logger.warning(f"⚠️ [PROMPT-MONITOR] Großer Payload: {total_chars} Zeichen")
    # --------------------------------------------------------------

    from google.genai.types import AutomaticFunctionCallingConfig

    response = client.models.generate_content(
        model=model,
        contents=contents,
        config=GenerateContentConfig(
            system_instruction=sys_msg,
            temperature=temperature,
            max_output_tokens=max_tokens,
            automatic_function_calling=AutomaticFunctionCallingConfig(
                disable=True,
            )
        )
    )

    # ==========================================
    # 🛑 DIAGNOSE: WARUM HAT GOOGLE ABGEBROCHEN?
    # ==========================================
    try:
        reason = response.candidates[0].finish_reason
        print(f"\n🚨 VERTEX FINISH REASON: {reason} 🚨\n")
    except Exception as e:
        print(f"\n🚨 Konnte Finish Reason nicht lesen: {e} 🚨\n")
    # ==========================================

    return response.text

    # Ticket 3: Sicheres Token-Logging für neues SDK
    try:
        usage = getattr(response, "usage_metadata", None)
        if usage:
            prompt_tokens = getattr(usage, "prompt_token_count", 0)
            completion_tokens = getattr(usage, "candidates_token_count", 0)
            # NEU: Hartes Print für das Terminal + Info-Log
            print(f"📊 [VERTEX TOKENS] Prompt: {prompt_tokens} | Completion: {completion_tokens}")
            logger.info(f"[vertex_direct] Tokens — Prompt: {prompt_tokens}, Completion: {completion_tokens}")
    except Exception as e:
        logger.warning(f"⚠️ Konnte Vertex-Tokens nicht loggen: {e}")
    
    # --- TICKET 1b: THREAD-SAFE STATS (VERTEX) ---
    try:
        if hasattr(st, 'session_state') and 'call_stats' in st.session_state:
            st.session_state.call_stats.append({
                "task": "vertex_direct",
                "backend": "vertex",
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens
            })
    except Exception:
        pass # Im Async-Thread (Reranker) ignorieren wir die Statistik einfach
    return response.text.strip()

def _vertex_call_streaming(
    client,
    model: str,
    sys_msg: str,
    messages: list,
    temperature: float,
    max_tokens: int,
    use_search: bool = False,  # <--- NEU
):
    """Übersetzt den OpenAI-Message-Stack in Vertex AI generate_content_stream()."""
    from google.genai.types import (
        GenerateContentConfig,
        Content,
        Part,
        Tool,
        GoogleSearch,
    )

    contents = []
    for msg in messages:
        if msg["role"] == "system":
            continue
        role = "user" if msg["role"] == "user" else "model"
        contents.append(
            Content(role=role, parts=[Part(text=msg["content"])])
        )

    tools = [Tool(google_search=GoogleSearch())] if use_search else None
    config_kwargs = dict(
        system_instruction=sys_msg,
        temperature=temperature,
        max_output_tokens=max_tokens,
    )
    if tools:
        config_kwargs["tools"] = tools
    from google.genai.types import AutomaticFunctionCallingConfig

    config_kwargs["automatic_function_calling"] = AutomaticFunctionCallingConfig(
        disable=True
    )
   
    stream = client.models.generate_content_stream(
        model=model,
        contents=contents,
        config=GenerateContentConfig(**config_kwargs)
    )

    for chunk in stream:
        if chunk.text:
            yield chunk.text

# --- TICKET 1b: STATS FÜR STREAMING (SAUBER) ---
    if 'call_stats' in st.session_state:
        p_tokens = 0
        c_tokens = 0
        try:
            # Vertex schickt die Token-Abrechnung meist im allerletzten Chunk des Streams mit
            if chunk and hasattr(chunk, "usage_metadata") and chunk.usage_metadata:
                p_tokens = getattr(chunk.usage_metadata, "prompt_token_count", 0)
                c_tokens = getattr(chunk.usage_metadata, "candidates_token_count", 0)
        except Exception:
            pass # Fallback, falls Vertex die Tokens im Stream verschluckt

        st.session_state.call_stats.append({
            "task": "vertex_streaming",
            "backend": "vertex",
            "prompt_tokens": p_tokens,
            "completion_tokens": c_tokens
        })

# ==============================================================================
# KERN-FUNKTIONEN
# ==============================================================================

def llm_call(
    prompt: str,
    task: str = "synthesis",
    system_instruction: Optional[str] = None,
    temperature: float = 0.3,
    max_tokens: int = MAX_TOKENS_PER_CALL,  # v51: aus config.py
    history: Optional[list] = None,
) -> str:
    """
    Universeller LLM-Aufruf — gibt Text zurück.

    Args:
        prompt:             Der eigentliche Prompt / User-Turn
        task:               Task-Key für Modellauswahl (aus config.py)
        system_instruction: Überschreibt Standard-Instruction (optional)
        temperature:        Sampling-Temperatur (default: 0.3)
        max_tokens:         Max Output-Tokens (default: MAX_TOKENS_PER_CALL)
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
        client, model = get_llm_client(task=task)
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

        # Vertex AI: anderes SDK, anderer Response-Typ
        if LLM_BACKEND == "vertex":
            return _vertex_call(client, model, sys_msg, messages, temperature, max_tokens)

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        result = response.choices[0].message.content.strip()
        # --- TICKET 1b: THREAD-SAFE STATS ---
        try:
            st.session_state.call_stats.append({
                "task": task,
                "backend": LLM_BACKEND,
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "timestamp": time.time()
            })
        except Exception:
            pass # Im Async-Thread (Enforcer) ignorieren wir die Statistik einfach, um Crashes zu vermeiden

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
    max_tokens: int = MAX_TOKENS_PER_CALL,
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
    max_tokens: int = MAX_TOKENS_PER_CALL,  # v51: aus config.py
    history: Optional[list] = None,
    use_search: bool = False,  # <--- NEU
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
        client, model = get_llm_client(task=task)
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

        # Vertex AI: anderes SDK, anderer Response-Typ
        if LLM_BACKEND == "vertex":
            yield from _vertex_call_streaming(
                client, model, sys_msg, messages, temperature, max_tokens,
                use_search=use_search  # <--- NEU
            )
            return

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
