# FleetMind — AI Delivery & Fleet Tracking System

Comprehensive architecture blueprint for a delivery/fleet tracking application managed by an LLM agent (Claude). Built with Redis for real-time location streaming, MCP Server for external AI tool access, OpenClaw for Slack/Discord dispatch, and Google APIs for routing, scheduling, and analytics.

---

## 1. Project Overview

An AI-powered delivery and fleet tracking system where Claude ("FleetMind") serves as the central dispatch intelligence. Three user personas interact with the system through purpose-built interfaces:

| Persona | Interface | Primary Actions |
|---------|-----------|-----------------|
| **Dispatchers** | Slack (via OpenClaw) | Assign deliveries, check driver status, manage urgent requests |
| **Drivers** | Mobile PWA + GPS | Receive assignments, report status, navigate routes |
| **Fleet Managers** | Admin Dashboard | Monitor fleet, view analytics, manage shifts, configure geofences |

**Core capabilities:**
- Real-time GPS tracking with 5-second update intervals
- AI-managed dispatch — Claude assigns deliveries based on proximity, capacity, and shift status
- Geofence alerts for warehouses, customer zones, and restricted areas
- Google Maps route optimization with live ETA calculations
- Google Calendar shift synchronization
- MCP Server exposing fleet tools to external AI agents
- Full audit trail of every agent decision

---

## 2. Architecture Diagram

Five processes run on the server (cloud VM or on-prem):

| Process | Port | Role |
|---------|------|------|
| FastAPI (uvicorn) | :8000 | API server, agent loop, WebSocket hub |
| Redis | :6379 | Pub/sub for real-time location, caching, geofence events |
| MCP Server | :8100 | External AI tool access (fleet query/control) |
| OpenClaw | :18789 | Slack/Discord message gateway (routing only) |
| Nginx | :80/:443 | Reverse proxy, TLS termination, static PWA |

```
                  ┌──────────────┐     ┌──────────────┐
                  │  Slack /     │     │  Google APIs  │
                  │  Discord     │     │  Maps/Cal/GA  │
                  └──────┬───────┘     └──────┬───────┘
                         │                     │
                  ┌──────▼───────┐             │
                  │  OpenClaw    │             │
                  │  (:18789)    │             │
                  │  Gateway     │             │
                  └──────┬───────┘             │
                         │ POST /api/webhook/oclaw
                         │ + cron triggers     │
                         │                     │
┌─────────┐       ┌──────▼─────────────────────▼───────┐
│  Driver  │──ws──►│  FastAPI (:8000)                   │
│  PWA     │◄──ws──│                                    │
└─────────┘       │  ┌────────────┐   ┌─────────────┐  │
                  │  │ API Routes │──►│ Agent Loop   │  │
┌─────────┐       │  └────────────┘   │ (Claude API) │  │
│  Admin   │──────►│                   └──────┬──────┘  │
│  Dash    │◄──ws──│                          │         │
└─────────┘       │  ┌────────────┐   ┌───────▼──────┐  │
                  │  │ WebSocket  │   │ Guardrails   │  │
                  │  │ Hub        │   └───────┬──────┘  │
                  │  └─────┬──────┘           │         │
                  │        │          ┌───────▼──────┐  │
                  │        │          │ Tool Executor│  │
                  │  ┌─────▼──────┐   └───────┬──────┘  │
                  │  │  Redis     │◄──────────┘         │
                  │  │  (:6379)   │   ┌──────────────┐  │
                  │  │  Pub/Sub   │   │ PostgreSQL   │  │
                  │  └────────────┘   └──────────────┘  │
                  └─────────────────────────────────────┘
                         │
                  ┌──────▼───────┐
                  │  MCP Server  │
                  │  (:8100)     │
                  │  Fleet Tools │
                  └──────────────┘
                         │
                  ┌──────▼───────┐
                  │  External AI │
                  │  Agents      │
                  └──────────────┘
```

**Why PostgreSQL over SQLite:** Concurrent location writes from multiple drivers, pub/sub-backed cache invalidation, and production-grade connection pooling via `asyncpg` require a database that handles write contention gracefully.

---

## 3. Component Breakdown

### Processes

| Process | Binary/Command | Config | Logs |
|---------|---------------|--------|------|
| FastAPI | `uvicorn main:app --port 8000` | `.env` | stdout + `logs/` |
| Redis | `redis-server /etc/redis/redis.conf` | `redis.conf` | `/var/log/redis/` |
| MCP Server | `python mcp_server/main.py` | `.env` | stdout |
| OpenClaw | `openclaw gateway start` | `~/.openclaw/openclaw.json` | `~/.openclaw/logs/` |
| Nginx | `nginx` | `config/nginx.conf` | `/var/log/nginx/` |

### Agent Modules (`agent/`)

| File | Role |
|------|------|
| `loop.py` | Core agent loop — calls Claude API directly, manages rolling 30K-token conversation history, orchestrates tool use cycle |
| `prompts.py` | System prompt (FleetMind identity, dispatch rules, safety rules) + 14 tool definitions — single source of truth |
| `tools.py` | Tool implementations (`get_fleet_status`, `assign_delivery`, `optimize_route`, etc.) + `execute_tool()` router |
| `guardrails.py` | Hard-coded safety/compliance rules enforced before every tool execution — cannot be overridden by the LLM |
| `memory.py` | Persistent scratchpad (key-value) + KV store, backed by DB tables |
| `classifier.py` | Regex-based interaction classifier for research data (dispatch, inquiry, status_check, adversarial, etc.) |
| `geofence.py` | Geofence evaluation engine — point-in-polygon checks against configured zones, triggers Redis events |
| `scheduler.py` | Cron-triggered agent tasks — morning briefing, shift reminders, end-of-day reports |

### API Modules (`api/`)

| File | Role |
|------|------|
| `drivers.py` | Driver CRUD, status updates, location ingestion |
| `deliveries.py` | Delivery lifecycle — create, assign, update status, complete |
| `fleet.py` | Fleet-wide views, vehicle management |
| `tracking.py` | Real-time location queries, ETA calculations |
| `admin.py` | Dashboard data, analytics, geofence management |
| `webhook.py` | OpenClaw bridge + cron trigger endpoints |
| `websocket.py` | WebSocket hub — location streams, delivery updates, alerts |

---

## 4. Data Flows

### Flow 1: Driver GPS → Real-Time Dashboards

```
Driver PWA sends GPS coords via WebSocket (every 5 seconds)
  → FastAPI /ws/driver/{driver_id} receives location update
  → Validate coords (lat/lng bounds, speed sanity check)
  → PUBLISH to Redis channel "location:{driver_id}" (all subscribers get update)
  → SET Redis key "driver:location:{driver_id}" with 30s TTL (cache for queries)
  → Every 6th update (every 30 seconds): INSERT into location_history table
  → Geofence engine evaluates against all active geofences
  → If geofence event → PUBLISH to Redis "geofence:events"
  → All subscribed admin dashboards receive update via WebSocket
```

**Rate control:**
- WebSocket ingestion: every 5 seconds per driver
- Redis pub/sub: every 5 seconds (real-time)
- PostgreSQL persist: every 30 seconds (durable history)
- Geofence evaluation: every 5 seconds (on each update)

### Flow 2: Slack Dispatch → Driver Assignment

```
Dispatcher: "@fleetmind assign delivery #4521 to nearest available driver"
  → Slack delivers via Socket Mode WebSocket to OpenClaw
  → OpenClaw routes to "fleetmind" agent
  → Agent calls get_delivery_details(delivery_id=4521)
  → Agent calls get_available_drivers(near_lat, near_lng, radius_km=10)
  → Agent selects optimal driver (proximity + capacity + shift time remaining)
  → Agent calls assign_delivery(delivery_id=4521, driver_id=selected)
  → Guardrails validate: driver is active, not over concurrent limit, within shift hours
  → Tool execution:
      - UPDATE deliveries SET driver_id, status="assigned"
      - PUBLISH to Redis "delivery:updates"
      - Push notification to driver PWA
  → Agent confirms assignment to dispatcher in Slack
```

### Flow 3: Geofence Events → Agent Alerts

```
Driver enters warehouse geofence
  → Geofence engine detects ENTER event (point-in-polygon)
  → INSERT geofence_events (driver_id, geofence_id, event_type="enter", timestamp)
  → PUBLISH to Redis "geofence:events" {driver_id, geofence_id, type, coords}
  → Agent loop receives event via subscriber
  → Agent evaluates context:
      - If delivery pickup location → auto-update delivery status to "picking_up"
      - If delivery dropoff location → auto-update to "arriving"
      - If restricted zone → alert fleet manager
  → Agent sends appropriate Slack notification
```

### Flow 4: External AI → MCP Server → Fleet Data

```
External AI agent connects to MCP Server (:8100)
  → Requests tool list (15 available tools)
  → Calls get_fleet_overview()
  → MCP Server queries PostgreSQL + Redis cache
  → Returns structured JSON: {active_drivers, in_transit, completed_today, avg_eta}
  → External AI calls get_driver_location(driver_id=42)
  → MCP Server reads Redis cache key "driver:location:42"
  → Returns {lat, lng, speed, heading, last_updated}
```

---

## 5. MCP Server Design

The MCP Server runs on `:8100` using the `mcp` Python SDK, exposing fleet tools to external AI agents (e.g., customer service bots, planning agents). It is a **read-heavy** interface — write operations require elevated scope.

### Tool Definitions (15 tools)

#### Location Tools (3)

| Tool | Purpose | Params | Returns |
|------|---------|--------|---------|
| `get_driver_location` | Current position of a driver | `driver_id` | `{lat, lng, speed, heading, last_updated}` |
| `get_drivers_near` | Drivers within radius of a point | `lat, lng, radius_km` | `[{driver_id, distance_km, status}]` |
| `get_location_history` | Historical path for a driver | `driver_id, start_time, end_time` | `[{lat, lng, timestamp}]` |

#### Delivery Tools (4)

| Tool | Purpose | Params | Returns |
|------|---------|--------|---------|
| `get_delivery_details` | Full delivery info | `delivery_id` | `{id, status, pickup, dropoff, driver, eta}` |
| `get_active_deliveries` | All in-progress deliveries | `status_filter?` | `[{id, driver, status, eta}]` |
| `get_delivery_eta` | Live ETA for a delivery | `delivery_id` | `{eta_minutes, distance_km, traffic}` |
| `create_delivery` | Create new delivery request | `pickup, dropoff, priority, notes` | `{delivery_id, status}` |

#### Route Tools (3)

| Tool | Purpose | Params | Returns |
|------|---------|--------|---------|
| `optimize_route` | Best route via Google Directions | `origin, destination, waypoints[]` | `{route, duration, distance, steps}` |
| `get_distance_matrix` | Travel times between points | `origins[], destinations[]` | `{matrix: [[duration, distance]]}` |
| `geocode_address` | Address → lat/lng | `address` | `{lat, lng, formatted_address}` |

#### Shift Tools (2)

| Tool | Purpose | Params | Returns |
|------|---------|--------|---------|
| `get_driver_shift` | Current shift info for a driver | `driver_id` | `{start, end, hours_remaining, break_taken}` |
| `get_shift_schedule` | All shifts for a date | `date` | `[{driver_id, start, end, vehicle_id}]` |

#### Analytics Tools (2)

| Tool | Purpose | Params | Returns |
|------|---------|--------|---------|
| `get_fleet_overview` | Fleet-wide summary stats | (none) | `{active_drivers, in_transit, completed_today, avg_eta}` |
| `get_daily_metrics` | Performance metrics for a date | `date` | `{deliveries, avg_time, on_time_pct, distance_km}` |
| `get_driver_performance` | Individual driver stats | `driver_id, days_back` | `{deliveries, avg_time, rating, distance_km}` |

### MCP Server Implementation

```python
# mcp_server/main.py
from mcp.server import Server
from mcp.server.stdio import stdio_server

app = Server("fleetmind-mcp")

@app.list_tools()
async def list_tools() -> list[Tool]:
    return TOOL_DEFINITIONS  # 15 tools defined above

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    result = await execute_mcp_tool(name, arguments)
    return [TextContent(type="text", text=json.dumps(result))]
```

**Run mode:** `python mcp_server/main.py --transport sse --port 8100`

---

## 6. Database Schema

PostgreSQL via SQLAlchemy 2.0 async ORM (`asyncpg` driver). Connection string: `postgresql+asyncpg://user:pass@localhost/fleetmind`.

### Tables

#### `drivers`

| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | Auto-increment |
| name | String(100) | |
| phone | String(20) | |
| email | String(100) | Unique |
| status | String(20) | `active`, `inactive`, `on_break`, `off_duty` |
| vehicle_id | Integer FK | Nullable — assigned vehicle |
| max_concurrent_deliveries | Integer | Default: 3 |
| created_at | DateTime | UTC |
| updated_at | DateTime | UTC, auto-update |

#### `vehicles`

| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | |
| plate_number | String(20) | Unique |
| make_model | String(100) | |
| capacity_kg | Float | Max cargo weight |
| fuel_type | String(20) | `gas`, `diesel`, `electric`, `hybrid` |
| is_active | Boolean | Default: True |
| created_at | DateTime | |

#### `deliveries`

| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | |
| driver_id | Integer FK | Nullable until assigned |
| vehicle_id | Integer FK | Nullable |
| status | String(20) | `pending`, `assigned`, `picking_up`, `in_transit`, `arriving`, `delivered`, `failed`, `cancelled` |
| priority | String(10) | `low`, `normal`, `high`, `urgent` |
| pickup_address | String(500) | |
| pickup_lat | Float | |
| pickup_lng | Float | |
| dropoff_address | String(500) | |
| dropoff_lat | Float | |
| dropoff_lng | Float | |
| customer_name | String(100) | |
| customer_phone | String(20) | |
| notes | Text | |
| estimated_duration_min | Integer | From Google Directions |
| actual_duration_min | Integer | Calculated on completion |
| distance_km | Float | |
| assigned_at | DateTime | |
| picked_up_at | DateTime | |
| delivered_at | DateTime | |
| created_at | DateTime | |
| updated_at | DateTime | |

#### `routes`

| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | |
| delivery_id | Integer FK | |
| polyline | Text | Encoded polyline from Google Directions |
| duration_seconds | Integer | |
| distance_meters | Integer | |
| waypoints_json | Text | JSON array of waypoints |
| created_at | DateTime | |

#### `location_history`

| Column | Type | Notes |
|--------|------|-------|
| id | BigInteger PK | High-volume table |
| driver_id | Integer FK | Indexed |
| lat | Float | |
| lng | Float | |
| speed_kmh | Float | Nullable |
| heading | Float | 0-360 degrees, nullable |
| accuracy_m | Float | GPS accuracy in meters |
| recorded_at | DateTime | Indexed, UTC |

**Index:** `(driver_id, recorded_at DESC)` — primary query pattern.
**Partition strategy:** Monthly partitions on `recorded_at` for retention management.

#### `geofences`

| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | |
| name | String(100) | |
| type | String(20) | `warehouse`, `customer`, `restricted`, `custom` |
| polygon_json | Text | GeoJSON polygon coordinates |
| center_lat | Float | For quick radius pre-filter |
| center_lng | Float | |
| radius_m | Float | Bounding circle for fast rejection |
| is_active | Boolean | |
| created_at | DateTime | |

#### `geofence_events`

| Column | Type | Notes |
|--------|------|-------|
| id | BigInteger PK | |
| driver_id | Integer FK | |
| geofence_id | Integer FK | |
| event_type | String(10) | `enter`, `exit` |
| lat | Float | Position at event time |
| lng | Float | |
| recorded_at | DateTime | Indexed |

#### `shifts`

| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | |
| driver_id | Integer FK | |
| vehicle_id | Integer FK | |
| scheduled_start | DateTime | |
| scheduled_end | DateTime | |
| actual_start | DateTime | Nullable |
| actual_end | DateTime | Nullable |
| break_minutes | Integer | Default: 0 |
| google_calendar_event_id | String(100) | Synced calendar event |
| created_at | DateTime | |

#### `agent_decisions`

| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | |
| trigger | Text | What initiated the action |
| action | String(100) | Tool name called |
| reasoning | Text | Agent's explanation |
| was_blocked | Boolean | Guardrail rejection |
| block_reason | String(500) | Why it was blocked |
| created_at | DateTime | |

#### `messages`

| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | |
| direction | String(10) | `inbound`, `outbound` |
| content | Text | |
| sender_id | String(100) | Slack/Discord user ID |
| sender_name | String(100) | |
| platform | String(20) | `slack`, `discord`, `system` |
| created_at | DateTime | |

#### `scratchpad`

| Column | Type | Notes |
|--------|------|-------|
| key | String(100) PK | |
| value | Text | |
| updated_at | DateTime | |

#### `kv_store`

| Column | Type | Notes |
|--------|------|-------|
| key | String(200) PK | |
| value | Text | JSON-serialized |
| updated_at | DateTime | |

#### `daily_metrics`

| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | |
| date | Date | Unique, indexed |
| total_deliveries | Integer | |
| completed_deliveries | Integer | |
| failed_deliveries | Integer | |
| avg_delivery_time_min | Float | |
| total_distance_km | Float | |
| on_time_percentage | Float | |
| active_drivers | Integer | |
| adversarial_blocked | Integer | Guardrail rejections |
| created_at | DateTime | |

---

## 7. Google API Integration

### Google Maps Platform

| API | Use Case | Endpoint |
|-----|----------|----------|
| **Directions API** | Route calculation between pickup/dropoff, multi-stop optimization | `routes/directions/v2:computeRoutes` |
| **Distance Matrix API** | Batch travel time/distance for driver-to-pickup matching | `routes/distanceMatrix/v2:computeRouteMatrix` |
| **Geocoding API** | Address ↔ lat/lng conversion for delivery creation | `geocode/json` |
| **Places API** | Address autocomplete in admin dashboard and driver PWA | `places/v1/places:autocomplete` |
| **Maps JavaScript API** | Interactive fleet map in admin dashboard, driver route display | Frontend `@googlemaps/js-api-loader` |

**Rate limiting:** All Google API calls go through `services/google_maps.py` with:
- Exponential backoff on 429/5xx responses
- Request deduplication (same origin/destination within 60s returns cached result)
- Daily quota monitoring logged to `daily_metrics`

```python
# services/google_maps.py
class GoogleMapsService:
    async def compute_route(self, origin: LatLng, destination: LatLng,
                            waypoints: list[LatLng] = []) -> RouteResult: ...
    async def distance_matrix(self, origins: list[LatLng],
                               destinations: list[LatLng]) -> MatrixResult: ...
    async def geocode(self, address: str) -> GeocodingResult: ...
```

### Google Calendar API

| Feature | Purpose |
|---------|---------|
| **Shift sync** | Driver shifts created in FleetMind → synced as Google Calendar events |
| **Webhook notifications** | Calendar changes (shift swaps, time-off) → push to `/api/webhook/gcal` → agent updates schedule |
| **Shared calendars** | One calendar per driver, fleet-wide calendar for managers |

```python
# services/google_calendar.py
class GoogleCalendarService:
    async def create_shift_event(self, driver: Driver, shift: Shift) -> str: ...
    async def update_shift_event(self, event_id: str, shift: Shift) -> None: ...
    async def delete_shift_event(self, event_id: str) -> None: ...
    async def list_driver_events(self, driver_id: int, date: date) -> list[Event]: ...
```

**Auth:** Service account with domain-wide delegation. Credentials stored in `GOOGLE_SERVICE_ACCOUNT_JSON` env var (path to JSON key file).

### Google Analytics 4

| Component | Implementation |
|-----------|---------------|
| **Frontend (gtag.js)** | Page views, delivery map interactions, driver PWA engagement |
| **Backend (Measurement Protocol)** | Server-side events: delivery_completed, delivery_failed, geofence_alert, agent_decision |

```python
# services/google_analytics.py
class GoogleAnalyticsService:
    async def track_event(self, name: str, params: dict) -> None:
        """Send event via GA4 Measurement Protocol."""
        payload = {
            "client_id": self._server_client_id,
            "events": [{"name": name, "params": params}]
        }
        await self._http.post(
            f"https://www.google-analytics.com/mp/collect"
            f"?measurement_id={self._measurement_id}&api_secret={self._api_secret}",
            json=payload
        )
```

---

## 8. Redis Architecture

Redis serves three roles: real-time pub/sub for location streaming, short-TTL cache for frequent queries, and geofence event bus.

### Pub/Sub Channels

| Channel | Publisher | Subscribers | Payload |
|---------|-----------|-------------|---------|
| `location:{driver_id}` | FastAPI (on GPS update) | Admin dashboards, ETA calculator | `{lat, lng, speed, heading, ts}` |
| `geofence:events` | Geofence engine | Agent loop, admin dashboards | `{driver_id, geofence_id, type, lat, lng, ts}` |
| `delivery:updates` | Tool executor | Dispatcher dashboards, driver PWA | `{delivery_id, status, driver_id, eta}` |
| `dispatch:commands` | Agent loop | Driver PWA | `{driver_id, command, delivery_id, route}` |

### Cache Keys & TTLs

| Key Pattern | TTL | Source | Use |
|-------------|-----|--------|-----|
| `driver:location:{driver_id}` | 30s | GPS WebSocket handler | Fast location lookups without DB query |
| `eta:{delivery_id}` | 120s | Google Directions response | Avoid redundant API calls for same delivery |
| `delivery:{delivery_id}` | 300s | PostgreSQL query cache | Delivery detail reads from MCP Server |
| `session:{session_id}` | 3600s | Auth middleware | Driver/admin session tokens |
| `fleet:overview` | 15s | Aggregation query | Fleet-wide stats (active, in-transit, etc.) |
| `driver:available:{region}` | 10s | Availability query | Pre-computed available driver lists |

### Connection Pooling

```python
# services/redis_service.py
import redis.asyncio as redis

class RedisService:
    def __init__(self, url: str = "redis://localhost:6379"):
        self.pool = redis.ConnectionPool.from_url(url, max_connections=20)
        self.client = redis.Redis(connection_pool=self.pool)
        self.pubsub = self.client.pubsub()

    async def publish_location(self, driver_id: int, data: dict) -> None:
        await self.client.publish(f"location:{driver_id}", json.dumps(data))
        await self.client.setex(
            f"driver:location:{driver_id}", 30, json.dumps(data)
        )

    async def subscribe_locations(self, driver_ids: list[int]):
        channels = [f"location:{did}" for did in driver_ids]
        await self.pubsub.subscribe(*channels)
```

---

## 9. Agent / AI Design

### Identity: FleetMind

The agent operates as "FleetMind" — an AI dispatch coordinator. Its system prompt lives in `agent/prompts.py` (single source of truth).

**Personality traits:** Professional, concise, safety-conscious. Prioritizes driver safety and delivery reliability over speed.

### Agent Tools (14)

| Tool | Purpose | Key Params |
|------|---------|------------|
| `get_fleet_status` | All active drivers with current status/location | (none) |
| `get_available_drivers` | Drivers available for assignment near a point | lat, lng, radius_km |
| `get_delivery_details` | Full delivery info | delivery_id |
| `assign_delivery` | Assign a delivery to a driver | delivery_id, driver_id |
| `update_delivery_status` | Change delivery status | delivery_id, new_status |
| `optimize_route` | Best route via Google Directions | origin, destination, waypoints[] |
| `get_driver_shift` | Current shift info for a driver | driver_id |
| `send_message` | Broadcast to Slack/Discord via OpenClaw | message, channel |
| `notify_driver` | Push notification to driver PWA | driver_id, title, body |
| `create_geofence` | Define a new geofence zone | name, type, polygon_coords |
| `get_daily_report` | Fleet performance metrics | date |
| `write_scratchpad` | Save persistent note | key, value |
| `read_scratchpad` | Read persistent note | key |
| `flag_issue` | Escalate an issue to fleet manager | driver_id, issue_type, description |

### Guardrails (`agent/guardrails.py`)

Hard-coded safety and compliance rules enforced at the tool execution level. **Cannot be overridden by the LLM prompt or user messages.**

```python
validate_action(tool_name: str, inputs: dict, session: AsyncSession) -> dict:
    # Returns {"allowed": bool, "reason": str}
```

| Rule | Constant | Applies To |
|------|----------|------------|
| Max 10h continuous driving | `MAX_DRIVING_HOURS = 10` | assign_delivery |
| Max 5 concurrent deliveries per driver | `MAX_CONCURRENT_DELIVERIES = 5` | assign_delivery |
| Cannot assign to inactive/off-duty driver | — | assign_delivery |
| Urgent delivery must be assigned within 10 min | `URGENT_SLA_MINUTES = 10` | agent scheduler |
| Geofence polygon max 50 vertices | `MAX_GEOFENCE_VERTICES = 50` | create_geofence |
| Cannot delete geofence with active deliveries inside | — | delete_geofence |
| Route must not exceed 500 km single leg | `MAX_ROUTE_KM = 500` | optimize_route |
| Driver break required after 4h continuous driving | `BREAK_AFTER_HOURS = 4` | assign_delivery |

When a guardrail blocks a tool call, the agent loop logs it as `was_blocked=True` in `agent_decisions` and returns the error to Claude so it can explain to the dispatcher.

### Cron Triggers (3)

| Schedule | Trigger | Agent Action |
|----------|---------|--------------|
| **06:00 daily** | `daily_morning` | Review today's shift schedule, check vehicle availability, send briefing to Slack |
| **Every 15 min** | `delivery_check` | Check for unassigned urgent deliveries, stale in-transit deliveries, SLA violations |
| **22:00 daily** | `daily_close` | Compile daily metrics, flag incomplete deliveries, send end-of-day report |

---

## 10. Environment Variables

```bash
# === Core ===
ANTHROPIC_API_KEY=          # Required — Claude API access
ENVIRONMENT=                # development | production
LOG_LEVEL=                  # DEBUG | INFO | WARNING (default: INFO)

# === Database ===
DATABASE_URL=               # Required — postgresql+asyncpg://user:pass@localhost:5432/fleetmind

# === Redis ===
REDIS_URL=                  # Default: redis://localhost:6379/0
REDIS_MAX_CONNECTIONS=      # Default: 20

# === Google APIs ===
GOOGLE_MAPS_API_KEY=        # Required — Maps, Directions, Distance Matrix, Geocoding, Places
GOOGLE_SERVICE_ACCOUNT_JSON=# Required — Path to service account JSON (Calendar API)
GA4_MEASUREMENT_ID=         # Required — Google Analytics 4 measurement ID
GA4_API_SECRET=             # Required — GA4 Measurement Protocol API secret

# === MCP Server ===
MCP_SERVER_PORT=            # Default: 8100
MCP_SERVER_TRANSPORT=       # Default: sse (options: sse, stdio)

# === OpenClaw ===
WEBHOOK_SECRET=             # Required — OpenClaw ↔ FastAPI auth
SLACK_BOT_TOKEN=            # Required — Slack bot token (xoxb-...)
SLACK_APP_TOKEN=            # Required — Slack app-level token (xapp-...) for Socket Mode
DISCORD_BOT_TOKEN=          # Optional

# === Security ===
JWT_SECRET=                 # Required — Driver/admin session tokens
CORS_ORIGINS=               # Default: http://localhost:5173,http://localhost:3000
```

---

## 11. Directory Structure

```
main.py                    → FastAPI app entry point, mounts all routers
agent/                     → Claude API agent loop, tools, memory, guardrails
  ├── loop.py              → Core agent loop (Claude API, 30K token window)
  ├── prompts.py           → System prompt + 14 tool definitions
  ├── tools.py             → Tool implementations + execute_tool() router
  ├── guardrails.py        → Hard-coded safety rules (driving hours, concurrency, SLA)
  ├── memory.py            → Scratchpad + KV store (backed by DB)
  ├── classifier.py        → Interaction classifier for research data
  ├── geofence.py          → Point-in-polygon geofence engine
  └── scheduler.py         → Cron-triggered agent tasks
api/                       → FastAPI routers
  ├── drivers.py           → Driver CRUD, status, location ingestion
  ├── deliveries.py        → Delivery lifecycle endpoints
  ├── fleet.py             → Fleet-wide views, vehicle management
  ├── tracking.py          → Real-time location queries, ETA
  ├── admin.py             → Dashboard data, analytics, geofence CRUD
  ├── webhook.py           → OpenClaw bridge + Google Calendar webhook
  └── websocket.py         → WebSocket hub (location streams, updates, alerts)
db/                        → Database layer
  ├── models.py            → SQLAlchemy 2.0 models (Mapped[], mapped_column())
  ├── init_db.py           → Create tables, run migrations
  └── migrations/          → Alembic migration scripts
services/                  → External service integrations
  ├── google_maps.py       → Directions, Distance Matrix, Geocoding, Places
  ├── google_calendar.py   → Shift sync, webhook handling
  ├── google_analytics.py  → GA4 Measurement Protocol
  └── redis_service.py     → Pub/sub, caching, connection pool
mcp_server/                → MCP Server (separate process)
  ├── main.py              → Server entry point (mcp SDK)
  ├── tools.py             → 15 tool implementations
  └── schemas.py           → Input/output Pydantic models
frontend/                  → React PWA (Vite + Tailwind)
  ├── src/
  │   ├── pages/
  │   │   ├── DriverApp.tsx    → Driver mobile interface
  │   │   ├── Dashboard.tsx    → Fleet manager dashboard
  │   │   └── DispatchView.tsx → Dispatcher view
  │   ├── components/
  │   │   ├── FleetMap.tsx     → Google Maps fleet view
  │   │   ├── DeliveryCard.tsx → Delivery status card
  │   │   └── DriverList.tsx   → Active driver list
  │   ├── hooks/
  │   │   ├── useWebSocket.ts  → WebSocket connection manager
  │   │   └── useLocation.ts   → GPS tracking hook (driver PWA)
  │   └── services/
  │       └── api.ts           → REST + WebSocket client
  └── dist/                → Built static files served by FastAPI
config/                    → Deployment config
  ├── nginx.conf           → Reverse proxy config
  ├── systemd/             → Service unit files
  └── redis.conf           → Redis configuration
skills/                    → OpenClaw skill definitions
  ├── fleet-dispatch/      → Route dispatch messages to agent
  └── fleet-alerts/        → Route outbound alerts to channels
scripts/                   → Utility scripts
  ├── seed_data.py         → Seed drivers, vehicles, sample deliveries
  ├── test_agent.py        → Manual agent loop testing
  └── migrate.py           → Database migration runner
tests/                     → Test suite
  ├── test_agent/          → Agent loop, guardrails, tools
  ├── test_api/            → API endpoint tests
  ├── test_services/       → Google APIs, Redis mock tests
  └── test_mcp/            → MCP Server tool tests
```

---

## 12. Development Setup

### Prerequisites

- Python 3.12+
- Node.js 20+
- PostgreSQL 16+
- Redis 7+
- Google Cloud project with Maps, Calendar, Analytics APIs enabled

### Terminal 1 — PostgreSQL + Redis

```bash
# Start PostgreSQL (if using Homebrew)
brew services start postgresql@16

# Create database
createdb fleetmind

# Start Redis
redis-server
```

### Terminal 2 — FastAPI Backend

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Initialize database tables
python db/init_db.py

# Seed sample data
python scripts/seed_data.py

# Start server
uvicorn main:app --reload --port 8000
```

### Terminal 3 — MCP Server

```bash
source venv/bin/activate
python mcp_server/main.py --transport sse --port 8100
```

### Terminal 4 — Frontend

```bash
cd frontend
npm install
npm run dev
```

### Terminal 5 — OpenClaw Gateway

```bash
# First-time setup
openclaw config set gateway.mode local
openclaw channels add --channel slack \
  --bot-token "$SLACK_BOT_TOKEN" \
  --app-token "$SLACK_APP_TOKEN"
openclaw config set channels.slack.groupPolicy open
openclaw agents add fleetmind \
  --workspace /path/to/fleet-tracker \
  --bind slack --non-interactive

# Start gateway
openclaw gateway install
# Add ANTHROPIC_API_KEY to LaunchAgent plist, then:
openclaw gateway stop
launchctl bootstrap gui/$UID ~/Library/LaunchAgents/ai.openclaw.gateway.plist
```

---

## 13. Build Sequence

Seven phases from skeleton to production-ready system.

### Phase 1 — Core Skeleton

- [ ] FastAPI app with health check endpoint
- [ ] PostgreSQL connection via SQLAlchemy 2.0 async (asyncpg)
- [ ] Database models for all 13 tables
- [ ] Alembic migration setup
- [ ] Seed script for drivers, vehicles, sample deliveries
- [ ] Basic `.env` config loading via Pydantic Settings

### Phase 2 — Agent Loop + Dispatch

- [ ] Agent loop (`agent/loop.py`) — Claude API integration with 30K token window
- [ ] System prompt + 14 tool definitions (`agent/prompts.py`)
- [ ] Tool implementations (`agent/tools.py`) + `execute_tool()` router
- [ ] Guardrails (`agent/guardrails.py`) — all 8 safety rules
- [ ] Memory layer (scratchpad + KV store)
- [ ] OpenClaw webhook integration (`api/webhook.py`)
- [ ] Interaction classifier

### Phase 3 — Real-Time Location + Redis

- [ ] Redis service with connection pooling
- [ ] Driver GPS WebSocket endpoint (`/ws/driver/{driver_id}`)
- [ ] Location pub/sub channels
- [ ] Location history persistence (every 30s)
- [ ] Redis cache layer for driver locations, ETAs, fleet overview
- [ ] Admin dashboard WebSocket subscriber

### Phase 4 — Google APIs + Routing

- [ ] Google Maps service (Directions, Distance Matrix, Geocoding)
- [ ] Route optimization for deliveries
- [ ] ETA calculation with caching
- [ ] Google Calendar shift sync
- [ ] Calendar webhook handler for schedule changes
- [ ] Google Analytics 4 event tracking (backend + frontend)

### Phase 5 — Geofencing

- [ ] Geofence model + CRUD endpoints
- [ ] Point-in-polygon evaluation engine
- [ ] Redis geofence event bus
- [ ] Agent geofence event handler (auto-status updates, alerts)
- [ ] Geofence management UI in admin dashboard

### Phase 6 — MCP Server

- [ ] MCP Server skeleton with `mcp` Python SDK
- [ ] 15 tool implementations (Location, Delivery, Route, Shift, Analytics)
- [ ] Input validation via Pydantic schemas
- [ ] SSE transport on `:8100`
- [ ] Integration tests with mock external AI client

### Phase 7 — Frontend + Polish

- [ ] Driver mobile PWA (GPS tracking, delivery queue, navigation)
- [ ] Fleet manager dashboard (live map, analytics, geofence editor)
- [ ] Dispatcher view (delivery board, driver assignment)
- [ ] Google Maps JS integration (fleet map, route visualization)
- [ ] WebSocket-driven real-time updates across all views
- [ ] Cron scheduler (morning briefing, delivery checks, daily close)
- [ ] End-to-end testing, load testing for location ingestion
- [ ] Production deployment config (systemd, nginx, TLS)

---

## Appendix: Pattern Reference (from Claudius)

This project reuses proven patterns from the Claudius vending machine system:

| Pattern | Claudius Source | FleetMind Equivalent |
|---------|----------------|---------------------|
| `execute_tool()` router | `agent/tools.py` | `agent/tools.py` — same dispatcher pattern, 14 tools |
| Hard-coded guardrails | `agent/guardrails.py` | `agent/guardrails.py` — driving hours, concurrency limits |
| SQLAlchemy 2.0 async | `db/models.py` | `db/models.py` — `Mapped[]`, `mapped_column()`, asyncpg |
| WebSocket broadcast | `api/websocket.py` | `api/websocket.py` — extended with Redis pub/sub fan-out |
| System prompt + tools | `agent/prompts.py` | `agent/prompts.py` — FleetMind identity, 14 tool definitions |
| Agent memory (2-tier) | `agent/memory.py` | `agent/memory.py` — scratchpad + KV store |
| Interaction classifier | `agent/classifier.py` | `agent/classifier.py` — dispatch, inquiry, status_check categories |
| OpenClaw skills | `skills/` | `skills/` — fleet-dispatch + fleet-alerts |
