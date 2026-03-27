"""LLM provider abstraction — switch between Anthropic and Ollama.

Unified dataclasses (TextBlock, ToolUseBlock, LLMResponse) mirror the
Anthropic SDK's attribute interface so the rest of the codebase needs
minimal changes.
"""

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Unified response types
# ---------------------------------------------------------------------------

@dataclass
class TextBlock:
    text: str
    type: str = "text"


@dataclass
class ToolUseBlock:
    id: str
    name: str
    input: dict = field(default_factory=dict)
    type: str = "tool_use"


@dataclass
class LLMResponse:
    content: list = field(default_factory=list)
    stop_reason: str = "end_turn"
    model: str = ""
    usage: dict = field(default_factory=lambda: {"input_tokens": 0, "output_tokens": 0})


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------

class LLMProviderError(Exception):
    """Base exception for LLM provider errors."""


class LLMAuthError(LLMProviderError):
    """Authentication or billing error."""


class LLMRateLimitError(LLMProviderError):
    """Rate limit exceeded."""


class LLMConnectionError(LLMProviderError):
    """Cannot connect to LLM service (e.g. Ollama not running)."""


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class LLMProvider(ABC):
    @abstractmethod
    def create(self, **kwargs) -> LLMResponse:
        """Synchronous completion."""

    @abstractmethod
    async def acreate(self, **kwargs) -> LLMResponse:
        """Async completion."""


# ---------------------------------------------------------------------------
# Anthropic provider
# ---------------------------------------------------------------------------

class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: str):
        import anthropic as _anthropic
        self._sync = _anthropic.Anthropic(api_key=api_key)
        self._async = _anthropic.AsyncAnthropic(api_key=api_key)
        self._anthropic = _anthropic

    def _convert_response(self, resp) -> LLMResponse:
        blocks = []
        for b in resp.content:
            if b.type == "text":
                blocks.append(TextBlock(text=b.text))
            elif b.type == "tool_use":
                blocks.append(ToolUseBlock(id=b.id, name=b.name, input=b.input))
            else:
                blocks.append(TextBlock(text=str(b), type=b.type))
        return LLMResponse(
            content=blocks,
            stop_reason=resp.stop_reason,
            model=resp.model,
            usage={"input_tokens": resp.usage.input_tokens, "output_tokens": resp.usage.output_tokens},
        )

    def create(self, **kwargs) -> LLMResponse:
        try:
            resp = self._sync.messages.create(**kwargs)
            return self._convert_response(resp)
        except self._anthropic.AuthenticationError as e:
            raise LLMAuthError(str(e)) from e
        except self._anthropic.RateLimitError as e:
            raise LLMRateLimitError(str(e)) from e
        except self._anthropic.APIStatusError as e:
            if "credit balance" in str(e).lower():
                raise LLMAuthError(str(e)) from e
            raise LLMProviderError(str(e)) from e

    async def acreate(self, **kwargs) -> LLMResponse:
        try:
            resp = await self._async.messages.create(**kwargs)
            return self._convert_response(resp)
        except self._anthropic.AuthenticationError as e:
            raise LLMAuthError(str(e)) from e
        except self._anthropic.RateLimitError as e:
            raise LLMRateLimitError(str(e)) from e
        except self._anthropic.APIStatusError as e:
            if "credit balance" in str(e).lower():
                raise LLMAuthError(str(e)) from e
            raise LLMProviderError(str(e)) from e


# ---------------------------------------------------------------------------
# Ollama provider (OpenAI-compatible API)
# ---------------------------------------------------------------------------

class OllamaProvider(LLMProvider):
    def __init__(self, base_url: str, default_model: str):
        from openai import OpenAI
        self._client = OpenAI(base_url=base_url, api_key="ollama")
        self._default_model = default_model

    # -- Format translators --------------------------------------------------

    @staticmethod
    def _convert_tools(anthropic_tools: list[dict]) -> list[dict]:
        """Anthropic tool format -> OpenAI function-calling format."""
        openai_tools = []
        for t in anthropic_tools:
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": t.get("input_schema", {}),
                },
            })
        return openai_tools

    @staticmethod
    def _convert_messages(
        messages: list[dict],
        system: str | None = None,
    ) -> list[dict]:
        """Anthropic conversation format -> OpenAI chat format."""
        oai_msgs: list[dict] = []

        if system:
            oai_msgs.append({"role": "system", "content": system})

        for msg in messages:
            role = msg["role"]
            content = msg.get("content", "")

            # Simple string content
            if isinstance(content, str):
                oai_msgs.append({"role": role, "content": content})
                continue

            # List content (tool_use blocks from assistant, tool_result from user)
            if isinstance(content, list):
                # Check if this is a tool_result list (user role)
                if content and isinstance(content[0], dict) and content[0].get("type") == "tool_result":
                    for block in content:
                        oai_msgs.append({
                            "role": "tool",
                            "tool_call_id": block["tool_use_id"],
                            "content": block.get("content", ""),
                        })
                    continue

                # Assistant message with tool_use blocks
                text_parts = []
                tool_calls = []
                for block in content:
                    if isinstance(block, dict):
                        if block.get("type") == "text":
                            text_parts.append(block["text"])
                        elif block.get("type") == "tool_use":
                            tool_calls.append({
                                "id": block["id"],
                                "type": "function",
                                "function": {
                                    "name": block["name"],
                                    "arguments": json.dumps(block["input"]),
                                },
                            })

                assistant_msg: dict[str, Any] = {"role": "assistant"}
                if text_parts:
                    assistant_msg["content"] = "\n".join(text_parts)
                else:
                    assistant_msg["content"] = None
                if tool_calls:
                    assistant_msg["tool_calls"] = tool_calls
                oai_msgs.append(assistant_msg)
                continue

            # Fallback
            oai_msgs.append({"role": role, "content": str(content)})

        return oai_msgs

    @staticmethod
    def _convert_response(resp, model: str) -> LLMResponse:
        """OpenAI chat completion response -> our LLMResponse."""
        msg = resp.choices[0].message
        blocks: list = []

        if msg.content:
            blocks.append(TextBlock(text=msg.content))

        # Detect tool calls by presence, not by finish_reason
        if msg.tool_calls:
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except (json.JSONDecodeError, TypeError):
                    args = {"_raw": tc.function.arguments}
                    logger.warning("Malformed tool args from Ollama: %s", tc.function.arguments)
                blocks.append(ToolUseBlock(
                    id=tc.id or f"ollama_{tc.function.name}",
                    name=tc.function.name,
                    input=args,
                ))

        stop_reason = "tool_use" if msg.tool_calls else "end_turn"

        usage_data = {"input_tokens": 0, "output_tokens": 0}
        if resp.usage:
            usage_data = {
                "input_tokens": resp.usage.prompt_tokens or 0,
                "output_tokens": resp.usage.completion_tokens or 0,
            }

        return LLMResponse(content=blocks, stop_reason=stop_reason, model=model, usage=usage_data)

    # -- Public API -----------------------------------------------------------

    def _build_kwargs(self, **kwargs) -> dict:
        """Translate Anthropic-style kwargs to OpenAI-style."""
        model = kwargs.pop("model", self._default_model)
        max_tokens = kwargs.pop("max_tokens", 2048)
        system = kwargs.pop("system", None)
        messages = kwargs.pop("messages", [])
        tools = kwargs.pop("tools", None)

        oai_kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": self._convert_messages(messages, system=system),
        }
        if tools:
            oai_kwargs["tools"] = self._convert_tools(tools)

        return oai_kwargs, model

    def create(self, **kwargs) -> LLMResponse:
        try:
            oai_kwargs, model = self._build_kwargs(**kwargs)
            resp = self._client.chat.completions.create(**oai_kwargs)
            return self._convert_response(resp, model)
        except ConnectionError as e:
            raise LLMConnectionError(
                f"Cannot connect to Ollama at {self._client.base_url}. Is it running? (ollama serve)"
            ) from e
        except Exception as e:
            if "connection" in str(e).lower():
                raise LLMConnectionError(
                    f"Cannot connect to Ollama at {self._client.base_url}. Is it running? (ollama serve)"
                ) from e
            raise LLMProviderError(str(e)) from e

    async def acreate(self, **kwargs) -> LLMResponse:
        # openai SDK's sync client works fine for Ollama local calls.
        # For true async we'd need AsyncOpenAI, but Ollama is local and fast.
        return self.create(**kwargs)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def get_llm_provider() -> LLMProvider:
    """Return the configured LLM provider instance."""
    from config_app import settings

    if settings.llm_provider == "ollama":
        return OllamaProvider(
            base_url=settings.ollama_base_url,
            default_model=settings.ollama_model,
        )
    else:
        return AnthropicProvider(api_key=settings.anthropic_api_key)
