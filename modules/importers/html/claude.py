from typing import List, Dict, Any
from ..base import ConfigBasedImporter


class ClaudeImporter(ConfigBasedImporter):
    @property
    def platform_name(self):
        return "Claude (Anthropic)"

    @property
    def platform_id(self):
        return "claude"

    @property
    def detection_signatures(self):
        return ["font-claude-message", "chat-ui-core", "anthropic", "font-user-message"]

    def parse(self, content: Any, **kwargs) -> List[Dict[str, Any]]:
        container = kwargs.get("container")
        soup = self.parse_html(content)
        messages = []

        # --- STRATEGIE 1: Präzise Selektoren ---
        all_divs = soup.find_all("div")

        for div in all_divs:
            role = None
            text = ""

            # 1. Check User
            if div.get("data-testid") == "user-message":
                role = "user"
                text_elem = div.find("p", class_="whitespace-pre-wrap")
                if text_elem:
                    text = text_elem.get_text(separator="\n", strip=True)
                else:
                    text = div.get_text(separator="\n", strip=True)

            # 2. Check Model (Claude)
            elif "font-claude-response" in div.get("class", []):
                role = "model"
                # Wir suchen nach dem Inhalt.
                # WICHTIG: Wir nehmen den ganzen Text des Containers, um Artifacts nicht zu verlieren.
                text = div.get_text(separator="\n", strip=True)

                # --- NEU: Fix für die doppelte erste Zeile (Claude DOM-Anomalie) ---
                if text:
                    # Zerlegen und leere Zeilen ignorieren, um die echten ersten zwei Zeilen zu finden
                    lines = text.split("\n")
                    non_empty_lines = [l.strip() for l in lines if l.strip()]

                    if (
                        len(non_empty_lines) >= 2
                        and non_empty_lines[0] == non_empty_lines[1]
                    ):
                        # Wenn die erste und zweite Zeile identisch sind,
                        # entfernen wir das ERSTE Vorkommen dieser Zeile aus dem Originaltext.
                        # Wir nutzen replace mit count=1, um die Formatierung (Leerzeilen) danach zu erhalten.
                        text = text.replace(non_empty_lines[0], "", 1).lstrip()

            # --- SPEICHERN & DEDUPLIZIERUNG ---
            if role and text:
                # 1. Exakte Duplikate verhindern
                if messages and messages[-1]["content"] == text:
                    continue

                # 2. Fragmente verhindern (Der Fix!)
                # Wenn der neue Text im vorherigen Text enthalten ist (und kürzer ist),
                # dann ist es wahrscheinlich nur ein Kind-Element, das wir schon haben.
                if (
                    messages
                    and text in messages[-1]["content"]
                    and len(text) < len(messages[-1]["content"])
                ):
                    continue

                # Bereinigung
                if role == "user" and text.startswith("User"):
                    text = text[4:].strip()

                messages.append({"role": role, "content": text})

        if messages:
            if container:
                container.success(
                    f"✅ Claude (Präzision): {len(messages)} Nachrichten extrahiert."
                )
            return messages

        # --- STRATEGIE 2: Fallback (gekürzt, da Strategie 1 meist greift) ---
        if container:
            container.warning(
                "Claude: Standard-Selektoren fehlgeschlagen. Starte Fallback..."
            )
        # (Hier könnte der alte Fallback stehen, aber meist reicht Strategie 1 jetzt)
        return []
