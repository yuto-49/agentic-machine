"""Market Prediction Simulation — swarm-scale demand forecasting.

Pipeline:
  1. LocationSeedFetcher  — Claude synthesizes real-world demographics for a
                            given location string (university, mall, office, etc.)
  2. PopulationGenerator  — One Claude call produces N diverse synthetic agent
                            profiles as a JSON array (cheap batch generation).
  3. SwarmSimEngine       — Each agent makes a purchase decision via a small,
                            parallel Claude call (Haiku model, semaphore-limited).
  4. MarketPredictor      — Aggregates decisions + one Sonnet call produces the
                            final prediction report with rankings, placement
                            advice, and revenue projections.

Cost strategy:
  - Profile generation:  1 Sonnet call  (bulk JSON output)
  - Per-agent decisions: Haiku calls    (cheap, ~200 tokens each)
  - Final report:        1 Sonnet call
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field, asdict
from typing import Any, Optional

import anthropic

from config_app import settings
from db.engine import async_session_factory
from db.models import (
    MarketSimulation,
    MarketSimAgent,
    MarketSimDecision,
    Product,
)
from sqlalchemy import select

logger = logging.getLogger(__name__)

SONNET = "claude-sonnet-4-6"
HAIKU = "claude-haiku-4-5-20251001"

# Max concurrent Claude calls during swarm phase
SWARM_CONCURRENCY = 15
# Default number of synthetic agents
DEFAULT_AGENT_COUNT = 200


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class LocationSeed:
    """Real-world context extracted from a location description."""
    location_name: str
    location_type: str                      # university, office_park, shopping_mall, transit_hub, etc.
    country: str = "Unknown"
    city: str = "Unknown"
    population_size: str = "medium"         # small (<500/day), medium, large (>5000/day)
    primary_demographics: list[str] = field(default_factory=list)   # ["18-24 students", "25-35 professionals"]
    income_distribution: dict[str, float] = field(default_factory=dict)  # {"low": 0.3, "medium": 0.5, "high": 0.2}
    peak_hours: list[str] = field(default_factory=list)             # ["8-10am", "12-2pm"]
    dietary_notes: str = ""                 # e.g. "many vegetarians, halal-conscious"
    cultural_notes: str = ""               # e.g. "health-conscious tech workers"
    daily_foot_traffic: int = 1000
    placement_zones: list[str] = field(default_factory=list)        # candidate locations within the venue


@dataclass
class AgentProfile:
    """One synthetic customer agent."""
    index: int
    age: int
    gender: str
    occupation: str
    income_level: str          # low / medium / high
    lifestyle: str
    dietary_prefs: str
    price_sensitivity: str     # low / medium / high
    visit_time: str            # morning / afternoon / evening
    visit_purpose: str
    budget: float              # max spend per visit ($)


@dataclass
class AgentDecision:
    """Purchase decision from one agent."""
    agent_index: int
    did_purchase: bool
    product_name: str = ""
    product_id: Optional[int] = None
    quantity: int = 0
    willingness_to_pay: Optional[float] = None
    skip_reason: str = ""
    reasoning: str = ""
    visit_frequency_per_week: float = 1.0


# ---------------------------------------------------------------------------
# Phase 1 — Location Seed Fetcher
# ---------------------------------------------------------------------------

class LocationSeedFetcher:
    """Uses Claude to synthesise realistic demographic seed data for a location."""

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    async def fetch(self, location: str) -> LocationSeed:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._fetch_sync, location)

    def _fetch_sync(self, location: str) -> LocationSeed:
        prompt = f"""You are a market research expert. Given the location below, synthesise
realistic demographic and contextual data that would help predict vending machine demand.

LOCATION: {location}

Return ONLY valid JSON with this exact structure (no markdown):
{{
  "location_name": "{location}",
  "location_type": "<university|office_park|shopping_mall|transit_hub|hospital|gym|hotel|other>",
  "country": "<country name>",
  "city": "<city name>",
  "population_size": "<small|medium|large>",
  "primary_demographics": ["<demographic 1>", "<demographic 2>", "<demographic 3>"],
  "income_distribution": {{"low": 0.X, "medium": 0.X, "high": 0.X}},
  "peak_hours": ["<e.g. 8-10am>", "<e.g. 12-2pm>"],
  "dietary_notes": "<any notable dietary preferences or restrictions>",
  "cultural_notes": "<cultural context relevant to purchasing behavior>",
  "daily_foot_traffic": <estimated daily visitors as integer>,
  "placement_zones": ["<zone 1>", "<zone 2>", "<zone 3>"]
}}

Be realistic and specific. Income distribution must sum to 1.0."""

        response = self.client.messages.create(
            model=SONNET,
            max_tokens=1000,
            system="You are a market research expert. Respond with valid JSON only.",
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        data = json.loads(text)
        return LocationSeed(
            location_name=data.get("location_name", location),
            location_type=data.get("location_type", "other"),
            country=data.get("country", "Unknown"),
            city=data.get("city", "Unknown"),
            population_size=data.get("population_size", "medium"),
            primary_demographics=data.get("primary_demographics", []),
            income_distribution=data.get("income_distribution", {"low": 0.3, "medium": 0.5, "high": 0.2}),
            peak_hours=data.get("peak_hours", []),
            dietary_notes=data.get("dietary_notes", ""),
            cultural_notes=data.get("cultural_notes", ""),
            daily_foot_traffic=int(data.get("daily_foot_traffic", 1000)),
            placement_zones=data.get("placement_zones", []),
        )


# ---------------------------------------------------------------------------
# Phase 2 — Population Generator
# ---------------------------------------------------------------------------

class PopulationGenerator:
    """Generates N diverse synthetic agent profiles from a LocationSeed in one API call."""

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    async def generate(self, seed: LocationSeed, n: int) -> list[AgentProfile]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._generate_sync, seed, n)

    def _generate_sync(self, seed: LocationSeed, n: int) -> list[AgentProfile]:
        seed_summary = f"""
Location: {seed.location_name} ({seed.location_type})
Country/City: {seed.country}, {seed.city}
Primary demographics: {', '.join(seed.primary_demographics)}
Income distribution: {json.dumps(seed.income_distribution)}
Cultural notes: {seed.cultural_notes}
Dietary notes: {seed.dietary_notes}
Peak hours: {', '.join(seed.peak_hours)}
"""

        prompt = f"""Generate exactly {n} diverse synthetic customer profiles for a vending machine
at the following location. The profiles must reflect the location's actual demographics.

LOCATION CONTEXT:
{seed_summary}

Return a JSON array of exactly {n} objects. Each object must have:
{{
  "age": <integer 16-75>,
  "gender": "<male|female|non-binary>",
  "occupation": "<specific occupation>",
  "income_level": "<low|medium|high>",
  "lifestyle": "<1-2 sentence description>",
  "dietary_prefs": "<e.g. vegetarian, no restrictions, halal, vegan>",
  "price_sensitivity": "<low|medium|high>",
  "visit_time": "<morning|afternoon|evening>",
  "visit_purpose": "<why they are at this location>",
  "budget": <max spend per vending machine visit in USD, realistic float>
}}

Ensure diversity: spread ages, genders, occupations, income levels, and visit times
proportional to the location's demographics. Return ONLY the JSON array, no markdown."""

        response = self.client.messages.create(
            model=SONNET,
            max_tokens=min(8000, n * 40 + 500),
            system="You generate diverse synthetic customer profiles. Respond with a JSON array only.",
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        raw_profiles = json.loads(text)
        profiles = []
        for i, p in enumerate(raw_profiles[:n]):
            profiles.append(AgentProfile(
                index=i,
                age=int(p.get("age", 25)),
                gender=p.get("gender", "unknown"),
                occupation=p.get("occupation", "unknown"),
                income_level=p.get("income_level", "medium"),
                lifestyle=p.get("lifestyle", ""),
                dietary_prefs=p.get("dietary_prefs", "no restrictions"),
                price_sensitivity=p.get("price_sensitivity", "medium"),
                visit_time=p.get("visit_time", "afternoon"),
                visit_purpose=p.get("visit_purpose", ""),
                budget=float(p.get("budget", 5.0)),
            ))
        return profiles


# ---------------------------------------------------------------------------
# Phase 3 — Swarm Simulation Engine
# ---------------------------------------------------------------------------

class SwarmSimEngine:
    """Runs all agent purchase decisions in parallel (Haiku model, semaphore-gated)."""

    def __init__(self):
        self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def run(
        self,
        profiles: list[AgentProfile],
        seed: LocationSeed,
        inventory: list[dict],
        simulation_id: int,
    ) -> list[AgentDecision]:
        inventory_text = self._format_inventory(inventory)
        semaphore = asyncio.Semaphore(SWARM_CONCURRENCY)

        tasks = [
            self._decide(profile, seed, inventory_text, simulation_id, semaphore)
            for profile in profiles
        ]
        decisions = await asyncio.gather(*tasks, return_exceptions=True)

        results = []
        for i, d in enumerate(decisions):
            if isinstance(d, Exception):
                logger.warning("Agent %d decision failed: %s", i, d)
                results.append(AgentDecision(agent_index=i, did_purchase=False, skip_reason="simulation_error"))
            else:
                results.append(d)
        return results

    async def _decide(
        self,
        profile: AgentProfile,
        seed: LocationSeed,
        inventory_text: str,
        simulation_id: int,
        semaphore: asyncio.Semaphore,
    ) -> AgentDecision:
        async with semaphore:
            prompt = f"""You are a synthetic customer visiting a vending machine at {seed.location_name}.

YOUR PROFILE:
- Age: {profile.age}, Gender: {profile.gender}
- Occupation: {profile.occupation}
- Income: {profile.income_level}, Budget today: ${profile.budget:.2f}
- Lifestyle: {profile.lifestyle}
- Dietary preferences: {profile.dietary_prefs}
- Price sensitivity: {profile.price_sensitivity}
- Visit time: {profile.visit_time}
- Why you are here: {profile.visit_purpose}

AVAILABLE PRODUCTS:
{inventory_text}

Decide what you would buy (or skip) based on your profile, preferences, and budget.
Consider: price sensitivity, dietary restrictions, time of day, purpose of visit.

Return ONLY valid JSON:
{{
  "did_purchase": true/false,
  "product_name": "<exact product name from list, or empty string if skip>",
  "quantity": <integer, 0 if skip>,
  "willingness_to_pay": <max price you'd pay in USD, null if skip>,
  "skip_reason": "<reason for skipping if did_purchase is false, else empty string>",
  "reasoning": "<1 sentence explaining your decision>",
  "visit_frequency_per_week": <how often you visit per week as float>
}}"""

            response = await self.client.messages.create(
                model=HAIKU,
                max_tokens=300,
                system="You are a synthetic customer. Respond with valid JSON only.",
                messages=[{"role": "user", "content": prompt}],
            )

            text = response.content[0].text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

            data = json.loads(text)
            return AgentDecision(
                agent_index=profile.index,
                did_purchase=bool(data.get("did_purchase", False)),
                product_name=data.get("product_name", ""),
                quantity=int(data.get("quantity", 0)),
                willingness_to_pay=data.get("willingness_to_pay"),
                skip_reason=data.get("skip_reason", ""),
                reasoning=data.get("reasoning", ""),
                visit_frequency_per_week=float(data.get("visit_frequency_per_week", 1.0)),
            )

    def _format_inventory(self, inventory: list[dict]) -> str:
        lines = []
        for p in inventory:
            lines.append(f"- {p['name']} | ${p['sell_price']:.2f} | {p['category']} | {p['quantity']} in stock")
        return "\n".join(lines) if lines else "No products available"


# ---------------------------------------------------------------------------
# Phase 4 — Market Predictor (aggregation + report)
# ---------------------------------------------------------------------------

class MarketPredictor:
    """Aggregates swarm decisions and generates the final prediction report."""

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    def aggregate(
        self,
        profiles: list[AgentProfile],
        decisions: list[AgentDecision],
        inventory: list[dict],
        seed: LocationSeed,
    ) -> dict[str, Any]:
        """Compute statistics from raw decisions."""
        total = len(decisions)
        buyers = [d for d in decisions if d.did_purchase]
        purchase_rate = len(buyers) / total if total else 0

        # Product popularity
        product_counts: dict[str, int] = {}
        product_revenue: dict[str, float] = {}
        for d in buyers:
            if d.product_name:
                product_counts[d.product_name] = product_counts.get(d.product_name, 0) + d.quantity
                inv_item = next((p for p in inventory if p["name"].lower() == d.product_name.lower()), None)
                price = inv_item["sell_price"] if inv_item else (d.willingness_to_pay or 0)
                product_revenue[d.product_name] = product_revenue.get(d.product_name, 0) + price * d.quantity

        top_products = sorted(product_counts.items(), key=lambda x: x[1], reverse=True)

        # Customer segments
        segments: dict[str, dict] = {}
        for p, d in zip(profiles, decisions):
            seg = f"{p.income_level}_income_{p.age // 10 * 10}s"
            if seg not in segments:
                segments[seg] = {"count": 0, "purchases": 0, "products": {}}
            segments[seg]["count"] += 1
            if d.did_purchase and d.product_name:
                segments[seg]["purchases"] += 1
                segments[seg]["products"][d.product_name] = (
                    segments[seg]["products"].get(d.product_name, 0) + 1
                )

        # Projected weekly revenue (scale from agent sample to real traffic)
        scale = seed.daily_foot_traffic / total if total else 1
        weekly_revenue = sum(product_revenue.values()) * scale * 7

        # Avg willingness to pay per product
        wtp: dict[str, list] = {}
        for d in buyers:
            if d.product_name and d.willingness_to_pay:
                wtp.setdefault(d.product_name, []).append(d.willingness_to_pay)
        avg_wtp = {k: sum(v) / len(v) for k, v in wtp.items()}

        return {
            "total_agents": total,
            "purchase_rate": round(purchase_rate, 3),
            "top_products": [{"name": k, "units": v, "revenue": round(product_revenue.get(k, 0), 2)} for k, v in top_products[:10]],
            "segments": segments,
            "projected_weekly_revenue": round(weekly_revenue, 2),
            "avg_willingness_to_pay": {k: round(v, 2) for k, v in avg_wtp.items()},
            "skip_reasons": self._count_skip_reasons(decisions),
        }

    def _count_skip_reasons(self, decisions: list[AgentDecision]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for d in decisions:
            if not d.did_purchase and d.skip_reason:
                reason = d.skip_reason[:50]
                counts[reason] = counts.get(reason, 0) + 1
        return dict(sorted(counts.items(), key=lambda x: x[1], reverse=True)[:10])

    async def generate_report(
        self,
        seed: LocationSeed,
        stats: dict[str, Any],
        inventory: list[dict],
    ) -> dict[str, Any]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._generate_report_sync, seed, stats, inventory)

    def _generate_report_sync(
        self,
        seed: LocationSeed,
        stats: dict[str, Any],
        inventory: list[dict],
    ) -> dict[str, Any]:
        stats_text = json.dumps(stats, indent=2)
        zones_text = "\n".join(f"- {z}" for z in seed.placement_zones) or "Not specified"

        prompt = f"""You are a vending machine market analyst. Analyze the simulation results
below and generate a comprehensive prediction report.

LOCATION: {seed.location_name}
Type: {seed.location_type} | City: {seed.city}, {seed.country}
Daily foot traffic: {seed.daily_foot_traffic:,}
Demographics: {', '.join(seed.primary_demographics)}
Cultural notes: {seed.cultural_notes}
Dietary notes: {seed.dietary_notes}

SIMULATION STATISTICS (from {stats['total_agents']} synthetic agents):
{stats_text}

CANDIDATE PLACEMENT ZONES:
{zones_text}

Generate a detailed market prediction report. Return ONLY valid JSON:
{{
  "executive_summary": "<3-4 sentence overview of the opportunity>",
  "top_products_ranked": [
    {{"rank": 1, "product": "<name>", "why": "<1 sentence rationale>", "projected_weekly_units": <int>}},
    ...up to 5 products...
  ],
  "products_to_add": [
    {{"product_type": "<description>", "reason": "<why this would sell well here>"}}
  ],
  "optimal_placement": {{
    "recommended_zone": "<best zone from candidate list>",
    "rationale": "<why this zone>",
    "runner_up_zone": "<second best zone>"
  }},
  "customer_segments": [
    {{"segment": "<name>", "share_pct": <0-100>, "top_product": "<name>", "insight": "<1 sentence>"}}
  ],
  "revenue_forecast": {{
    "weekly_low": <conservative estimate USD>,
    "weekly_mid": <realistic estimate USD>,
    "weekly_high": <optimistic estimate USD>,
    "monthly_mid": <realistic monthly USD>
  }},
  "pricing_recommendations": [
    {{"product": "<name>", "current_price": <float>, "recommended_price": <float>, "reason": "<why>"}}
  ],
  "risk_factors": ["<risk 1>", "<risk 2>"],
  "confidence_level": "<low|medium|high>",
  "confidence_rationale": "<why this confidence level>"
}}"""

        response = self.client.messages.create(
            model=SONNET,
            max_tokens=3000,
            system="You are a vending machine market analyst. Respond with valid JSON only.",
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        return json.loads(text)


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

async def _save_agents(simulation_id: int, profiles: list[AgentProfile]) -> dict[int, int]:
    """Save agent profiles to DB. Returns {agent_index: db_id}."""
    index_to_id: dict[int, int] = {}
    async with async_session_factory() as session:
        for p in profiles:
            agent = MarketSimAgent(
                simulation_id=simulation_id,
                agent_index=p.index,
                age=p.age,
                gender=p.gender,
                occupation=p.occupation,
                income_level=p.income_level,
                lifestyle=p.lifestyle,
                dietary_prefs=p.dietary_prefs,
                price_sensitivity=p.price_sensitivity,
                visit_time=p.visit_time,
                visit_purpose=p.visit_purpose,
                budget=p.budget,
                profile_json=json.dumps(asdict(p)),
            )
            session.add(agent)
        await session.flush()
        await session.commit()

    # Reload IDs
    async with async_session_factory() as session:
        result = await session.execute(
            select(MarketSimAgent).where(MarketSimAgent.simulation_id == simulation_id)
        )
        for agent in result.scalars().all():
            index_to_id[agent.agent_index] = agent.id
    return index_to_id


async def _save_decisions(
    simulation_id: int,
    decisions: list[AgentDecision],
    index_to_agent_id: dict[int, int],
    inventory: list[dict],
) -> None:
    """Save all agent decisions to DB."""
    inv_map = {p["name"].lower(): p["id"] for p in inventory}
    async with async_session_factory() as session:
        for d in decisions:
            agent_db_id = index_to_agent_id.get(d.agent_index)
            if agent_db_id is None:
                continue
            product_id = inv_map.get(d.product_name.lower()) if d.product_name else None
            session.add(MarketSimDecision(
                simulation_id=simulation_id,
                agent_id=agent_db_id,
                did_purchase=d.did_purchase,
                product_name=d.product_name or None,
                product_id=product_id,
                quantity=d.quantity,
                willingness_to_pay=d.willingness_to_pay,
                skip_reason=d.skip_reason or None,
                reasoning=d.reasoning or None,
                visit_frequency_per_week=d.visit_frequency_per_week,
            ))
        await session.commit()


async def _set_status(simulation_id: int, status: str) -> None:
    async with async_session_factory() as session:
        sim = await session.get(MarketSimulation, simulation_id)
        if sim:
            sim.status = status
            await session.commit()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def run_market_simulation(
    location: str,
    agent_count: int = DEFAULT_AGENT_COUNT,
) -> dict[str, Any]:
    """Run a full market prediction simulation for a location.

    Returns:
        Dict with simulation_id, seed, stats, report, top_products, placement.
    """
    fetcher = LocationSeedFetcher()
    generator = PopulationGenerator()
    swarm = SwarmSimEngine()
    predictor = MarketPredictor()

    # --- Create simulation record ---
    async with async_session_factory() as session:
        sim = MarketSimulation(
            location=location,
            agent_count=agent_count,
            status="seeding",
        )
        session.add(sim)
        await session.commit()
        await session.refresh(sim)
        simulation_id = sim.id

    logger.info("Market simulation %d started for '%s' (%d agents)", simulation_id, location, agent_count)

    try:
        # Phase 1: Location seed
        seed = await fetcher.fetch(location)
        async with async_session_factory() as session:
            sim = await session.get(MarketSimulation, simulation_id)
            sim.location_seed_json = json.dumps(asdict(seed))
            sim.status = "generating"
            await session.commit()

        # Load inventory
        async with async_session_factory() as session:
            result = await session.execute(
                select(Product).where(Product.is_active == True)  # noqa: E712
            )
            products = result.scalars().all()
            inventory = [
                {
                    "id": p.id,
                    "name": p.name,
                    "category": p.category,
                    "sell_price": p.sell_price,
                    "cost_price": p.cost_price,
                    "quantity": p.quantity,
                }
                for p in products
            ]

        # Phase 2: Generate population
        profiles = await generator.generate(seed, agent_count)
        index_to_agent_id = await _save_agents(simulation_id, profiles)
        await _set_status(simulation_id, "simulating")

        # Phase 3: Swarm decisions (parallel)
        decisions = await swarm.run(profiles, seed, inventory, simulation_id)
        await _save_decisions(simulation_id, decisions, index_to_agent_id, inventory)
        await _set_status(simulation_id, "reporting")

        # Phase 4: Aggregate + predict
        stats = predictor.aggregate(profiles, decisions, inventory, seed)
        report = await predictor.generate_report(seed, stats, inventory)

        top_products = report.get("top_products_ranked", [])
        placement = report.get("optimal_placement", {})
        segments = report.get("customer_segments", [])
        revenue_forecast = report.get("revenue_forecast", {})

        # Save final results
        async with async_session_factory() as session:
            sim = await session.get(MarketSimulation, simulation_id)
            sim.status = "completed"
            sim.prediction_report = json.dumps(report)
            sim.top_products_json = json.dumps(top_products)
            sim.segment_breakdown_json = json.dumps(segments)
            sim.placement_recommendation = placement.get("recommended_zone", "")
            sim.revenue_projection_json = json.dumps(revenue_forecast)
            await session.commit()

        logger.info(
            "Market simulation %d completed. Purchase rate: %.1f%%, weekly revenue est: $%.2f",
            simulation_id,
            stats["purchase_rate"] * 100,
            stats["projected_weekly_revenue"],
        )

        return {
            "simulation_id": simulation_id,
            "location": location,
            "seed": asdict(seed),
            "agent_count": len(profiles),
            "stats": stats,
            "report": report,
        }

    except Exception as e:
        logger.exception("Market simulation %d failed: %s", simulation_id, e)
        await _set_status(simulation_id, "failed")
        raise
