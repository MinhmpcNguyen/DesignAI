from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator


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
    gpt_4o: OpenAIModelConfig | None = None
    gpt_4o_mini: OpenAIModelConfig | None = None

    def primary_model(self) -> OpenAIModelConfig:
        return self._require_model(self.primary or self.gpt_4o, "primary")

    def helper_model(self) -> OpenAIModelConfig:
        return self._require_model(self.helper or self.gpt_4o_mini, "helper")

    def resolved_models(self) -> dict[str, OpenAIModelConfig]:
        return {
            "primary": self.primary_model(),
            "helper": self.helper_model(),
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


class MistralModelConfig(BaseModel):
    name: str


class MistralModelGroupConfig(BaseModel):
    primary: MistralModelConfig
    helper: MistralModelConfig


class GeminiModelConfig(BaseModel):
    name: str


class GeminiModelGroupConfig(BaseModel):
    primary: GeminiModelConfig
    helper: GeminiModelConfig


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
        message = (
            "Configure either services.openai.api_key or both "
            + "services.openai.public_key and services.openai.private_key_file."
        )
        raise ValueError(message)

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


class PydanticAIAgentConfig(BaseModel):
    model: str
    system_prompt: str | None = None
    retries: int = Field(default=1, ge=0)
    output_mode: Literal["text", "json"] = "json"
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)


class PydanticAIConfig(BaseModel):
    agents: dict[str, PydanticAIAgentConfig] = Field(default_factory=dict)

    def agent(self, name: str) -> PydanticAIAgentConfig:
        agent_config = self.agents.get(name)
        if agent_config is None:
            raise ValueError(f"services.pydantic_ai.agents.{name} is required.")
        return agent_config


class Service(BaseModel):
    openai: OpenAIConfig
    ollama: OllamaConfig = Field(default_factory=OllamaConfig)
    mistral: MistralConfig = Field(default_factory=MistralConfig)
    gemini: GeminiConfig = Field(default_factory=GeminiConfig)
    semantic_search: SemanticSearchConfig = Field(default_factory=SemanticSearchConfig)
    pydantic_ai: PydanticAIConfig = Field(default_factory=PydanticAIConfig)

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
