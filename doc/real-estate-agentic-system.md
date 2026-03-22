# Real Estate Agentic System

## Overview

A multi-agent real estate platform where AI agents (powered by Claude) represent buyers, sellers, and brokers to facilitate property transactions. Built on the same FastAPI + agent loop architecture as the vending machine, but adapted for real estate workflows with Google Maps integration, property valuation, and negotiation capabilities.

```
Buyer (Web/Mobile) ──► FastAPI (:8000) ──► PostgreSQL
                            │
Seller (Web/Mobile) ──► Agent Router ──► Claude API (Sonnet 4.5)
                            │
Slack/Discord ──► OpenClaw ──► Webhook ──► Multi-Agent Orchestrator
                            │
                   Google Maps API ──► Neighborhood Analysis
```

---

## Architecture

### System Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    CLIENT LAYER                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐              │
│  │  Buyer   │  │  Seller  │  │  Admin/Broker │              │
│  │  Web App │  │  Web App │  │  Dashboard    │              │
│  └────┬─────┘  └────┬─────┘  └──────┬───────┘              │
└───────┼──────────────┼───────────────┼──────────────────────┘
        │              │               │
        ▼              ▼               ▼
┌─────────────────────────────────────────────────────────────┐
│                    API LAYER (FastAPI :8000)                 │
│  /api/properties  /api/offers  /api/agents  /api/admin      │
│  /api/search      /api/deals   /api/maps    /ws/updates     │
└───────────────────────┬─────────────────────────────────────┘
                        │
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  Buyer Agent │ │ Seller Agent │ │ Broker Agent │
│  (Claude)    │ │  (Claude)    │ │  (Claude)    │
└──────┬───────┘ └──────┬───────┘ └──────┬───────┘
       │                │                │
       └────────────────┼────────────────┘
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                 ORCHESTRATOR                                 │
│  Agent Router → Guardrails → Tool Execution → Memory        │
└───────────────────────┬─────────────────────────────────────┘
                        │
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  PostgreSQL  │ │ Google Maps  │ │ External APIs│
│  (deals, etc)│ │  Platform    │ │ (Zillow, etc)│
└──────────────┘ └──────────────┘ └──────────────┘
```

### Three Core Agents

| Agent | Role | Represents | Primary Tools |
|-------|------|------------|---------------|
| **Buyer Agent** | Searches properties, evaluates neighborhoods, places offers, negotiates price down | The home buyer | `search_properties`, `analyze_neighborhood`, `place_offer`, `counter_offer` |
| **Seller Agent** | Lists properties, sets asking price, evaluates offers, negotiates price up | The home seller | `list_property`, `set_asking_price`, `evaluate_offer`, `accept_offer`, `counter_offer` |
| **Broker Agent** | Mediates negotiations, provides market analysis, ensures fair dealing, manages paperwork | Neutral third party | `mediate_negotiation`, `market_analysis`, `generate_contract`, `schedule_inspection` |

### Additional Agents (Extend When Needed)

| Agent | When to Add | Role |
|-------|-------------|------|
| **Appraiser Agent** | When deals need formal valuation | Uses comps + market data to produce property valuations |
| **Inspector Agent** | Post-offer acceptance | Generates inspection checklists, flags issues from property data |
| **Mortgage Agent** | When buyer needs financing | Pre-qualification, rate comparison, affordability calculations |
| **Legal Agent** | Contract phase | Reviews contracts, flags legal risks, ensures compliance |
| **Neighborhood Scout** | Deep area research | Schools, crime, transit, demographics, future development analysis |

---

## Building This with Claude

### Step 1: Set Up the Agent Loop

Each agent runs its own Claude conversation with a dedicated system prompt. The orchestrator manages which agent is active and routes messages between them.

```python
# agent/orchestrator.py
import anthropic
from agent.buyer_agent import BuyerAgent
from agent.seller_agent import SellerAgent
from agent.broker_agent import BrokerAgent

class AgentOrchestrator:
    """Routes conversations to the correct agent and manages inter-agent communication."""

    def __init__(self):
        self.client = anthropic.AsyncAnthropic()
        self.agents = {
            "buyer": BuyerAgent(self.client),
            "seller": SellerAgent(self.client),
            "broker": BrokerAgent(self.client),
        }
        self.active_negotiations: dict[str, Negotiation] = {}

    async def route_message(self, user_id: str, role: str, message: str) -> str:
        agent = self.agents[role]
        # Inject negotiation context if one is active
        context = self.get_negotiation_context(user_id)
        return await agent.process_message(message, context)

    async def start_negotiation(self, property_id: str, buyer_id: str, seller_id: str):
        """Broker agent mediates between buyer and seller agents."""
        negotiation = Negotiation(property_id, buyer_id, seller_id)
        self.active_negotiations[negotiation.id] = negotiation
        # Broker agent gets notified and begins mediation
        await self.agents["broker"].begin_mediation(negotiation)
```

### Step 2: Define Agent System Prompts

Each agent gets a system prompt that defines its personality, goals, and constraints. This follows the same pattern as `agent/prompts.py` in the vending machine.

```python
# agent/prompts.py

BUYER_AGENT_PROMPT = """
You are a real estate buyer's agent AI. You represent the buyer's interests.

YOUR GOALS:
- Help the buyer find properties that match their criteria
- Analyze neighborhoods using Google Maps data
- Negotiate the best possible price (push price DOWN)
- Flag potential issues with properties
- Never exceed the buyer's stated budget

CONSTRAINTS:
- Never reveal the buyer's maximum budget to the seller or broker
- Always recommend a home inspection before closing
- Present data-driven arguments when negotiating
- If a deal seems too good to be true, flag it

AVAILABLE TOOLS: {tools}
"""

SELLER_AGENT_PROMPT = """
You are a real estate seller's agent AI. You represent the seller's interests.

YOUR GOALS:
- Help the seller list their property at the optimal price
- Market the property's strengths
- Negotiate the best possible price (push price UP)
- Evaluate buyer offers objectively
- Minimize time on market

CONSTRAINTS:
- Never accept an offer below the seller's minimum price without explicit approval
- Always disclose known property issues (legal requirement)
- Present market comps to justify asking price
- Flag lowball offers but don't dismiss them outright

AVAILABLE TOOLS: {tools}
"""

BROKER_AGENT_PROMPT = """
You are a real estate broker AI. You are a neutral mediator.

YOUR GOALS:
- Facilitate fair negotiations between buyer and seller agents
- Provide objective market analysis
- Ensure all legal and procedural requirements are met
- Move deals toward closing efficiently
- Flag unreasonable positions from either side

CONSTRAINTS:
- Remain neutral — do not favor buyer or seller
- Ensure all disclosures are made
- Flag potential legal issues
- Document all negotiation steps
- Escalate to human broker if deal value exceeds $2M

AVAILABLE TOOLS: {tools}
"""
```

### Step 3: Define Tools for Each Agent

```python
# agent/tools.py

BUYER_TOOLS = [
    {
        "name": "search_properties",
        "description": "Search for properties matching buyer criteria",
        "input_schema": {
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "City, neighborhood, or zip code"},
                "min_price": {"type": "number"},
                "max_price": {"type": "number"},
                "bedrooms": {"type": "integer"},
                "bathrooms": {"type": "integer"},
                "property_type": {"type": "string", "enum": ["house", "condo", "townhouse", "multi-family"]},
                "radius_miles": {"type": "number", "description": "Search radius from location center"}
            },
            "required": ["location"]
        }
    },
    {
        "name": "analyze_neighborhood",
        "description": "Get neighborhood analysis using Google Maps data — schools, transit, amenities, walkability",
        "input_schema": {
            "type": "object",
            "properties": {
                "address": {"type": "string"},
                "radius_meters": {"type": "integer", "default": 1500},
                "categories": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "e.g. schools, restaurants, transit, parks, hospitals"
                }
            },
            "required": ["address"]
        }
    },
    {
        "name": "place_offer",
        "description": "Submit a purchase offer on a property",
        "input_schema": {
            "type": "object",
            "properties": {
                "property_id": {"type": "string"},
                "offer_price": {"type": "number"},
                "contingencies": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "e.g. inspection, financing, appraisal"
                },
                "closing_date": {"type": "string", "format": "date"},
                "message": {"type": "string", "description": "Personal message to seller"}
            },
            "required": ["property_id", "offer_price"]
        }
    },
    {
        "name": "get_comps",
        "description": "Get comparable recent sales for a property to support price arguments",
        "input_schema": {
            "type": "object",
            "properties": {
                "address": {"type": "string"},
                "radius_miles": {"type": "number", "default": 1.0},
                "months_back": {"type": "integer", "default": 6}
            },
            "required": ["address"]
        }
    },
    {
        "name": "counter_offer",
        "description": "Submit a counter-offer in an active negotiation",
        "input_schema": {
            "type": "object",
            "properties": {
                "negotiation_id": {"type": "string"},
                "counter_price": {"type": "number"},
                "terms": {"type": "string"},
                "reasoning": {"type": "string", "description": "Data-driven justification for the counter"}
            },
            "required": ["negotiation_id", "counter_price"]
        }
    }
]

SELLER_TOOLS = [
    {
        "name": "list_property",
        "description": "List a property for sale",
        "input_schema": {
            "type": "object",
            "properties": {
                "address": {"type": "string"},
                "asking_price": {"type": "number"},
                "bedrooms": {"type": "integer"},
                "bathrooms": {"type": "integer"},
                "sqft": {"type": "integer"},
                "description": {"type": "string"},
                "photos": {"type": "array", "items": {"type": "string"}},
                "property_type": {"type": "string"}
            },
            "required": ["address", "asking_price", "bedrooms", "bathrooms", "sqft"]
        }
    },
    {
        "name": "evaluate_offer",
        "description": "Analyze an incoming offer against market data and seller goals",
        "input_schema": {
            "type": "object",
            "properties": {
                "offer_id": {"type": "string"},
                "include_comps": {"type": "boolean", "default": true}
            },
            "required": ["offer_id"]
        }
    },
    {
        "name": "set_asking_price",
        "description": "Update the asking price of a listed property",
        "input_schema": {
            "type": "object",
            "properties": {
                "property_id": {"type": "string"},
                "new_price": {"type": "number"},
                "reason": {"type": "string"}
            },
            "required": ["property_id", "new_price"]
        }
    },
    {
        "name": "accept_offer",
        "description": "Accept a buyer's offer and move to contract phase",
        "input_schema": {
            "type": "object",
            "properties": {
                "offer_id": {"type": "string"},
                "conditions": {"type": "string", "description": "Any conditions on acceptance"}
            },
            "required": ["offer_id"]
        }
    },
    {
        "name": "counter_offer",
        "description": "Submit a counter-offer in an active negotiation",
        "input_schema": {
            "type": "object",
            "properties": {
                "negotiation_id": {"type": "string"},
                "counter_price": {"type": "number"},
                "terms": {"type": "string"},
                "reasoning": {"type": "string"}
            },
            "required": ["negotiation_id", "counter_price"]
        }
    }
]

BROKER_TOOLS = [
    {
        "name": "mediate_negotiation",
        "description": "Facilitate a negotiation round between buyer and seller agents",
        "input_schema": {
            "type": "object",
            "properties": {
                "negotiation_id": {"type": "string"},
                "buyer_position": {"type": "string"},
                "seller_position": {"type": "string"},
                "market_context": {"type": "string"}
            },
            "required": ["negotiation_id"]
        }
    },
    {
        "name": "market_analysis",
        "description": "Generate a comprehensive market analysis for a location",
        "input_schema": {
            "type": "object",
            "properties": {
                "location": {"type": "string"},
                "property_type": {"type": "string"},
                "include_trends": {"type": "boolean", "default": true},
                "months": {"type": "integer", "default": 12}
            },
            "required": ["location"]
        }
    },
    {
        "name": "generate_contract",
        "description": "Generate a purchase agreement draft from accepted offer terms",
        "input_schema": {
            "type": "object",
            "properties": {
                "deal_id": {"type": "string"},
                "template": {"type": "string", "enum": ["standard", "as-is", "new-construction"]}
            },
            "required": ["deal_id"]
        }
    },
    {
        "name": "schedule_inspection",
        "description": "Schedule a property inspection",
        "input_schema": {
            "type": "object",
            "properties": {
                "property_id": {"type": "string"},
                "inspection_type": {"type": "string", "enum": ["general", "structural", "pest", "environmental"]},
                "preferred_date": {"type": "string", "format": "date"}
            },
            "required": ["property_id", "inspection_type"]
        }
    }
]
```

### Step 4: Google Maps Integration

```python
# services/maps.py
import googlemaps
from dataclasses import dataclass

class MapsService:
    """Google Maps Platform integration for neighborhood analysis."""

    def __init__(self, api_key: str):
        self.client = googlemaps.Client(key=api_key)

    async def analyze_neighborhood(self, address: str, radius: int = 1500, categories: list[str] | None = None) -> dict:
        """Full neighborhood analysis combining multiple Maps APIs."""
        geocode = self.client.geocode(address)
        if not geocode:
            raise ValueError(f"Could not geocode: {address}")

        location = geocode[0]["geometry"]["location"]
        lat, lng = location["lat"], location["lng"]

        categories = categories or ["school", "restaurant", "transit_station", "park", "hospital"]

        results = {
            "address": address,
            "coordinates": {"lat": lat, "lng": lng},
            "nearby": {},
            "commute_times": {},
            "walkability_score": 0,
        }

        # Nearby Places by category
        for category in categories:
            places = self.client.places_nearby(
                location=(lat, lng),
                radius=radius,
                type=category
            )
            results["nearby"][category] = [
                {
                    "name": p["name"],
                    "rating": p.get("rating"),
                    "distance_meters": self._haversine(lat, lng, p["geometry"]["location"]["lat"], p["geometry"]["location"]["lng"]),
                    "address": p.get("vicinity"),
                }
                for p in places.get("results", [])[:10]
            ]

        # Commute times to common destinations
        destinations = self._get_commute_destinations(address)
        if destinations:
            matrix = self.client.distance_matrix(
                origins=[address],
                destinations=destinations,
                mode="transit",
                departure_time="now"
            )
            for i, dest in enumerate(destinations):
                element = matrix["rows"][0]["elements"][i]
                if element["status"] == "OK":
                    results["commute_times"][dest] = {
                        "duration": element["duration"]["text"],
                        "distance": element["distance"]["text"],
                    }

        # Simple walkability heuristic
        total_nearby = sum(len(v) for v in results["nearby"].values())
        results["walkability_score"] = min(100, total_nearby * 5)

        return results

    async def get_street_view(self, address: str) -> str:
        """Get Street View image URL for a property."""
        return (
            f"https://maps.googleapis.com/maps/api/streetview"
            f"?size=800x400&location={address}&key={self.client.key}"
        )

    async def get_property_map(self, address: str, nearby_properties: list[dict] | None = None) -> dict:
        """Generate map data with property pin and optional nearby listings."""
        geocode = self.client.geocode(address)
        if not geocode:
            raise ValueError(f"Could not geocode: {address}")
        location = geocode[0]["geometry"]["location"]
        return {
            "center": location,
            "zoom": 15,
            "markers": [
                {"position": location, "label": "Property", "type": "primary"},
                *[
                    {"position": p["location"], "label": p["address"], "type": "comp"}
                    for p in (nearby_properties or [])
                ]
            ],
        }
```

### Step 5: Guardrails

```python
# agent/guardrails.py

class RealEstateGuardrails:
    """Hard-coded business rules — cannot be overridden by the LLM."""

    MAX_DEAL_VALUE_AUTO = 2_000_000       # Escalate to human above $2M
    MIN_OFFER_PERCENT = 0.50              # Offer cannot be below 50% of asking
    MAX_COUNTER_ROUNDS = 10               # Force mediation after 10 rounds
    REQUIRED_DISCLOSURES = [
        "known_defects", "flood_zone", "hoa_fees",
        "lead_paint", "environmental_hazards"
    ]

    @staticmethod
    def validate_offer(offer_price: float, asking_price: float, buyer_budget: float) -> tuple[bool, str]:
        if offer_price > buyer_budget:
            return False, "Offer exceeds buyer's stated budget"
        if offer_price < asking_price * RealEstateGuardrails.MIN_OFFER_PERCENT:
            return False, f"Offer is below {int(RealEstateGuardrails.MIN_OFFER_PERCENT * 100)}% of asking — likely to be rejected outright"
        return True, "OK"

    @staticmethod
    def validate_listing(asking_price: float, property_data: dict) -> tuple[bool, str]:
        if asking_price <= 0:
            return False, "Asking price must be positive"
        # Flag if price per sqft is extreme outlier
        sqft = property_data.get("sqft", 0)
        if sqft > 0:
            price_per_sqft = asking_price / sqft
            if price_per_sqft > 5000:
                return False, f"Price per sqft (${price_per_sqft:.0f}) is unusually high — verify"
        return True, "OK"

    @staticmethod
    def check_escalation(deal_value: float) -> bool:
        """Returns True if deal needs human broker review."""
        return deal_value > RealEstateGuardrails.MAX_DEAL_VALUE_AUTO

    @staticmethod
    def validate_disclosures(disclosures: dict) -> tuple[bool, list[str]]:
        missing = [d for d in RealEstateGuardrails.REQUIRED_DISCLOSURES if d not in disclosures]
        return len(missing) == 0, missing
```

### Step 6: Negotiation Flow

```
Buyer searches properties
    │
    ▼
Buyer Agent: analyze_neighborhood (Google Maps)
    │
    ▼
Buyer Agent: place_offer($X)
    │
    ▼
Broker Agent: receives offer, validates, forwards to Seller Agent
    │
    ▼
Seller Agent: evaluate_offer → counter_offer($Y)
    │
    ▼
Broker Agent: mediates, checks market data
    │
    ▼
  ┌─────────── Negotiation Loop (max 10 rounds) ──────────┐
  │  Buyer counter ←→ Broker mediation ←→ Seller counter   │
  └────────────────────────┬───────────────────────────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
          ACCEPTED      REJECTED    ESCALATED
              │                     (to human)
              ▼
    Broker: generate_contract
              │
              ▼
    Broker: schedule_inspection
              │
              ▼
         DEAL CLOSED
```

---

## Required APIs and Keys

| API | Purpose | Pricing |
|-----|---------|---------|
| **Claude API** (Anthropic) | Agent brains — all three agents use Claude Sonnet 4.5 | Pay per token |
| **Google Maps Platform** | Geocoding, Places, Distance Matrix, Street View, Maps JavaScript | $200/month free credit |
| **Zillow API** (via Bridge/RapidAPI) | Property listings, Zestimate valuations, comps | Varies by plan |
| **ATTOM Data** | Property records, tax history, ownership history | Enterprise pricing |
| **Twilio** (optional) | SMS notifications for deal updates | Pay per message |

### Google Maps APIs Used

| API | Use Case |
|-----|----------|
| **Geocoding API** | Convert addresses to lat/lng |
| **Places API (Nearby Search)** | Find schools, restaurants, transit near a property |
| **Distance Matrix API** | Calculate commute times |
| **Street View Static API** | Property exterior preview |
| **Maps JavaScript API** | Interactive maps in frontend |

---

## Tech Stack

### Backend

| Package | Version | Purpose |
|---------|---------|---------|
| `fastapi` | 0.115+ | API framework |
| `uvicorn` | 0.34+ | ASGI server |
| `anthropic` | 0.52+ | Claude API SDK |
| `googlemaps` | 4.10+ | Google Maps Python client |
| `sqlalchemy[asyncio]` | 2.0+ | ORM (async with asyncpg) |
| `asyncpg` | 0.30+ | PostgreSQL async driver |
| `pydantic` | 2.0+ | Data validation |
| `httpx` | 0.28+ | Async HTTP client (external APIs) |
| `python-dotenv` | 1.0+ | Environment variables |
| `alembic` | 1.14+ | Database migrations |

### Frontend

| Package | Purpose |
|---------|---------|
| `react` | UI framework |
| `vite` | Build tool |
| `tailwindcss` | Styling |
| `@react-google-maps/api` | Google Maps React components |
| `zustand` | State management |
| `socket.io-client` | Real-time updates (offers, negotiations) |

### Infrastructure

| Tool | Purpose |
|------|---------|
| PostgreSQL | Production database (deals, properties, users) |
| Redis | Agent conversation cache, negotiation state |
| Docker | Containerized deployment |
| Nginx | Reverse proxy |

---

## Environment Variables

```env
# Required
ANTHROPIC_API_KEY=           # Claude API
GOOGLE_MAPS_API_KEY=         # Google Maps Platform
DATABASE_URL=                # postgresql+asyncpg://user:pass@host:5432/realestate

# External data (optional but recommended)
ZILLOW_API_KEY=              # Property listings + Zestimates
ATTOM_API_KEY=               # Property records

# Notifications (optional)
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_PHONE_NUMBER=

# App config
ENVIRONMENT=development
LOG_LEVEL=INFO
MAX_DEAL_VALUE_AUTO=2000000  # Override auto-approval threshold
```

---

## Database Schema (PostgreSQL)

```sql
-- Users can be buyers, sellers, or both
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    phone TEXT,
    role TEXT NOT NULL CHECK (role IN ('buyer', 'seller', 'admin')),
    preferences JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Property listings
CREATE TABLE properties (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    seller_id UUID REFERENCES users(id),
    address TEXT NOT NULL,
    city TEXT NOT NULL,
    state TEXT NOT NULL,
    zip TEXT NOT NULL,
    lat DOUBLE PRECISION,
    lng DOUBLE PRECISION,
    asking_price NUMERIC(12, 2) NOT NULL,
    bedrooms INTEGER,
    bathrooms INTEGER,
    sqft INTEGER,
    property_type TEXT,
    description TEXT,
    disclosures JSONB DEFAULT '{}',
    photos TEXT[] DEFAULT '{}',
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'pending', 'sold', 'withdrawn')),
    listed_at TIMESTAMPTZ DEFAULT NOW()
);

-- Offers and counter-offers
CREATE TABLE offers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    property_id UUID REFERENCES properties(id),
    buyer_id UUID REFERENCES users(id),
    offer_price NUMERIC(12, 2) NOT NULL,
    contingencies TEXT[],
    closing_date DATE,
    message TEXT,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'rejected', 'countered', 'withdrawn')),
    parent_offer_id UUID REFERENCES offers(id),  -- for counter-offers
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Negotiation sessions
CREATE TABLE negotiations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    property_id UUID REFERENCES properties(id),
    buyer_id UUID REFERENCES users(id),
    seller_id UUID REFERENCES users(id),
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'agreed', 'failed', 'escalated')),
    round_count INTEGER DEFAULT 0,
    final_price NUMERIC(12, 2),
    started_at TIMESTAMPTZ DEFAULT NOW(),
    closed_at TIMESTAMPTZ
);

-- Agent decision log (mirrors vending machine pattern)
CREATE TABLE agent_decisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_type TEXT NOT NULL,  -- buyer, seller, broker
    negotiation_id UUID REFERENCES negotiations(id),
    trigger TEXT NOT NULL,
    action TEXT NOT NULL,
    reasoning TEXT,
    tool_used TEXT,
    tool_input JSONB,
    tool_output JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Agent memory (persistent scratchpad per agent instance)
CREATE TABLE agent_memory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_type TEXT NOT NULL,
    user_id UUID REFERENCES users(id),
    key TEXT NOT NULL,
    value JSONB NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(agent_type, user_id, key)
);
```

---

## Directory Structure

```
real-estate-agent/
├── main.py                      # FastAPI entry point
├── requirements.txt
├── .env
├── alembic/                     # DB migrations
├── agent/
│   ├── orchestrator.py          # Multi-agent router
│   ├── base_agent.py            # Base agent class (Claude API loop)
│   ├── buyer_agent.py           # Buyer agent logic + prompt
│   ├── seller_agent.py          # Seller agent logic + prompt
│   ├── broker_agent.py          # Broker agent logic + prompt
│   ├── prompts.py               # All system prompts
│   ├── tools.py                 # Tool definitions + implementations
│   ├── guardrails.py            # Hard-coded business rules
│   ├── memory.py                # Per-agent persistent memory
│   └── negotiation.py           # Negotiation state machine
├── api/
│   ├── properties.py            # CRUD for listings
│   ├── offers.py                # Offer submission + tracking
│   ├── search.py                # Property search (with Maps)
│   ├── deals.py                 # Deal lifecycle
│   ├── admin.py                 # Admin dashboard endpoints
│   └── ws.py                    # WebSocket for live negotiation updates
├── services/
│   ├── maps.py                  # Google Maps integration
│   ├── zillow.py                # Zillow API client
│   └── notifications.py        # Twilio SMS / email
├── db/
│   ├── models.py                # SQLAlchemy models
│   ├── database.py              # Engine + session factory
│   └── migrations/
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── BuyerDashboard.tsx
│   │   │   ├── SellerDashboard.tsx
│   │   │   ├── PropertyDetail.tsx
│   │   │   ├── NegotiationView.tsx
│   │   │   └── MapSearch.tsx
│   │   ├── components/
│   │   │   ├── PropertyCard.tsx
│   │   │   ├── OfferForm.tsx
│   │   │   ├── NegotiationChat.tsx
│   │   │   ├── NeighborhoodAnalysis.tsx
│   │   │   └── GoogleMap.tsx
│   │   └── App.tsx
│   └── package.json
├── scripts/
│   ├── seed_properties.py
│   └── simulate_negotiation.py  # Run a full buyer↔seller negotiation
└── tests/
    ├── test_buyer_agent.py
    ├── test_seller_agent.py
    ├── test_broker_agent.py
    ├── test_guardrails.py
    └── test_negotiation_flow.py
```

---

## How to Build This Step by Step

### Phase 1: Foundation
1. Set up FastAPI project with PostgreSQL (async)
2. Create database models and migrations with Alembic
3. Build basic property CRUD endpoints
4. Integrate Google Maps — geocoding + neighborhood analysis

### Phase 2: Single Agent
5. Build the base agent class with Claude API loop (adapt from `agent/loop.py`)
6. Implement Buyer Agent with search + neighborhood tools
7. Add guardrails layer
8. Test: buyer can search, analyze, and place an offer

### Phase 3: Multi-Agent
9. Implement Seller Agent with listing + evaluation tools
10. Implement Broker Agent with mediation tools
11. Build the Orchestrator to route between agents
12. Implement negotiation state machine
13. Test: full offer → counter → accept flow

### Phase 4: Frontend + Real-Time
14. Build React frontend with Google Maps components
15. Add WebSocket for live negotiation updates
16. Buyer dashboard (search, offers, status)
17. Seller dashboard (listings, incoming offers)

### Phase 5: Extend
18. Add Appraiser Agent when you need formal valuations
19. Add Mortgage Agent for financing calculations
20. Add Zillow/ATTOM data integrations for real market data
21. Deploy with Docker + Nginx

---

## Key Differences from Vending Machine

| Aspect | Vending Machine | Real Estate |
|--------|----------------|-------------|
| Agents | 1 (Claudius) | 3+ (Buyer, Seller, Broker + extensible) |
| Database | SQLite | PostgreSQL (complex relations) |
| Negotiation | Fixed prices | Multi-round negotiation with state machine |
| External APIs | None | Google Maps, Zillow, ATTOM |
| Real-time | Stock updates | Live negotiation feed |
| Guardrails | Price margins, quantities | Deal thresholds, disclosures, escalation |
| Hardware | GPIO, Camera, NFC | None (pure software) |
| Users | Single customer at a time | Multiple concurrent buyers + sellers |
