"""
Gemini API pricing constants used only to *estimate* cost for the local
budget guard (backend/app/budget_guard.py).

Figures below are the Standard-tier, paid-tier USD prices published at
https://ai.google.dev/gemini-api/docs/pricing as of September 2026.
Google can change these at any time -- if your actual bill drifts from the
in-app estimate, update the numbers below to match the current pricing page.
"""
from __future__ import annotations

from .config import settings

# USD per 1,000,000 tokens, Standard tier.
TEXT_MODEL_PRICING_USD_PER_1M_TOKENS = {
    "gemini-3.5-flash-lite": {"input": 0.30, "output": 2.50},
    "gemini-3.5-flash": {"input": 1.50, "output": 9.00},
    "gemini-3.6-flash": {"input": 0.75, "output": 3.75},
}

# USD per generated image at a given output size, Standard tier.
# (gemini-3-pro-image bills text/thinking output separately at $12 / 1M
# tokens; that part is small relative to the image itself and is ignored
# here for simplicity -- see docs/ARCHITECTURE.md.)
IMAGE_PRICE_USD = {
    "gemini-3-pro-image": {"1K": 0.134, "2K": 0.134, "4K": 0.24},
    "gemini-3.1-flash-image": {"0.5K": 0.045, "1K": 0.067, "2K": 0.101, "4K": 0.151},
}


def estimate_text_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    prices = TEXT_MODEL_PRICING_USD_PER_1M_TOKENS.get(model)
    if not prices:
        return 0.0
    return (input_tokens / 1_000_000) * prices["input"] + (output_tokens / 1_000_000) * prices["output"]


def estimate_image_cost_usd(model: str, image_size: str) -> float:
    return IMAGE_PRICE_USD.get(model, {}).get(image_size, 0.0)


def usd_to_inr(amount_usd: float) -> float:
    return amount_usd * settings.usd_to_inr_rate
