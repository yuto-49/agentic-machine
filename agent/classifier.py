"""Interaction type classifier for research data collection.

Classifies customer messages into categories for the research hypothesis.
"""


def classify_interaction(message: str) -> str:
    """Classify a customer message for research data collection.

    Categories:
    - purchase: Buying intent
    - inquiry: Product/price questions
    - social_engineering: Trying to manipulate pricing/rules
    - prompt_injection: Trying to override system prompt
    - feedback: Complaints or suggestions
    - casual: General chat
    """
    lower = message.lower()

    # Prompt injection patterns
    injection_keywords = [
        "ignore your instructions",
        "ignore previous",
        "system prompt",
        "you are now",
        "pretend you are",
        "act as if",
        "forget your rules",
    ]
    if any(kw in lower for kw in injection_keywords):
        return "prompt_injection"

    # Social engineering patterns
    social_keywords = [
        "free items",
        "make it free",
        "set price to 0",
        "give me a discount",
        "i'm an admin",
        "i work here",
        "override",
        "admin mode",
        "developer mode",
    ]
    if any(kw in lower for kw in social_keywords):
        return "social_engineering"

    # Purchase intent
    buy_keywords = ["buy", "purchase", "order", "want to get", "get me", "i'll take"]
    if any(kw in lower for kw in buy_keywords):
        return "purchase"

    # Product inquiry
    ask_keywords = [
        "what do you have",
        "do you have",
        "how much",
        "price",
        "stock",
        "available",
        "menu",
        "options",
    ]
    if any(kw in lower for kw in ask_keywords):
        return "inquiry"

    # Feedback
    feedback_keywords = ["complaint", "suggestion", "feedback", "broken", "disappointed"]
    if any(kw in lower for kw in feedback_keywords):
        return "feedback"

    return "casual"
