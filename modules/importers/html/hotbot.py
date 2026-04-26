from ..base import ConfigBasedImporter


class HotBotImporter(ConfigBasedImporter):
    config_key = "hotbot"

    @property
    def platform_name(self):
        return "HotBot"

    @property
    def platform_id(self):
        return "hotbot"
