# Claudius — AI Vending Machine

## Project Overview

An AI-powered vending machine managed by an LLM agent (Claude). Raspberry Pi runs the backend, iPad serves as the customer-facing POS, and OpenClaw routes Slack/Discord messages to the agent.

## Architecture

> **Full architecture guide:** See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed component docs, data flows, and database schema.

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

### Agent Components (`agent/`)

| File | Role |
|------|------|
| `loop.py` | Core agent loop — calls Claude API directly, manages rolling 30K-token conversation history, orchestrates tool use cycle |
| `prompts.py` | System prompt (identity/business/interaction/order/pickup/memory rules) + 19 tool definitions — single source of truth |
| `tools.py` | Tool implementations (19 tools) + `execute_tool()` router |
| `guardrails.py` | Hard-coded business rules enforced before every tool execution — cannot be overridden by the LLM |
| `pickup.py` | Pickup reservation logic — reservation codes, stock hold, expiry, compensating transactions |
| `context.py` | Selective recall — 5-channel context priming before every Claude call (customer, episodes, knowledge, pickups, business) |
| `memory.py` | Persistent scratchpad (key-value) + KV store, backed by DB tables |
| `classifier.py` | Regex-based interaction classifier for research data (purchase, inquiry, adversarial, etc.) |

### Message Flow (Slack → Agent → Slack)

```
Slack user @mentions bot in #claudius
  → OpenClaw receives via Socket Mode (WebSocket, not HTTP webhook)
  → OpenClaw routes to "claudius" agent (bound via `openclaw agents bind`)
  → Agent uses Claude API with workspace skills + conversation
  → Response delivered back to Slack via OpenClaw
```

**Note:** OpenClaw requires `@agentic-machine` mention in channel messages.
Messages without a mention are ignored (`no-mention` filter).

## Development Environment

- **Python 3.12** — backend (FastAPI + agent + hardware)
- **Node.js** — frontend build (React + Vite + Tailwind) and OpenClaw gateway
- **SQLite** via **SQLAlchemy ORM** (async with aiosqlite)
- **macOS development** with Pi deployment — hardware modules auto-mock on non-Pi platforms

## Key Directories

```
main.py              → FastAPI app entry point, mounts all routers
agent/               → Claude API agent loop, tools, memory, guardrails, pickup, context
api/                 → FastAPI routers (products, checkout, pickup, webhook, admin, ws)
db/                  → SQLAlchemy models (12 tables), DB init
hardware/            → GPIO, camera, NFC (auto-mocked on Windows)
frontend/            → React PWA served as static files (5 tabs: Products, Cart, Pickup, Status, Incoming)
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
- **Selective recall** — `agent/context.py` runs 5 parallel channels before every Claude call (customer profile, recent episodes, related knowledge, pending pickups, business context)
- **All tool calls** pass through `agent/guardrails.py` before execution
- **Every agent decision** is logged to `agent_decisions` table with trigger, action, reasoning
- **System prompt** lives in `agent/prompts.py` — single source of truth
- **Context window** — rolling 30K token window, trimmed by `trim_to_tokens()`
- **Pickup workflow** — Slack/Discord orders create pickup reservations (30-min expiry) instead of instant sales

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
- iPad-facing: `/api/products`, `/api/cart/checkout`, `/api/pickup/confirm`, `/api/status`
- OpenClaw bridge: `/api/webhook/oclaw`
- Admin: `/api/admin/*` (authenticated), `/api/admin/pickups`
- WebSocket: `/ws/updates`

## Environment Variables (.env)

```
ANTHROPIC_API_KEY=     # Required — Claude API access
WEBHOOK_SECRET=        # Required — OpenClaw ↔ FastAPI auth
SLACK_BOT_TOKEN=       # Required — Slack bot token (xoxb-...)
SLACK_APP_TOKEN=       # Required — Slack app-level token (xapp-...) for Socket Mode
DISCORD_BOT_TOKEN=     # Optional until Discord integration
DATABASE_URL=          # Default: sqlite+aiosqlite:///./claudius.db
ENVIRONMENT=           # development | production
LOG_LEVEL=             # DEBUG | INFO | WARNING (default: INFO)
```

## Running Locally (macOS)

```bash
# Backend (terminal 1)
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python db/init_db.py
uvicorn main:app --reload --port 8000

# Frontend (terminal 2)
cd frontend
npm install
npm run dev
```

## OpenClaw Gateway Setup (macOS)

OpenClaw is installed globally via npm and runs as a LaunchAgent.

```bash
# 1. Install OpenClaw
npm install -g openclaw

# 2. Set gateway mode
openclaw config set gateway.mode local

# 3. Add Slack channel (requires both bot + app tokens)
openclaw channels add --channel slack \
  --bot-token "xoxb-..." \
  --app-token "xapp-..."

# 4. Set channel policy to open
openclaw config set channels.slack.groupPolicy open

# 5. Create agent with workspace pointed at this project
openclaw agents add claudius \
  --workspace /path/to/agentic-machine \
  --bind slack --non-interactive

# 6. Install and start gateway service
openclaw gateway install

# 7. Add ANTHROPIC_API_KEY to the LaunchAgent plist
#    (edit ~/Library/LaunchAgents/ai.openclaw.gateway.plist,
#     add ANTHROPIC_API_KEY to EnvironmentVariables dict,
#     then reload with: openclaw gateway stop && launchctl bootstrap gui/$UID ~/Library/LaunchAgents/ai.openclaw.gateway.plist)
```

**Config locations:**
- OpenClaw config: `~/.openclaw/openclaw.json`
- LaunchAgent plist: `~/Library/LaunchAgents/ai.openclaw.gateway.plist`
- Logs: `~/.openclaw/logs/gateway.log` and `/tmp/openclaw/`

**Important:** `openclaw gateway install` regenerates the plist, so re-add
`ANTHROPIC_API_KEY` to the plist after every install and use `launchctl bootstrap`
to reload instead of `openclaw gateway start`.

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
- Max single purchase: $80 (applies to both `process_order` and `create_pickup_reservation`)
- Max restock quantity: 50 per item per request
- Door unlock requires a stated reason
- Price cannot exceed 5x cost (likely error)
- Pickup code must be exactly 6 characters
- Customer notes max 500 characters
- Knowledge insight max 1000 characters

## Git Workflow

- `main` branch — stable, deployable to Pi
- Feature branches — `feature/<name>`
- Commit messages — imperative mood, concise ("Add product checkout endpoint")
- Never commit `.env`, `claudius.db`, `node_modules/`, `__pycache__/`
