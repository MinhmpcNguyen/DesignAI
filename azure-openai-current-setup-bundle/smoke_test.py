from typing import cast

from openai.types.chat import ChatCompletion

from clients.openai_client import OpenAIClient


def main() -> None:
    client = OpenAIClient()
    # OpenAIClient delegates to chat.completions.create, which returns ChatCompletion.
    response = cast(
        ChatCompletion,
        client.chat_completion(
            [
                {
                    "role": "user",
                    "content": "Reply exactly with: azure-ok",
                }
            ],
            max_tokens=64,
        ),
    )

    if not response.choices:
        raise RuntimeError("Azure/OpenAI returned no choices.")

    content = response.choices[0].message.content
    if content is None:
        raise RuntimeError("Azure/OpenAI returned an empty message.")

    print(content)


if __name__ == "__main__":
    main()
