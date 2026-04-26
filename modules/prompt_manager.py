# modules/prompt_manager.py
import yaml
import logging
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

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
        
        source_rule = self._data.get("shared_rules", {}).get("source_rule", "")
        if text and source_rule:
            text = text.rstrip() + "\n\n" + source_rule
                
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
        if (intent == "ESSENCE_PARITY" 
            and semantic_intent == "ANALYTICAL_FORENSIC"
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