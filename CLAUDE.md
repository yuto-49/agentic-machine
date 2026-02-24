# Claudius — AI Vending Machine

## Project Overview

An AI-powered vending machine managed by an LLM agent (Claude). Raspberry Pi runs the backend, iPad serves as the customer-facing POS, and OpenClaw routes Slack/Discord messages to the agent.

## Architecture

```
iPad (PWA) ──► FastAPI (Pi :8000) ──► SQLite DB
                    │
OpenClaw GW ──► Webhook ──► Agent Loop ──► Claude API (Sonnet 4.5)
                    │
              Hardware Controller ──► GPIO / Camera / NFC
```

**Three processes on the Pi:**
1. `FastAPI` (uvicorn :8000) — API server + agent loop
2. `OpenClaw` (:18789) — Slack/Discord message gateway (routing only, NOT the agent brain)
3. `Nginx` (:80) — reverse proxy for iPad

## Development Environment

- **Python 3.13** — backend (FastAPI + agent + hardware)
- **Node.js** — frontend build (React + Vite + Tailwind) and OpenClaw gateway
- **SQLite** via **SQLAlchemy ORM** (async with aiosqlite)
- **Windows development** with Pi deployment — hardware modules auto-mock on non-Pi platforms

## Key Directories

```
main.py              → FastAPI app entry point, mounts all routers
agent/               → Claude API agent loop, tools, memory, guardrails
api/                 → FastAPI routers (products, checkout, webhook, admin, ws)
db/                  → SQLAlchemy models, DB init, migrations
hardware/            → GPIO, camera, NFC (auto-mocked on Windows)
frontend/            → React PWA served as static files
config/              → systemd services, nginx, openclaw.yaml
skills/              → OpenClaw skill definitions (thin routing wrappers)
scripts/             → Seed data, backup, manual test scripts
```

## Coding Conventions

### Python
- **Async everywhere** — all FastAPI routes and agent functions are `async def`
- **Type hints required** — use `typing` module, especially for function signatures
- **SQLAlchemy 2.0 style** — use `select()`, `Mapped[]`, `mapped_column()`, `AsyncSession`
- **Pydantic models** for all API request/response schemas (in each api/ module)
- **No bare `except:`** — always catch specific exceptions
- **Logging** — use `logging` module, not `print()`. Logger per module: `logger = logging.getLogger(__name__)`
- **f-strings** for string formatting, never `.format()` or `%`

### Agent
- **Agent loop** calls Claude API directly via `anthropic` SDK — OpenClaw is NOT in the loop
- **All tool calls** pass through `agent/guardrails.py` before execution
- **Every agent decision** is logged to `agent_decisions` table with trigger, action, reasoning
- **System prompt** lives in `agent/prompts.py` — single source of truth
- **Context window** — rolling 30K token window, trimmed by `trim_to_tokens()`

### Hardware
- `hardware/__init__.py` exports `get_controller()` which returns real or mock controller based on platform
- On Windows: all hardware calls are no-ops that log to console
- On Pi: uses `gpiozero` for GPIO, `picamera2` for camera

### Frontend
- React 18 + Vite + TailwindCSS
- Built on dev machine, `dist/` served as static files from FastAPI
- WebSocket at `/ws/updates` for real-time stock/price pushes

### API Design
- RESTful endpoints under `/api/`
- iPad-facing: `/api/products`, `/api/cart/checkout`, `/api/status`
- OpenClaw bridge: `/api/webhook/oclaw`
- Admin: `/api/admin/*` (authenticated)
- WebSocket: `/ws/updates`

## Environment Variables (.env)

```
ANTHROPIC_API_KEY=     # Required — Claude API access
WEBHOOK_SECRET=        # Required — OpenClaw ↔ FastAPI auth
SLACK_BOT_TOKEN=       # Optional until OpenClaw integration
DISCORD_BOT_TOKEN=     # Optional until OpenClaw integration
DATABASE_URL=          # Default: sqlite+aiosqlite:///./claudius.db
ENVIRONMENT=           # development | production
LOG_LEVEL=             # DEBUG | INFO | WARNING (default: INFO)
```

## Running Locally (Windows)

```bash
# Backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python db/init_db.py
uvicorn main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

## Running on Pi (Production)

```bash
sudo systemctl start claudius    # FastAPI + Agent
sudo systemctl start openclaw    # Gateway
sudo systemctl start nginx       # Reverse proxy
```

## Testing

```bash
# Run all tests
pytest

# Test agent loop manually
python scripts/test_agent.py

# Seed product data
python scripts/seed_products.py
```

## Guardrail Rules (Hard-Coded, NOT in LLM prompt)

These are enforced in `agent/guardrails.py` at the tool execution level:
- `sell_price >= cost_price * 1.3` (minimum 30% margin)
- Max discount: 15% without admin override
- Max single purchase: $80
- Max restock quantity: 50 per item per request
- Door unlock requires a stated reason
- Price cannot exceed 5x cost (likely error)

## Git Workflow

- `main` branch — stable, deployable to Pi
- Feature branches — `feature/<name>`
- Commit messages — imperative mood, concise ("Add product checkout endpoint")
- Never commit `.env`, `claudius.db`, `node_modules/`, `__pycache__/`
