import logging
import os

from cryptography.fernet import Fernet

from config import root_config
from config.models import OpenAIModelConfig, OpenAIModelGroupConfig

openai_config = root_config.services.openai
_BENCHMARK_TEXT_MODEL_ENV = "TKNT_BENCHMARK_TEXT_MODEL"
_OPENAI_AZURE_ENV = "OPENAI_AZURE"
_LEGACY_OPENAI_AZURE_ENV = "AZURE_OPENAI_ENABLED"
_OPENAI_API_KEY_ENV = "OPENAI_API_KEY"
_AZURE_OPENAI_API_KEY_ENV = "AZURE_OPENAI_API_KEY"
_OPENAI_API_VERSION_ENV = "OPENAI_API_VERSION"
_AZURE_OPENAI_API_VERSION_ENV = "AZURE_OPENAI_API_VERSION"
_OPENAI_BASE_URL_ENV = "OPENAI_BASE_URL"
_AZURE_OPENAI_ENDPOINT_ENV = "AZURE_OPENAI_ENDPOINT"
_LEGACY_AZURE_OPENAI_ENDPOINT_ENV = "OPENAI_AZURE_ENDPOINT"
_OPENAI_AGENT_MODEL_ENV = "OPENAI_AGENT_MODEL"
_OPENAI_PRIMARY_MODEL_ENV = "OPENAI_PRIMARY_MODEL"
_OPENAI_HELPER_MODEL_ENV = "OPENAI_HELPER_MODEL"
_OPENAI_EMBEDDING_MODEL_ENV = "OPENAI_EMBEDDING_MODEL"
_AZURE_OPENAI_CHAT_DEPLOYMENT_ENV = "AZURE_OPENAI_CHAT_DEPLOYMENT"
_AZURE_OPENAI_PRIMARY_DEPLOYMENT_ENV = "AZURE_OPENAI_PRIMARY_DEPLOYMENT"
_AZURE_OPENAI_HELPER_DEPLOYMENT_ENV = "AZURE_OPENAI_HELPER_DEPLOYMENT"
_AZURE_OPENAI_EMBEDDING_DEPLOYMENT_ENV = "AZURE_OPENAI_EMBEDDING_DEPLOYMENT"


def _configured_value(value: str | None) -> str | None:
    if value is None:
        return None
    clean = value.strip()
    if not clean or (clean.startswith("${") and clean.endswith("}")):
        return None
    return clean


def _configured_env(*names: str) -> str | None:
    for name in names:
        value = _configured_value(os.getenv(name))
        if value is not None:
            return value
    return None


def _env_bool_override(*names: str) -> bool | None:
    for name in names:
        raw = os.getenv(name)
        if raw is None:
            continue
        normalized = raw.strip().lower()
        if normalized in {"1", "true", "yes", "on", "azure"}:
            return True
        if normalized in {"0", "false", "no", "off", "openai"}:
            return False
    return None


def _azure_enabled() -> bool:
    env_override = _env_bool_override(_OPENAI_AZURE_ENV, _LEGACY_OPENAI_AZURE_ENV)
    if env_override is not None:
        return env_override
    return bool(openai_config.azure)


def _benchmark_text_model_name() -> str:
    return os.getenv(_BENCHMARK_TEXT_MODEL_ENV, "").strip()


def _api_version() -> str:
    return (
        _configured_env(_AZURE_OPENAI_API_VERSION_ENV, _OPENAI_API_VERSION_ENV)
        or openai_config.api_version
    )


def _openai_base_url() -> str | None:
    return _configured_env(_OPENAI_BASE_URL_ENV) or _configured_value(
        openai_config.base_url
    )


def _azure_endpoint() -> str | None:
    endpoint_from_env = _configured_env(
        _AZURE_OPENAI_ENDPOINT_ENV,
        _LEGACY_AZURE_OPENAI_ENDPOINT_ENV,
    )
    if endpoint_from_env is not None:
        return endpoint_from_env
    if openai_config.azure:
        return _configured_value(openai_config.base_url)
    return None


def _model_name_override(
    *,
    default: str,
    openai_env: str,
    azure_envs: tuple[str, ...] = (),
) -> str:
    if _azure_enabled():
        value = _configured_env(*azure_envs, openai_env)
        if value is not None:
            return value
    return _configured_env(openai_env) or default


def _azure_endpoint_for_model(model: OpenAIModelConfig) -> str | None:
    if not _azure_enabled():
        return model.azure_endpoint
    return _azure_endpoint() or _configured_value(model.azure_endpoint)


def _with_runtime_overrides(
    model: OpenAIModelConfig,
    *,
    name: str,
) -> OpenAIModelConfig:
    return OpenAIModelConfig(
        name=name,
        azure_endpoint=_azure_endpoint_for_model(model),
    )


def _resolve_private_key_location() -> str | None:
    private_key_file = _configured_value(openai_config.private_key_file)
    if private_key_file is None:
        return None
    return os.path.join(os.path.dirname(__file__), os.pardir, private_key_file)


PRIVATE_KEY_LOCATION = _resolve_private_key_location()


def _generation_models() -> OpenAIModelGroupConfig:
    models = openai_config.models
    forced_model_name = _benchmark_text_model_name()
    if not forced_model_name:
        primary = models.primary_model()
        helper = models.helper_model()
        embedding = models.embedding_model()
        return OpenAIModelGroupConfig(
            primary=_with_runtime_overrides(
                primary,
                name=_model_name_override(
                    default=primary.name,
                    openai_env=_OPENAI_PRIMARY_MODEL_ENV,
                    azure_envs=(
                        _AZURE_OPENAI_PRIMARY_DEPLOYMENT_ENV,
                        _AZURE_OPENAI_CHAT_DEPLOYMENT_ENV,
                    ),
                ),
            ),
            helper=_with_runtime_overrides(
                helper,
                name=_model_name_override(
                    default=helper.name,
                    openai_env=_OPENAI_HELPER_MODEL_ENV,
                    azure_envs=(
                        _AZURE_OPENAI_HELPER_DEPLOYMENT_ENV,
                        _AZURE_OPENAI_CHAT_DEPLOYMENT_ENV,
                    ),
                ),
            ),
            embedding=_with_runtime_overrides(
                embedding,
                name=_model_name_override(
                    default=embedding.name,
                    openai_env=_OPENAI_EMBEDDING_MODEL_ENV,
                    azure_envs=(_AZURE_OPENAI_EMBEDDING_DEPLOYMENT_ENV,),
                ),
            ),
        )
    return OpenAIModelGroupConfig(
        primary=_with_runtime_overrides(
            models.primary_model(),
            name=forced_model_name,
        ),
        helper=_with_runtime_overrides(
            models.helper_model(),
            name=forced_model_name,
        ),
        embedding=_with_runtime_overrides(
            models.embedding_model(),
            name=models.embedding_model().name,
        ),
    )


def _agent_models() -> dict[str, str]:
    forced_model_name = _benchmark_text_model_name()
    if forced_model_name:
        return {
            name: forced_model_name
            for name in openai_config.agent_models
            if name.strip()
        }
    agent_override = _configured_env(_OPENAI_AGENT_MODEL_ENV)
    if _azure_enabled():
        agent_override = (
            _configured_env(_AZURE_OPENAI_CHAT_DEPLOYMENT_ENV) or agent_override
        )
    if agent_override:
        return {
            name: agent_override
            for name in openai_config.agent_models
            if name.strip()
        }
    return {name: model.name for name, model in openai_config.agent_models.items()}


class OpenAIAccess:
    @staticmethod
    def _encrypt_string(input_string: str) -> None:
        if PRIVATE_KEY_LOCATION is None:
            raise ValueError("Missing services.openai.private_key_file configuration.")

        key = Fernet.generate_key()
        cipher_suite = Fernet(key)

        # Encrypt sensitive data
        encrypted_data = cipher_suite.encrypt(input_string.encode())

        with open(PRIVATE_KEY_LOCATION, "wb") as config_file:
            _ = config_file.write(encrypted_data)

        logging.info("Encrypted in %s!", PRIVATE_KEY_LOCATION)
        logging.info(f"The public key = {key}, please save it for further processing!")

    @staticmethod
    def get_openai_access() -> str | None:
        if _azure_enabled():
            api_key = _configured_env(
                _AZURE_OPENAI_API_KEY_ENV,
                _OPENAI_API_KEY_ENV,
            )
            if api_key:
                return api_key

        api_key = _configured_env(_OPENAI_API_KEY_ENV) or _configured_value(
            openai_config.api_key
        )
        if api_key:
            return api_key

        public_key = _configured_value(openai_config.public_key)
        if not public_key or PRIVATE_KEY_LOCATION is None:
            return None

        try:
            cipher_suite: Fernet = Fernet(key=public_key)
            with open(file=PRIVATE_KEY_LOCATION, mode="rb") as config_file:
                encrypted_data: bytes = config_file.read()
                decrypted_data: str = cipher_suite.decrypt(
                    token=encrypted_data
                ).decode()
                return decrypted_data
        except Exception:
            logging.exception(
                msg="Unexpected error during initialization OpenAI Access"
            )
            return None


class OpenAIConfig:
    ENABLED: bool = openai_config.enabled
    IS_OPENAI_AZURE: bool = _azure_enabled()
    OPENAI_API_KEY: str | None = OpenAIAccess.get_openai_access()
    API_VERSION: str = _api_version()
    BASE_URL: str | None = _openai_base_url()
    AZURE_ENDPOINT: str | None = _azure_endpoint()
    BENCHMARK_TEXT_MODEL: str = _benchmark_text_model_name()
    MODELS: OpenAIModelGroupConfig = _generation_models()
    AGENT_MODELS: dict[str, str] = _agent_models()
