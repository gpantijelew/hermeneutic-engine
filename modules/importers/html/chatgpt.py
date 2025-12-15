from ..base import ConfigBasedImporter

class ChatGPTImporter(ConfigBasedImporter):
    config_key = 'chatgpt'

    @property
    def platform_name(self): return "ChatGPT (OpenAI)"

    @property
    def platform_id(self): return "chatgpt"