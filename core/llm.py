import json
from openai import AsyncOpenAI
from config import settings
from core.logger import get_logger
from core.exceptions import LLMError

logger = get_logger(__name__)

_client: AsyncOpenAI | None = None


def get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            base_url=settings.llm_api_base,
            api_key=settings.llm_api_key,
            timeout=30.0,
            max_retries=2,
        )
        logger.info(f"LLM client initialized: {settings.llm_api_base} (heavy={settings.llm_model}, light={settings.llm_model_small})")
    return _client


def _resolve_model(model: str | None = None, task_type: str = "heavy") -> str:
    if model:
        return model
    if task_type == "light" and settings.llm_auto_downgrade:
        return settings.llm_model_small
    return settings.llm_model


async def chat(
    messages: list[dict],
    temperature: float | None = None,
    json_mode: bool = False,
    model: str | None = None,
    task_type: str = "heavy",
) -> str:
    resolved_model = _resolve_model(model, task_type)
    try:
        client = get_client()
        kwargs = {
            "model": resolved_model,
            "messages": messages,
            "temperature": temperature or settings.llm_temperature,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        response = await client.chat.completions.create(**kwargs)
        usage = response.usage
        if usage:
            logger.debug(f"LLM call ({resolved_model}): {usage.prompt_tokens}+{usage.completion_tokens} tokens")
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"LLM chat error: {e}")
        raise LLMError(str(e)) from e


async def chat_stream(messages: list[dict], temperature: float | None = None):
    try:
        client = get_client()
        stream = await client.chat.completions.create(
            model=settings.llm_model,
            messages=messages,
            temperature=temperature or settings.llm_temperature,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content
    except Exception as e:
        logger.error(f"LLM stream error: {e}")
        raise LLMError(str(e)) from e


async def chat_json(
    messages: list[dict],
    temperature: float | None = None,
    model: str | None = None,
    task_type: str = "heavy",
) -> dict:
    raw = await chat(messages, temperature=temperature, json_mode=True, model=model, task_type=task_type)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error(f"LLM JSON parse error: {e}, raw: {raw[:200]}")
        raise LLMError(f"LLM returned invalid JSON: {e}") from e
