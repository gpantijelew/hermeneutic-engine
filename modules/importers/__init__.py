"""
Importer Registry für verschiedene Chat-Plattformen und Dokument-Formate.

Unterstützte Plattformen:
    - Chat-Plattformen: ChatGPT, Claude, Gemini, DeepSeek, Kimi, Grok, etc.
    - Dokumente: PDF, EPUB
    - Web-Quellen: Wikisource (MediaWiki)
    - Fallback: Text-Parser für unbekannte Formate

Usage:
    from modules.importers import get_importer, detect_platform, list_platforms
    
    # Auto-Detection
    platform = detect_platform(html_content)
    importer = get_importer(platform)
    messages = importer.parse(html_content)
    
    # Manuelle Auswahl
    importer = get_importer('chatgpt')
    messages = importer.parse(html_content)
"""

from typing import Dict, List, Type

# HTML-basierte Chat-Importer
from .html.lmarena import LMArenaImporter
from .html.chatgpt import ChatGPTImporter
from .html.deepseek import DeepSeekImporter
from .html.kimi import KimiImporter
from .html.claude import ClaudeImporter
from .html.hotbot import HotBotImporter
from .html.gemini import GeminiImporter
from .html.perplexity import PerplexityImporter
from .html.grok import GrokImporter
from .html.glm import GLMImporter
from .html.wikisource import WikisourceImporter  # NEU!

# Dokument-Importer
from .documents.pdf import PDFImporter
from .documents.epub import EPubImporter
from .documents.fb2 import FB2Importer

# Fallback & Utils
from .text_parser import TextParserImporter
from .utils import detect_platform
from .base import BaseImporter

# Export-Liste (für `from modules.importers import *`)
__all__ = [
    'IMPORTERS',
    'IMPORTER_METADATA',
    'get_importer',
    'detect_platform',
    'list_platforms',
    'is_experimental',
    'get_platform_info',
]

# Importer-Registry (Haupt-Mapping)
IMPORTERS: Dict[str, Type[BaseImporter]] = {
    'text_fallback': TextParserImporter,
    'lmarena': LMArenaImporter,
    'chatgpt': ChatGPTImporter,
    'deepseek': DeepSeekImporter,
    'kimi': KimiImporter,
    'claude': ClaudeImporter,
    'hotbot': HotBotImporter,
    'gemini': GeminiImporter,
    'perplexity': PerplexityImporter,
    'grok': GrokImporter,
    'glm': GLMImporter,
    'wikisource': WikisourceImporter,  # NEU!
    'pdf': PDFImporter,
    'epub': EPubImporter,
    'fb2': FB2Importer,
}

# Metadaten für UI-Darstellung (v49.5 - mit Wikisource)
IMPORTER_METADATA: Dict[str, dict] = {
    'chatgpt': {
        'name': 'ChatGPT (OpenAI)',
        'formats': ['.html'],
        'experimental': False,
        'description': 'Import von ChatGPT HTML-Exports'
    },
    'claude': {
        'name': 'Claude (Anthropic)',
        'formats': ['.html'],
        'experimental': False,
        'description': 'Import von Claude HTML-Exports'
    },
    'gemini': {
        'name': 'Gemini (Google)',
        'formats': ['.html'],
        'experimental': False,
        'description': 'Import von Gemini HTML-Exports'
    },
    'deepseek': {
        'name': 'DeepSeek',
        'formats': ['.html'],
        'experimental': False,
        'description': 'Import von DeepSeek HTML-Exports'
    },
    'kimi': {
        'name': 'Kimi (Moonshot)',
        'formats': ['.html'],
        'experimental': False,
        'description': 'Import von Kimi HTML-Exports'
    },
    'grok': {
        'name': 'Grok (X.ai)',
        'formats': ['.html'],
        'experimental': True,
        'description': 'Import von Grok HTML-Exports (Experimental)'
    },
    'hotbot': {
        'name': 'HotBot',
        'formats': ['.html'],
        'experimental': True,
        'description': 'Import von HotBot HTML-Exports (Experimental)'
    },
    'perplexity': {
        'name': 'Perplexity',
        'formats': ['.html'],
        'experimental': True,
        'description': 'Import von Perplexity HTML-Exports (Experimental)'
    },
    'lmarena': {
        'name': 'LM Arena (Chatbot Arena)',
        'formats': ['.html'],
        'experimental': True,
        'description': 'Import von LM Arena Conversations (Experimental)'
    },
    'glm': {
        'name': 'GLM-4 (Zhipu AI)',
        'formats': ['.html'],
        'experimental': True,
        'description': 'Import von GLM-4 HTML-Exports (Experimental)'
    },
    'wikisource': {  # NEU!
        'name': 'Wikisource (MediaWiki)',
        'formats': ['.html'],
        'experimental': False,
        'description': 'Import von Wikisource/MediaWiki HTML-Seiten'
    },
    'pdf': {
        'name': 'PDF Document',
        'formats': ['.pdf'],
        'experimental': False,
        'description': 'Import von PDF-Dokumenten (v49.5 - verbesserte Text-Extraktion)'
    },
    'epub': {
        'name': 'EPUB E-Book',
        'formats': ['.epub'],
        'experimental': False,
        'description': 'Import von EPUB E-Books'
    },
    'fb2': {  # <--- NEU
        'name': 'FictionBook (FB2)',
        'formats': ['.fb2'],
        'experimental': False,
        'description': 'Import von FB2 E-Books'
    },
    'text_fallback': {
        'name': 'Text-Parser (Fallback)',
        'formats': ['.txt', '.html'],
        'experimental': False,
        'description': 'KI-basierter Parser für unbekannte Formate'
    },
}

def get_importer(platform: str) -> BaseImporter:
    """
    Gibt den Importer für die angegebene Plattform zurück.
    
    Args:
        platform: Plattform-Name (z.B. 'chatgpt', 'claude', 'pdf', 'wikisource')
    
    Returns:
        Instanziierter Importer
    
    Raises:
        ValueError: Wenn Plattform unbekannt
    
    Example:
        >>> importer = get_importer('wikisource')
        >>> messages = importer.parse(html_content)
    """
    if platform not in IMPORTERS:
        available = ', '.join(list_platforms())
        raise ValueError(
            f"Unknown platform: '{platform}'. "
            f"Available: {available}"
        )
    return IMPORTERS[platform]()

def list_platforms() -> List[str]:
    """
    Gibt Liste aller unterstützten Plattformen zurück.
    
    Returns:
        Liste von Plattform-Namen
    
    Example:
        >>> platforms = list_platforms()
        >>> print(platforms)
        ['chatgpt', 'claude', 'gemini', 'wikisource', ...]
    """
    return list(IMPORTERS.keys())

def is_experimental(platform: str) -> bool:
    """
    Prüft, ob eine Plattform als experimentell markiert ist.
    
    Args:
        platform: Plattform-Name
    
    Returns:
        True wenn experimentell, False sonst
    
    Example:
        >>> is_experimental('grok')
        True
        >>> is_experimental('wikisource')
        False
    """
    return IMPORTER_METADATA.get(platform, {}).get('experimental', False)

def get_platform_info(platform: str) -> dict:
    """
    Gibt vollständige Metadaten für eine Plattform zurück.
    
    Args:
        platform: Plattform-Name
    
    Returns:
        Dictionary mit Metadaten (name, formats, experimental, description)
    
    Example:
        >>> info = get_platform_info('wikisource')
        >>> print(info['name'])
        'Wikisource (MediaWiki)'
    """
    if platform not in IMPORTER_METADATA:
        return {
            'name': platform,
            'formats': [],
            'experimental': True,
            'description': 'Unbekannte Plattform'
        }
    return IMPORTER_METADATA[platform]