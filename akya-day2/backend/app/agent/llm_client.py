"""LLM client for the organizer's OpenAI-compatible GLM gateway.

Models and settings: docs/AGENT_PROMPTS_AND_TOOLS.md §1.

One async client per process: tool calling, a concurrency limit matching the gateway (4 requests
at once), a disk cache keyed by the full request (reruns and demos cost nothing) and one log line
per call. Agents depend on the `ChatLLM` protocol, so tests use a fake and another provider can be
plugged in behind the same interface.
"""

import asyncio
import hashlib
import json
import logging
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Protocol, cast

import openai
from openai import AsyncOpenAI

from app.core.config import Settings
from app.core.errors import LLMError

logger = logging.getLogger(__name__)

Message = dict[str, Any]
ToolSpec = dict[str, Any]


@dataclass(frozen=True)
class ToolCall:
    """One function call requested by the model; `arguments` is the raw JSON string."""

    id: str
    name: str
    arguments: str


@dataclass(frozen=True)
class ChatResult:
    """The parts of a chat completion the agents use."""

    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    reasoning: str = ""  # GLM's thinking text (`reasoning_content`); kept for traces only
    finish_reason: str = "stop"
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int = 0
    cached: bool = False

    def assistant_message(self) -> Message:
        """The assistant turn to append before sending tool results back."""
        msg: Message = {"role": "assistant", "content": self.content}
        if self.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": c.id,
                    "type": "function",
                    "function": {"name": c.name, "arguments": c.arguments},
                }
                for c in self.tool_calls
            ]
        return msg


class ChatLLM(Protocol):
    """Chat completion with tools; implemented by `GLMClient` and by test fakes."""

    model: str

    async def chat(
        self,
        messages: list[Message],
        tools: list[ToolSpec],
        *,
        model: str | None = None,
        reasoning_effort: str = "low",
        max_tokens: int = 8000,
    ) -> ChatResult:
        """Run one completion; raises LLMError on transport or API failure."""
        ...


class GLMClient:
    """`ChatLLM` over the OpenAI-compatible GLM gateway."""

    def __init__(self, settings: Settings) -> None:
        if not settings.llm_enabled or settings.llm_api_key is None:
            raise LLMError("no GLM API key configured")
        self.model = settings.llm_model
        self._client = AsyncOpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key.get_secret_value(),
            timeout=settings.llm_timeout_s,
            max_retries=settings.llm_max_retries,
        )
        self._limit = asyncio.Semaphore(settings.llm_max_concurrency)
        self._cache_dir: Path | None = settings.cache_dir / "llm" if settings.llm_cache else None
        self.calls = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0

    async def chat(
        self,
        messages: list[Message],
        tools: list[ToolSpec],
        *,
        model: str | None = None,
        reasoning_effort: str = "low",
        max_tokens: int = 8000,
    ) -> ChatResult:
        """Run one completion (or return the cached one for an identical request)."""
        request: dict[str, Any] = {
            "model": model or self.model,
            "messages": messages,
            "reasoning_effort": reasoning_effort,
            "max_tokens": max_tokens,
        }
        if tools:
            request["tools"] = tools
        key = hashlib.sha256(
            json.dumps(request, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
        cached = self._read_cache(key)
        if cached is not None:
            logger.info("llm call", extra={"model": request["model"], "cache_hit": True})
            return cached

        started = time.perf_counter()
        async with self._limit:
            try:
                response = await self._client.chat.completions.create(**cast(Any, request))
            except openai.OpenAIError as exc:
                raise LLMError(f"{type(exc).__name__}: {exc}") from exc
        latency_ms = round((time.perf_counter() - started) * 1000)
        if not response.choices:
            raise LLMError("empty response")
        choice = response.choices[0]
        usage = response.usage
        extra = choice.message.model_extra or {}
        result = ChatResult(
            content=choice.message.content or "",
            reasoning=str(extra.get("reasoning_content") or ""),
            tool_calls=[
                ToolCall(id=c.id, name=c.function.name, arguments=c.function.arguments or "{}")
                for c in (choice.message.tool_calls or [])
                if c.type == "function"
            ],
            finish_reason=choice.finish_reason or "stop",
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            latency_ms=latency_ms,
        )
        self.calls += 1
        self.prompt_tokens += result.prompt_tokens
        self.completion_tokens += result.completion_tokens
        logger.info(
            "llm call",
            extra={
                "model": request["model"],
                "cache_hit": False,
                "latency_ms": latency_ms,
                "prompt_tokens": result.prompt_tokens,
                "completion_tokens": result.completion_tokens,
                "finish_reason": result.finish_reason,
            },
        )
        self._write_cache(key, result)
        return result

    def _read_cache(self, key: str) -> ChatResult | None:
        if self._cache_dir is None:
            return None
        path = self._cache_dir / f"{key}.json"
        if not path.is_file():
            return None
        raw = json.loads(path.read_text(encoding="utf-8"))
        raw["tool_calls"] = [ToolCall(**c) for c in raw["tool_calls"]]
        return ChatResult(**{"reasoning": "", **raw, "cached": True})

    def _write_cache(self, key: str, result: ChatResult) -> None:
        if self._cache_dir is None or result.finish_reason == "length":
            return
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        (self._cache_dir / f"{key}.json").write_text(
            json.dumps(asdict(result), ensure_ascii=False), encoding="utf-8"
        )


def build_llm(settings: Settings) -> ChatLLM | None:
    """The configured client, or None when no key is set (agents then use their fallbacks)."""
    return GLMClient(settings) if settings.llm_enabled else None


def llm_status(settings: Settings) -> tuple[bool, str]:
    """Report whether an LLM endpoint is configured (no network call)."""
    if not settings.llm_enabled:
        return False, "no API key configured; fallback brief will be used"
    return True, f"{settings.llm_model} @ {settings.llm_base_url}"
