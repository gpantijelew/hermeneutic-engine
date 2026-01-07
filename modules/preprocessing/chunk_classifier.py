# modules/preprocessing/chunk_classifier.py - v50.8: GENERISCH & METADATA-REICH
"""
Chunk Classifier - Metadaten-Anreicherung für Text-Chunks.

PHILOSOPHIE (v50.8 - RADIKAL VEREINFACHT):
"Code ist DUMM, Prompts sind SCHLAU"

Dieser Classifier sammelt reichhaltige Metadata, OHNE zu werten oder zu filtern.
Alle Intelligenz liegt in den Prompts (llm_instructions.py), nicht im Code.

DESIGN-PRINZIPIEN:
1. Keine Hardcoding (keine SUBJECTS-Liste!)
2. Keine Normalisierung (Speaker-Versionen bleiben erhalten!)
3. Dynamische Entity-Extraktion (erkennt ALLE Eigennamen)
4. Reichhaltige Metadata (nichts wird weggeworfen)

VERWENDUNG:
    classifier = ChunkClassifier()
    enriched_meta = classifier.process_chunk(chunk_text, existing_metadata)

ÄNDERUNGSHISTORIE:
- v50.8: Radikal vereinfacht (generisch, keine Hardcoding)
- v50.7: Performance-Optimierung + erweiterte Subjects (VERWORFEN)
- v47: Initiale Version (Native Dict Support)
"""

import re
from typing import Dict, List, Any, Optional


class ChunkClassifier:
    """
    Generischer Metadaten-Anreicherer für Text-Chunks.
    
    FEATURES:
    - Speaker-Erkennung via Pattern-Matching (hierarchisch: Familie + Version)
    - Entity-Extraktion (dynamisch, alle Eigennamen)
    - Content-Type-Klassifikation (Frage, Analyse, Vergleich, Selbstreflexion)
    - Kontextuelles Gedächtnis (last_speaker für Speaker-Kontinuität)
    
    LIMITATIONS:
    - Regex-basiert (keine ML-Modelle)
    - Deutsche Sprache optimiert (andere Sprachen funktionieren schlechter)
    - Heuristiken können bei Edge Cases versagen
    
    WICHTIG:
    Dieser Classifier ist absichtlich "dumm" (generisch).
    Intelligente Filter/Entscheidungen passieren in den LLM-Prompts!
    
    TODO v51:
    - query_analyzer.py: LLM-basierte Filter-Extraktion aus User-Queries
    - Metadata-Filter-Support in vector_store.py (für Szenario C)
    """
    
    # =========================================================================
    # KONFIGURATION (Minimal!)
    # =========================================================================
    
    # Bekannte AI-Modelle (Minimal-Liste, nur für Pattern-Matching)
    # RATIONALE: Diese Namen erscheinen oft als "Speaker:" im Text.
    # NICHT für Filterung oder Semantik – nur für Pattern-Recognition!
    KNOWN_SPEAKERS = [
        "ChatGPT", "GPT", "Claude", "Gemini", "DeepSeek", 
        "Grok", "Kimi", "GLM", "Perplexity", "User"
    ]
    
    def __init__(self):
        """
        Initialisiert den Classifier mit pre-compiled Regex.
        
        PERFORMANCE-OPTIMIERUNG:
        Regex-Pattern wird nur 1x beim Init gebaut, nicht bei jedem Call!
        """
        # Kontextuelles Gedächtnis
        self.last_speaker = "Unknown"
        self.last_speaker_full = "Unknown"  # NEU v50.8: Mit Version
        
        # Pre-compile Regex für Speaker-Erkennung
        speaker_names = '|'.join(map(re.escape, self.KNOWN_SPEAKERS))
        self.speaker_pattern = re.compile(
            r'^(' + speaker_names + r'[^\s:]*?)(?:\s*\(.*?\))?:?\s',
            re.MULTILINE | re.IGNORECASE
        )
    
    # =========================================================================
    # SPEAKER-KLASSIFIKATION (Hierarchisch: Familie + Version)
    # =========================================================================
    
    def classify_speaker(self, text: str) -> Dict[str, Any]:
        """
        Erkennt Speaker aus Text-Patterns am Zeilenanfang.
        
        NEU v50.8: HIERARCHISCHE METADATA
        Statt Normalisierung → Behalte ALLE Informationen:
        - speaker_raw: Original (z.B. "DeepSeek-R1")
        - speaker_family: Familie (z.B. "DeepSeek")
        - speaker_version: Version (z.B. "R1")
        
        RATIONALE:
        User kann fragen:
        - "Alle DeepSeek-Antworten" → Nutze speaker_family
        - "DeepSeek-V3 vs DeepSeek-R1" → Nutze speaker_version
        
        Args:
            text: Chunk-Text zur Klassifikation
        
        Returns:
            Dict mit:
            - speaker_raw (str): Original (volle Fidelity!)
            - speaker_family (str): Basis-Name ohne Version
            - speaker_version (str|None): Extrahierte Version
            - confidence (float, 0-1)
        
        Beispiele:
            >>> classifier = ChunkClassifier()
            >>> classifier.classify_speaker("DeepSeek-R1: Hello")
            {
                'speaker_raw': 'DeepSeek-R1',
                'speaker_family': 'DeepSeek',
                'speaker_version': 'R1',
                'confidence': 0.95
            }
            
            >>> classifier.classify_speaker("ChatGPT-4o: Hi")
            {
                'speaker_raw': 'ChatGPT-4o',
                'speaker_family': 'ChatGPT',
                'speaker_version': '4o',
                'confidence': 0.95
            }
        """
        # Pattern-Match
        match = self.speaker_pattern.match(text)
        
        if match:
            speaker_raw = match.group(1).strip()
            
            # Extrahiere Familie und Version
            family, version = self._parse_speaker_hierarchy(speaker_raw)
            
            # Update Kontext-Gedächtnis
            self.last_speaker = family
            self.last_speaker_full = speaker_raw
            
            return {
                'speaker_raw': speaker_raw,       # "DeepSeek-R1"
                'speaker_family': family,         # "DeepSeek"
                'speaker_version': version,       # "R1"
                'confidence': 0.95
            }
        
        # Fallback: Letzter bekannter Speaker (Kontext-Kontinuität)
        if self.last_speaker != "Unknown":
            return {
                'speaker_raw': self.last_speaker_full,
                'speaker_family': self.last_speaker,
                'speaker_version': None,
                'confidence': 0.6
            }
        
        # Last Resort: Unknown
        return {
            'speaker_raw': 'Unknown',
            'speaker_family': 'Unknown',
            'speaker_version': None,
            'confidence': 0.3
        }
    
    def _parse_speaker_hierarchy(self, speaker_raw: str) -> tuple[str, Optional[str]]:
        """
        Extrahiert Familie und Version aus Speaker-String.
        
        STRATEGIE:
        - Familie: Erster Teil vor "-" oder Whitespace
        - Version: Alles nach "-" (z.B. "4o", "V3", "R1")
        
        Args:
            speaker_raw: Raw Speaker-String (z.B. "DeepSeek-R1")
        
        Returns:
            Tuple: (family, version)
        
        Beispiele:
            >>> _parse_speaker_hierarchy("DeepSeek-R1")
            ('DeepSeek', 'R1')
            
            >>> _parse_speaker_hierarchy("ChatGPT-4o")
            ('ChatGPT', '4o')
            
            >>> _parse_speaker_hierarchy("Claude")
            ('Claude', None)
        """
        # Trenne bei "-" oder Whitespace
        if '-' in speaker_raw:
            parts = speaker_raw.split('-', 1)
            family = parts[0].strip()
            version = parts[1].strip() if len(parts) > 1 else None
        elif ' ' in speaker_raw:
            parts = speaker_raw.split(None, 1)
            family = parts[0].strip()
            version = parts[1].strip() if len(parts) > 1 else None
        else:
            family = speaker_raw
            version = None
        
        return family, version
    
    # =========================================================================
    # ENTITY-EXTRAKTION (Dynamisch, keine Hardcoding!)
    # =========================================================================
    
    def extract_entities(self, text: str) -> List[str]:
        """
        Extrahiert ALLE Eigennamen dynamisch (Named Entity Recognition light).
        
        NEU v50.8: KEINE HARDCODING!
        Statt statischer SUBJECTS-Liste → Nutze Kapitalisierung als Signal.
        
        STRATEGIE:
        1. Finde alle Wörter, die mit Großbuchstaben beginnen
        2. Filtere False Positives (Satzanfänge, kurze Wörter)
        3. Keine semantische Wertung – sammle ALLES
        
        WICHTIG:
        Diese Methode ist absichtlich "dumm" (generisch).
        LLM entscheidet später, welche Entities relevant sind!
        
        Args:
            text: Chunk-Text zur Analyse
        
        Returns:
            Liste von gefundenen Eigennamen (unique)
        
        Beispiele:
            >>> classifier = ChunkClassifier()
            >>> classifier.extract_entities("Heidegger definiert Dasein als...")
            ['Heidegger', 'Dasein']
            
            >>> classifier.extract_entities("Fernando Pessoa schrieb über...")
            ['Fernando', 'Pessoa']
            
            >>> classifier.extract_entities("Claude und ChatGPT vergleichen")
            ['Claude', 'ChatGPT']
        """
        entities = []
        
        # Tokenisiere nach Whitespace
        words = text.split()
        
        for i, word in enumerate(words):
            # Bereinige Interpunktion
            clean_word = word.strip('.,!?:;()[]"\'«»„"')
            
            if not clean_word:
                continue
            
            # Kriterium 1: Beginnt mit Großbuchstaben
            if not clean_word[0].isupper():
                continue
            
            # Kriterium 2: Länger als 2 Zeichen (filtert "Er", "Im", "Am")
            if len(clean_word) <= 2:
                continue
            
            # Kriterium 3: Nicht am Satzanfang (heuristisch)
            # Wir nehmen an: Wenn vorheriges Wort mit "." endete, ist es Satzanfang
            if i > 0 and words[i-1].rstrip('.,!?:;()[]"\'«»„"').endswith('.'):
                continue
            
            entities.append(clean_word)
        
        # Duplikate entfernen, alphabetisch sortieren
        return sorted(list(set(entities)))
    
    # =========================================================================
    # CONTENT-TYPE-KLASSIFIKATION (Unverändert aus v50.7)
    # =========================================================================
    
    def classify_type(self, text: str) -> str:
        """
        Klassifiziert den Typ der Aussage (heuristisch).
        
        KATEGORIEN:
        - **Frage**: Enthält '?' + Fragewort ODER endet mit '?'
        - **Selbstreflexion**: Meta-Aussagen über eigene KI-Natur
        - **Vergleich**: Explizite Vergleichswörter
        - **Analyse**: Default (wenn nichts anderes zutrifft)
        
        Args:
            text: Chunk-Text zur Klassifikation
        
        Returns:
            String: 'Frage', 'Selbstreflexion', 'Vergleich', oder 'Analyse'
        """
        text_lower = text.lower()
        
        # 1. FRAGE
        if '?' in text:
            fragewörter = [
                'was ', 'wie ', 'warum ', 'welche ', 'wozu ', 
                'wer ', 'wann ', 'wo ', 'weshalb ', 'wieso '
            ]
            if any(w in text_lower for w in fragewörter):
                return 'Frage'
            
            if text.strip().endswith('?'):
                return 'Frage'
        
        # 2. SELBSTREFLEXION
        reflexion_triggers = [
            'ich denke', 'meine einschätzung', 'aus meiner sicht', 
            'meiner meinung', 'ich fühle', 'mein algorithmus', 
            'meine programmierung', 'als ki', 'als sprachmodell'
        ]
        if any(trigger in text_lower for trigger in reflexion_triggers):
            return 'Selbstreflexion'
        
        # 3. VERGLEICH
        vergleich_triggers = [
            'im gegensatz', 'während', 'beide', 'verglichen mit', 
            'unterschied', 'ähnlich wie', 'dagegen', 'im vergleich',
            'versus', 'vs.', 'anders als'
        ]
        if any(trigger in text_lower for trigger in vergleich_triggers):
            return 'Vergleich'
        
        # 4. ANALYSE (Default)
        return 'Analyse'
    
    # =========================================================================
    # HAUPT-API (Harmonisiert mit hierarchischem Speaker)
    # =========================================================================
    
    def process_chunk(
        self, 
        chunk_text: str, 
        existing_metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Haupt-Funktion: Reichert Metadaten mit Klassifikationen an.
        
        NEU v50.8: HIERARCHISCHE SPEAKER-METADATA
        - speaker_raw: Original (volle Fidelity)
        - speaker_family: Basis-Name (für Aggregation)
        - speaker_version: Version (für Vergleiche)
        
        WORKFLOW:
        1. Speaker-Klassifikation (hierarchisch)
        2. Entity-Extraktion (dynamisch, keine Hardcoding)
        3. Type-Klassifikation (heuristisch)
        
        Args:
            chunk_text: Text des Chunks
            existing_metadata: Bestehende Metadaten (werden angereichert)
        
        Returns:
            Angereichertes Metadata-Dict
        
        WICHTIG:
        Diese Funktion ist **nicht-destruktiv**!
        Bestehende Metadaten bleiben erhalten, nur neue Felder werden hinzugefügt.
        
        Beispiel:
            >>> classifier = ChunkClassifier()
            >>> meta = {'chat_title': 'DeepSeek-Diskussion'}
            >>> enriched = classifier.process_chunk(
            ...     "DeepSeek-R1: Heideggers Dasein ist In-der-Welt-sein.",
            ...     meta
            ... )
            >>> enriched
            {
                'chat_title': 'DeepSeek-Diskussion',
                'speaker_raw': 'DeepSeek-R1',       # NEU: Original
                'speaker_family': 'DeepSeek',       # NEU: Familie
                'speaker_version': 'R1',            # NEU: Version
                'model_name': 'DeepSeek-R1',        # Legacy (für Kompatibilität)
                'speaker_confidence': 0.95,
                'entities': ['Heideggers', 'Dasein', 'Welt'],  # NEU: Dynamisch!
                'entity_count': 3,                  # NEU: Für Queries
                'content_type': 'Analyse'
            }
        """
        if existing_metadata is None:
            existing_metadata = {}
        
        # =====================================================================
        # 1. SPEAKER-KLASSIFIKATION (Hierarchisch)
        # =====================================================================
        speaker_info = self.classify_speaker(chunk_text)
        
        # NEU v50.8: Hierarchische Metadata
        existing_metadata['speaker_raw'] = speaker_info['speaker_raw']
        existing_metadata['speaker_family'] = speaker_info['speaker_family']
        existing_metadata['speaker_version'] = speaker_info['speaker_version']
        existing_metadata['speaker_confidence'] = speaker_info['confidence']
        
        # Legacy-Feld (für Kompatibilität mit alter Pipeline)
        # WICHTIG: Wir überschreiben nur, wenn noch nicht gesetzt oder Unknown
        current_speaker = existing_metadata.get('model_name', 'Unknown')
        if current_speaker in ['Unknown', 'Unbekannt', None] or speaker_info['confidence'] > 0.9:
            existing_metadata['model_name'] = speaker_info['speaker_raw']
        
        # =====================================================================
        # 2. ENTITY-EXTRAKTION (Dynamisch!)
        # =====================================================================
        entities = self.extract_entities(chunk_text)
        existing_metadata['entities'] = entities
        existing_metadata['entity_count'] = len(entities)
        
        # =====================================================================
        # 3. TYPE-KLASSIFIKATION
        # =====================================================================
        existing_metadata['content_type'] = self.classify_type(chunk_text)
        
        return existing_metadata