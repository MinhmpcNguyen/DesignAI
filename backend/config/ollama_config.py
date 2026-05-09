from config import root_config
from config.models import OllamaModelGroupConfig

ollama_config = root_config.services.ollama


class OllamaConfig:
    ENABLED: bool = ollama_config.enabled
    API_KEY: str = ollama_config.api_key
    BASE_URL: str | None = ollama_config.base_url
    MODELS: OllamaModelGroupConfig | None = ollama_config.models
