"""
GeminiJsonImporter — für Exports der Chrome-Extension 'gemini-export'
Format: {"exportType": "combined", "dialogue": [{role, content, id}]}
Fixes:
- role "assistant" → "model"
- role "thought" → überspringen
- UTF-8/Latin-1 Encoding-Fehler korrigieren
"""

import json
from typing import List, Dict, Any
from ftfy import fix_text
from ..base import ConfigBasedImporter


class GeminiJsonImporter(ConfigBasedImporter):
    config_key = "gemini_json"

    @property
    def platform_name(self):
        return "Gemini JSON (Chrome Extension)"

    @property
    def platform_id(self):
        return "gemini_json"

    @property
    def detection_signatures(self):
        return []

    def parse(self, content: Any, **kwargs) -> List[Dict[str, Any]]:
        container = kwargs.get("container")

        # Bytes → String
        if isinstance(content, bytes):
            text = content.decode("utf-8", errors="replace")
        else:
            text = content

        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            if container:
                container.error(f"❌ JSON-Fehler: {e}")
            return []

        dialogue = data.get("dialogue", [])
        messages = []

        for entry in dialogue:
            role = entry.get("role", "")
            content_text = entry.get("content", "")

            # Thought-Blöcke überspringen
            if role == "thought":
                continue

            # Rolle normalisieren
            if role == "assistant":
                role = "model"
            elif role != "user":
                continue

            # Encoding reparieren
            content_text = fix_text(content_text)

            if content_text.strip():
                messages.append({"role": role, "content": content_text.strip()})

        if container:
            user_count = sum(1 for m in messages if m["role"] == "user")
            model_count = sum(1 for m in messages if m["role"] == "model")
            container.success(
                f"✅ {len(messages)} Nachrichten ({user_count} User / {model_count} Model)"
            )

        return messages if self.validate(messages) else []
