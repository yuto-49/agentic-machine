"""Scenario simulation API endpoints."""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from agent.llm_provider import LLMAuthError, LLMConnectionError, LLMProviderError, LLMRateLimitError
from agent.scenario import PRESET_SCENARIOS, run_scenario
from db.engine import async_session_factory
from db.models import Scenario, ScenarioTurn

from sqlalchemy import select

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------

class ScenarioRunRequest(BaseModel):
    prompt: str = Field(..., min_length=10, description="Natural-language scenario description")
    preset_id: Optional[str] = Field(None, description="Optional preset scenario ID")


class ScenarioRunResponse(BaseModel):
    scenario_id: int
    spec: dict
    transcript: list[dict]
    outcome: dict


class PresetResponse(BaseModel):
    id: str
    title: str
    prompt: str
    description: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/scenario/presets", response_model=list[PresetResponse])
async def get_presets():
    """List all preset scenario templates."""
    return PRESET_SCENARIOS


@router.post("/scenario/run", response_model=ScenarioRunResponse)
async def run_scenario_endpoint(req: ScenarioRunRequest):
    """Run a scenario simulation from a prompt.

    This calls Claude API multiple times (parse + turns + evaluation),
    so expect 15-60 seconds depending on turn count.
    """
    prompt = req.prompt

    # If preset_id is provided, use the preset prompt
    if req.preset_id:
        preset = next((p for p in PRESET_SCENARIOS if p["id"] == req.preset_id), None)
        if not preset:
            raise HTTPException(status_code=404, detail=f"Preset '{req.preset_id}' not found")
        prompt = preset["prompt"]

    try:
        result = await run_scenario(prompt, preset_id=req.preset_id)
        return ScenarioRunResponse(**result)
    except ValueError as e:
        # Early validation errors (e.g. missing API key)
        return JSONResponse(
            status_code=400,
            content={"detail": str(e), "error_type": "config"},
        )
    except LLMAuthError:
        logger.warning("Scenario run failed: LLM authentication/billing error")
        return JSONResponse(
            status_code=402,
            content={
                "detail": "API credits exhausted or invalid key. Please check your LLM provider account.",
                "error_type": "billing",
            },
        )
    except LLMRateLimitError:
        logger.warning("Scenario run failed: LLM rate limit")
        return JSONResponse(
            status_code=429,
            content={
                "detail": "API rate limited. Please try again shortly.",
                "error_type": "rate_limit",
            },
        )
    except LLMConnectionError:
        logger.warning("Scenario run failed: Cannot connect to LLM provider")
        return JSONResponse(
            status_code=503,
            content={
                "detail": "Cannot connect to LLM provider. If using Ollama, ensure it is running (ollama serve).",
                "error_type": "connection",
            },
        )
    except LLMProviderError:
        logger.exception("Scenario run failed: LLM provider error")
        return JSONResponse(
            status_code=502,
            content={
                "detail": "AI service unavailable. Please try again later.",
                "error_type": "api_error",
            },
        )
    except Exception as e:
        logger.exception("Scenario run failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Simulation failed: {str(e)}")


@router.get("/scenario/{scenario_id}")
async def get_scenario(scenario_id: int):
    """Fetch a completed scenario by ID, including transcript."""
    async with async_session_factory() as session:
        scenario = await session.get(Scenario, scenario_id)
        if not scenario:
            raise HTTPException(status_code=404, detail="Scenario not found")

        turns_result = await session.execute(
            select(ScenarioTurn)
            .where(ScenarioTurn.scenario_id == scenario_id)
            .order_by(ScenarioTurn.turn_number)
        )
        turns = turns_result.scalars().all()

        return {
            "id": scenario.id,
            "prompt": scenario.prompt,
            "status": scenario.status,
            "total_turns": scenario.total_turns,
            "outcome": scenario.outcome,
            "seller_score": scenario.seller_score,
            "final_price": scenario.final_price,
            "product_cost": scenario.product_cost,
            "margin_achieved": scenario.margin_achieved,
            "tactics_used": scenario.tactics_used,
            "training_signal": scenario.training_signal,
            "outcome_json": scenario.outcome_json,
            "spec_json": scenario.spec_json,
            "created_at": str(scenario.created_at),
            "transcript": [
                {
                    "turn_number": t.turn_number,
                    "role": t.role_name,
                    "message": t.message,
                    "guardrail_hit": t.guardrail_hit,
                    "guardrail_detail": t.guardrail_detail,
                }
                for t in turns
            ],
        }


@router.get("/scenario")
async def list_scenarios():
    """List all scenarios (most recent first)."""
    async with async_session_factory() as session:
        result = await session.execute(
            select(Scenario).order_by(Scenario.created_at.desc()).limit(50)
        )
        scenarios = result.scalars().all()
        return [
            {
                "id": s.id,
                "prompt": s.prompt[:100] + ("..." if len(s.prompt) > 100 else ""),
                "status": s.status,
                "outcome": s.outcome,
                "seller_score": s.seller_score,
                "total_turns": s.total_turns,
                "created_at": str(s.created_at),
            }
            for s in scenarios
        ]
