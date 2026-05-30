# modules/llm_wrapper.py — v52: Universeller LLM-Wrapper
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
import threading
from queue import Queue, Empty
from typing import Optional, Any

# Streamlit optional — llm_wrapper funktioniert auch ohne laufende ST-Session
try:
    import streamlit as st
    from streamlit.runtime.scriptrunner import get_script_run_ctx
    _STREAMLIT_AVAILABLE = True
except ImportError:
    _STREAMLIT_AVAILABLE = False

from modules.config import (
    LLM_BACKEND,
    get_llm_client,
    MAX_TOKENS_PER_CALL,
)

# Marker-Objekt für interne JSON-Parse-Failure-Erkennung (Retry-Logik)
_JSON_PARSE_FAILED = object()


# --- A.2: DETERMINISTIC PIPELINE MODE ---

def _get_backend_type() -> str:
    """Ermittelt das aktive Backend robust."""
    from modules.config import LLM_BACKEND
    if LLM_BACKEND == "lmstudio":
        return "lmstudio"
    elif LLM_BACKEND == "openai":
        return "openai"
    return "vertex"


def _apply_domain_profile(
    kwargs: dict, domain: str, backend: str
) -> dict:
    """Injiziert das Parameter-Profil basierend auf der Domain."""
    from modules.config import DOMAIN_PROFILES, BACKEND_CAPABILITIES

    profile = DOMAIN_PROFILES.get(domain)
    if not profile:
        return kwargs

    caps = BACKEND_CAPABILITIES.get(backend, {"seed": False})

    if "temperature" in profile:
        kwargs["temperature"] = profile["temperature"]
    if "top_p" in profile:
        kwargs["top_p"] = profile["top_p"]

    if "seed" in profile and caps.get("seed"):
        kwargs["seed"] = profile["seed"]

    return kwargs

# ==============================================================================
# THREAD-SICHERE STATISTIK-SAMMLUNG
# ==============================================================================
_stats_queue: Queue = Queue()
_stats_thread_local = threading.local()

def _get_thread_local_stats() -> list:
    if not hasattr(_stats_thread_local, "call_stats"):
        _stats_thread_local.call_stats = []
    return _stats_thread_local.call_stats

def _enqueue_stat(stat_entry: dict) -> None:
    """Schreibt einen Statistik-Eintrag absolut thread-sicher ohne Streamlit-Warnungen."""
    # 1. Prüfen, ob wir im Streamlit-Haupt-Thread sind (verhindert die rote Warnung!)
    if _STREAMLIT_AVAILABLE:
        ctx = get_script_run_ctx()

        if ctx is not None:
            # Wir sind im Haupt-Thread -> Direkter Schreibzugriff
            try:
                if "call_stats" in st.session_state:
                    st.session_state.call_stats.append(stat_entry)
                    return
            except Exception:
                pass

    # 2. Wir sind in einem Neben-Thread -> Ab in die Queue
    try:
        _stats_queue.put(stat_entry, block=False)
    except Exception:
        pass

    # 3. Fallback
    _get_thread_local_stats().append(stat_entry)

def drain_stats_to_session_state() -> int:
    count = 0
    if not _STREAMLIT_AVAILABLE:
        # Streamlit nicht verfügbar -> Queue leeren ohne session_state
        while True:
            try:
                _stats_queue.get(block=False)
                count += 1
            except Empty:
                break
        return count
    
    try:
        if "call_stats" not in st.session_state:
            st.session_state.call_stats = []
        while True:
            try:
                stat = _stats_queue.get(block=False)
                st.session_state.call_stats.append(stat)
                count += 1
            except Empty:
                break
    except Exception:
        pass
    return count

def get_session_stats() -> list:
    drain_stats_to_session_state()
    if not _STREAMLIT_AVAILABLE:
        return []
    try:
        return st.session_state.get("call_stats", [])
    except Exception:
        return []

def print_session_summary():
    """Druckt eine lesbare Zusammenfassung in die Konsole."""
    if not _STREAMLIT_AVAILABLE:
        print("⚠️ Streamlit nicht verfügbar - keine Session-Statistik.")
        return
    
    if not st.session_state.call_stats:
        print("Keine Calls in dieser Session.")
        return
    from collections import Counter

    tasks = Counter(s["task"] for s in st.session_state.call_stats)
    backends = Counter(s["backend"] for s in st.session_state.call_stats)
    total_prompt = sum(s.get("prompt_tokens", 0) for s in st.session_state.call_stats)
    total_completion = sum(
        s.get("completion_tokens", 0) for s in st.session_state.call_stats
    )
    print("\n📊 SESSION-STATISTIK")
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

def _vertex_call_with_retry(call_fn, max_retries: int = 3):
    """
    Führt einen Vertex-API-Call mit exponentiellem Backoff durch.
    Fängt stille Quota-Abbrüche (leere oder abgeschnittene Antworten) ab.
    """
    last_exception = None
    for attempt in range(max_retries):
        try:
            result = call_fn()
            # Validierung: War die Antwort vollständig?
            if result is None or (isinstance(result, str) and len(result.strip()) == 0):
                wait = (2 ** attempt) * 1.5
                logger.warning(
                    f"⚠️ Vertex leere Antwort (Versuch {attempt+1}/{max_retries}). "
                    f"Warte {wait:.1f}s..."
                )
                time.sleep(wait)
                continue
            return result
        except Exception as e:
            last_exception = e
            wait = (2 ** attempt) * 2
            logger.warning(
                f"⚠️ Vertex-Fehler (Versuch {attempt+1}/{max_retries}): {e}. "
                f"Warte {wait:.1f}s..."
            )
            time.sleep(wait)
    
    if last_exception:
        raise last_exception
    return ""

def _vertex_call(
    client,
    model: str,
    sys_msg: str,
    messages: list,
    temperature: float,
    max_tokens: int,
    seed: Optional[int] = None,
    top_p: float = 0.95,
) -> str:
    """Übersetzt den OpenAI-Message-Stack in Vertex AI generate_content()."""
    from google.genai.types import (
        GenerateContentConfig,
        Content,
        Part,
        AutomaticFunctionCallingConfig,
    )

    contents = []
    for msg in messages:
        if msg["role"] == "system":
            continue  # System-Instruction geht in config, nicht contents
        role = "user" if msg["role"] == "user" else "model"
        contents.append(Content(role=role, parts=[Part(text=msg["content"])]))

    # --- TICKET 11: Prompt-Monitoring (Claudes sichere Version) ---
    total_chars = sum(
        len(part.text)
        for c in contents
        for part in c.parts
        if hasattr(part, "text") and part.text
    )
    logger.info(f"📋 [PROMPT-MONITOR] Turns: {len(contents)} | Zeichen: {total_chars}")
    if total_chars > 50000:
        logger.warning(f"⚠️ [PROMPT-MONITOR] Großer Payload: {total_chars} Zeichen")
    # --------------------------------------------------------------

    config_kwargs = dict(
        system_instruction=sys_msg,
        temperature=temperature,
        top_p=top_p,
        max_output_tokens=max_tokens,
        automatic_function_calling=AutomaticFunctionCallingConfig(disable=True),
    )
    if seed is not None:
        config_kwargs["seed"] = seed

    config = GenerateContentConfig(**config_kwargs)

    response = _vertex_call_with_retry(
        lambda: client.models.generate_content(
            model=model, contents=contents, config=config
        )
    )

    if not response:
        return ""

    # --- Token Tracking für Text-Generierung ---
    try:
        usage = getattr(response, "usage_metadata", None)
        if usage:
            p_tokens = getattr(usage, "prompt_token_count", 0)
            c_tokens = getattr(usage, "candidates_token_count", 0)
            _enqueue_stat({
                "task": "vertex_direct",
                "backend": "vertex",
                "prompt_tokens": p_tokens,
                "completion_tokens": c_tokens,
                "timestamp": time.time(),
            })
            logger.info(f"[vertex_direct] Tokens — Prompt: {p_tokens}, Completion: {c_tokens}")
    except Exception as e:
        logger.debug(f"Konnte Vertex-Tokens nicht loggen: {e}")

    return response.text


def _vertex_call_streaming(
    client,
    model: str,
    sys_msg: str,
    messages: list,
    temperature: float,
    max_tokens: int,
    use_search: bool = False,  # <--- NEU
    seed: Optional[int] = None,
    top_p: float = 0.95,
):
    """Übersetzt den OpenAI-Message-Stack in Vertex AI generate_content_stream()."""
    from google.genai.types import (
        GenerateContentConfig,
        Content,
        Part,
        Tool,  # <--- NEU
        GoogleSearch,  # <--- NEU
    )

    contents = []
    for msg in messages:
        if msg["role"] == "system":
            continue
        role = "user" if msg["role"] == "user" else "model"
        contents.append(Content(role=role, parts=[Part(text=msg["content"])]))

    # --- Google Search Grounding ---
    tools = [Tool(google_search=GoogleSearch())] if use_search else None
    config_kwargs = dict(
        system_instruction=sys_msg,
        temperature=temperature,
        top_p=top_p,
        max_output_tokens=max_tokens,
    )
    if tools:
        config_kwargs["tools"] = tools
    if seed is not None:
        config_kwargs["seed"] = seed
    from google.genai.types import AutomaticFunctionCallingConfig

    config_kwargs["automatic_function_calling"] = AutomaticFunctionCallingConfig(
        disable=True
    )

    stream = client.models.generate_content_stream(
        model=model, contents=contents, config=GenerateContentConfig(**config_kwargs)
    )

    p_tokens = 0
    c_tokens = 0
    for chunk in stream:
        if chunk.text:
            try:
                if hasattr(chunk, "usage_metadata") and chunk.usage_metadata:
                    p_tokens = getattr(chunk.usage_metadata, "prompt_token_count", 0)
                    c_tokens = getattr(
                        chunk.usage_metadata, "candidates_token_count", 0
                    )
            except Exception:
                pass
            yield chunk.text

    try:
        stat_entry = {
            "task": "vertex_streaming",
            "backend": "vertex",
            "prompt_tokens": p_tokens,
            "completion_tokens": c_tokens,
            "timestamp": time.time(),
        }
        _enqueue_stat(stat_entry)
    except Exception:
        pass

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
    top_p: float = 0.95,
    domain: str = None,
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
        top_p:              Nucleus-Sampling (default: 0.95)
        domain:             A.2 Domain-Profil (analysis_pipeline, ifs_resonanzraum, etc.)

    Returns:
        Antwort-Text als String. Bei Fehler: leerer String.

    Raises:
        Kein raise — Fehler werden geloggt und als "" zurückgegeben.
        Aufrufende Module müssen auf leeren String prüfen.
    """
    try:
        client, model = get_llm_client(task=task)
        sys_msg = system_instruction or _get_system_instruction()

        # --- A.2: DETERMINISTIC PIPELINE MODE ---
        backend_type = _get_backend_type()
        call_params = {"temperature": temperature, "top_p": top_p}
        if domain:
            call_params = _apply_domain_profile(call_params, domain, backend_type)
        temperature = call_params.get("temperature", temperature)
        top_p = call_params.get("top_p", top_p)
        seed = call_params.get("seed")

        # Messages aufbauen
        messages = [{"role": "system", "content": sys_msg}]

        # Konversationshistorie einfügen (falls vorhanden)
        if history:
            for turn in history:
                role = turn.get("role", "user")
                if role == "model":  # Gemini-Relikt - OpenAI normalisieren
                    role = "assistant"
                content = turn.get("content", "") or _extract_text_from_parts(turn)
                if content:
                    messages.append({"role": role, "content": content})

        messages.append({"role": "user", "content": prompt})

        # Vertex AI: anderes SDK, anderer Response-Typ
        if LLM_BACKEND == "vertex":
            return _vertex_call(
                client, model, sys_msg, messages, temperature, max_tokens,
                seed=seed, top_p=top_p,
            )

        openai_kwargs = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p,
        }
        if seed is not None:
            openai_kwargs["seed"] = seed

        response = client.chat.completions.create(**openai_kwargs)

        result = response.choices[0].message.content.strip()
        # --- TICKET 1b: THREAD-SAFE STATS ---
        try:
            stat_entry = {
                "task": task,
                "backend": LLM_BACKEND,
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "timestamp": time.time(),
            }
            _enqueue_stat(stat_entry)
        except Exception:
            pass  # Im Async-Thread (Enforcer) ignorieren wir die Statistik einfach, um Crashes zu vermeiden

        # Token-Logging (hilfreich für Debugging)
        usage = response.usage
        reasoning = getattr(usage.completion_tokens_details, "reasoning_tokens", 0) or 0
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
    domain: str = None,
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
    sys_msg = system_instruction or _get_system_instruction()

    # Retry-Loop für JSON-Cutoffs (max. 3 Versuche)
    _MAX_JSON_RETRIES = 3
    for attempt in range(1, _MAX_JSON_RETRIES + 1):
        raw = llm_call(
            prompt=full_prompt,
            task=task,
            system_instruction=sys_msg,
            temperature=temperature,
            max_tokens=max_tokens,
            domain=domain,
        )

        if not raw:
            return fallback

        try:
            # JSON parsen — echtes Fallback, damit wir Cutoff vs. echtes Ergebnis unterscheiden
            result = _parse_json_safe(raw, fallback=fallback)
            # Wenn Parsing fehlschlägt UND der Raw-Text wie ein Cutoff aussieht → Retry triggern
            if result == fallback and _is_json_cutoff(raw):
                raise ValueError("JSON Cutoff detected")
            return result  # Erfolg
        except Exception:
            if attempt < _MAX_JSON_RETRIES:
                logger.warning(f"JSON Cutoff erkannt, starte Retry {attempt}/{_MAX_JSON_RETRIES}...")
                time.sleep(0.5 * attempt)  # Lokaler Backoff: 0.5s, 1.0s
            else:
                logger.error(f"JSON-Parsing nach {_MAX_JSON_RETRIES} Versuchen fehlgeschlagen")

    return fallback


def llm_call_streaming(
    prompt: str,
    task: str = "chat",
    system_instruction: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = MAX_TOKENS_PER_CALL,  # v51: aus config.py
    history: Optional[list] = None,
    use_search: bool = False,  # <--- NEU
    top_p: float = 0.95,
    domain: str = None,
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

        # --- A.2: DETERMINISTIC PIPELINE MODE ---
        backend_type = _get_backend_type()
        call_params = {"temperature": temperature, "top_p": top_p}
        if domain:
            call_params = _apply_domain_profile(call_params, domain, backend_type)
        temperature = call_params.get("temperature", temperature)
        top_p = call_params.get("top_p", top_p)
        seed = call_params.get("seed")

        messages = [{"role": "system", "content": sys_msg}]

        if history:
            for turn in history:
                role = turn.get("role", "user")
                if role == "model":  # Gemini-Relikt - OpenAI normalisieren
                    role = "assistant"
                content = turn.get("content", "") or _extract_text_from_parts(turn)
                if content:
                    messages.append({"role": role, "content": content})

        messages.append({"role": "user", "content": prompt})

        # Vertex AI: anderes SDK, anderer Response-Typ
        if LLM_BACKEND == "vertex":
            yield from _vertex_call_streaming(
                client,
                model,
                sys_msg,
                messages,
                temperature,
                max_tokens,
                use_search=use_search,  # <--- NEU
                seed=seed,
                top_p=top_p,
            )
            return

        openai_kwargs = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p,
            "stream": True,
        }
        if seed is not None:
            openai_kwargs["seed"] = seed

        stream = client.chat.completions.create(**openai_kwargs)

        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    except Exception as e:
        logger.error(f"❌ Streaming-Fehler [{task}]: {e}")
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


def _parse_json_safe(raw_text: str, fallback: Any = None) -> Any:
    """
    Versucht, JSON aus einem String zu extrahieren, selbst wenn das Modell
    Markdown-Blöcke (```json) oder 'lautes Denken' (Chain-of-Thought) davor/danach packt.
    Sucht gezielt nach dem ersten '[' und dem letzten ']'.
    """
    if not raw_text:
        return fallback

    text = raw_text.strip()

    # 1. Versuch: Direkter Parse (falls es schon sauberes JSON ist)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2. Versuch: Markdown-Blöcke entfernen
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

    # 3. Versuch: Brute-Force Regex für JSON-Arrays [...]
    # Sucht das erste '[' und das letzte ']' im gesamten Text
    import re
    match = re.search(r'\[.*\]', raw_text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
            
    # 4. Versuch: Brute-Force Regex für JSON-Objekte {...}
    match = re.search(r'\{.*\}', raw_text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    logger.error(f"JSON-Parsing endgültig fehlgeschlagen. Raw: {raw_text[:100]}...")
    return fallback


def llm_call_vision(
    images: list,
    user_question: str,
    image_origin: str = "photograph",
    system_instruction: Optional[str] = None,
    temperature: float = 0.3,
    top_p: float = 0.95,
    domain: str = None,
    seed: Optional[int] = None,
) -> str:
    """
    Vision-Call: Analysiert ein oder mehrere Bilder mit dem konfigurierten Vision-Modell.
    Nur für LLM_BACKEND='vertex' implementiert.

    Args:
        images: Liste von Dictionaries [{"bytes": bytes, "mime": str}, ...]
        user_question: Frage/Kontext vom User
        image_origin: Ursprungstyp für hermeneutische Regel
        system_instruction: Überschreibt Standard Vision-Prompt
        temperature: Sampling-Temperatur
        top_p: Nucleus-Sampling (default: 0.95)
        domain: A.2 Domain-Profil
        seed: Deterministischer Seed (A.2)
    """
    if LLM_BACKEND != "vertex":
        logger.error("❌ llm_call_vision: Nur für LLM_BACKEND='vertex' verfügbar.")
        return ""

    if not images:
        logger.error("❌ llm_call_vision: Keine Bilder übergeben.")
        return ""

    # Size Check (Vertex Limit ~20MB insgesamt)
    MAX_IMAGE_BYTES = 20 * 1024 * 1024
    total_bytes = sum(len(img["bytes"]) for img in images)
    if total_bytes > MAX_IMAGE_BYTES:
        logger.error(f"❌ Bilder zu groß insgesamt: {total_bytes / (1024*1024):.1f} MB (Max: 20 MB)")
        return ""

    try:
        from google.genai.types import (
            GenerateContentConfig,
            Content,
            Part,
        )

        client, model = get_llm_client(task="synthesis")
        
        # System-Instruction sicherstellen und Origin-Regel injizieren
        from modules.prompt_manager import PromptManager
        pm = PromptManager()
        
        if not system_instruction:
            system_instruction = pm.get_vision_instruction()
            
        origin_rule = pm.get_vision_origin_rule(image_origin)
        if origin_rule:
            system_instruction = system_instruction.rstrip() + "\n\n" + origin_rule

        # Parts dynamisch aufbauen: Erst alle Bilder, dann den Text
        content_parts = []
        for img in images:
            image_part = Part.from_bytes(data=img["bytes"], mime_type=img["mime"])
            content_parts.append(image_part)
        
        # Fallback-Prompt, falls User leer gelassen
        final_question = user_question
        if not final_question:
            if len(images) >= 2:
                final_question = "Analysiere und vergleiche diese beiden Bilder präzise nach dem Protokoll."
            else:
                final_question = "Analysiere dieses Bild nach dem Protokoll."
                
        text_part = Part(text=final_question)
        content_parts.append(text_part)

        contents = [
            Content(role="user", parts=content_parts)
        ]

        # --- A.2: DETERMINISTIC PIPELINE MODE ---
        backend_type = _get_backend_type()
        call_params = {"temperature": temperature, "top_p": top_p}
        if domain:
            call_params = _apply_domain_profile(call_params, domain, backend_type)
        temperature = call_params.get("temperature", temperature)
        top_p = call_params.get("top_p", top_p)
        seed = call_params.get("seed", seed)

        config_kwargs = dict(
            system_instruction=system_instruction,
            temperature=temperature,
            top_p=top_p,
            max_output_tokens=8192,
        )
        if seed is not None:
            config_kwargs["seed"] = seed

        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=GenerateContentConfig(**config_kwargs),
        )

        result = (response.text or "").strip()
        logger.info(f"✅ Vision-Call abgeschlossen ({len(images)} Bilder). Protokoll-Länge: {len(result)} Zeichen")
        return result

    except Exception as e:
        logger.error(f"❌ Vision-Call fehlgeschlagen: {e}")
        return ""

def llm_call_json_structured(
    prompt: str,
    response_schema,  # Erwartet ein Pydantic-Modell
    system_instruction: Optional[str] = None,
    temperature: float = 0.1,
    task: str = "reranker",
    top_p: float = 0.95,
    domain: str = None,
    seed: Optional[int] = None,
) -> dict:
    """
    Structured Output Call: Zwingt Vertex AI, EXAKT das übergebene JSON-Schema zurückzugeben.
    Keine Base64-Halluzinationen mehr. Kein String-Parsing.
    Nur für LLM_BACKEND='vertex' implementiert.
    """
    if LLM_BACKEND != "vertex":
        logger.error("❌ llm_call_json_structured: Nur für LLM_BACKEND='vertex' verfügbar.")
        return {}

    try:
        from google.genai.types import (
            GenerateContentConfig,
            AutomaticFunctionCallingConfig
        )

        client, model = get_llm_client(task=task)

        # --- A.2: DETERMINISTIC PIPELINE MODE ---
        backend_type = _get_backend_type()
        call_params = {"temperature": temperature, "top_p": top_p}
        if domain:
            call_params = _apply_domain_profile(call_params, domain, backend_type)
        temperature = call_params.get("temperature", temperature)
        top_p = call_params.get("top_p", top_p)
        seed = call_params.get("seed", seed)

        config_kwargs = dict(
            system_instruction=system_instruction,
            temperature=temperature,
            top_p=top_p,
            max_output_tokens=8192,
            response_mime_type="application/json",
            response_schema=response_schema,
            automatic_function_calling=AutomaticFunctionCallingConfig(disable=True),
        )
        if seed is not None:
            config_kwargs["seed"] = seed

        config = GenerateContentConfig(**config_kwargs)

        response = _vertex_call_with_retry(
            lambda: client.models.generate_content(
                model=model,
                contents=prompt,
                config=config
            )
        )
        if not response:
            return {}

        # --- NEU: Token Tracking für Structured Outputs (Reranker) ---
        try:
            usage = getattr(response, "usage_metadata", None)
            if usage:
                p_tokens = getattr(usage, "prompt_token_count", 0)
                c_tokens = getattr(usage, "candidates_token_count", 0)
                _enqueue_stat({
                    "task": task,
                    "backend": "vertex_structured",
                    "prompt_tokens": p_tokens,
                    "completion_tokens": c_tokens,
                    "timestamp": time.time(),
                })
        except Exception as e:
            logger.debug(f"Konnte Structured Tokens nicht loggen: {e}")

        if hasattr(response, 'parsed') and response.parsed is not None:
            return response.parsed.model_dump() if hasattr(response.parsed, 'model_dump') else dict(response.parsed)
        elif response.text:
            import json
            try:
                return json.loads(response.text)
            except json.JSONDecodeError:
                logger.error(f"❌ Structured Output lieferte ungültiges JSON: {response.text[:200]}")
                return {}
        else:
            # Leere Antwort - logge den kompletten Response-Status
            logger.error(f"❌ Structured Output lieferte leere Antwort. Response: {response}")
            logger.error(f"❌ Prompt (erste 200 Zeichen): {prompt[:200]}")
            return {}

    except Exception as e:
        logger.error(f"❌ Structured JSON Call fehlgeschlagen: {e}")
        return {}