from config.openai_config import OpenAIConfig


def main() -> None:
    primary_model = OpenAIConfig.MODELS.primary_model().name
    helper_model = OpenAIConfig.MODELS.helper_model().name

    print(
        {
            "enabled": OpenAIConfig.ENABLED,
            "azure": OpenAIConfig.IS_OPENAI_AZURE,
            "endpoint_configured": bool(OpenAIConfig.AZURE_ENDPOINT),
            "credential_configured": bool(OpenAIConfig.OPENAI_API_KEY),
            "primary_model": primary_model,
            "helper_model": helper_model,
            "agent_model_count": len(OpenAIConfig.AGENT_MODELS),
        }
    )


if __name__ == "__main__":
    main()
