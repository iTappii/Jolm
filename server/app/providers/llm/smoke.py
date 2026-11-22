"""`make llm-smoke`: send one tiny prompt to the configured DeepSeek and print the answer."""

import asyncio
import sys

from app.config import get_settings
from app.providers.llm import LLMError, Message, collect, get_llm_provider


async def main() -> int:
    settings = get_settings()
    if not settings.deepseek_api_key.get_secret_value():
        print(
            "DEEPSEEK_API_KEY is empty. Put DEEPSEEK_API_KEY=<your key> in .env (not in git),\n"
            "optionally DEEPSEEK_MODEL / DEEPSEEK_BASE_URL, then run `make llm-smoke` again."
        )
        return 0
    settings.llm_provider = "deepseek"
    try:
        provider = get_llm_provider(settings)
        done = await collect(provider.stream([Message(role="user", content="Say OK in one word.")]))
    except LLMError as exc:
        print(f"llm-smoke failed: {exc.code}: {exc.message}")
        return 1
    print(f"model reply: {done.text!r}")
    print(f"usage: in={done.usage.input_tokens} out={done.usage.output_tokens}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
