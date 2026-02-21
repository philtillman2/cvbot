import json
from collections.abc import AsyncGenerator

import httpx
from app.config import settings

OPENROUTER_URL = settings.openrouter_url
MODELS_URL = settings.models_url

# Cached model pricing: model_id -> {input, output} price per token
_pricing: dict[str, dict[str, float]] = {}


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": settings.url,
        "X-Title": "CVbot",
    }


async def fetch_models() -> list[dict]:
    """Fetch available models and cache pricing."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(MODELS_URL, headers=_headers(), timeout=15)
        resp.raise_for_status()
        data = resp.json().get("data", [])

    for m in data:
        pricing = m.get("pricing", {})
        _pricing[m["id"]] = {
            "input": float(pricing.get("prompt", "0")),
            "output": float(pricing.get("completion", "0")),
        }
    return data


def get_model_pricing(model_id: str) -> dict[str, float] | None:
    return _pricing.get(model_id)


async def stream_chat(
    messages: list[dict[str, str]],
    model: str = "openai/gpt-4o-mini",
) -> AsyncGenerator[dict, None]:
    """
    Stream chat completion from OpenRouter.
    Yields dicts: {"type": "token", "content": "..."} or {"type": "usage", ...}
    """
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "usage": {"include": True},
    }

    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0)) as client:
        async with client.stream(
            "POST", OPENROUTER_URL, headers=_headers(), json=payload
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data_str = line[6:]
                if data_str.strip() == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_str)
                except json.JSONDecodeError:
                    continue

                # Token content
                choices = chunk.get("choices", [])
                if choices:
                    delta = choices[0].get("delta", {})
                    content = delta.get("content")
                    if content:
                        yield {"type": "token", "content": content}

                # Usage info (usually in the final chunk)
                usage = chunk.get("usage")
                if usage:
                    yield {
                        "type": "usage",
                        "input_tokens": usage.get("prompt_tokens", 0),
                        "output_tokens": usage.get("completion_tokens", 0),
                    }
