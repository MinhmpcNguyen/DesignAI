from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Literal, Protocol, TypedDict

LLMModelKey = Literal["primary", "helper", "embedding"]
ThinkingLevel = Literal["minimal", "low", "medium", "high"]


class ChatMessage(TypedDict):
    role: Literal["system", "user", "assistant", "developer", "tool"]
    content: str


class LLMClientProtocol(Protocol):
    def get_model_name(self, key: LLMModelKey) -> str: ...

    def chat_completion(
        self,
        messages: Sequence[ChatMessage],
        *,
        model_key: LLMModelKey = "primary",
        model_name: str | None = None,
        fallback_model_names: Sequence[str] | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        max_tokens: int | None = None,
        thinking_level: ThinkingLevel | None = None,
        response_mime_type: str | None = None,
        response_schema: Mapping[str, object] | None = None,
        tools: Sequence[dict[str, object]] | None = None,
        tool_choice: dict[str, object] | str | None = None,
    ) -> object: ...

    def embeddings(
        self,
        inputs: str | Sequence[str],
        *,
        model_key: LLMModelKey = "embedding",
    ) -> object: ...
