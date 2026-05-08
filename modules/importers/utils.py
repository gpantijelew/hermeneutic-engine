"""
utils.py (v52 - Minimale Ergänzung zu Grigoris Version)

Änderungen:
- PLATFORM_MARKERS erweitert um 'wikisource' und 'deepseek'
- Alle anderen Funktionen bleiben unverändert (Confidence-Score, Diagnostics)
"""
import os
from modules.llm_wrapper import llm_call
from typing import Tuple, Optional, Dict, List, Any

# Marker (aus alter importer.py) + ERGÄNZUNGEN
PLATFORM_MARKERS = {
    "chatgpt": ['data-testid="conversation-turn-'],
    "kimi": ["chat-content-item-user", "chat-content-item-assistant"],
    "claude": ["font-user-message", "font-claude-message"],
    "gemini": [
        "message-box",
        "ai-markdown-artifact-renderer",
        "bard-chat-ui",
        "markdown-main-panel",
    ],
    "hotbot": ["tyn-qa-item", "tyn-qa-item-usr"],
    "lmarena": [
        'data-sentry-component="SideBySideOrStackedMessageGroup"',
        "bg-surface-primary relative flex w-full",
    ],
    # NEU v49.5: DeepSeek
    "deepseek": ["ds-message-item", "ds-chat-container", "deepseek-chat"],
    # NEU v49.5: Wikisource/MediaWiki
    "wikisource": [
        "mw-parser-output",  # Haupt-Content-Container
        "mediawiki",  # Generator-Meta-Tag (oft im <head>)
        "mw-content-text",  # Content-Wrapper
        "ws-noexport",  # Wikisource-spezifisch
    ],
    # NEU: Grok, Perplexity, GLM (v52.1)
    "grok": ["grok.com", "x.ai", "response-content-markdown", "message-bubble"],
    "perplexity": ["perplexity.ai", "group/query", "prose dark:prose-invert", "pplx-icon"],
    "glm": ["glm-chat-item", "zhipu-ai-response"],
}

# JSON-Struktur-Signaturen für Auto-Detection
JSON_SIGNATURES = {
    "gemini_json": ("exportType", "dialogue"),
    "chatgpt_json": ("conversations", "mapping"),
    "claude_json": ("chat_messages", "sender"),
}


def detect_platform(
    content: bytes, file_path: Optional[str] = None
) -> Tuple[Optional[str], float, Dict]:
    """
    Erkennt die Plattform anhand von HTML/JSON-Signaturen und File-Extension.

    Returns:
        Tuple: (platform_name, confidence, diagnostics)
        - platform_name: String (z.B. 'chatgpt') oder None
        - confidence: Float 0.0-1.0 (Anteil gefundener Marker)
        - diagnostics: Dict mit gefundenen Signaturen pro Plattform
    """
    diagnostics: Dict[str, Any] = {}

    # ── 1. File-Extension als schwacher Hinweis ──────────────────────────
    ext_hint: Optional[str] = None
    if file_path:
        ext = os.path.splitext(file_path)[1].lower()
        ext_map = {
            ".pdf": "pdf",
            ".epub": "epub",
            ".fb2": "fb2",
            ".md": "markdown",
            ".markdown": "markdown",
            ".json": "json_probe",
            ".html": "html_probe",
            ".htm": "html_probe",
        }
        ext_hint = ext_map.get(ext)
        diagnostics["extension"] = ext
        diagnostics["ext_hint"] = ext_hint

    # ── 2. JSON-Erkennung (vor HTML-Analyse) ─────────────────────────────
    try:
        text = content.decode("utf-8", errors="ignore").strip()
        if text.startswith("{") or text.startswith("["):
            import json as _json

            data = _json.loads(text)
            # Gemini JSON
            if isinstance(data, dict) and data.get("exportType") == "combined" and "dialogue" in data:
                return "gemini_json", 1.0, {**diagnostics, "gemini_json": ["exportType", "dialogue"]}
            # ChatGPT JSON (v50.7 Export-Format)
            if isinstance(data, dict) and "conversations" in data and any(
                "mapping" in c for c in data.get("conversations", []) if isinstance(c, dict)
            ):
                return "chatgpt_json", 1.0, {**diagnostics, "chatgpt_json": ["conversations", "mapping"]}
            # Claude JSON
            if isinstance(data, dict) and "chat_messages" in data and any(
                "sender" in m for m in data.get("chat_messages", []) if isinstance(m, dict)
            ):
                return "claude_json", 1.0, {**diagnostics, "claude_json": ["chat_messages", "sender"]}
    except Exception:
        pass

    # ── 3. HTML-Erkennung ───────────────────────────────────────────────
    try:
        html_str = content.decode("utf-8", errors="ignore").lower()
    except Exception:
        return ext_hint or None, 0.1 if ext_hint else 0.0, diagnostics

    found_signatures = {}

    for platform, signatures in PLATFORM_MARKERS.items():
        matches = [sig for sig in signatures if sig in html_str]
        if matches:
            found_signatures[platform] = len(matches)

    if found_signatures:
        best_match = max(found_signatures, key=found_signatures.get)
        confidence = found_signatures[best_match] / len(PLATFORM_MARKERS[best_match])
        diag_signatures = {
            p: [s for s in PLATFORM_MARKERS[p] if s in html_str] for p in found_signatures
        }
        diagnostics.update(diag_signatures)
        return best_match, confidence, diagnostics

    # ── 4. Fallback: Ext-Hinweis ohne Inhaltserkennung ────────────────────
    if ext_hint and ext_hint != "json_probe" and ext_hint != "html_probe":
        return ext_hint, 0.1, diagnostics

    return None, 0.0, diagnostics


def get_topic_summary(history: List[Dict]) -> str:
    """
    Generiert einen kurzen Topic-Summary aus den ersten Messages.

    Args:
        history: Liste von Message-Dicts mit 'role' und 'content'

    Returns:
        String: 3-5 Wort-Zusammenfassung oder "Analyse" (Fallback)
    """
    try:
        context_text = ""
        for msg in history[:4]:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")[:500]
            context_text += f"{role}: {content}\n"

        result = llm_call(
            f"Fasse das Thema dieses Chats in maximal 3-5 Worten zusammen. Chat:\n{context_text}",
            task="title_gen"
        )
        
        return result.strip() if result else "Analyse"

    except Exception:
        return "Analyse"