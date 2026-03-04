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

Assembles the FastAPI app. Mounts seven routers and initializes the database on startup via the `lifespan` context manager.

| Router | Prefix | Source |
|--------|--------|--------|
| products | `/api` | `api/products.py` |
| checkout | `/api` | `api/checkout.py` |
| webhook | `/api` | `api/webhook.py` |
| admin | `/api/admin` | `api/admin.py` |
| requests | `/api` | `api/requests.py` |
| pickup | `/api` | `api/pickup.py` |
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
4. Run selective recall (prime_context) — 5 parallel channels
5. Call Claude API with SYSTEM_PROMPT + context_block + TOOL_DEFINITIONS + trimmed history
6. WHILE stop_reason == "tool_use":
   a. For each tool call in response:
      - Inject metadata (sender_id, platform) into pickup tools
      - validate_action() via guardrails.py
      - If blocked → log, return error string to Claude
      - If allowed → execute_tool() via tools.py, log decision
   b. Send tool results back to Claude
   c. Get new response
7. Extract final text
8. Log message, agent decision, and user interaction to DB
9. Return response text
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

**TOOL_DEFINITIONS (19 tools):**

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
| `process_order` | Process iPad/in-person purchase | items[], customer_name |
| `search_product_online` | Search online retailers | query, max_results |
| `request_online_product` | Save confirmed product request | query, product_name, price, url |
| `request_restock` | Submit restock request to admin | items[], urgency |
| `create_pickup_reservation` | Reserve items + generate pickup code | items[], customer_name |
| `confirm_pickup` | Validate code + unlock door | code |
| `get_pending_pickups` | List active reservations | sender_id (opt) |
| `recall_customer` | Fetch customer profile | sender_id |
| `update_customer_notes` | Save private customer notes | sender_id, notes |
| `record_knowledge` | Persist business insight | topic, insight, keywords |
| `expire_pickups` | Force expiry of stale reservations | (none) |

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
| Max $80 per purchase | `MAX_SINGLE_PURCHASE = 80.0` | process_order, create_pickup_reservation |
| Max 50 units per restock item | `MAX_RESTOCK_QTY_PER_ITEM = 50` | request_restock |
| Positive quantities | — | process_order, create_pickup_reservation, request_restock |
| Product must exist and be active | — | process_order, create_pickup_reservation |
| Sufficient stock | — | process_order, create_pickup_reservation |
| Door unlock needs a reason | — | unlock_door |
| Pickup code exactly 6 chars | — | confirm_pickup |
| Customer notes max 500 chars | `MAX_CUSTOMER_NOTES_LENGTH = 500` | update_customer_notes |
| Knowledge insight max 1000 chars | `MAX_KNOWLEDGE_INSIGHT_LENGTH = 1000` | record_knowledge |

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

### 6b. Selective Recall — `agent/context.py`

5-channel context engine that runs before every Claude call via `asyncio.gather()`:

| # | Channel | Scoping | What it Fetches |
|---|---------|---------|----------------|
| 1 | Customer Profile | sender_id | Name, spend, purchase count, private notes. Auto-creates on first interaction. |
| 2 | Recent Episodes | global | Last 8h of AgentEpisode entries (max 15) |
| 3 | Related Knowledge | keyword match | AgentKnowledge rows matching words from the message |
| 4 | Pending Pickups | sender_id | Active reservations with code, total, minutes remaining |
| 5 | Business Context | global | Cash balance, today's revenue, low-stock alerts (qty <= 3) |

Privacy: Channels 1 and 4 are scoped by sender_id. Customer A's data never appears in Customer B's context.

### 6c. Pickup Agent — `agent/pickup.py`

Reservation-based pickup workflow:

| Function | Purpose |
|----------|---------|
| `create_reservation()` | Generate 6-char code, hold stock, create sale transactions |
| `confirm_pickup()` | Validate code, mark picked_up, unlock door |
| `expire_stale_pickups()` | Expire reservations past 30-min window, release stock |
| `get_pending_pickups()` | List active reservations, optionally by customer |

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
| POST | `/api/pickup/confirm` | pickup.pickup_confirm | Confirm pickup reservation |
| GET | `/api/pickup/status/{code}` | pickup.pickup_status | Check reservation status |
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
| GET | `/api/admin/pickups` | pickup.list_pending_pickups | List pending pickups |
| POST | `/api/admin/pickups/expire` | pickup.force_expire_pickups | Manual expiry trigger |

---

## Data Flows

### Flow 1: Slack Customer Message

```
Customer @mentions bot in #claudius
  → Slack delivers via Socket Mode WebSocket to OpenClaw
  → OpenClaw routes to "claudius" agent (bound via openclaw agents bind)
  → Agent uses Claude API with workspace skills + conversation
  → Response delivered back to Slack channel via OpenClaw
```

**Note:** The `api/webhook.py` routes exist for an alternative webhook-based
integration but are not used in the current Socket Mode setup. OpenClaw handles
the full message lifecycle (receive → agent → respond) internally.

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

### Flow 3: Agent Order via Slack (Pickup Reservation)

```
Customer: "I want to buy a Coke"
  → Agent calls get_inventory (via tool loop)
  → Agent confirms with customer
  → Agent calls create_pickup_reservation({items, customer_name})
  → Guardrails validate: stock, active, $80 limit, qty > 0
  → create_reservation():
      - Generate unique 6-char code (A-Z0-9)
      - Decrement stock immediately (prevents overselling)
      - Create Transaction records (type="sale")
      - Create PickupOrder row (status="reserved", expires in 30 min)
      - Update CustomerProfile (spend, purchase count)
      - Log episode for recall
      - Broadcast stock_update via WebSocket
  → Agent tells customer: "Your pickup code is ABC123. Enter it at the machine within 30 minutes."
```

### Flow 3b: Pickup Confirmation (iPad)

```
Customer enters 6-char code on iPad Pickup tab
  → POST /api/pickup/confirm  {code: "ABC123"}
  → confirm_pickup():
      - Look up PickupOrder by code
      - Validate: status=reserved, not expired
      - Mark status=picked_up, set picked_up_at
      - Call hw.unlock_door()
      - Broadcast pickup_confirmed
  → iPad shows items + total + "Door unlocked"
```

### Flow 3c: Pickup Expiry

```
30 minutes pass OR cron trigger fires
  → expire_stale_pickups():
      - Query all reserved pickups past expiry
      - For each: mark expired, release stock via compensating transactions
      - Create refund Transaction records (negative amounts)
      - Broadcast stock_update (stock restored)
```

### Flow 4: Cron Triggers

```
OpenClaw cron fires (8am / every 4h / 11pm)
  → POST /api/admin/agent/trigger  {type: "daily_morning"}
  → Auto-expire stale pickups before agent_step
  → agent_step(trigger="Good morning, review inventory, check pending pickups...")
  → Agent checks inventory, expires pickups, records insights, sends alerts
```

### Flow 5: Selective Recall (every agent_step)

```
Message arrives (any source)
  → prime_context(sender_id, sender_name, message, session)
  → asyncio.gather() runs 5 channels in parallel:
      1. _recall_customer(sender_id) → profile, spend, notes
      2. _recall_episodes() → last 8h events (max 15)
      3. _recall_knowledge(message) → keyword-matched insights
      4. _recall_pending_pickups(sender_id) → active reservations
      5. _recall_business_context() → balance, revenue, low stock
  → Assemble <context> block
  → Prepend to system prompt for Claude call
```

---

## Database Schema

12 tables, all in SQLite via SQLAlchemy 2.0 async ORM.

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `products` | Product catalog | name, cost_price, sell_price, quantity, slot, is_active |
| `transactions` | Financial ledger | type (sale/restock/refund/fee), amount, balance_after |
| `agent_decisions` | Audit trail | trigger, action, reasoning, was_blocked |
| `messages` | All messages | direction, content, sender_id, platform |
| `user_interactions` | Research data | interaction_type, message_text, agent_response, guardrail_hit |
| `product_requests` | Customer product requests | product_name, estimated_price, status |
| `pickup_orders` | Pickup reservations | code, status, items_json, total_amount, expires_at |
| `customer_profiles` | Per-customer profiles | sender_id, display_name, total_spend, private_notes |
| `agent_episodes` | Episodic memory | event_type, sender_id, summary, timestamp |
| `agent_knowledge` | Business insights | topic, insight, keywords |
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

## OpenClaw Configuration

OpenClaw runs as a **LaunchAgent** on macOS (or systemd on Pi). It connects to Slack
via **Socket Mode** (persistent WebSocket, no public HTTP endpoint needed).

**Actual config:** `~/.openclaw/openclaw.json` (NOT `config/openclaw.yaml` — that file
is a reference only and is not loaded by OpenClaw).

**Key config settings:**

| Setting | Value | Purpose |
|---------|-------|---------|
| `gateway.mode` | `local` | Required — gateway won't start without this |
| `channels.slack.mode` | `socket` | Socket Mode (WebSocket, requires app-level token) |
| `channels.slack.groupPolicy` | `open` | Accept messages from all channels |
| `channels.slack.botToken` | `xoxb-...` | Bot user OAuth token |
| `channels.slack.appToken` | `xapp-...` | App-level token for Socket Mode |

**Agent routing:** Agents are isolated workspaces. The `claudius` agent is bound to
Slack with its workspace pointing at this project directory.

```
openclaw agents add claudius --workspace /path/to/agentic-machine --bind slack
```

**LaunchAgent plist:** `~/Library/LaunchAgents/ai.openclaw.gateway.plist`
- Must include `ANTHROPIC_API_KEY` in `EnvironmentVariables`
- `openclaw gateway install` regenerates the plist (wipes custom env vars)
- After install, re-add API key and reload with `launchctl bootstrap`

**Mention requirement:** OpenClaw only responds to messages that `@mention` the bot
in channels. Direct messages don't require a mention.

**Logs:**
- `~/.openclaw/logs/gateway.log` — stdout (startup, connections, agent activity)
- `~/.openclaw/logs/gateway.err.log` — stderr (errors, crash info)
- `/tmp/openclaw/openclaw-YYYY-MM-DD.log` — detailed JSON log

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
| SLACK_BOT_TOKEN | Yes | — | Slack bot token (xoxb-...) |
| SLACK_APP_TOKEN | Yes | — | Slack app-level token (xapp-...) for Socket Mode |
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
