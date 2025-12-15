from ..base import ConfigBasedImporter

class GrokImporter(ConfigBasedImporter):
    config_key = 'grok'
    @property
    def platform_name(self): return "Grok (xAI)"
    @property
    def platform_id(self): return "grok"
    @property
    def detection_signatures(self): return ['grok-response', 'xai-message-block']