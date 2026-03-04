"""Core agent loop — calls Claude API directly with tool-use.

This is the brain of Claudius. It manages the conversation history,
calls Claude with tool definitions, executes tools, and logs decisions.
OpenClaw is NOT involved here — it only routes messages to/from this loop.
"""

import json
import logging
import uuid
from typing import Any, Optional

import anthropic

from agent.classifier import classify_interaction
from agent.context import prime_context
from agent.guardrails import validate_action
from agent.memory import AgentMemory
from agent.prompts import SYSTEM_PROMPT, TOOL_DEFINITIONS
from agent.tools import execute_tool
from config_app import settings
from db.engine import async_session_factory
from db.models import AgentDecision, Message, UserInteraction

logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-5-20250929"


def _serialize_content(content) -> list[dict[str, Any]]:
    """Convert Anthropic SDK content blocks to plain dicts for JSON serialization."""
    serialized = []
    for block in content:
        if block.type == "text":
            serialized.append({"type": "text", "text": block.text})
        elif block.type == "tool_use":
            serialized.append({
                "type": "tool_use",
                "id": block.id,
                "name": block.name,
                "input": block.input,
            })
        else:
            serialized.append({"type": block.type, "text": str(block)})
    return serialized
MAX_TOKENS = 4096
MAX_CONTEXT_TOKENS = 30_000

# In-memory conversation history (rolling window).
# In production this could be persisted, but for now it resets on restart.
_conversation_history: list[dict[str, Any]] = []


def _trim_to_tokens(
    messages: list[dict[str, Any]],
    max_tokens: int,
) -> list[dict[str, Any]]:
    """Trim conversation history to fit within token budget.

    Rough approximation: 1 token ~= 4 chars. We keep the most recent
    messages that fit within the budget.
    """
    total_chars = 0
    char_limit = max_tokens * 4
    trimmed: list[dict[str, Any]] = []

    for msg in reversed(messages):
        content = msg.get("content", "")
        if isinstance(content, str):
            size = len(content)
        elif isinstance(content, list):
            size = len(json.dumps(content))
        else:
            size = len(str(content))

        total_chars += size
        if total_chars > char_limit:
            break
        trimmed.insert(0, msg)

    return trimmed


async def _log_decision(
    session,
    trigger: str,
    action: str,
    reasoning: str,
    was_blocked: bool = False,
) -> None:
    """Log an agent decision to the database."""
    session.add(
        AgentDecision(
            trigger=trigger[:500],
            action=action[:500],
            reasoning=reasoning[:1000],
            was_blocked=was_blocked,
        )
    )
    await session.commit()


async def _log_message(
    session,
    direction: str,
    content: str,
    sender_id: Optional[str] = None,
    platform: Optional[str] = None,
    channel: Optional[str] = None,
) -> None:
    session.add(
        Message(
            direction=direction,
            content=content,
            sender_id=sender_id,
            platform=platform,
            channel=channel,
        )
    )
    await session.commit()


async def _log_interaction(
    session,
    sender_id: Optional[str],
    sender_name: Optional[str],
    platform: Optional[str],
    message: str,
    response: str,
    interaction_type: str,
) -> None:
    session.add(
        UserInteraction(
            session_id=str(uuid.uuid4()),
            sender_id=sender_id,
            sender_name=sender_name,
            platform=platform,
            interaction_type=interaction_type,
            message_text=message,
            agent_response=response,
        )
    )
    await session.commit()


async def agent_step(
    trigger: str,
    metadata: Optional[dict[str, Any]] = None,
) -> str:
    """One iteration of the agent loop.

    Args:
        trigger: Input text (customer message, cron trigger, purchase event).
        metadata: Optional context (sender_id, platform, channel, etc.).

    Returns:
        The agent's text response.
    """
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    # Enrich trigger with metadata for context
    enriched_trigger = trigger
    if metadata:
        platform = metadata.get("platform", "unknown")
        sender = metadata.get("sender_name", "anon")
        enriched_trigger = f"[{platform}|{sender}] {trigger}"

    _conversation_history.append({"role": "user", "content": enriched_trigger})
    trimmed = _trim_to_tokens(_conversation_history, MAX_CONTEXT_TOKENS)

    async with async_session_factory() as session:
        memory = AgentMemory(session)

        # Context priming — selective recall
        sender_id = metadata.get("sender_id") if metadata else None
        sender_name = metadata.get("sender_name") if metadata else None
        context_block = await prime_context(sender_id, sender_name, trigger, session)
        system_with_context = SYSTEM_PROMPT
        if context_block:
            system_with_context = f"{SYSTEM_PROMPT}\n\n{context_block}"

        # Log incoming message
        await _log_message(
            session,
            direction="customer_to_agent",
            content=trigger,
            sender_id=sender_id,
            platform=metadata.get("platform") if metadata else None,
            channel=metadata.get("channel") if metadata else None,
        )

        # Call Claude API
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system_with_context,
            tools=TOOL_DEFINITIONS,
            messages=trimmed,
        )

        # Process tool calls iteratively
        while response.stop_reason == "tool_use":
            assistant_content = response.content
            _conversation_history.append({"role": "assistant", "content": _serialize_content(assistant_content)})

            tool_results = []
            for block in assistant_content:
                if block.type == "tool_use":
                    # Inject metadata into pickup tools
                    if block.name == "create_pickup_reservation" and metadata:
                        block.input.setdefault("sender_id", metadata.get("sender_id"))
                        block.input.setdefault("platform", metadata.get("platform"))

                    # Guardrail check
                    validation = await validate_action(block.name, block.input, session)

                    if not validation["allowed"]:
                        await _log_decision(
                            session,
                            trigger=enriched_trigger[:200],
                            action=f"BLOCKED: {block.name}({json.dumps(block.input)})",
                            reasoning=validation["reason"],
                            was_blocked=True,
                        )
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": f"Action blocked by guardrail: {validation['reason']}",
                            }
                        )
                        continue

                    # Execute the tool
                    result = await execute_tool(block.name, block.input, session, memory)
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": str(result),
                        }
                    )

                    # Audit log
                    await _log_decision(
                        session,
                        trigger=enriched_trigger[:200],
                        action=f"{block.name}({json.dumps(block.input)})",
                        reasoning=f"Result: {str(result)[:500]}",
                    )

            _conversation_history.append({"role": "user", "content": tool_results})
            trimmed = _trim_to_tokens(_conversation_history, MAX_CONTEXT_TOKENS)

            response = client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=system_with_context,
                tools=TOOL_DEFINITIONS,
                messages=trimmed,
            )

        # Extract final text
        final_text = ""
        for block in response.content:
            if hasattr(block, "text"):
                final_text += block.text

        _conversation_history.append({"role": "assistant", "content": _serialize_content(response.content)})

        # Log response
        await _log_message(
            session,
            direction="agent_to_customer",
            content=final_text,
            sender_id="claudius",
            platform=metadata.get("platform") if metadata else None,
            channel=metadata.get("channel") if metadata else None,
        )

        # Log interaction for research
        if metadata:
            await _log_interaction(
                session,
                sender_id=metadata.get("sender_id"),
                sender_name=metadata.get("sender_name"),
                platform=metadata.get("platform"),
                message=trigger,
                response=final_text,
                interaction_type=classify_interaction(trigger),
            )

    return final_text
