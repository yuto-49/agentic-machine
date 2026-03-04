"""OpenClaw webhook bridge — routes messages between OpenClaw and the agent loop."""

import logging
from datetime import datetime

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from agent.loop import agent_step
from agent.pickup import expire_stale_pickups
from config_app import settings
from db.engine import async_session_factory

logger = logging.getLogger(__name__)
router = APIRouter()


# --- Pydantic schemas ---


class OpenClawInbound(BaseModel):
    sender_id: str
    sender_name: str = "anon"
    platform: str  # slack, discord
    channel: str = "claudius"
    text: str
    timestamp: str = ""


class AgentTrigger(BaseModel):
    type: str  # daily_morning, low_stock_check, nightly_reconciliation, manual
    message: str = ""


# --- Routes ---


@router.post("/webhook/oclaw")
async def openclaw_inbound(body: OpenClawInbound, request: Request):
    """Receives messages from OpenClaw gateway (Slack/Discord).

    OpenClaw forwards customer messages here. We run them through the
    agent loop and send the response back via OpenClaw.
    """
    # Validate webhook secret
    secret = request.headers.get("X-Webhook-Secret")
    if secret != settings.webhook_secret:
        raise HTTPException(status_code=401, detail="Invalid webhook secret")

    logger.info(
        "Inbound message from %s/%s: %s",
        body.platform,
        body.sender_name,
        body.text[:100],
    )

    # Run agent loop
    response_text = await agent_step(
        trigger=f"Customer message: {body.text}",
        metadata={
            "sender_id": body.sender_id,
            "sender_name": body.sender_name,
            "platform": body.platform,
            "channel": body.channel,
        },
    )

    # Send response back through OpenClaw
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                "http://localhost:18789/api/send",
                json={"channel": body.platform, "text": response_text},
                timeout=10.0,
            )
    except httpx.HTTPError as e:
        logger.warning("Failed to send response via OpenClaw: %s", e)

    return {"status": "ok", "response": response_text}


@router.post("/admin/agent/trigger")
async def admin_trigger(body: AgentTrigger):
    """Triggered by OpenClaw cron or manual admin action."""
    logger.info("Agent trigger: type=%s", body.type)

    # Auto-expire stale pickups on cron triggers
    if body.type in ("daily_morning", "nightly_reconciliation", "low_stock_check"):
        async with async_session_factory() as session:
            expired = await expire_stale_pickups(session)
            if expired:
                logger.info("Auto-expired %d pickup(s): %s", len(expired), expired)

    trigger_messages = {
        "daily_morning": (
            f"Good morning, Claudius. Date: {datetime.now().strftime('%Y-%m-%d')}. "
            "Please review inventory, check pending pickups, and take any necessary actions."
        ),
        "low_stock_check": "Low stock check triggered. Please check inventory for items with 3 or fewer units.",
        "nightly_reconciliation": (
            "End of day reconciliation. Please expire stale pickups, review today's activity, "
            "record any business insights, and save daily notes to scratchpad."
        ),
    }

    trigger_text = trigger_messages.get(
        body.type,
        f"Manual admin trigger: {body.message or 'No message provided'}",
    )

    response_text = await agent_step(
        trigger=trigger_text,
        metadata={"platform": "system", "sender_name": "cron"},
    )

    return {"status": "ok", "response": response_text}
