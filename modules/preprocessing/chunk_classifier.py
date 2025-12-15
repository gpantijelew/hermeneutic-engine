# modules/preprocessing/chunk_classifier.py
import re
from typing import Dict, List, Any

class ChunkClassifier:
    """
    Klassifiziert Text-Chunks nach Speaker, Subject und Type.
    Angepasst für v47 (Native Dict Support).
    """

    # Erweiterte Listen basierend auf unseren Projektdaten
    SPEAKERS = ["ChatGPT", "GLM-4.6", "User", "Kimi", "DeepSeek", "Grok", "Claude", "Gemini", "DeepSeek"]
    SUBJECTS = ["DeepSeek", "Grok", "Kimi", "ChatGPT", "GLM", "Claude", "Gemini", "Blade Runner", "Zensur"]

    def __init__(self):
        self.last_speaker = "Unknown"

    def classify_speaker(self, text: str) -> Dict[str, Any]:
        """
        Erkennt Speaker aus Text-Patterns am Zeilenanfang.
        """
        # Pattern: "Name:" oder "**Name**:" oder "Name (" am Anfang
        # Wir bauen das Pattern dynamisch aus der Liste
        speaker_pattern = r'^(' + '|'.join(map(re.escape, self.SPEAKERS)) + r')(?:\s*\(.*?\))?:?\s'

        match = re.match(speaker_pattern, text, re.MULTILINE | re.IGNORECASE)

        if match:
            speaker = match.group(1)
            # Normalisierung (z.B. "ChatGPT-4o" -> "ChatGPT")
            if "chatgpt" in speaker.lower(): speaker = "ChatGPT"

            self.last_speaker = speaker
            return {'speaker': speaker, 'confidence': 0.95}

        # Fallback: Letzter bekannter Speaker (Kontext-Gedächtnis)
        if self.last_speaker != "Unknown":
            return {'speaker': self.last_speaker, 'confidence': 0.6}

        return {'speaker': 'Unknown', 'confidence': 0.3}

    def extract_subjects(self, text: str) -> List[str]:
        """
        Extrahiert Modellnamen und Schlüsselbegriffe (NER-light).
        """
        subjects = []
        for subject in self.SUBJECTS:
            # Suche nach ganzem Wort, case-insensitive
            if re.search(rf'\b{re.escape(subject)}\b', text, re.IGNORECASE):
                subjects.append(subject)
        return list(set(subjects)) # Duplikate entfernen

    def classify_type(self, text: str) -> str:
        """
        Klassifiziert den Typ der Aussage.
        """
        text_lower = text.lower()

        # Frage
        if '?' in text and any(w in text_lower for w in ['was ', 'wie ', 'warum ', 'welche ', 'wozu ']):
            return 'Frage'

        # Selbstreflexion (Wichtig für DeepSeek/Kimi Analyse)
        reflexion_triggers = [
            'ich denke', 'meine einschätzung', 'aus meiner sicht', 
            'meiner meinung', 'ich fühle', 'mein algorithmus', 
            'meine programmierung', 'als ki'
        ]
        if any(w in text_lower for w in reflexion_triggers):
            return 'Selbstreflexion'

        # Vergleich
        vergleich_triggers = [
            'im gegensatz', 'während', 'beide', 'verglichen mit', 
            'unterschied', 'ähnlich wie'
        ]
        if any(w in text_lower for w in vergleich_triggers):
            return 'Vergleich'

        # Analyse (default)
        return 'Analyse'

    def process_chunk(self, chunk_text: str, existing_metadata: Dict = None) -> Dict[str, Any]:
        """
        Hauptfunktion: Angereicherte Metadaten zurückgeben.
        """
        if existing_metadata is None:
            existing_metadata = {}

        # 1. Speaker
        speaker_info = self.classify_speaker(chunk_text)

        # Wir überschreiben den Speaker nur, wenn wir uns sicher sind oder noch keiner da ist
        current_speaker = existing_metadata.get('model_name', 'Unknown')
        if current_speaker in ['Unknown', 'Unbekannt', None] or speaker_info['confidence'] > 0.9:
            existing_metadata['model_name'] = speaker_info['speaker']
            existing_metadata['speaker_confidence'] = speaker_info['confidence']

        # 2. Subject
        subjects = self.extract_subjects(chunk_text)
        existing_metadata['subjects'] = ', '.join(subjects) if subjects else 'General'

        # 3. Type
        existing_metadata['content_type'] = self.classify_type(chunk_text)

        return existing_metadata