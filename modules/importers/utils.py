import os
import google.generativeai as genai
from typing import Tuple, Optional, Dict, List

# Marker (aus alter importer.py)
PLATFORM_MARKERS = {
    'chatgpt': ['data-testid="conversation-turn-'],
    'kimi': ['chat-content-item-user', 'chat-content-item-assistant'],
    'claude': ['font-user-message', 'font-claude-message'],
    'gemini': ['message-box', 'ai-markdown-artifact-renderer', 'bard-chat-ui', 'markdown-main-panel'],
    'hotbot': ['tyn-qa-item', 'tyn-qa-item-usr'],
    'lmarena': ['data-sentry-component="SideBySideOrStackedMessageGroup"', 'bg-surface-primary relative flex w-full']
}

# API Key Setup (Redundant, aber sicher ist sicher für Standalone-Nutzung)
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

def detect_platform(html_content: bytes) -> Tuple[Optional[str], float, Dict]:
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
    diag_signatures = {p: [s for s in PLATFORM_MARKERS[p] if s in html_str] for p in found_signatures}

    return best_match_platform, confidence, diag_signatures

def get_topic_summary(history: List[Dict]) -> str:
    try:
        context_text = ""
        for msg in history[:4]:
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')[:500]
            context_text += f"{role}: {content}\n"

        model = genai.GenerativeModel("gemini-2.0-flash-lite-001")
        prompt = f"Fasse das Thema dieses Chats in maximal 3-5 Worten zusammen. Chat:\n{context_text}"
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception:
        return "Analyse"