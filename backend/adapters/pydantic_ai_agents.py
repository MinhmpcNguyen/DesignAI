from __future__ import annotations

from pydantic_ai import Agent

from config.models import PydanticAIAgentConfig


class PydanticAIAgentFactory:
    def text_agent(self, config: PydanticAIAgentConfig) -> Agent[None, str]:
        system_prompt = config.system_prompt or ()
        return Agent(
            config.model,
            system_prompt=system_prompt,
            retries=config.retries,
        )
