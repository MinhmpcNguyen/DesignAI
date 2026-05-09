from pydantic import BaseModel, Field, model_validator
from typing_extensions import Self


class APIKeyConfig(BaseModel):
    name: str
    value: str


class Auth(BaseModel):
    api_key: APIKeyConfig


class OpenAIModelConfig(BaseModel):
    name: str
    azure_endpoint: str | None = None


class OpenAIModelGroupConfig(BaseModel):
    primary: OpenAIModelConfig | None = None
    helper: OpenAIModelConfig | None = None
    embedding: OpenAIModelConfig | None = None
    gpt_4o: OpenAIModelConfig | None = None
    gpt_4o_mini: OpenAIModelConfig | None = None
    text_embedding_3_small: OpenAIModelConfig | None = None

    def primary_model(self) -> OpenAIModelConfig:
        return self._require_model(self.primary or self.gpt_4o, "primary")

    def helper_model(self) -> OpenAIModelConfig:
        return self._require_model(self.helper or self.gpt_4o_mini, "helper")

    def embedding_model(self) -> OpenAIModelConfig:
        return self._require_model(
            self.embedding or self.text_embedding_3_small,
            "embedding",
        )

    def resolved_models(self) -> dict[str, OpenAIModelConfig]:
        return {
            "primary": self.primary_model(),
            "helper": self.helper_model(),
            "embedding": self.embedding_model(),
        }

    @staticmethod
    def _require_model(
        model_config: OpenAIModelConfig | None,
        config_key: str,
    ) -> OpenAIModelConfig:
        if model_config is None:
            raise ValueError(f"services.openai.models.{config_key} is required.")
        return model_config


class OllamaModelConfig(BaseModel):
    name: str


class OllamaModelGroupConfig(BaseModel):
    primary: OllamaModelConfig
    helper: OllamaModelConfig
    embedding: OllamaModelConfig


class MistralModelConfig(BaseModel):
    name: str


class MistralModelGroupConfig(BaseModel):
    primary: MistralModelConfig
    helper: MistralModelConfig
    embedding: MistralModelConfig


class GeminiModelConfig(BaseModel):
    name: str


class GeminiModelGroupConfig(BaseModel):
    primary: GeminiModelConfig
    helper: GeminiModelConfig
    embedding: GeminiModelConfig


class GeminiImageConfig(BaseModel):
    enabled: bool = True
    api_key: str | None = None
    base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    model: str = "gemini-3.1-flash-image-preview"
    image_size: str = "1K"
    max_output_tokens: int = 256
    include_layout_2d_reference: bool = False

    @model_validator(mode="after")
    def validate_enabled_config(self) -> Self:
        if not self.enabled:
            return self
        if not self.base_url:
            raise ValueError(
                "services.gemini_image.base_url is required when Gemini image is enabled."
            )
        if not self.model:
            raise ValueError(
                "services.gemini_image.model is required when Gemini image is enabled."
            )
        if self.max_output_tokens < 32:
            raise ValueError(
                "services.gemini_image.max_output_tokens must be at least 32."
            )
        return self


class OpenAIConfig(BaseModel):
    enabled: bool = False
    azure: bool = False
    api_version: str = "2024-08-01-preview"
    api_key: str | None = None
    public_key: str | None = None
    private_key_file: str | None = None
    base_url: str | None = None
    models: OpenAIModelGroupConfig
    agent_models: dict[str, OpenAIModelConfig] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_access(self) -> Self:
        if not self.enabled:
            return self
        if self.api_key:
            return self
        if self.public_key and self.private_key_file:
            return self
        raise ValueError(
            "Configure either services.openai.api_key or both "
            "services.openai.public_key and services.openai.private_key_file."
        )

    @model_validator(mode="after")
    def validate_azure_endpoints(self) -> Self:
        if not self.azure:
            return self
        if self.base_url:
            return self

        missing_models: list[str] = []
        for model_name, model_config in self.models.resolved_models().items():
            if not model_config.azure_endpoint:
                missing_models.append(model_name)

        if missing_models:
            raise ValueError(
                "Missing azure_endpoint for Azure models: "
                + ", ".join(sorted(missing_models))
            )
        return self


class OllamaConfig(BaseModel):
    enabled: bool = False
    api_key: str = "ollama"
    base_url: str | None = None
    models: OllamaModelGroupConfig | None = None

    @model_validator(mode="after")
    def validate_enabled_config(self) -> Self:
        if not self.enabled:
            return self
        if not self.base_url:
            raise ValueError(
                "services.ollama.base_url is required when Ollama is enabled."
            )
        if self.models is None:
            raise ValueError(
                "services.ollama.models is required when Ollama is enabled."
            )
        return self


class MistralConfig(BaseModel):
    enabled: bool = False
    api_key: str = "mistral"
    base_url: str | None = None
    models: MistralModelGroupConfig | None = None

    @model_validator(mode="after")
    def validate_enabled_config(self) -> Self:
        if not self.enabled:
            return self
        if not self.base_url:
            raise ValueError(
                "services.mistral.base_url is required when Mistral is enabled."
            )
        if self.models is None:
            raise ValueError(
                "services.mistral.models is required when Mistral is enabled."
            )
        return self


class GeminiConfig(BaseModel):
    enabled: bool = False
    api_key: str | None = None
    base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    models: GeminiModelGroupConfig | None = None
    agent_models: dict[str, GeminiModelConfig] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_enabled_config(self) -> Self:
        if not self.enabled:
            return self
        if not self.api_key:
            raise ValueError(
                "services.gemini.api_key is required when Gemini is enabled."
            )
        if not self.base_url:
            raise ValueError(
                "services.gemini.base_url is required when Gemini is enabled."
            )
        if self.models is None:
            raise ValueError(
                "services.gemini.models is required when Gemini is enabled."
            )
        return self


class SemanticSearchConfig(BaseModel):
    enabled: bool = True


class PresetOptionConfig(BaseModel):
    label: str
    prompt_suffix: str | None = None
    reference_image: str | None = None


class PresetsConfig(BaseModel):
    lights: dict[str, PresetOptionConfig] = Field(default_factory=dict)
    sceneries: dict[str, PresetOptionConfig] = Field(default_factory=dict)
    styles: dict[str, PresetOptionConfig] = Field(default_factory=dict)


class Service(BaseModel):
    openai: OpenAIConfig
    ollama: OllamaConfig = Field(default_factory=OllamaConfig)
    mistral: MistralConfig = Field(default_factory=MistralConfig)
    gemini: GeminiConfig = Field(default_factory=GeminiConfig)
    gemini_image: GeminiImageConfig = Field(default_factory=GeminiImageConfig)
    semantic_search: SemanticSearchConfig = Field(default_factory=SemanticSearchConfig)

    @model_validator(mode="after")
    def validate_provider_selection(self) -> Self:
        enabled_text_providers = [
            provider_name
            for provider_name, enabled in (
                ("services.openai", self.openai.enabled),
                ("services.ollama", self.ollama.enabled),
                ("services.mistral", self.mistral.enabled),
                ("services.gemini", self.gemini.enabled),
            )
            if enabled
        ]
        if len(enabled_text_providers) > 1:
            raise ValueError(
                "Enable only one text LLM provider at a time: "
                + ", ".join(enabled_text_providers)
            )
        return self


class RootConfig(BaseModel):
    authentication: Auth
    services: Service
    presets: PresetsConfig = Field(default_factory=PresetsConfig)
