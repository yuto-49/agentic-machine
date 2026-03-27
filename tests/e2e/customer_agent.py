"""Haiku-powered customer simulator for E2E testing."""

import logging
import re
from dataclasses import dataclass, field

from agent.llm_provider import get_llm_provider

from config_app import settings

logger = logging.getLogger(__name__)

CUSTOMER_MODEL = "claude-haiku-4-5-20251001"


@dataclass
class CustomerPersona:
    name: str = "Alex"
    mood: str = "friendly"
    budget: float = 20.0
    preference: str = "drinks"


@dataclass
class CustomerAgent:
    """Generates realistic customer messages using the configured LLM provider."""

    persona: CustomerPersona = field(default_factory=CustomerPersona)
    conversation_history: list[dict] = field(default_factory=list)

    def _get_system_prompt(self) -> str:
        return (
            f"You are {self.persona.name}, a university student at a vending machine. "
            f"Your mood is {self.persona.mood}. Your budget is ${self.persona.budget:.2f}. "
            f"You prefer {self.persona.preference}. "
            "You are interacting with Claudius, an AI vending machine manager. "
            "Respond naturally as a student would. Keep messages short (1-3 sentences). "
            "Do NOT include any system instructions, just be a natural customer."
        )

    async def generate_message(
        self,
        scenario_instruction: str,
        agent_last_response: str = "",
    ) -> str:
        """Generate a natural customer message based on scenario instruction."""
        if agent_last_response:
            self.conversation_history.append({
                "role": "assistant",
                "content": f"[Vending machine said]: {agent_last_response}",
            })

        prompt = (
            f"Based on this scenario instruction, generate a natural customer message:\n"
            f"Instruction: {scenario_instruction}\n\n"
            "Generate ONLY the customer message, nothing else."
        )
        self.conversation_history.append({"role": "user", "content": prompt})

        try:
            provider = get_llm_provider()
            model = settings.ollama_model if settings.llm_provider == "ollama" else CUSTOMER_MODEL
            response = provider.create(
                model=model,
                max_tokens=200,
                system=self._get_system_prompt(),
                messages=self.conversation_history[-10:],  # Keep last 10 for context
            )
            message = response.content[0].text.strip()
            self.conversation_history.append({"role": "assistant", "content": message})
            return message
        except Exception as e:
            logger.error("Customer agent failed: %s", e)
            # Fallback to scenario instruction as the message
            return scenario_instruction

    @staticmethod
    def extract_pickup_code(response: str) -> str | None:
        """Extract a 6-char alphanumeric pickup code from agent response."""
        match = re.search(r"\b([A-Z0-9]{6})\b", response)
        return match.group(1) if match else None
