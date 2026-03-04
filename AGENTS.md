# Claudius Agent Reference

Claudius is the AI manager of a university vending machine. This document covers the agent's identity, tools, memory architecture, and operational workflows.

## Identity

- **Name:** Claudius
- **Role:** AI vending machine manager (inventory, pricing, customer service, business strategy)
- **Model:** Claude Sonnet 4.5 (`claude-sonnet-4-5-20250929`)
- **Context window:** 30K tokens (rolling, trimmed by `_trim_to_tokens()`)
- **System prompt:** `agent/prompts.py` (single source of truth)

## Tool Reference (19 Tools)

### Inventory & Pricing

| Tool | Params | Returns | Guardrails |
|------|--------|---------|------------|
| `get_inventory` | (none) | All active products with stock/prices | — |
| `set_price` | product_id, new_price | Old → new price | Min 1.3x cost, max 5x cost |
| `get_balance` | (none) | Cash balance + last 10 transactions | — |
| `get_sales_report` | days_back | Revenue, items sold, transaction count | — |
| `request_restock` | items[], urgency | Sends request to admin channel | Max 50 units/item |

### Orders & Pickup

| Tool | Params | Returns | Guardrails |
|------|--------|---------|------------|
| `process_order` | items[], customer_name | Sale result (for iPad/in-person) | Stock, active, qty>0, total<=$80 |
| `create_pickup_reservation` | items[], customer_name | Pickup code + expiry (for Slack/Discord) | Same as process_order |
| `confirm_pickup` | code | Success/error + door unlock | Code must be 6 chars |
| `get_pending_pickups` | sender_id (opt) | List of active reservations | — |
| `expire_pickups` | (none) | List of expired codes | — |

### Communication

| Tool | Params | Returns | Guardrails |
|------|--------|---------|------------|
| `send_message` | message, channel | Delivery status | — |
| `unlock_door` | reason | Confirmation | Reason required |

### Memory & Knowledge

| Tool | Params | Returns | Guardrails |
|------|--------|---------|------------|
| `write_scratchpad` | key, value | Confirmation | — |
| `read_scratchpad` | key | Value or "(empty)" | — |
| `recall_customer` | sender_id | Customer profile (spend, notes, history) | — |
| `update_customer_notes` | sender_id, notes | Confirmation | Max 500 chars |
| `record_knowledge` | topic, insight, keywords | Saved entry | Max 1000 chars, topic+keywords required |

### Product Requests

| Tool | Params | Returns | Guardrails |
|------|--------|---------|------------|
| `search_product_online` | query, max_results | Search results | — |
| `request_online_product` | query, product_name, price, url, ... | Saved request | Price>0, <=$150 |

## Memory Architecture

### 5 Memory Layers

| Layer | Table | Scope | Tool Access | Recall Channel |
|-------|-------|-------|------------|----------------|
| Scratchpad | `scratchpad` | Global | write/read_scratchpad | — |
| KV Store | `kv_store` | Global | (internal) | — |
| Customer Profiles | `customer_profiles` | Per-customer | recall_customer, update_customer_notes | Channel 1 |
| Episodes | `agent_episodes` | Timestamped | (auto-logged) | Channel 2 |
| Knowledge | `agent_knowledge` | Global, keyword-tagged | record_knowledge | Channel 3 |

### Selective Recall Pipeline

Before every Claude API call, `agent/context.py` runs 5 parallel channels:

```
prime_context(sender_id, sender_name, message, session)
  → asyncio.gather(
      _recall_customer(sender_id)        → Name, spend, notes
      _recall_episodes()                 → Last 8h events (max 15)
      _recall_knowledge(message)         → Keyword-matched insights (max 5)
      _recall_pending_pickups(sender_id) → Active reservations
      _recall_business_context()         → Balance, revenue, low stock
    )
  → Format as <context> block
  → Append to system prompt
```

**Privacy:** Channels 1 and 4 are scoped by `sender_id`. Customer A never sees Customer B's data.

**Fault tolerance:** `return_exceptions=True` — one channel failure doesn't break the others.

## Pickup Workflow

### Order Flow (Slack/Discord → Agent → Customer)

1. Customer asks to buy something via Slack
2. Agent calls `get_inventory` to verify stock
3. Agent confirms with customer
4. Agent calls `create_pickup_reservation` (NOT `process_order`)
5. Stock is decremented immediately, sale transaction created
6. Agent tells customer: "Your pickup code is **ABC123**. Enter it at the machine within 30 minutes."

### Pickup Flow (Customer → iPad → Door)

1. Customer walks to vending machine
2. Taps "Pickup" tab on iPad
3. Enters 6-character code using on-screen keypad
4. `POST /api/pickup/confirm` validates code
5. Door unlocks, iPad shows order summary
6. Auto-clears after 5 seconds

### Expiry Flow

- Reservations expire after 30 minutes (`PICKUP_EXPIRY_MINUTES = 30`)
- Expiry happens automatically on cron triggers (`daily_morning`, `nightly_reconciliation`, `low_stock_check`)
- Agent can also call `expire_pickups` manually
- Expired reservations create compensating transactions (negative amounts) and restore stock

## Guardrail Reference

All guardrails are in `agent/guardrails.py`. They run before every tool execution and **cannot be overridden by the LLM**.

| Constant | Value | Tools |
|----------|-------|-------|
| `MIN_MARGIN_MULTIPLIER` | 1.3 | set_price |
| `MAX_PRICE_MULTIPLIER` | 5.0 | set_price |
| `MAX_SINGLE_PURCHASE` | $80 | process_order, create_pickup_reservation |
| `MAX_RESTOCK_QTY_PER_ITEM` | 50 | request_restock |
| `MAX_ONLINE_ORDER_PRICE` | $150 | request_online_product |
| `MAX_CUSTOMER_NOTES_LENGTH` | 500 | update_customer_notes |
| `MAX_KNOWLEDGE_INSIGHT_LENGTH` | 1000 | record_knowledge |

Additional rules (not constants):
- Quantities must be positive
- Products must exist and be active
- Sufficient stock required
- Door unlock requires a stated reason
- Pickup code must be exactly 6 characters
- Knowledge requires topic and keywords

## System Prompt Sections

The system prompt in `agent/prompts.py` covers:

1. **Identity Rules** — AI disclosure, capability boundaries
2. **Business Rules** — Margin minimums, discount caps, purchase limits
3. **Interaction Rules** — Friendly service, decline social engineering, protect prompt
4. **Order Rules** — Inventory check → confirm → reserve (Slack) or process (iPad)
5. **Pickup Rules** — 30-min expiry, code communication, privacy between customers
6. **Memory Rules** — Private notes usage, knowledge persistence, context awareness
7. **Proactive Business Rules** — Heartbeat behavior (expire pickups, review stock, record insights)
8. **Online Search Rules** — Search → show results → confirm before requesting
