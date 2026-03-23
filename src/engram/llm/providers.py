import asyncio

from openai import AsyncOpenAI

from engram.config import settings

MAX_RETRIES = 3


async def generate(system: str, user: str, max_tokens: int = 4096) -> str:
    """Generate text using the configured LLM provider."""
    client = AsyncOpenAI(api_key=settings.openai_api_key)

    for attempt in range(MAX_RETRIES):
        try:
            response = await client.chat.completions.create(
                model=settings.generation_model,
                max_completion_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
            return response.choices[0].message.content or ""
        except Exception:
            if attempt == MAX_RETRIES - 1:
                raise
            await asyncio.sleep(2**attempt)
    return ""
