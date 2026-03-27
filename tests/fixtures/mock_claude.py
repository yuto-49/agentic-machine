"""Deterministic LLM provider mock for agent loop tests."""

from typing import Any

from agent.llm_provider import LLMProvider, LLMResponse, TextBlock, ToolUseBlock


# Backward-compat aliases
MockTextBlock = TextBlock
MockToolUseBlock = ToolUseBlock
MockResponse = LLMResponse


class MockLLMProvider(LLMProvider):
    """Mock LLM provider that returns queued responses."""

    def __init__(self):
        self._response_queue: list[LLMResponse] = []
        self.calls: list[dict[str, Any]] = []

    def queue_response(self, response: LLMResponse) -> None:
        self._response_queue.append(response)

    def queue_text(self, text: str) -> None:
        self._response_queue.append(
            LLMResponse(content=[TextBlock(text=text)])
        )

    def queue_tool_then_text(
        self,
        tool_name: str,
        tool_input: dict,
        final_text: str,
        tool_id: str = "toolu_test_001",
    ) -> None:
        self._response_queue.append(
            LLMResponse(
                content=[ToolUseBlock(id=tool_id, name=tool_name, input=tool_input)],
                stop_reason="tool_use",
            )
        )
        self._response_queue.append(
            LLMResponse(content=[TextBlock(text=final_text)])
        )

    def create(self, **kwargs) -> LLMResponse:
        self.calls.append(kwargs)
        if not self._response_queue:
            return LLMResponse(content=[TextBlock(text="(no queued response)")])
        return self._response_queue.pop(0)

    async def acreate(self, **kwargs) -> LLMResponse:
        return self.create(**kwargs)


# Backward-compat alias
MockAnthropicClient = MockLLMProvider
