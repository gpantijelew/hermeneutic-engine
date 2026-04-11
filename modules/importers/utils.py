"""
utils.py (v49.5 - Minimale Ergänzung zu Grigoris Version)

Änderungen:
- PLATFORM_MARKERS erweitert um 'wikisource' und 'deepseek'
- Alle anderen Funktionen bleiben unverändert (Confidence-Score, Diagnostics)
"""

import os
from google import genai
from typing import Tuple, Optional, Dict, List

# Marker (aus alter importer.py) + ERGÄNZUNGEN
PLATFORM_MARKERS = {
    'chatgpt': ['data-testid="conversation-turn-'],
    'kimi': ['chat-content-item-user', 'chat-content-item-assistant'],
    'claude': ['font-user-message', 'font-claude-message'],
    'gemini': ['message-box', 'ai-markdown-artifact-renderer', 'bard-chat-ui', 'markdown-main-panel'],
    'hotbot': ['tyn-qa-item', 'tyn-qa-item-usr'],
    'lmarena': ['data-sentry-component="SideBySideOrStackedMessageGroup"', 'bg-surface-primary relative flex w-full'],
    
    # NEU v49.5: DeepSeek
    'deepseek': ['ds-message-item', 'ds-chat-container', 'deepseek-chat'],
    
    # NEU v49.5: Wikisource/MediaWiki
    'wikisource': [
        'mw-parser-output',        # Haupt-Content-Container
        'mediawiki',                # Generator-Meta-Tag (oft im <head>)
        'mw-content-text',          # Content-Wrapper
        'ws-noexport'               # Wikisource-spezifisch
    ]
}

def detect_platform(html_content: bytes) -> Tuple[Optional[str], float, Dict]:
    """
    Erkennt die Plattform anhand von HTML-Signaturen.
    
    Returns:
        Tuple: (platform_name, confidence, diagnostics)
        - platform_name: String (z.B. 'chatgpt') oder None
        - confidence: Float 0.0-1.0 (Anteil gefundener Marker)
        - diagnostics: Dict mit gefundenen Signaturen pro Plattform
    """
    # JSON-Erkennung (vor HTML-Analyse)
    try:
        json_str = html_content.decode('utf-8', errors='ignore').strip()
        if json_str.startswith('{'):
            import json as _json
            data = _json.loads(json_str)
            if data.get('exportType') == 'combined' and 'dialogue' in data:
                return 'gemini_json', 1.0, {'gemini_json': ['exportType', 'dialogue']}
    except Exception:
        pass

    try:
        html_str = html_content.decode('utf-8', errors='ignore').lower()
    except Exception:
        return None, 0.0, {}    
    found_signatures = {}
    
    for platform, signatures in PLATFORM_MARKERS.items():
        matches = [sig for sig in signatures if sig in html_str]
        if matches:
            found_signatures[platform] = len(matches)
    
    if not found_signatures:
        return None, 0.0, {}
    
    best_match_platform = max(found_signatures, key=found_signatures.get)
    confidence = found_signatures[best_match_platform] / len(PLATFORM_MARKERS[best_match_platform])
    
    # Diagnostics: Welche Signaturen wurden gefunden?
    diag_signatures = {
        p: [s for s in PLATFORM_MARKERS[p] if s in html_str] 
        for p in found_signatures
    }
    
    return best_match_platform, confidence, diag_signatures


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
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')[:500]
            context_text += f"{role}: {content}\n"

        api_key = os.environ.get('GEMINI_API_KEY', '')
        if not api_key:
            return "Analyse (Kein API Key)"

        # --- NEUES SDK: Client statt GenerativeModel ---
        client = genai.Client(api_key=api_key)
        
        response = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=f"Fasse das Thema dieses Chats in maximal 3-5 Worten zusammen. Chat:\n{context_text}"
        )
        
        return response.text.strip()
    
    except Exception:
        return "Analyse"