from ..base import ConfigBasedImporter


class GLMImporter(ConfigBasedImporter):
    config_key = "glm"

    @property
    def platform_name(self):
        return "GLM-4 (Zhipu)"

    @property
    def platform_id(self):
        return "glm"

    @property
    def detection_signatures(self):
        return ["glm-chat-item", "zhipu-ai-response"]
