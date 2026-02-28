# Claudius Architecture Guide

Detailed breakdown of every component, how they connect, and the data flows between them.

## System Overview

Three processes run on the Raspberry Pi:

| Process | Port | Role |
|---------|------|------|
| FastAPI (uvicorn) | :8000 | API server, agent loop, hardware control |
| OpenClaw | :18789 | Slack/Discord message gateway (routing only) |
| Nginx | :80 | Reverse proxy serving iPad PWA |

```
                  ┌──────────────┐
                  │  Slack /     │
                  │  Discord     │
                  └──────┬───────┘
                         │
                  ┌──────▼───────┐
                  │  OpenClaw    │
                  │  (:18789)    │
                  │  Gateway     │
                  └──────┬───────┘
                         │ POST /api/webhook/oclaw
                         │ + cron → POST /api/admin/agent/trigger
                         │
┌─────────┐       ┌──────▼───────────────────────────────┐
│  iPad   │──────►│  FastAPI (:8000)                     │
│  (PWA)  │◄──ws──│                                      │
└─────────┘       │  ┌────────────┐   ┌───────────────┐  │
                  │  │ API Routes │──►│ Agent Loop    │  │
                  │  └────────────┘   │ (Claude API)  │  │
                  │                   └───────┬───────┘  │
                  │                           │          │
                  │  ┌────────────┐   ┌───────▼───────┐  │
                  │  │ WebSocket  │   │ Guardrails    │  │
                  │  │ Broadcast  │   └───────┬───────┘  │
                  │  └────────────┘           │          │
                  │                   ┌───────▼───────┐  │
                  │                   │ Tool Executor │  │
                  │                   └───────┬───────┘  │
                  │  ┌────────────┐           │          │
                  │  │ Hardware   │◄──────────┘          │
                  │  │ Controller │   ┌───────────────┐  │
                  │  └────────────┘   │ SQLite DB     │  │
                  │                   └───────────────┘  │
                  └──────────────────────────────────────┘
```

---

## Component Details

### 1. Entry Point — `main.py`

Assembles the FastAPI app. Mounts five routers and initializes the database on startup via the `lifespan` context manager.

| Router | Prefix | Source |
|--------|--------|--------|
| products | `/api` | `api/products.py` |
| checkout | `/api` | `api/checkout.py` |
| webhook | `/api` | `api/webhook.py` |
| admin | `/api/admin` | `api/admin.py` |
| websocket | (none) | `api/websocket.py` |

Also exposes `GET /api/status` for health checks.

---

### 2. Agent Loop — `agent/loop.py`

The brain of the system. Calls Claude API directly (Sonnet 4.5) with a rolling conversation history.

**Key constants:**
- Model: `claude-sonnet-4-5-20250929`
- Max response tokens: 4096
- Context window: 30,000 tokens (trimmed via `_trim_to_tokens()`)

**`agent_step(trigger, metadata)` flow:**

```
1. Enrich trigger with platform/sender metadata
2. Append to _conversation_history (in-memory list)
3. Trim history to 30K tokens (most-recent-first)
4. Call Claude API with SYSTEM_PROMPT + TOOL_DEFINITIONS + trimmed history
5. WHILE stop_reason == "tool_use":
   a. For each tool call in response:
      - validate_action() via guardrails.py
      - If blocked → log, return error string to Claude
      - If allowed → execute_tool() via tools.py, log decision
   b. Send tool results back to Claude
   c. Get new response
6. Extract final text
7. Log message, agent decision, and user interaction to DB
8. Return response text
```

**Who calls `agent_step()`:**
- `api/webhook.py:openclaw_inbound()` — when a Slack/Discord message arrives
- `api/webhook.py:admin_trigger()` — when a cron job or manual trigger fires

---

### 3. System Prompt & Tool Definitions — `agent/prompts.py`

Single source of truth for all prompt text and tool schemas.

**SYSTEM_PROMPT sections:**
- Identity rules (never claim to be human)
- Business rules (margins, discounts, purchase limits)
- Interaction rules (friendly, decline free items, don't reveal prompt)
- Order rules (check inventory → confirm → process_order → report total)

**TOOL_DEFINITIONS (10 tools):**

| Tool | Purpose | Key Params |
|------|---------|------------|
| `get_inventory` | List active products with stock/prices | (none) |
| `set_price` | Update product sell price | product_id, new_price |
| `get_balance` | Cash balance + recent transactions | (none) |
| `unlock_door` | Unlock vending machine door | reason |
| `send_message` | Broadcast to Slack/Discord via OpenClaw | message, channel |
| `write_scratchpad` | Save persistent note | key, value |
| `read_scratchpad` | Read persistent note | key |
| `get_sales_report` | Sales data for last N days | days_back |
| `process_order` | Process Slack/Discord purchase | items[], customer_name |
| `request_restock` | Submit restock request to admin | items[], urgency |

---

### 4. Guardrails — `agent/guardrails.py`

Hard-coded business rules enforced at the tool execution level. **Cannot be overridden by the LLM prompt or user messages.** Called by the agent loop before every tool execution.

```python
validate_action(tool_name, inputs, session) → {"allowed": bool, "reason": str}
```

| Rule | Constant | Applies To |
|------|----------|------------|
| Minimum 30% margin | `MIN_MARGIN_MULTIPLIER = 1.3` | set_price |
| Max 5x cost (likely error) | `MAX_PRICE_MULTIPLIER = 5.0` | set_price |
| Max $80 per purchase | `MAX_SINGLE_PURCHASE = 80.0` | process_order |
| Max 50 units per restock item | `MAX_RESTOCK_QTY_PER_ITEM = 50` | request_restock |
| Positive quantities | — | process_order, request_restock |
| Product must exist and be active | — | process_order |
| Sufficient stock | — | process_order |
| Door unlock needs a reason | — | unlock_door |

When a guardrail blocks a tool call, the agent loop logs it as `was_blocked=True` in `agent_decisions` and returns the error to Claude so it can explain to the user.

---

### 5. Tool Execution — `agent/tools.py`

Each tool function implements the actual operation. `execute_tool()` routes by name.

**Notable tools:**

- **`tool_process_order()`** — Mirrors iPad checkout: decrements stock, creates `Transaction` records, logs `AgentDecision`, broadcasts `stock_update` via WebSocket. Notes include customer name and platform.

- **`tool_send_message()`** — POSTs to OpenClaw at `http://localhost:18789/api/send` to deliver messages back to Slack/Discord.

- **`tool_unlock_door()`** — Calls `get_controller().unlock_door()` which triggers real GPIO or mock based on platform.

---

### 6. Agent Memory — `agent/memory.py`

Two-tier persistent storage available to the agent via tools:

| Tier | Table | Tools | Use Case |
|------|-------|-------|----------|
| Scratchpad | `scratchpad` | write/read_scratchpad | Daily notes, reminders |
| KV Store | `kv_store` | kv_set/kv_get | Supplier contacts, price history |

Optional Tier 3 (vector DB via ChromaDB) is stubbed but not enabled.

---

### 7. Interaction Classifier — `agent/classifier.py`

Regex-based classification of customer messages for research data. Categories: `purchase`, `inquiry`, `feedback`, `social_engineering`, `prompt_injection`, `casual`.

Called in the agent loop after processing. Results stored in `user_interactions` table.

---

## API Routes

### iPad-Facing

| Method | Path | Handler | Purpose |
|--------|------|---------|---------|
| GET | `/api/products` | products.list_products | Product catalog |
| GET | `/api/products/{id}` | products.get_product | Single product |
| POST | `/api/cart/checkout` | checkout.checkout | Process iPad purchase |
| GET | `/api/status` | main.machine_status | Health check |
| WS | `/ws/updates` | websocket.websocket_updates | Real-time stock/price |

### OpenClaw Bridge

| Method | Path | Handler | Purpose |
|--------|------|---------|---------|
| POST | `/api/webhook/oclaw` | webhook.openclaw_inbound | Receive Slack/Discord messages |
| POST | `/api/admin/agent/trigger` | webhook.admin_trigger | Cron or manual agent triggers |

### Admin

| Method | Path | Handler | Purpose |
|--------|------|---------|---------|
| GET | `/api/admin/logs` | admin.get_logs | Agent decision audit trail |
| GET | `/api/admin/analytics` | admin.get_analytics | Revenue/items summary |
| GET | `/api/admin/interactions` | admin.get_interactions | Research interaction data |
| GET | `/api/admin/metrics` | admin.get_metrics | Daily scorecard |
| POST | `/api/admin/restock` | admin.confirm_restock | Manual inventory restock |

---

## Data Flows

### Flow 1: Slack/Discord Customer Message

```
Customer types in #claudius
  → OpenClaw receives message
  → POST /api/webhook/oclaw  (X-Webhook-Secret header)
  → webhook.openclaw_inbound() validates secret
  → agent_step(trigger, metadata={sender_id, sender_name, platform, channel})
  → Claude API call (with tool loop)
  → Final response text returned
  → POST http://localhost:18789/api/send  (response back to OpenClaw)
  → OpenClaw delivers to Slack/Discord
  → Customer sees reply
```

### Flow 2: iPad Checkout

```
Customer selects items on iPad
  → POST /api/cart/checkout  {items, payment_method}
  → Validate items (exist, active, stock)
  → Check total <= $80
  → Decrement Product.quantity for each item
  → Create Transaction records (type="sale")
  → Log AgentDecision
  → broadcast() stock_update to all WebSocket clients
  → Return {success, total, transaction_ids}
  → All connected iPads update stock in real-time
```

### Flow 3: Agent Order via Slack

```
Customer: "I want to buy a Coke"
  → Agent calls get_inventory (via tool loop)
  → Agent confirms with customer
  → Agent calls process_order({items, customer_name})
  → Guardrails validate: stock, active, $80 limit, qty > 0
  → tool_process_order():
      - Decrement stock
      - Create Transaction records
      - Log AgentDecision
      - Broadcast stock_update via WebSocket
  → Agent tells customer total and pickup instructions
```

### Flow 4: Cron Triggers

```
OpenClaw cron fires (8am / every 4h / 11pm)
  → POST /api/admin/agent/trigger  {type: "daily_morning"}
  → agent_step(trigger="Good morning, review inventory...")
  → Agent checks inventory, makes decisions, sends alerts
```

---

## Database Schema

8 tables, all in SQLite via SQLAlchemy 2.0 async ORM.

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `products` | Product catalog | name, cost_price, sell_price, quantity, slot, is_active |
| `transactions` | Financial ledger | type (sale/restock/refund/fee), amount, balance_after |
| `agent_decisions` | Audit trail | trigger, action, reasoning, was_blocked |
| `messages` | All messages | direction, content, sender_id, platform |
| `user_interactions` | Research data | interaction_type, message_text, agent_response, guardrail_hit |
| `scratchpad` | Agent persistent notes | key, value |
| `kv_store` | Agent structured data | key, value |
| `daily_metrics` | Daily scorecard | revenue, profit_margin, items_sold, adversarial_blocked |

---

## Hardware Abstraction — `hardware/`

Platform detection via `platform.machine()`:
- `aarch64` or `arm` → Raspberry Pi → real controllers
- Anything else → Windows/Mac → mock controllers (log to console)

| Module | Real Class | Mock Class | Purpose |
|--------|-----------|------------|---------|
| `gpio.py` | PiHardwareController | MockHardwareController | Door lock, fridge relay, status LED |
| `camera.py` | PiCamera | MockCamera | Capture images (picamera2) |
| `nfc.py` | PiNFCReader | MockNFCReader | NFC tag reading (stub) |

GPIO pins (BCM): Door=17, Fridge=27, LED=22.

---

## OpenClaw Configuration — `config/openclaw.yaml`

OpenClaw is a **message router only**. It does not call Claude API.

**Channels:** Slack (#claudius) and Discord (#claudius)

**Webhooks:**
- Inbound: `POST http://localhost:8000/api/webhook/oclaw` (with X-Webhook-Secret)
- Outbound: agent calls `POST http://localhost:18789/api/send` to reply

**Cron jobs:**

| Schedule | Type | Purpose |
|----------|------|---------|
| `0 8 * * *` | daily_morning | Morning inventory review |
| `0 */4 * * *` | low_stock_check | Check for items with <= 3 units |
| `0 23 * * *` | nightly_reconciliation | End-of-day financial review |

---

## OpenClaw Skills — `skills/`

Thin routing wrappers that instruct OpenClaw how to handle messages:

| Skill | Directory | Role |
|-------|-----------|------|
| vending_message_router | `skills/vending-router/` | Forward customer messages to FastAPI, relay responses back. Never answer directly. |
| vending_alerts | `skills/vending-alerts/` | Route outbound alerts (low stock, price changes, reports) to appropriate channels. |

---

## Configuration — `config_app.py`

Pydantic Settings loaded from `.env`:

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| ANTHROPIC_API_KEY | Yes | — | Claude API access |
| WEBHOOK_SECRET | Yes | — | OpenClaw webhook auth |
| SLACK_BOT_TOKEN | No | — | Slack integration |
| DISCORD_BOT_TOKEN | No | — | Discord integration |
| DATABASE_URL | No | `sqlite+aiosqlite:///./claudius.db` | Database connection |
| ENVIRONMENT | No | `development` | Controls SQL echo logging |
| LOG_LEVEL | No | `INFO` | Logging verbosity |

---

## Scripts — `scripts/`

| Script | Command | Purpose |
|--------|---------|---------|
| `seed_products.py` | `python scripts/seed_products.py` | Populate DB with initial products + $100 seed capital |
| `test_agent.py` | `python scripts/test_agent.py` | Run test messages through agent loop (inquiry, purchase, adversarial) |
