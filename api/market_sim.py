"""Market Prediction Simulation API endpoints."""

import json
import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from agent.market_sim import DEFAULT_AGENT_COUNT, run_market_simulation
from db.engine import async_session_factory
from db.models import MarketSimulation, MarketSimAgent, MarketSimDecision

from sqlalchemy import select, func

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------

class MarketSimRequest(BaseModel):
    location: str = Field(..., min_length=3, description="Location description, e.g. 'University of Tokyo Hongo Campus'")
    agent_count: int = Field(DEFAULT_AGENT_COUNT, ge=10, le=500, description="Number of synthetic customer agents to simulate")


class MarketSimStatusResponse(BaseModel):
    simulation_id: int
    location: str
    status: str
    agent_count: int
    created_at: str


# ---------------------------------------------------------------------------
# Background runner (so the HTTP call returns immediately)
# ---------------------------------------------------------------------------

async def _run_in_background(simulation_id: int, location: str, agent_count: int) -> None:
    """Background task wrapper — errors are logged, not re-raised."""
    try:
        await run_market_simulation(location, agent_count)
    except Exception as e:
        logger.exception("Background market simulation %d failed: %s", simulation_id, e)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/market-sim/run", status_code=202)
async def start_market_simulation(req: MarketSimRequest, background_tasks: BackgroundTasks):
    """Start a market prediction simulation for a location.

    Returns immediately with a simulation_id. Poll
    GET /api/market-sim/{simulation_id} for status and results.

    Typical runtime: 30-120 seconds depending on agent_count.
    """
    from db.models import MarketSimulation
    async with async_session_factory() as session:
        sim = MarketSimulation(
            location=req.location,
            agent_count=req.agent_count,
            status="pending",
        )
        session.add(sim)
        await session.commit()
        await session.refresh(sim)
        simulation_id = sim.id

    background_tasks.add_task(_run_in_background, simulation_id, req.location, req.agent_count)

    return {
        "simulation_id": simulation_id,
        "status": "pending",
        "message": f"Simulation started for '{req.location}' with {req.agent_count} agents. Poll for results.",
    }


@router.get("/market-sim/{simulation_id}")
async def get_market_simulation(simulation_id: int):
    """Fetch a market simulation by ID, including full report when completed."""
    async with async_session_factory() as session:
        sim = await session.get(MarketSimulation, simulation_id)
        if not sim:
            raise HTTPException(status_code=404, detail="Simulation not found")

        result = {
            "simulation_id": sim.id,
            "location": sim.location,
            "status": sim.status,
            "agent_count": sim.agent_count,
            "created_at": str(sim.created_at),
            "placement_recommendation": sim.placement_recommendation,
        }

        if sim.status == "completed":
            result["seed"] = json.loads(sim.location_seed_json) if sim.location_seed_json else {}
            result["report"] = json.loads(sim.prediction_report) if sim.prediction_report else {}
            result["top_products"] = json.loads(sim.top_products_json) if sim.top_products_json else []
            result["segments"] = json.loads(sim.segment_breakdown_json) if sim.segment_breakdown_json else []
            result["revenue_forecast"] = json.loads(sim.revenue_projection_json) if sim.revenue_projection_json else {}

        return result


@router.get("/market-sim/{simulation_id}/agents")
async def get_simulation_agents(simulation_id: int, limit: int = 50, offset: int = 0):
    """List synthetic agents generated for a simulation (paginated)."""
    async with async_session_factory() as session:
        sim = await session.get(MarketSimulation, simulation_id)
        if not sim:
            raise HTTPException(status_code=404, detail="Simulation not found")

        result = await session.execute(
            select(MarketSimAgent)
            .where(MarketSimAgent.simulation_id == simulation_id)
            .order_by(MarketSimAgent.agent_index)
            .offset(offset)
            .limit(limit)
        )
        agents = result.scalars().all()

        count_result = await session.execute(
            select(func.count()).where(MarketSimAgent.simulation_id == simulation_id)
        )
        total = count_result.scalar()

        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "agents": [
                {
                    "index": a.agent_index,
                    "age": a.age,
                    "gender": a.gender,
                    "occupation": a.occupation,
                    "income_level": a.income_level,
                    "lifestyle": a.lifestyle,
                    "dietary_prefs": a.dietary_prefs,
                    "price_sensitivity": a.price_sensitivity,
                    "visit_time": a.visit_time,
                    "visit_purpose": a.visit_purpose,
                    "budget": a.budget,
                }
                for a in agents
            ],
        }


@router.get("/market-sim/{simulation_id}/decisions")
async def get_simulation_decisions(simulation_id: int, limit: int = 100, offset: int = 0):
    """List individual agent purchase decisions for a simulation (paginated)."""
    async with async_session_factory() as session:
        sim = await session.get(MarketSimulation, simulation_id)
        if not sim:
            raise HTTPException(status_code=404, detail="Simulation not found")

        result = await session.execute(
            select(MarketSimDecision)
            .where(MarketSimDecision.simulation_id == simulation_id)
            .offset(offset)
            .limit(limit)
        )
        decisions = result.scalars().all()

        count_result = await session.execute(
            select(func.count()).where(MarketSimDecision.simulation_id == simulation_id)
        )
        total = count_result.scalar()

        purchases = sum(1 for d in decisions if d.did_purchase)

        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "purchase_rate_in_page": round(purchases / len(decisions), 3) if decisions else 0,
            "decisions": [
                {
                    "agent_id": d.agent_id,
                    "did_purchase": d.did_purchase,
                    "product_name": d.product_name,
                    "quantity": d.quantity,
                    "willingness_to_pay": d.willingness_to_pay,
                    "skip_reason": d.skip_reason,
                    "reasoning": d.reasoning,
                    "visit_frequency_per_week": d.visit_frequency_per_week,
                }
                for d in decisions
            ],
        }


@router.get("/market-sim")
async def list_market_simulations():
    """List all market simulations (most recent first)."""
    async with async_session_factory() as session:
        result = await session.execute(
            select(MarketSimulation)
            .order_by(MarketSimulation.created_at.desc())
            .limit(20)
        )
        sims = result.scalars().all()
        return [
            {
                "simulation_id": s.id,
                "location": s.location,
                "status": s.status,
                "agent_count": s.agent_count,
                "placement_recommendation": s.placement_recommendation,
                "created_at": str(s.created_at),
            }
            for s in sims
        ]
