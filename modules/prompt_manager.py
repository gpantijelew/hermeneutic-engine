# modules/prompt_manager.py
import yaml
import logging
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Füge diese Konstante am Anfang der Datei oder der Klasse hinzu
MULTI_SOURCE_MODES = {"ANALYTICAL_FORENSIC", "ANALYTICAL", "META_ANALYTICAL", "LITERARY", "STILISTIC", "STILISTIC_DEEPENING"}

class PromptManager:
    """Lädt und formatiert hermeneutische Prompts aus der hermeneutic_protocol.yaml."""
    
    def __init__(self, yaml_path: Optional[str] = None):
        if yaml_path is None:
            # Sucht die YAML standardmäßig eine Ebene über dem modules/ Ordner
            yaml_path = Path(__file__).parent.parent / "hermeneutic_protocol.yaml"
        
        self._data = self._load_yaml(yaml_path)

    def _load_yaml(self, path: Path) -> Dict:
        """Lädt YAML sicher mit UTF-8 Encoding."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"❌ Prompt-YAML nicht gefunden: {path}")
        
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
                
        if not data:
            raise ValueError(f"❌ Prompt-YAML ist leer oder fehlerhaft: {path}")
                
        logger.info(f"✅ Prompt-YAML geladen: {path.name}")
        return data

    def get_system_instruction(self, semantic_intent: str) -> str:
        """Holt System-Instruction und injiziert automatisch die shared QUELLENREGEL."""
        instructions = self._data.get("system_instructions", {})
        text = instructions.get(semantic_intent, instructions.get("DEFAULT", ""))

        # Schicht 1: Globale source_rule (bestehende Logik)
        source_rule = self._data.get("shared_rules", {}).get("source_rule", "")
        if text and source_rule:
            text = text.rstrip() + "\n\n" + source_rule

        # Schicht 2: Familien-Regelwerk (NEUE LOGIK)
        if semantic_intent in MULTI_SOURCE_MODES:
            family = self._data.get("family_rules", {}).get("multi_source", {})

            # WICHTIG: Die Reihenfolge der Injektion ist entscheidend!
            # Erst die Regeln, dann der spezifische Prompt.

            citation = family.get("citation_rules", "")
            chronology = family.get("chronology_rules", "")
            synthesis = family.get("global_synthesis", "") # Globale Synthese auch laden

            # Baue den Prompt von oben nach unten auf
            rule_block = ""
            if citation:
                rule_block += citation.rstrip() + "\n\n"
            if chronology:
                rule_block += chronology.rstrip() + "\n\n"

            # Füge die Regeln VOR dem spezifischen Modus-Text ein
            text = rule_block + text

            # Hänge die globale Synthese-Anweisung an das ENDE an
            # STILISTIC bekommt eine eigene Synthese-Struktur
            if semantic_intent == "STILISTIC":
                stilistic_synthesis = family.get("global_synthesis_stilistic", "")
                if stilistic_synthesis:
                    text = text.rstrip() + "\n\n" + stilistic_synthesis
                elif synthesis:
                    text = text.rstrip() + "\n\n" + synthesis
            elif synthesis:
                text = text.rstrip() + "\n\n" + synthesis

            # ── Komparativer Modus: GRUPPENVERGLEICH-Instruktion (Test 16+) ──
            from modules.config import COMPARATIVE_MODE
            if COMPARATIVE_MODE:
                comparative = family.get("comparative_rules", "")
                if comparative:
                    text = text.rstrip() + "\n\n" + comparative

        return text

    def get_mode_instruction(self, intent: str, semantic_intent: Optional[str] = None, **kwargs) -> str:
        """Holt Mode-Instruction, formatiert Platzhalter und fügt bedingt das forensic_appendix an."""
        modes = self._data.get("mode_instructions", {})
        mode_data = modes.get(intent, modes.get("ANALYTICAL", {}))
        
        # Fallback falls Mode ein String statt Dict ist
        if isinstance(mode_data, str):
            base_text = mode_data
        else:
            base_text = mode_data.get("base", "")
        
        # Forensic-Appendix bedingt anhängen (nur bei ESSENCE_PARITY + FORENSIC)
        if (semantic_intent == "ANALYTICAL_FORENSIC"
    and isinstance(mode_data, dict)
    and "forensic_appendix" in mode_data):
            base_text = base_text.rstrip() + "\n\n" + mode_data["forensic_appendix"]
        
        # Platzhalter sicher formatieren (ignoriert fehlende Keys)
        class SafeDict(dict):
            def __missing__(self, key):
                return "{" + key + "}"
                    
        if kwargs:
            try:
                text = base_text.format_map(SafeDict(kwargs))
            except Exception as e:
                logger.error(f"❌ Fehler bei Prompt-Platzhalter-Ersetzung: {e}")
                text = base_text
        else:
            text = base_text

        # Stilprotokoll automatisch anhängen, wenn der Intent es anfordert (YAML-gesteuert)
        if isinstance(mode_data, dict) and mode_data.get("use_stilprotokoll", False):
            stilprotokoll = self._data.get("shared_rules", {}).get("stilprotokoll", "")
            if stilprotokoll:
                text = text.rstrip() + "\n\nSTILPROTOKOLL (DNA):\n" + stilprotokoll

        return text

    def get_mode_display(self, intent: str) -> str:
        """Holt den UI Anzeige-String für einen Intent."""
        modes = self._data.get("mode_instructions", {})
        mode_data = modes.get(intent, modes.get("ANALYTICAL", {}))
        
        if isinstance(mode_data, dict):
            return mode_data.get("mode_display", intent)
        return intent

    def build_task_prompt(self, query: str, mode_display: str, 
                          base_instruction: str, context_text: str) -> str:
        """Baut den finalen User-Prompt (AUFGABE-Block) zusammen."""
        template = self._data.get("task_template", "")
        
        if not template:
            return f"FRAGE: {query}\n\n{context_text}\n\nANTWORT:"
                
        return template.format(
            query=query,
            mode_display=mode_display,
            base_instruction=base_instruction,
            context_text=context_text
        )

    def get_vision_instruction(self, semantic_intent: Optional[str] = None) -> str:
        """Holt die System-Instruction für die semiotische Bildanalyse.
        Wenn semantic_intent='ANALYTICAL_FORENSIC', wird der forensic_appendix angehängt.
        """
        vision_data = self._data.get("vision_protocol", {})
        base_instruction = vision_data.get("system_instruction", "")
        
        if semantic_intent == "ANALYTICAL_FORENSIC":
            forensic_appendix = vision_data.get("forensic_appendix", "")
            if base_instruction and forensic_appendix:
                base_instruction = base_instruction.rstrip() + "\n\n" + forensic_appendix
                
        return base_instruction

    def get_vision_origin_rule(self, origin: str) -> str:
        """Holt die spezifische Regel für den Bildursprung (ai_generated, photograph, etc.)."""
        vision_data = self._data.get("vision_protocol", {})
        origin_rules = vision_data.get("image_origin_rules", {})
        return origin_rules.get(origin, "")

    def get_synthesis_params(self, intent: str) -> dict:
        """Liest maschinenlesbare Parameter aus mode_instructions aus."""
        modes = self._data.get("mode_instructions", {})
        mode_data = modes.get(intent, {})
        return {
            "temperature": mode_data.get("temperature", 0.5),
            "context_strategy": mode_data.get("context_strategy", "rag"),
        }

    def get_enforcer_prompt(self) -> str:
        """Lädt den Standard-Enforcer-Prompt."""
        return self._data.get("enforcer_protocol", {}).get("hermeneutic_prompt", "")

    def get_multisource_enforcer_prompt(self) -> str:
        """Lädt den Multi-Source-Enforcer-Prompt."""
        return self._data.get("enforcer_protocol", {}).get("multisource_prompt", "")

    def get_stilistic_lab_etappe_2_3(
        self,
        source_id: str,
        python_stats: str,
        vergleichstabelle: str,
        text_excerpt: str,
    ) -> dict:
        """
        Liest stilistic_lab_etappe_2_3 aus YAML und formatiert das Template.

        Args:
            source_id:       Label der Quelle (z.B. "QUELLE 1: Herzen")
            python_stats:    Formatierte Etappe-1-Statistiken
            vergleichstabelle: Formatierte Vergleichstabelle
            text_excerpt:    Auszug aus dem Originaltext

        Returns:
            Dict mit 'system_instruction', 'prompt', 'compact_instruction'.
            Leeres Dict wenn YAML-Key fehlt.
        """
        key = "stilistic_lab_etappe_2_3"
        data = self._data.get(key, {})

        if not data:
            logger.warning(f"YAML-Key '{key}' nicht gefunden. Fallback auf hardcoded Prompts.")
            return {}

        system_instruction = data.get("system_instruction", "")
        template = data.get("structure_template", "")
        compact = data.get("compact_instruction", "")

        # Platzhalter sicher formatieren (SafeDict ignoriert fehlende Keys)
        class SafeDict(dict):
            def __missing__(self, key):
                return "{" + key + "}"

        if template:
            try:
                prompt = template.format_map(SafeDict(
                    source_id=source_id,
                    python_stats=python_stats,
                    vergleichstabelle=vergleichstabelle,
                    text_excerpt=text_excerpt,
                ))
            except Exception as e:
                logger.error(f"Fehler bei Etappe-2-3-Template-Formatierung: {e}")
                prompt = template
        else:
            prompt = ""

        return {
            "system_instruction": system_instruction,
            "prompt": prompt,
            "compact_instruction": compact,
        }

    def get_stilistic_lab_synthese(
        self,
        vergleichstabelle: str,
        einzelanalysen: str,
    ) -> dict:
        """
        Liest stilistic_lab_synthese aus YAML und formatiert das Template.

        Args:
            vergleichstabelle: Formatierte Vergleichstabelle
            einzelanalysen:   Alle Etappe-2+3-Ergebnisse als Text

        Returns:
            Dict mit 'system_instruction', 'prompt', 'compact_instruction'.
            Leeres Dict wenn YAML-Key fehlt.
        """
        key = "stilistic_lab_synthese"
        data = self._data.get(key, {})

        if not data:
            logger.warning(f"YAML-Key '{key}' nicht gefunden. Fallback auf hardcoded Prompts.")
            return {}

        system_instruction = data.get("system_instruction", "")
        template = data.get("structure_template", "")
        compact = data.get("compact_instruction", "")

        # Platzhalter sicher formatieren
        class SafeDict(dict):
            def __missing__(self, key):
                return "{" + key + "}"

        if template:
            try:
                prompt = template.format_map(SafeDict(
                    vergleichstabelle=vergleichstabelle,
                    einzelanalysen=einzelanalysen,
                ))
            except Exception as e:
                logger.error(f"Fehler bei Synthese-Template-Formatierung: {e}")
                prompt = template
        else:
            prompt = ""

        return {
            "system_instruction": system_instruction,
            "prompt": prompt,
            "compact_instruction": compact,
        }
