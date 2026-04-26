from typing import List, Dict, Any
from ..base import ConfigBasedImporter


class KimiImporter(ConfigBasedImporter):
    config_key = "kimi"

    @property
    def platform_name(self):
        return "Kimi Chat"

    @property
    def platform_id(self):
        return "kimi"

    @property
    def detection_signatures(self):
        return ["kimi", "moonshot", "chat-content-item"]

    def parse(self, content: Any, **kwargs) -> List[Dict[str, Any]]:
        container = kwargs.get("container")
        soup = self.parse_html(content)
        messages = []

        # Suche nach Containern (ignoriert data-v Attribute)
        items = soup.find_all("div", class_=lambda x: x and "chat-content-item" in x)

        if not items:
            if container:
                container.warning("⚠️ Keine Kimi-Nachrichtenblöcke gefunden.")
            return []

        for item in items:
            classes = item.get("class", [])

            # Rolle bestimmen
            role = "model"  # Default
            if any("user" in c for c in classes):
                role = "user"

            # Inhalt finden
            content_div = item.find(class_=lambda x: x and "markdown" in x)

            if not content_div:
                content_div = item.find(
                    class_=lambda x: x and ("text" in x or "content" in x)
                )

            if not content_div:
                content_div = item

            text = content_div.get_text(separator="\n", strip=True)

            # Bereinigung
            if role == "user" and text.startswith("You"):
                text = text[3:].strip()
            elif role == "model" and text.startswith("Kimi"):
                text = text[4:].strip()

            if text:
                messages.append({"role": role, "content": text})

        if container:
            container.success(f"✅ Kimi: {len(messages)} Nachrichten extrahiert.")

        return messages
