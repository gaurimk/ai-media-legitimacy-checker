"""
Application configuration.

All values can be overridden with environment variables (see .env.example).
Nothing here talks to the network -- it only reads configuration.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# backend/
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
STATIC_DIR = BASE_DIR / "app" / "static"
VERDICT_IMAGE_DIR = STATIC_DIR / "verdicts"
FRONTEND_DIR = BASE_DIR.parent / "frontend"


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


@dataclass
class Settings:
    # Not frozen: tests monkeypatch individual fields (e.g. data_dir,
    # monthly_budget_inr) to isolate themselves from real config/state.
    """Runtime configuration, loaded once at import time."""

    gemini_api_key: str = os.environ.get("GEMINI_API_KEY", "")

    # Model choice.
    # gemini-3.5-flash-lite: cheapest Gemini 3.x model that still supports
    # multimodal input, Google Search grounding, URL context and Structured
    # Outputs -- a good fit for a cost-capped scam checker.
    analysis_model: str = os.environ.get("ANALYSIS_MODEL", "gemini-3.5-flash-lite")

    # gemini-3-pro-image (Nano Banana Pro): the Gemini image model documented
    # by Google as optimised for precise, legible text rendering at up to 4K,
    # which is exactly what the shareable warning graphic needs.
    image_model: str = os.environ.get("IMAGE_MODEL", "gemini-3-pro-image")

    # Soft, in-app monthly spending guard (see docs/ARCHITECTURE.md for why
    # this is a *soft* guard and should be paired with a real billing alert).
    monthly_budget_inr: float = _env_float("MONTHLY_BUDGET_INR", 2500.0)

    # Gemini API billing is in USD. This rate is only used to translate USD
    # token/image costs into INR for the local budget guard -- keep it close
    # to the live rate for an accurate estimate.
    usd_to_inr_rate: float = _env_float("USD_TO_INR_RATE", 90.0)

    # Upload size ceiling, mainly to keep video-analysis cost and latency
    # predictable on a small monthly budget.
    max_upload_mb: float = _env_float("MAX_UPLOAD_MB", 20.0)

    # Comma-separated list of allowed origins for CORS, e.g.
    # "https://your-app.onrender.com,https://yourdomain.com".
    # Defaults to "*" (open) for local development -- set this explicitly
    # once deployed publicly.
    allowed_origins: list[str] = None  # set below, dataclass can't do this inline

    data_dir: Path = DATA_DIR

    def __post_init__(self) -> None:
        raw = os.environ.get("ALLOWED_ORIGINS", "*")
        self.allowed_origins = ["*"] if raw.strip() == "*" else [
            o.strip() for o in raw.split(",") if o.strip()
        ]


settings = Settings()
