from config import root_config
from config.models import MistralModelGroupConfig

mistral_config = root_config.services.mistral


class MistralConfig:
    ENABLED: bool = mistral_config.enabled
    API_KEY: str = mistral_config.api_key
    BASE_URL: str | None = mistral_config.base_url
    MODELS: MistralModelGroupConfig | None = mistral_config.models
