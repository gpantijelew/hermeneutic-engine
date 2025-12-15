from .text_parser import TextParserImporter
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
from .documents.pdf import PDFImporter
from .documents.epub import EPubImporter
from .utils import detect_platform

IMPORTERS = {
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
    'pdf': PDFImporter,
    'epub': EPubImporter,
}

def get_importer(platform: str):
    if platform not in IMPORTERS:
        raise ValueError(f"Unknown platform: {platform}")
    return IMPORTERS[platform]()