"""Model and region settings. Override with environment variables."""

from __future__ import annotations

import os

from chatlas import ChatBedrock

# The event kit tests these GPT inference profiles in us-east-1:
#   us.openai.gpt-5.4, us.openai.gpt-5.5, us.openai.gpt-5.6-luna (default),
#   us.openai.gpt-5.6-sol, us.openai.gpt-5.6-terra
# Claude profiles (for example us.anthropic.claude-sonnet-5-5) also work if
# your account allows them.
MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "us.openai.gpt-5.6-luna")
REGION = os.getenv("AWS_REGION", "us-east-1")
MAX_TOKENS = int(os.getenv("CAREGIVERS_MAX_TOKENS", "2000"))


def make_chat(system_prompt: str, model: str | None = None) -> ChatBedrock:
    """A chatlas chat on Bedrock.

    `api="converse"` matters: with a `us.*` inference profile ID, chatlas would
    otherwise route GPT models to the bedrock-mantle endpoint and return 404.
    """
    return ChatBedrock(
        model=model or MODEL_ID,
        api="converse",
        aws_region=REGION,
        max_tokens=MAX_TOKENS,
        system_prompt=system_prompt,
    )
