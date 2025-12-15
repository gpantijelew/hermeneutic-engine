from ..base import ConfigBasedImporter

class PerplexityImporter(ConfigBasedImporter):
    config_key = 'perplexity'
    @property
    def platform_name(self): return "Perplexity AI"
    @property
    def platform_id(self): return "perplexity"
    @property
    def detection_signatures(self): return ['perplexity-message', 'pplx-answer-container']