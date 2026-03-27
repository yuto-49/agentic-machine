"""E2E test runner + FastAPI router for the Test Lab frontend."""

import asyncio
import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agent.llm_provider import LLMConnectionError, LLMProviderError
from api.websocket import broadcast
from config_app import settings
from db.engine import async_session_factory
from tests.e2e.orchestrator import Orchestrator, ScenarioResult
from tests.e2e.scenarios import SCENARIOS

logger = logging.getLogger(__name__)
router = APIRouter()

# In-memory store of test runs
_test_runs: dict[str, "TestRun"] = {}
_running_tasks: dict[str, asyncio.Task] = {}


@dataclass
class TestRun:
    id: str
    status: str = "pending"  # pending, running, completed, cancelled
    scenarios_requested: list[str] = field(default_factory=list)
    results: list[dict] = field(default_factory=list)
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    pass_count: int = 0
    fail_count: int = 0


# --- Pydantic schemas ---


class StartRunRequest(BaseModel):
    scenarios: list[str] = []
    config: dict = {}


class RunSummary(BaseModel):
    id: str
    status: str
    scenarios_requested: list[str]
    pass_count: int
    fail_count: int
    started_at: Optional[str]
    finished_at: Optional[str]


# --- Execution ---


async def _execute_run(run_id: str):
    """Background task that executes all requested scenarios."""
    run = _test_runs[run_id]
    run.status = "running"
    run.started_at = datetime.utcnow().isoformat()

    scenario_names = run.scenarios_requested or list(SCENARIOS.keys())

    for scenario_name in scenario_names:
        if run.status == "cancelled":
            break

        scenario = SCENARIOS.get(scenario_name)
        if scenario is None:
            run.results.append({
                "scenario_name": scenario_name,
                "status": "error",
                "steps": [],
                "error": f"Unknown scenario: {scenario_name}",
            })
            run.fail_count += 1
            continue

        async with async_session_factory() as session:
            orchestrator = Orchestrator(
                session=session,
                webhook_secret=settings.webhook_secret,
            )

            async def _progress(result: ScenarioResult, step):
                await broadcast({
                    "type": "test_update",
                    "run_id": run_id,
                    "scenario": result.scenario_name,
                    "step": step.step_name,
                    "status": step.status,
                    "duration_ms": step.duration_ms,
                })

            try:
                result = await orchestrator.run_scenario(scenario, progress_callback=_progress)
                run.results.append({
                    "scenario_name": result.scenario_name,
                    "status": result.status,
                    "steps": [
                        {
                            "name": s.step_name,
                            "status": s.status,
                            "duration_ms": s.duration_ms,
                            "customer_message": s.customer_message,
                            "agent_response": s.agent_response[:500],
                            "validation_details": s.validation_details,
                            "error": s.error,
                        }
                        for s in result.steps
                    ],
                    "started_at": result.started_at,
                    "finished_at": result.finished_at,
                })
                if result.status == "passed":
                    run.pass_count += 1
                else:
                    run.fail_count += 1
            except LLMConnectionError as e:
                logger.error("Scenario %s: LLM not reachable — %s", scenario_name, e)
                run.results.append({
                    "scenario_name": scenario_name,
                    "status": "error",
                    "steps": [],
                    "error": f"Cannot connect to LLM provider. If using Ollama, run: ollama serve",
                })
                run.fail_count += 1
                break  # No point continuing if LLM is down
            except LLMProviderError as e:
                logger.error("Scenario %s: LLM provider error — %s", scenario_name, e)
                run.results.append({
                    "scenario_name": scenario_name,
                    "status": "error",
                    "steps": [],
                    "error": f"LLM provider error: {e}",
                })
                run.fail_count += 1
            except Exception as e:
                logger.exception("Scenario %s failed", scenario_name)
                run.results.append({
                    "scenario_name": scenario_name,
                    "status": "error",
                    "steps": [],
                    "error": str(e),
                })
                run.fail_count += 1

            await broadcast({
                "type": "test_scenario_complete",
                "run_id": run_id,
                "scenario": scenario_name,
                "status": run.results[-1]["status"],
            })

    run.status = "completed"
    run.finished_at = datetime.utcnow().isoformat()


# --- API Routes ---


@router.post("/testing/run")
async def start_run(body: StartRunRequest):
    """Start a new test run."""
    run_id = uuid.uuid4().hex[:8]
    run = TestRun(
        id=run_id,
        scenarios_requested=body.scenarios,
    )
    _test_runs[run_id] = run

    task = asyncio.create_task(_execute_run(run_id))
    _running_tasks[run_id] = task

    return {"run_id": run_id, "status": "started"}


@router.get("/testing/runs")
async def list_runs():
    """List all test runs with pass/fail counts."""
    return [
        RunSummary(
            id=r.id,
            status=r.status,
            scenarios_requested=r.scenarios_requested,
            pass_count=r.pass_count,
            fail_count=r.fail_count,
            started_at=r.started_at,
            finished_at=r.finished_at,
        ).model_dump()
        for r in reversed(_test_runs.values())
    ]


@router.get("/testing/runs/{run_id}")
async def get_run(run_id: str):
    """Get detailed results for a specific run."""
    run = _test_runs.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return {
        "id": run.id,
        "status": run.status,
        "scenarios_requested": run.scenarios_requested,
        "results": run.results,
        "pass_count": run.pass_count,
        "fail_count": run.fail_count,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
    }


@router.post("/testing/runs/{run_id}/stop")
async def stop_run(run_id: str):
    """Cancel a running test."""
    run = _test_runs.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    run.status = "cancelled"
    task = _running_tasks.get(run_id)
    if task and not task.done():
        task.cancel()
    return {"status": "cancelled"}


@router.get("/testing/scenarios")
async def list_scenarios():
    """List available test scenarios."""
    return [
        {
            "name": key,
            "description": s.description,
            "step_count": len(s.steps),
        }
        for key, s in SCENARIOS.items()
    ]
